#!/usr/bin/env python3
"""v3.2 eval: parser candidates + model yes/no selection."""
import json
from collections import Counter
import torch
from chat import load
from common import ROOT
from eval_real import parse

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

def prob(s, f):
    p = s['prompt'].replace('<|assistant|>', f'FIELD: {f}\n<|assistant|>')
    ids = tok.encode(p)[-(model.ctx-16):]
    with torch.no_grad():
        logits,_ = model(torch.tensor([ids]))
    z = logits[0,-1]
    return float(z[YES]-z[NO])

raw = json.loads((ROOT/'data'/'real_samples.json').read_text(encoding='utf-8'))
val=[s for s in raw if s['val']]
by={}
for s in val: by.setdefault((s['file'],s['type']),[]).append(s)
gold={t['name']:t for t in json.loads((ROOT/'data'/'labels_real.json').read_text(encoding='utf-8'))['types'] if t['kind']=='class'}

# method-level accuracy on a 200-sample slice
random_rows = val[:200]
tp=fp=fn=tn=0
for s in random_rows:
    vs={p.strip().split(' ')[0] for p in s['target'].split('변수:')[1].split('\n')[0].split(',') if p.strip() and '없음' not in p}
    for f in fields(s['prompt']):
        sel = prob(s,f) > 0
        g = f in vs
        tp += sel and g; fp += sel and not g; fn += (not sel) and g; tn += (not sel) and not g
acc=(tp+tn)/max(1,tp+tn+fp+fn); prec=tp/max(1,tp+fp); rec=tp/max(1,tp+fn)
print(f'method-level acc={acc:.3f} prec={prec:.3f} rec={rec:.3f} (tp{tp} fp{fp} fn{fn} tn{tn})', flush=True)

hit=pred=gn=0; rows=[]
for (file,ty), items in list(by.items())[:10]:
    g=gold.get(ty)
    if not g: continue
    fs=set()
    for s in items[:5]:
        for f in fields(s['prompt']):
            if prob(s,f) > 0: fs.add(f)
    gf={f['name'] for f in g['fields'] if f['usages']}
    gn+=len(gf); hit+=len(fs&gf); pred+=len(fs)
    rows.append({'type':ty,'pred':sorted(fs),'gold':sorted(gf)})
    print(f'{ty:22s} fields={len(fs&gf)}/{len(gf)} pred={len(fs)}', flush=True)

m={'field_recall':round(hit/max(1,gn),3),'field_precision':round(hit/max(1,pred),3),
   'gold_fields':gn,'pred_fields':pred,'hit':hit,
   'method_acc':round(acc,3),'method_prec':round(prec,3),'method_rec':round(rec,3)}
print(json.dumps(m), flush=True)
(ROOT/'data'/'eval_select.json').write_text(json.dumps({'metrics':m,'rows':rows},ensure_ascii=False,indent=1),encoding='utf-8')
