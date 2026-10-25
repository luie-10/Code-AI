#!/usr/bin/env python3
"""Class-level evaluation of candidate prefilter variants."""
import json, re
import torch
from chat import load
from common import ROOT

torch.set_num_threads(2)
model, tok, ck = load(str(ROOT/'ckpt_v3_2_select'), 'last.pt')
YES = tok.encode('Y')[0]; NO = tok.encode('N')[0]

def fields(prompt):
    for line in prompt.splitlines():
        if line.startswith('FIELDS:'):
            b=line.split(':',1)[1].strip()
            if b=='없음' or not b: return []
            return [x.split(':')[0].strip() for x in b.split(',') if x.strip()]
    return []

def body(prompt):
    m=re.search(r'```cs\n(.*?)```', prompt, re.S)
    return m.group(1) if m else ''

def score(pairs):
    out=[]
    for i in range(0,len(pairs),8):
        ch=pairs[i:i+8]; seqs=[]
        for p,f in ch:
            pp=p.replace('<|assistant|>', f'FIELD: {f}\n<|assistant|>')
            seqs.append(tok.encode(pp)[-(model.ctx-16):])
        L=max(len(s) for s in seqs); pad=tok.special_ids['<|pad|>']
        inp=torch.full((len(seqs),L),pad,dtype=torch.long)
        for j,s in enumerate(seqs): inp[j,:len(s)]=torch.tensor(s)
        with torch.no_grad(): lg,_=model(inp)
        z=lg[torch.arange(len(seqs)),torch.tensor([len(s)-1 for s in seqs])]
        out.extend((z[:,YES]-z[:,NO]).tolist())
    return out

raw=json.loads((ROOT/'data'/'real_samples.json').read_text(encoding='utf-8'))
va=[s for s in raw if s['val']]
gold={t['name']:t for t in json.loads((ROOT/'data'/'labels_real.json').read_text(encoding='utf-8'))['types'] if t['kind']=='class'}
by={}
for s in va: by.setdefault((s['file'],s['type']),[]).append(s)
classes=[(k,v) for k,v in by.items() if k[1] in gold][:100]

methods=[]; flat=[]
for key,items in classes:
    ty=key[1]; gm={f['name'] for f in gold[ty]['fields'] if f['usages']}
    for s in items[:5]:
        fs=fields(s['prompt']); b=body(s['prompt'])
        methods.append({'type':ty,'fs':fs,'body':b,'gold':gm})
        flat.extend((s['prompt'],f) for f in fs)
print('pairs',len(flat), flush=True)
scs=score(flat)
p=0
for m in methods:
    m['sc']=scs[p:p+len(m['fs'])]; p+=len(m['fs'])

VARIANTS={
 'baseline':      lambda m,f,s: s>0,
 'prefilter_code':lambda m,f,s: (f in m['body']) and s>0,
 'parser_only':   lambda m,f,s: f in m['body'],
 'hybrid':        lambda m,f,s: (f in m['body']) or s>0,
}
res={'methods':len(methods),'pairs':len(flat),'gold':sum(len(m['gold']) for m in methods[:1])}
out={}
for name,rule in VARIANTS.items():
    hit=pred=gn=0; rows=[]; mtp=mfp=mfn=0
    per_class={}
    for m in methods:
        chosen={f for f,s in zip(m['fs'],m['sc']) if rule(m,f,s)}
        per_class.setdefault(m['type'],set()).update(chosen)
        # method-level
        mtp+=len(chosen & m['gold']); mfp+=len(chosen - m['gold']); mfn+=len(m['gold'] - chosen)
    for ty,fs in per_class.items():
        gm={f['name'] for f in gold[ty]['fields'] if f['usages']}
        hit+=len(fs&gm); pred+=len(fs); gn+=len(gm)
        rows.append({'type':ty,'pred':sorted(fs),'gold':sorted(gm)})
    rec=hit/max(1,gn); prec=hit/max(1,pred); f1=2*rec*prec/max(1e-9,rec+prec)
    mp=mtp/max(1,mtp+mfp); mr=mtp/max(1,mtp+mfn)
    out[name]={'recall':round(rec,3),'precision':round(prec,3),'f1':round(f1,3),
               'hit':hit,'pred':pred,'gold':gn,
               'method_precision':round(mp,3),'method_recall':round(mr,3)}
    print(name, out[name], flush=True)
    if name in ('baseline','prefilter_code','hybrid'):
        (ROOT/'data'/f'rows_{name}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=1),encoding='utf-8')
res['variants']=out
(ROOT/'data'/'eval_prefilter.json').write_text(json.dumps(res,ensure_ascii=False,indent=1),encoding='utf-8')
