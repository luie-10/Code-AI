#!/usr/bin/env python3
"""v3.8 eval: test 100클래스, 체크포인트에 저장된 dev 임계값 사용, 부트스트랩 95% CI.

  python3 eval_select38.py --ckpt ckpt_v3_8/best.pt
  python3 eval_select38.py --ckpt ckpt_v3_8/best.pt --compare ckpt_v3_7/best.pt   # 쌍대 부트스트랩
  python3 eval_select38.py --ckpt ckpt_v3_7/best.pt --trunc tail                 # v3.7 이전 체크포인트

임계값이 저장되지 않은 옛 체크포인트는 dev에서 다시 고릅니다(test는 선택에 쓰지 않음).
"""
import argparse
import json
from pathlib import Path

import torch

from common import ROOT
from select_common import (QueryEncoder, best_threshold, bootstrap_f1, class_queries, load_selector, load_splits,
                           load_tokenizer, per_class, prf, round_metrics, score, yes_no_ids)


def resolve(p):
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def run(path, args, tok, splits):
    model, ck = load_selector(resolve(path))
    _, dev, test, gold, _ = splits
    trunc = args.trunc or ck.get('args', {}).get('trunc', 'tail')  # pre-v3.8 checkpoints were trained with tail
    enc = QueryEncoder(tok, model.ctx, trunc)
    pad = tok.special_ids['<|pad|>']
    YES, NO = yes_no_ids(tok)
    if args.thr is not None:
        thr, src = args.thr, 'arg'
    elif 'thr' in ck and ck.get('args', {}).get('trunc', 'tail') == trunc:
        thr, src = ck['thr'], 'checkpoint'
    else:
        rows, types = class_queries(dev, enc)
        thr, _ = best_threshold(rows, score(model, rows, pad, YES, NO), gold, types)
        src = 'dev'
    rows, types = class_queries(test, enc)
    sc = score(model, rows, pad, YES, NO)
    counts = per_class(rows, sc, thr, gold, types)
    m = prf(counts)
    lo, hi = bootstrap_f1(counts)
    return {'ckpt': str(path), 'step': ck.get('step'), 'trunc': trunc, 'thr': thr, 'thr_source': src,
            **round_metrics(m), 'f1_ci95': [round(lo, 3), round(hi, 3)],
            'f1_thr0': round(prf(per_class(rows, sc, 0.0, gold, types))['f1'], 3)}, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt', required=True)
    ap.add_argument('--compare')
    ap.add_argument('--data', default=str(ROOT / 'data' / 'real_samples.json'))
    ap.add_argument('--labels', default=str(ROOT / 'data' / 'labels_real.json'))
    ap.add_argument('--tokenizer', default=str(ROOT / 'ckpt_v3' / 'tokenizer.json'))
    ap.add_argument('--trunc', choices=['smart', 'tail'], help='기본: 체크포인트 학습 설정')
    ap.add_argument('--thr', type=float, help='임계값 강제 지정')
    ap.add_argument('--out', default=str(ROOT / 'data' / 'eval_v38.json'))
    ap.add_argument('--threads', type=int, default=2)
    args = ap.parse_args()
    torch.set_num_threads(args.threads)

    tok = load_tokenizer(args.tokenizer)
    splits = load_splits(args.data, args.labels)
    res, counts = run(args.ckpt, args, tok, splits)
    print(json.dumps(res, ensure_ascii=False), flush=True)
    out = {'main': res}
    if args.compare:
        cargs = argparse.Namespace(**{**vars(args), 'trunc': None, 'thr': None})
        other, ocounts = run(args.compare, cargs, tok, splits)
        lo, hi = bootstrap_f1(counts, other=ocounts)
        diff = {'f1_diff': round(res['f1'] - other['f1'], 3), 'diff_ci95': [round(lo, 3), round(hi, 3)],
                'significant': lo > 0 or hi < 0}
        print(json.dumps(other, ensure_ascii=False), flush=True)
        print(json.dumps(diff), flush=True)
        out.update(compare=other, diff=diff)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print('saved', args.out, flush=True)


if __name__ == '__main__':
    main()
