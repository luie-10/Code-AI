#!/usr/bin/env python3
"""Train v2: 10.9M params, function-level samples."""
import argparse
import json
import math
import random
import time
from pathlib import Path

import torch

from common import BPETokenizer, ROOT
from model import GPT

torch.set_num_threads(2)


def collate(batch, ctx, pad_id):
    seqs, labs, msks = [], [], []
    for s in batch:
        p, t = s['p_ids'], s['t_ids']
        ids = (p + t)[:ctx]
        lab = ([-100] * len(p) + list(t))[:ctx]
        msk = ([0] * len(p) + [1] * len(t))[:ctx]
        seqs.append(ids); labs.append(lab); msks.append(msk)
    L = max(len(x) for x in seqs)
    inp = torch.full((len(seqs), L), pad_id, dtype=torch.long)
    lab = torch.full((len(seqs), L), -100, dtype=torch.long)
    msk = torch.zeros((len(seqs), L), dtype=torch.float)
    for i, (ids, l, m) in enumerate(zip(seqs, labs, msks)):
        inp[i, :len(ids)] = torch.tensor(ids)
        if len(ids) > 1:
            lab[i, :len(ids) - 1] = torch.tensor(ids[1:])
            msk[i, :len(ids) - 1] = torch.tensor(m[1:], dtype=torch.float)
    return inp, lab, msk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--steps', type=int, default=1100)
    ap.add_argument('--batch', type=int, default=6)
    ap.add_argument('--lr', type=float, default=5e-4)
    ap.add_argument('--ctx', type=int, default=320)
    ap.add_argument('--d', type=int, default=384)
    ap.add_argument('--layers', type=int, default=6)
    ap.add_argument('--heads', type=int, default=6)
    ap.add_argument('--dropout', type=float, default=0.1)
    ap.add_argument('--eval_every', type=int, default=200)
    ap.add_argument('--out', default='ckpt_v3')
    ap.add_argument('--samples', default='data/method_samples.json')
    ap.add_argument('--tokenizer', default='ckpt/tokenizer.json')
    args = ap.parse_args()

    out = ROOT / args.out
    out.mkdir(exist_ok=True)
    tok = BPETokenizer.load(ROOT / args.tokenizer)
    raw = json.loads((ROOT / args.samples).read_text(encoding='utf-8'))

    cache = ROOT / 'data' / (args.out + '_tokens.pt')
    if cache.exists():
        data = torch.load(cache, weights_only=False)
    else:
        t0 = time.time()
        data = []
        for i, s in enumerate(raw):
            d = dict(s)
            d['p_ids'] = tok.encode(s['prompt'])
            d['t_ids'] = tok.encode(s['target'])
            data.append(d)
            if i % 2000 == 0:
                print(f'  encoded {i}/{len(raw)} {time.time()-t0:.0f}s', flush=True)
        torch.save(data, cache)
    tr = [s for s in data if not s['val']]
    va = [s for s in data if s['val']]
    print(f'samples train={len(tr)} val={len(va)} avg_len={sum(len(s["p_ids"])+len(s["t_ids"]) for s in data)/len(data):.0f}')

    model = GPT(tok.vocab_size, d=args.d, n_layer=args.layers, n_head=args.heads, ctx=args.ctx, dropout=args.dropout)
    print(f'params {model.num_params()/1e6:.2f}M')
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, betas=(0.9, 0.95), weight_decay=0.02)
    warmup = 60

    def lr_at(step):
        if step < warmup:
            return args.lr * (step + 1) / warmup
        p = (step - warmup) / max(1, args.steps - warmup)
        return args.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * p)))

    hist, best = [], 1e9
    t0 = time.time()
    model.train()
    for step in range(1, args.steps + 1):
        for g in opt.param_groups:
            g['lr'] = lr_at(step)
        batch = [random.choice(tr) for _ in range(args.batch)]
        inp, lab, msk = collate(batch, args.ctx, tok.special_ids['<|pad|>'])
        _, loss = model(inp, lab, msk)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % 10 == 0 or step == 1:
            hist.append({'step': step, 'train': round(loss.item(), 4)})
            print(f'step {step:4d}/{args.steps} loss {loss.item():.4f} {time.time()-t0:.0f}s', flush=True)
        if step % args.eval_every == 0 or step == args.steps:
            model.eval()
            ls = []
            with torch.no_grad():
                for i in range(0, len(va), args.batch):
                    inp, lab, msk = collate(va[i:i + args.batch], args.ctx, tok.special_ids['<|pad|>'])
                    _, l = model(inp, lab, msk)
                    ls.append(l.item())
            vl = sum(ls) / len(ls)
            hist.append({'step': step, 'val': round(vl, 4)})
            print(f'  >> val {vl:.4f}', flush=True)
            if vl < best:
                best = vl
                torch.save({'model': model.state_dict(), 'config': {
                    'vocab_size': tok.vocab_size, 'd': args.d, 'n_layer': args.layers,
                    'n_head': args.heads, 'ctx': args.ctx}, 'step': step, 'val': vl}, out / 'best.pt')
            model.train()
    torch.save({'model': model.state_dict(), 'config': {
        'vocab_size': tok.vocab_size, 'd': args.d, 'n_layer': args.layers,
        'n_head': args.heads, 'ctx': args.ctx}, 'step': args.steps, 'val': hist[-1].get('val')}, out / 'last.pt')
    mins = (time.time() - t0) / 60
    (out / 'loss.json').write_text(json.dumps(hist, indent=1))
    (out / 'summary.json').write_text(json.dumps({
        'params': model.num_params(), 'train_samples': len(tr), 'val_samples': len(va),
        'steps': args.steps, 'best_val': best, 'minutes': mins, 'dropout': args.dropout,
        'config': {'d': args.d, 'layers': args.layers, 'heads': args.heads, 'ctx': args.ctx, 'vocab': tok.vocab_size}
    }, indent=1))
    print(f'done {mins:.1f} min best {best:.4f}')


if __name__ == '__main__':
    main()
