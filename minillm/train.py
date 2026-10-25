#!/usr/bin/env python3
"""Train the mini LLM on (C# code -> analysis) pairs."""
import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from common import ASSISTANT, END, PAD, USER, BPETokenizer, load_dataset, ROOT
from model import GPT

torch.set_num_threads(2)


def collate(batch, ctx, pad_id):
    seqs, masks = [], []
    for s in batch:
        p, t = s['prompt'], s['target']
        ids = (p + t)[:ctx]
        lab = ([-100] * len(p) + t)[:ctx]
        m = ([0] * len(p) + [1] * len(t))[:ctx]
        seqs.append(ids)
        masks.append(m)
    L = max(len(x) for x in seqs)
    inp = torch.full((len(seqs), L), pad_id, dtype=torch.long)
    lab = torch.full((len(seqs), L), -100, dtype=torch.long)
    msk = torch.zeros((len(seqs), L), dtype=torch.float)
    for i, (ids, mask) in enumerate(zip(seqs, masks)):
        inp[i, :len(ids)] = torch.tensor(ids)
        # label i = token i+1
        if len(ids) > 1:
            lab[i, :len(ids) - 1] = torch.tensor(ids[1:])
            msk[i, :len(ids) - 1] = torch.tensor(mask[1:], dtype=torch.float)
    return inp, lab, msk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--steps', type=int, default=900)
    ap.add_argument('--batch', type=int, default=4)
    ap.add_argument('--lr', type=float, default=8e-4)
    ap.add_argument('--ctx', type=int, default=448)
    ap.add_argument('--d', type=int, default=160)
    ap.add_argument('--layers', type=int, default=4)
    ap.add_argument('--heads', type=int, default=4)
    ap.add_argument('--vocab', type=int, default=700)
    ap.add_argument('--eval_every', type=int, default=100)
    ap.add_argument('--dropout', type=float, default=0.1)
    ap.add_argument('--out', default='ckpt')
    args = ap.parse_args()

    out = ROOT / args.out
    out.mkdir(exist_ok=True)

    tok_path = out / 'tokenizer.json'
    if tok_path.exists():
        tok = BPETokenizer.load(tok_path)
        print('tokenizer loaded', tok.vocab_size)
    else:
        print('training BPE tokenizer...')
        text = '\n'.join(p.read_text(encoding='utf-8', errors='ignore') for p in sorted((ROOT / 'data' / 'scripts').glob('*.cs')))
        labels_text = (ROOT / 'data' / 'labels.json').read_text(encoding='utf-8')
        corpus = (text * 1)[:600_000] + '\n' + labels_text[:150_000]
        t0 = time.time()
        tok = BPETokenizer.train(corpus, vocab_size=args.vocab)
        print(f'tokenizer trained in {time.time()-t0:.1f}s vocab={tok.vocab_size}')
        tok.save(tok_path)

    samples = load_dataset(tok, ctx=args.ctx)
    tr = [s for s in samples if not s['val']]
    va = [s for s in samples if s['val']]
    print(f'samples: train={len(tr)} val={len(va)} avg_tokens={sum(len(s["prompt"])+len(s["target"]) for s in samples)/len(samples):.0f}')

    model = GPT(tok.vocab_size, d=args.d, n_layer=args.layers, n_head=args.heads, ctx=args.ctx, dropout=args.dropout)
    print(f'model params: {model.num_params()/1e6:.2f}M')
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, betas=(0.9, 0.95), weight_decay=0.01)
    warmup = 50

    def lr_at(step):
        if step < warmup:
            return args.lr * (step + 1) / warmup
        p = (step - warmup) / max(1, args.steps - warmup)
        return args.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * p)))

    hist = []
    best = 1e9
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
            hist.append({'step': step, 'train': round(loss.item(), 4), 'lr': lr_at(step)})
            print(f'step {step:4d}/{args.steps} loss {loss.item():.4f} lr {lr_at(step):.2e} {time.time()-t0:.0f}s', flush=True)

        if step % args.eval_every == 0 or step == args.steps:
            model.eval()
            losses = []
            with torch.no_grad():
                for i in range(0, len(va), args.batch):
                    b = va[i:i + args.batch]
                    inp, lab, msk = collate(b, args.ctx, tok.special_ids['<|pad|>'])
                    _, l = model(inp, lab, msk)
                    losses.append(l.item())
            vl = sum(losses) / len(losses)
            hist.append({'step': step, 'val': round(vl, 4)})
            print(f'  >> val loss {vl:.4f}', flush=True)
            if vl < best:
                best = vl
                torch.save({'model': model.state_dict(), 'config': {
                    'vocab_size': tok.vocab_size, 'd': args.d, 'n_layer': args.layers,
                    'n_head': args.heads, 'ctx': args.ctx}, 'step': step, 'val': vl}, out / 'model.pt')
            model.train()

    torch.save({'model': model.state_dict(), 'config': {
        'vocab_size': tok.vocab_size, 'd': args.d, 'n_layer': args.layers,
        'n_head': args.heads, 'ctx': args.ctx}, 'step': args.steps, 'val': hist[-1].get('val')}, out / 'last.pt')
    (out / 'loss.json').write_text(json.dumps(hist, indent=1))
    print(f'done in {(time.time()-t0)/60:.1f} min, best val {best:.4f}')
    (out / 'summary.json').write_text(json.dumps({
        'params': model.num_params(), 'train_samples': len(tr), 'val_samples': len(va),
        'steps': args.steps, 'best_val': best, 'minutes': (time.time() - t0) / 60,
        'config': {'d': args.d, 'layers': args.layers, 'heads': args.heads, 'ctx': args.ctx, 'vocab': tok.vocab_size}
    }, indent=1))


if __name__ == '__main__':
    main()
