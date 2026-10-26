#!/usr/bin/env python3
import json, itertools
import torch
from common import BPETokenizer, ROOT
from model import GPT
torch.set_num_threads(2)
tok=BPETokenizer.load(ROOT/'ckpt_v3'/'tokenizer.json')
YES=tok.encode('Y')[0]; NO=tok.encode('N')[0]
def load(p):
    ck=torch.load(p,map_location='cpu'); c=ck['config']
    m=GPT(c['vocab_size'],d=c['d'],n_layer=c['n_layer'],n_head=c['n_head'],ctx=c['ctx'],dropout=0.0)
    m.load_state_dict(ck['model']); m.eval(); return m,c['ctx']
MODELS={
 'v35':('ckpt_v3_5_big/last.pt',),
 'v36':('ckpt_v3_6/best.pt',),
 'v37':('ckpt_v3_7/best.pt',),
}
loaded={k:load(ROOT/v[0]) for k,v in MODELS.items()}
def fields(p):
    for line in p.splitlines():
        if line.startswith('FIELDS:'):
            b=line.split(':',1)[1].strip()
            if b=='없음' or not b: return []
            return [x.split(':')[0].strip() for x in b.split(',') if x.strip()]
    return []
raw=json.loads((ROOT/'data'/'real_samples.json').read_text(encoding='utf-8'))
gold={t['name']:t for t in json.loads((ROOT/'data'/'labels_real.json').read_text(encoding='utf-8'))['types'] if t['kind']=='class'}
by={}
for s in raw:
    if s['val']: by.setdefault((s['file'],s['type']),[]).append(s)
allc=[(k,v) for k,v in by.items() if k[1] in gold]
TESTSET=allc[:100]; DEV=allc[100:]
def build(cls):
    ms=[]; flat=[]
    for key,items in cls:
        for s in items[:5]:
            fs=fields(s['prompt']); ms.append({'type':key[1],'fs':fs}); flat.extend((s['prompt'],f) for f in fs)
    return ms,flat
def score(model,ctx,pairs):
    out=[]
    for i in range(0,len(pairs),8):
        ch=pairs[i:i+8]; seqs=[tok.encode(p.replace('<|assistant|>',f'FIELD: {f}\n<|assistant|>'))[-(ctx-16):] for p,f in ch]
        L=max(len(x) for x in seqs); pad=tok.special_ids['<|pad|>']
        inp=torch.full((len(seqs),L),pad,dtype=torch.long)
        for j,x in enumerate(seqs): inp[j,:len(x)]=torch.tensor(x)
        with torch.no_grad(): lg,_=model(inp)
        z=lg[torch.arange(len(seqs)),torch.tensor([len(x)-1 for x in seqs])]
        out.extend((z[:,YES]-z[:,NO]).tolist())
    return out
def metrics(ms,sc,thr):
    p=0; per={}
    for m in ms:
        n=len(m['fs']); per.setdefault(m['type'],set()).update({f for f,s in zip(m['fs'],sc[p:p+n]) if s>thr}); p+=n
    hit=pred=gn=0
    for ty,fs in per.items():
        gm={f['name'] for f in gold[ty]['fields'] if f['usages']}
        hit+=len(fs&gm); pred+=len(fs); gn+=len(gm)
    r=hit/max(1,gn); pr=hit/max(1,pred); return {'recall':r,'precision':pr,'f1':2*r*pr/max(1e-9,r+pr),'hit':hit,'pred':pred,'gold':gn}
res={}
for name in ('test','dev'):
    cls=TESTSET if name=='test' else DEV
    ms,flat=build(cls)
    S={k:score(m,c,flat) for k,(m,c) in loaded.items()}
    res[name]={'ms':ms,'S':S}
json.dump({'n_test':len(TESTSET),'n_dev':len(DEV)},open('data/ens_meta.json','w'))
combos=[]
for r in range(1,4):
    combos+=list(itertools.combinations(['v35','v36','v37'],r))
rows=[]
for combo in combos:
    dev={t:sum(res['dev']['S'][k][i] for k in combo)/len(combo) for t,i in [('s',0)]} if False else None
    # dev scores
    ds=[sum(res['dev']['S'][k][i] for k in combo)/len(combo) for i in range(len(res['dev']['S']['v35']))]
    md=metrics(res['dev']['ms'],ds,0.0)
    best=(md['f1'],0.0)
    for th in [x/4 for x in range(-8,9)]:
        mm=metrics(res['dev']['ms'],ds,th)
        if mm['f1']>best[0]+1e-9: best=(mm['f1'],th)
    ts=[sum(res['test']['S'][k][i] for k in combo)/len(combo) for i in range(len(res['test']['S']['v35']))]
    mt=metrics(res['test']['ms'],ts,best[1]); m0=metrics(res['test']['ms'],ts,0.0)
    rows.append({'combo':'+'.join(combo),'dev_f1':round(md['f1'],3),'thr':best[1],'dev_best':round(best[0],3),
                 'test_f1':round(mt['f1'],3),'test_r':round(mt['recall'],3),'test_p':round(mt['precision'],3),
                 'test_f1_thr0':round(m0['f1'],3),'hit':mt['hit'],'pred':mt['pred'],'gold':mt['gold']})
    print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
best=max(rows,key=lambda x:x['dev_best'])
print('SELECTED_ON_DEV',json.dumps(best,ensure_ascii=False),flush=True)
json.dump(rows,open('data/ensemble_eval.json','w'),ensure_ascii=False,indent=1)
