#!/usr/bin/env python3
"""v3.8: Y/N field selector trainer (replaces finetune_select / train_big / v3.6~v3.7 one-off scripts).

v3.7까지와 다른 점
- 체크포인트 선택을 dev 클래스 F1(임계값 보정 후)로 함 — 최종 지표와 같은 단위. test는 학습 중 보지 않음.
- best.pt / last.pt 분리, 원자적 저장, 기존 출력 폴더 덮어쓰기 거부 → v3.5처럼 최고 체크포인트가 소실되지 않음.
- last.pt에 옵티마이저·RNG까지 저장 → --resume 으로 시간 상한 뒤 이어서 학습.
- 손실: v3.2~v3.7은 collate가 프롬프트 전체 토큰에 LM 손실을 걸었음(정답 Y/N은 2토큰).
  --loss mix(기본)는 정답 토큰 손실 + --lm-weight × 프롬프트 LM 손실.
- 보정 임계값이 체크포인트에 저장되어 eval_select38.py가 그대로 사용.

예)
  python3 train_select.py --out ckpt_v3_8                       # 25.77M from scratch, real_samples.json
  python3 train_select.py --out ckpt_v3_8 --resume              # 이어서
  python3 train_select.py --out ckpt_v3_8b --extra data/new_samples.json
  python3 train_select.py --out ckpt_v3_8_ft --init ckpt_v3/last.pt   # v3.2식 미세조정
"""
import argparse
import json
import math
import random
import shutil
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from common import ROOT
from model import GPT
from select_common import (QueryEncoder, atomic_save, best_threshold, build_pairs, class_queries, load_splits,
                           load_tokenizer, per_class, prf, score, yes_no_ids)


def parse():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--data', default=str(ROOT / 'data' / 'real_samples.json'))
    ap.add_argument('--labels', default=str(ROOT / 'data' / 'labels_real.json'))
    ap.add_argument('--extra', nargs='*', default=[], help='학습 전용 추가 샘플 (dev/test 클래스 이름은 자동 제외)')
    ap.add_argument('--tokenizer', default=str(ROOT / 'ckpt_v3' / 'tokenizer.json'))
    ap.add_argument('--init', help='미세조정 시작 체크포인트 (없으면 from scratch)')
    ap.add_argument('--d', type=int, default=512)
    ap.add_argument('--layers', type=int, default=8)
    ap.add_argument('--heads', type=int, default=8)
    ap.add_argument('--ctx', type=int, default=448)
    ap.add_argument('--dropout', type=float, default=0.05)
    ap.add_argument('--steps', type=int, default=3000, help='LR 스케줄 기준 총 step')
    ap.add_argument('--batch', type=int, default=8)
    ap.add_argument('--accum', type=int, default=1, help='gradient accumulation (실효 배치 = batch×accum)')
    ap.add_argument('--lr', type=float, default=3e-4)
    ap.add_argument('--warmup', type=int, default=50)
    ap.add_argument('--pos-frac', type=float, default=0.5)
    ap.add_argument('--loss', choices=['mix', 'answer', 'all'], default='mix')
    ap.add_argument('--lm-weight', type=float, default=0.1)
    ap.add_argument('--trunc', choices=['smart', 'tail'], default='smart')
    ap.add_argument('--eval-every', type=int, default=250)
    ap.add_argument('--patience', type=int, default=4, help='dev F1이 이 횟수만큼 연속으로 안 오르면 종료 (0=끄기)')
    ap.add_argument('--time-cap', type=float, default=0, help='초 단위 시간 상한 (0=없음). 도달 시 last.pt 저장 후 종료')
    ap.add_argument('--threads', type=int, default=2)
    ap.add_argument('--seed', type=int, default=38)
    return ap.parse_args()


