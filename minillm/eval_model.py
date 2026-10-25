#!/usr/bin/env python3
"""Quantitative evaluation: does the model copy the right inheritance, roles and field names?"""
import json
import re
from pathlib import Path

from chat import analyze, load
from common import ROOT

TYPES = json.loads((ROOT / 'data' / 'labels.json').read_text(encoding='utf-8'))['types']


def parse(out):
    d = {'base': None, 'roles': [], 'fields': [], 'methods': []}
    for line in out.splitlines():
        line = line.strip()
        if line.startswith('상속:'):
            d['base'] = line.split(':', 1)[1].strip()
        elif line.startswith('역할:'):
            d['roles'] = [x.strip() for x in line.split(':', 1)[1].split('/') if x.strip()]
        elif line.startswith('메서드:'):
            d['methods'] = [x.strip() for x in line.split(':', 1)[1].split(',') if x.strip()]
        elif line.startswith('- ') and ':' in line:
            d['fields'].append(line[2:].split(':', 1)[0].strip())
    return d


def main():
    import sys
    ckpt = sys.argv[1] if len(sys.argv) > 1 else 'model.pt'
    model, tok, ck = load(str(ROOT / 'ckpt'), ckpt)
    val = [t for t in TYPES if t['file'].startswith(('pool_', 'enemy_')) or 'Homing' in t['file']]
    val = val[:24]
    rows = []
    base_ok = 0
    field_hit = field_tot = field_pred = 0
    role_hit = role_tot = 0
    fmt_ok = 0
    for t in val:
        code = (ROOT / 'data' / 'scripts' / t['file']).read_text(encoding='utf-8', errors='ignore')
        out, tps = analyze(model, tok, code, t['file'], max_new=220, temperature=0.4)
        p = parse(out)
        gold_base = t['base'] or '없음'
        if t.get('interfaces'):
            gold_base += ' + ' + ', '.join(t['interfaces'])
        ok = bool(p['base']) and p['base'].split('+')[0].strip() == gold_base.split('+')[0].strip()
        base_ok += ok
        gold_fields = [f['name'] for f in t['fields']]
        hit = len(set(p['fields']) & set(gold_fields))
        field_hit += hit
        field_tot += len(gold_fields)
        field_pred += len(p['fields'])
        gold_roles = [r['name'] for r in t['roles'][:2]]
        role_hit += len(set(p['roles']) & set(gold_roles))
        role_tot += len(gold_roles)
        fmt_ok += bool(p['base'] and p['roles'] and (p['fields'] or not t['fields']))
        rows.append({'file': t['file'], 'type': t['name'], 'base_ok': ok, 'pred': out[:600], 'gold_fields': gold_fields, 'pred_fields': p['fields'], 'tok_s': round(tps, 1)})
        print(f'{t["file"]:24s} base={"O" if ok else "X"} fields={len(set(p["fields"]) & set(gold_fields))}/{len(gold_fields)}')
    n = len(val)
    metrics = {
        'val_samples': n,
        'base_acc': round(base_ok / n, 3),
        'field_recall': round(field_hit / max(1, field_tot), 3),
        'field_precision': round(field_hit / max(1, field_pred), 3),
        'role_recall': round(role_hit / max(1, role_tot), 3),
        'format_rate': round(fmt_ok / n, 3),
    }
    print(json.dumps(metrics, indent=1))
    (ROOT / 'data' / 'eval.json').write_text(json.dumps({'metrics': metrics, 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
