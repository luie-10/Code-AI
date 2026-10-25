#!/usr/bin/env python3
"""Eval v3.5 big selector, 100 held-out classes."""
import json
import torch
from chat import load
from common import ROOT

torch.set_num_threads(2)
model, tok, ck = load(str(ROOT/'ckpt_v3_5_big'), 'last.pt')
YES=tok.encode('Y')[0]; NO=tok.encode('N')[0]

def fields(prompt):
    for line in prompt.splitlines():
        if line.startswith('FIELDS:'):
            b=line.split(':',1)[1].strip()
            if b=='없음' or not b: return []
            return [x.split(':')[0].strip() for x in b.split(',') if x.strip()]
    return []

def score(pairs):
    out=[]
    for i in range(0,len(pairs),8):
        ch=pairs[i:i+8]; seqs=[]
        for p,f in ch:
            seqs.append(tok.encode(p.replace('<|assistant|>', f'FIELD: {f}\n<|assistant|>'))[-(model.ctx-16):])
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
    for s in items[:5]:
        fs=fields(s['prompt']); methods.append({'type':key[1],'fs':fs})
        flat.extend((s['prompt'],f) for f in fs)
print('pairs',len(flat), flush=True)
scs=score(flat); p=0
for m in methods:
    m['sc']=scs[p:p+len(m['fs'])]; p+=len(m['fs'])
hit=pred=gn=0; per={}
for m in methods:
    per.setdefault(m['type'],set()).update({f for f,s in zip(m['fs'],m['sc']) if s>0})
for ty,fs in per.items():
    gm={f['name'] for f in gold[ty]['fields'] if f['usages']}
    hit+=len(fs&gm); pred+=len(fs); gn+=len(gm)
rec=hit/max(1,gn); prec=hit/max(1,pred)
print(json.dumps({'recall':round(rec,3),'precision':round(prec,3),'f1':round(2*rec*prec/max(1e-9,rec+prec),3),'hit':hit,'pred':pred,'gold':gn}), flush=True)