def collate(batch, pad, ctx):
    """batch: [(prompt_ids, target_ids)] → inputs, next-token labels, answer mask."""
    seqs = [(p + t)[:ctx] for p, t in batch]
    L = max(len(s) for s in seqs)
    inp = torch.full((len(seqs), L), pad, dtype=torch.long)
    lab = torch.full((len(seqs), L), -100, dtype=torch.long)
    ans = torch.zeros((len(seqs), L), dtype=torch.bool)
    for i, ((p, _), s) in enumerate(zip(batch, seqs)):
        inp[i, :len(s)] = torch.tensor(s)
        if len(s) > 1:
            lab[i, :len(s) - 1] = torch.tensor(s[1:])
            ans[i, max(0, len(p) - 1):len(s) - 1] = True  # positions that predict target tokens
    return inp, lab, ans


def loss_fn(logits, lab, ans, mode, lm_weight):
    flat = F.cross_entropy(logits.view(-1, logits.size(-1)), lab.view(-1), ignore_index=-100, reduction='none')
    valid = (lab.view(-1) != -100).float()
    a = ans.view(-1).float() * valid
    la = (flat * a).sum() / a.sum().clamp(min=1)
    if mode == 'answer':
        return la
    lm = (flat * valid).sum() / valid.sum().clamp(min=1)
    if mode == 'all':
        return lm
    p = (1 - a) * valid
    return la + lm_weight * (flat * p).sum() / p.sum().clamp(min=1)


