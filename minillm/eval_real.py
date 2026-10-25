#!/usr/bin/env python3
"""Evaluate any checkpoint on the real-code held-out set (method -> class aggregation)."""
import argparse
import json
from collections import Counter

import torch

from chat import load
from common import ROOT

torch.set_num_threads(2)


def parse(out):
    d = {'base': None, 'method': None, 'role': None, 'vars': [], 'format': True}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith('상속:'):
            d['base'] = line.split(':', 1)[1].strip()
        elif line.startswith('메서드:'):
            d['method'] = line.split(':', 1)[1].strip()
        elif line.startswith('역할:'):
            d['role'] = line.split(':', 1)[1].strip()
        elif line.startswith('변수:'):
            body = line.split(':', 1)[1].strip()
            if body and body != '없음':
                for part in body.split(','):
                    name = part.strip().split(' ')[0]
                    if name:
                        d['vars'].append(name)
    d['format'] = all([d['base'], d['method'], d['role']])
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='ckpt_v3')
    ap.add_argument('--ckpt', default='last.pt')
    ap.add_argument('--out', default='data/eval_v3.json')
    ap.add_argument('--limit', type=int, default=10)
    args = ap.parse_args()

    model, tok, ck = load(str(ROOT / args.model), args.ckpt)
    raw = json.loads((ROOT / 'data' / 'real_samples.json').read_text(encoding='utf-8'))
    val = [s for s in raw if s['val']]
    by_type = {}
    for s in val:
        by_type.setdefault((s['file'], s['type']), []).append(s)

    gold = {}
    for t in json.loads((ROOT / 'data' / 'labels_real.json').read_text(encoding='utf-8'))['types']:
        if t['kind'] == 'class':
            gold[t['name']] = t

    rows = []
    base_ok = role_ok = role_n = fmt_ok = fmt_n = 0
    f_hit = f_pred = f_gold = 0
    for (file, ty), items in list(by_type.items())[:args.limit]:
        g = gold.get(ty)
        if not g:
            continue
        fields, bases, formats, outs = set(), [], [], []
        for s in items[:5]:
            ids = tok.encode(s['prompt'])[:model.ctx - 40]
            x = torch.tensor([ids])
            y = model.generate(x, max_new_tokens=110, temperature=0.3, top_k=30,
                               stop_id=tok.special_ids['<|end|>'], rep_penalty=1.15)
            out = tok.decode(y[0, len(ids):].tolist()).replace('<|end|>', '').strip()
            p = parse(out)
            outs.append(out)
            fields.update(p['vars'])
            bases.append(p['base'])
            formats.append(p['format'])
            role_n += 1
            role_ok += (p['role'] == s['role'])
        base = Counter([b for b in bases if b]).most_common(1)
        base = base[0][0] if base else None
        gbase = (g['base'] or '없음') + (' + ' + ', '.join(g['interfaces']) if g.get('interfaces') else '')
        ok = bool(base) and base.split('+')[0].strip() == gbase.split('+')[0].strip()
        base_ok += ok
        gf = {f['name'] for f in g['fields'] if f['usages']}
        f_gold += len(gf)
        f_hit += len(fields & gf)
        f_pred += len(fields)
        fmt_n += len(formats)
        fmt_ok += sum(formats)
        rows.append({'file': file, 'type': ty, 'base_ok': ok, 'base': base, 'gold_base': gbase,
                     'fields': sorted(fields), 'gold_fields': sorted(gf), 'sample': outs[0] if outs else ''})
        print(f'{ty:22s} base={"O" if ok else "X"} fields={len(fields & gf)}/{len(gf)}')

    metrics = {
        'classes': len(rows), 'method_outputs': role_n,
        'base_acc': round(base_ok / max(1, len(rows)), 3),
        'field_recall': round(f_hit / max(1, f_gold), 3),
        'field_precision': round(f_hit / max(1, f_pred), 3),
        'role_acc': round(role_ok / max(1, role_n), 3),
        'format_rate': round(fmt_ok / max(1, fmt_n), 3),
    }
    print(json.dumps(metrics, indent=1))
    (ROOT / args.out).write_text(json.dumps({'metrics': metrics, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
