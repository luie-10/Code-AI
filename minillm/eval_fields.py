#!/usr/bin/env python3
"""Evaluate the field-use head with copy-snap against prompt FIELDS."""
import json, difflib
from collections import Counter
import torch
from chat import load
from common import ROOT
from eval_real import parse

torch.set_num_threads(2)

def fields_from_prompt(p):
    for line in p.splitlines():
        if line.startswith('FIELDS:'):
            b = line.split(':',1)[1].strip()
            if b == '없음' or not b: return []
            return [x.split(':')[0].strip() for x in b.split(',') if x.strip()]
    return []

def snap(names, cand):
    out=[]
    for n in names:
        n=n.strip('`.,;()')
        if not n or n=='없음': continue
        if n in cand: out.append(n); continue
        m=difflib.get_close_matches(n,cand,n=1,cutoff=0.8)
        if m: out.append(m[0])
    return out

model, tok, ck = load(str(ROOT/'ckpt_v3_2'), 'last.pt')
raw = json.loads((ROOT/'data'/'real_samples.json').read_text(encoding='utf-8'))
val=[s for s in raw if s['val']]
by={}
for s in val: by.setdefault((s['file'],s['type']),[]).append(s)
gold={t['name']:t for t in json.loads((ROOT/'data'/'labels_real.json').read_text(encoding='utf-8'))['types'] if t['kind']=='class'}

hit=pred=gn=0; rows=[]
for (file,ty), items in list(by.items())[:10]:
    g=gold.get(ty)
    if not g: continue
    fs=set()
    for s in items[:5]:
        cand=fields_from_prompt(s['prompt'])
        p=s['prompt'].replace('<|assistant|>','TASK: USED_FIELDS\n<|assistant|>')
        ids=tok.encode(p)[:model.ctx-32]
        y=model.generate(torch.tensor([ids]), max_new_tokens=40, temperature=0.2, top_k=20,
                         stop_id=tok.special_ids['<|end|>'], rep_penalty=1.1)
        out=tok.decode(y[0,len(ids):].tolist()).replace('<|end|>','').strip()
        fs.update(snap([x for x in out.replace('\n',',').split(',')], cand))
    gf={f['name'] for f in g['fields'] if f['usages']}
    gn+=len(gf); hit+=len(fs&gf); pred+=len(fs)
    rows.append({'type':ty,'pred':sorted(fs),'gold':sorted(gf)})
    print(f'{ty:22s} fields={len(fs&gf)}/{len(gf)} pred={len(fs)}  {sorted(fs)[:3]}', flush=True)

m={'field_recall':round(hit/max(1,gn),3),'field_precision':round(hit/max(1,pred),3),'gold_fields':gn,'pred_fields':pred,'hit':hit}
print(json.dumps(m), flush=True)
(ROOT/'data'/'eval_fields.json').write_text(json.dumps({'metrics':m,'rows':rows},ensure_ascii=False,indent=1),encoding='utf-8')
