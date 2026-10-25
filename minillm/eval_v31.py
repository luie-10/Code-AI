#!/usr/bin/env python3
"""Field-recall eval with copy-snap (predicted names mapped to prompt FIELDS)."""
import json, sys, difflib
from collections import Counter
import torch
from chat import load
from common import ROOT
from eval_real import parse

torch.set_num_threads(2)

def fields_from_prompt(p):
    for line in p.splitlines():
        if line.startswith('FIELDS:'):
            b = line.split(':', 1)[1].strip()
            if b == '없음' or not b: return []
            return [x.split(':')[0].strip() for x in b.split(',') if x.strip()]
    return []

def snap(names, cand):
    out = []
    for n in names:
        n = n.strip('`.,;()')
        if n in cand: out.append(n); continue
        m = difflib.get_close_matches(n, cand, n=1, cutoff=0.72)
        if m: out.append(m[0])
    return out

def run(model_dir, ckpt='last.pt'):
    model, tok, ck = load(str(ROOT / model_dir), ckpt)
    raw = json.loads((ROOT/'data'/'real_samples.json').read_text(encoding='utf-8'))
    val = [s for s in raw if s['val']]
    by = {}
    for s in val: by.setdefault((s['file'], s['type']), []).append(s)
    gold = {}
    for t in json.loads((ROOT/'data'/'labels_real.json').read_text(encoding='utf-8'))['types']:
        if t['kind'] == 'class': gold[t['name']] = t
    rows=[]; base_ok=role_ok=role_n=fmt_ok=fmt_n=0; hit=pred=goldn=0
    for (file, ty), items in list(by.items())[:10]:
        g = gold.get(ty)
        if not g: continue
        fs, bases, fmts, outs = set(), [], [], []
        for s in items[:5]:
            cand = fields_from_prompt(s['prompt'])
            ids = tok.encode(s['prompt'])[:model.ctx-40]
            y = model.generate(torch.tensor([ids]), max_new_tokens=110, temperature=0.25, top_k=20,
                               stop_id=tok.special_ids['<|end|>'], rep_penalty=1.15)
            out = tok.decode(y[0, len(ids):].tolist()).replace('<|end|>','').strip()
            p = parse(out); outs.append(out)
            fs.update(snap(p['vars'], cand))
            bases.append(p['base']); fmts.append(p['format'])
            role_n += 1; role_ok += (p['role'] == s['role'])
        base = Counter([b for b in bases if b]).most_common(1); base = base[0][0] if base else None
        gb = (g['base'] or '없음') + (' + ' + ', '.join(g['interfaces']) if g.get('interfaces') else '')
        ok = bool(base) and base.split('+')[0].strip() == gb.split('+')[0].strip()
        base_ok += ok
        gf = {f['name'] for f in g['fields'] if f['usages']}
        goldn += len(gf); hit += len(fs & gf); pred += len(fs)
        fmt_n += len(fmts); fmt_ok += sum(fmts)
        rows.append({'type':ty,'base_ok':ok,'fields':sorted(fs),'gold_fields':sorted(gf),'sample':outs[0] if outs else ''})
        print(f'{ty:22s} base={"O" if ok else "X"} fields={len(fs&gf)}/{len(gf)} pred={len(fs)}', flush=True)
    m = {'classes':len(rows),'method_outputs':role_n,'base_acc':round(base_ok/max(1,len(rows)),3),
         'field_recall':round(hit/max(1,goldn),3),'field_precision':round(hit/max(1,pred),3),
         'role_acc':round(role_ok/max(1,role_n),3),'format_rate':round(fmt_ok/max(1,fmt_n),3)}
    print(model_dir, json.dumps(m), flush=True)
    return {'metrics':m,'rows':rows}

res = {'baseline_snap': run('ckpt_v3'), 'v31': run('ckpt_v3_1')}
(ROOT/'data'/'eval_v31.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