def main():
    args = parse()
    torch.set_num_threads(args.threads)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    if out.exists() and any(out.iterdir()) and not args.resume:
        raise SystemExit(f'{out} 이미 존재합니다. 이어서 하려면 --resume, 새로 하려면 다른 --out을 주세요.')
    out.mkdir(parents=True, exist_ok=True)

    tok = load_tokenizer(args.tokenizer)
    pad = tok.special_ids['<|pad|>']
    YES, NO = yes_no_ids(tok)
    rng = random.Random(args.seed)
    torch.manual_seed(args.seed)

    state = None
    if args.resume:
        lp = out / 'last.pt'
        if not lp.exists():
            raise SystemExit(f'{lp} 없음 — 처음부터 하려면 --resume 없이 실행')
        state = torch.load(lp, map_location='cpu', weights_only=False)
        saved = state['args']
        for k in ('steps', 'time_cap', 'patience', 'threads', 'eval_every'):
            saved[k] = getattr(args, k)  # 이 값들만 재개 시 바꿀 수 있음
        args = argparse.Namespace(**saved)
        args.resume = True

    if args.init and not state:
        ck = torch.load(ROOT / args.init if not Path(args.init).is_absolute() else args.init,
                        map_location='cpu', weights_only=False)
        cfg = dict(ck['config'])
        model = GPT(cfg['vocab_size'], d=cfg['d'], n_layer=cfg['n_layer'], n_head=cfg['n_head'], ctx=cfg['ctx'],
                    dropout=args.dropout)
        model.load_state_dict(ck['model'])
    else:
        cfg = state['config'] if state else {'vocab_size': tok.vocab_size, 'd': args.d, 'n_layer': args.layers,
                                             'n_head': args.heads, 'ctx': args.ctx}
        model = GPT(cfg['vocab_size'], d=cfg['d'], n_layer=cfg['n_layer'], n_head=cfg['n_head'], ctx=cfg['ctx'],
                    dropout=args.dropout)
    ctx = cfg['ctx']
    print('params %.2fM ctx %d' % (model.num_params() / 1e6, ctx), flush=True)

    enc = QueryEncoder(tok, ctx, args.trunc)
    train, dev, test, gold, dropped = load_splits(args.data, args.labels, args.extra)
    print(f'train samples {len(train)} (extra dropped {dropped}) · dev classes {len(dev)} · test classes {len(test)}',
          flush=True)
    t0 = time.time()
    pos, neg = build_pairs(train, enc)
    target_y, target_n = tok.encode('Y<|end|>'), tok.encode('N<|end|>')
    dev_rows, dev_types = class_queries(dev, enc)
    print(f'pos {len(pos)} neg {len(neg)} dev pairs {len(dev_rows)} · encode {time.time() - t0:.0f}s', flush=True)
    if not dev_rows:
        raise SystemExit('dev 클래스가 비어 있습니다 — 체크포인트 선택 불가')

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, betas=(0.9, 0.95), weight_decay=0.02)
    step, best, bad, history = 0, None, 0, []
    if state:
        model.load_state_dict(state['model'])
        opt.load_state_dict(state['opt'])
        step, best, bad, history = state['step'], state['best'], state['bad'], state['history']
        rng.setstate(state['rng'])
        torch.set_rng_state(state['torch_rng'])
        print(f'resumed at step {step}, best dev F1 {best and best["dev_f1"]}', flush=True)
    shutil.copy(args.tokenizer, out / 'tokenizer.json')

    def lr_at(i):
        if i < args.warmup:
            return args.lr * (i + 1) / args.warmup
        p = min(1.0, (i - args.warmup) / max(1, args.steps - args.warmup))
        return args.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * p)))

    def snapshot():
        return {'model': model.state_dict(), 'config': cfg, 'step': step, 'args': vars(args)}

    def save_last():
        s = snapshot()
        s.update(opt=opt.state_dict(), best=best, bad=bad, history=history, rng=rng.getstate(),
                 torch_rng=torch.get_rng_state())
        atomic_save(s, out / 'last.pt')
        (out / 'history.json').write_text(json.dumps({'best': best, 'history': history}, ensure_ascii=False, indent=1),
                                          encoding='utf-8')

    def evaluate():
        nonlocal best, bad
        sc = score(model, dev_rows, pad, YES, NO)
        thr, f1 = best_threshold(dev_rows, sc, gold, dev_types)
        m0 = prf(per_class(dev_rows, sc, 0.0, gold, dev_types))
        mt = prf(per_class(dev_rows, sc, thr, gold, dev_types))
        row = {'step': step, 'dev_f1': round(f1, 4), 'thr': thr, 'dev_f1_thr0': round(m0['f1'], 4),
               'dev_recall': round(mt['recall'], 4), 'dev_precision': round(mt['precision'], 4),
               'elapsed': round(time.time() - t0)}
        history.append(row)
        improved = best is None or f1 > best['dev_f1'] + 1e-9
        if improved:
            best, bad = row, 0
            s = snapshot()
            s.update(thr=thr, dev=row)
            atomic_save(s, out / 'best.pt')
        else:
            bad += 1
        print(json.dumps(row) + ('  ← best' if improved else f'  (no gain {bad}' + (f'/{args.patience}' if args.patience else '') + ')'), flush=True)

    t0 = time.time()
    model.train()
    reason = 'steps'
    n_pos = max(1, round(args.batch * args.pos_frac)) if pos else 0
    while step < args.steps:
        if args.time_cap and time.time() - t0 > args.time_cap:
            reason = 'time cap'
            break
        step += 1
        for g in opt.param_groups:
            g['lr'] = lr_at(step)
        opt.zero_grad(set_to_none=True)
        tot = 0.0
        for _ in range(args.accum):
            b = [(rng.choice(pos), target_y) for _ in range(n_pos)] + \
                [(rng.choice(neg), target_n) for _ in range(args.batch - n_pos)]
            inp, lab, ans = collate(b, pad, ctx)
            logits, _ = model(inp)
            loss = loss_fn(logits, lab, ans, args.loss, args.lm_weight) / args.accum
            loss.backward()
            tot += loss.item()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % 50 == 0 or step == 1:
            print(f'step {step}/{args.steps} loss {tot:.4f} lr {lr_at(step):.2e} {time.time() - t0:.0f}s', flush=True)
        if step % args.eval_every == 0:
            evaluate()
            save_last()
            if args.patience and bad >= args.patience:
                reason = 'early stop'
                break
    if not history or history[-1]['step'] != step:
        evaluate()
    save_last()
    print(f'done ({reason}) step {step} · best step {best["step"]} dev F1 {best["dev_f1"]} thr {best["thr"]}',
          flush=True)
    print(f'다음: python3 eval_select38.py --ckpt {out.name}/best.pt', flush=True)


if __name__ == '__main__':
    main()
