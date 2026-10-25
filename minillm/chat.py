#!/usr/bin/env python3
"""Run the trained mini LLM on a C# file (or inline code)."""
import argparse
import time
from pathlib import Path

import torch

from common import ASSISTANT, END, ROOT, BPETokenizer, build_prompt
from model import GPT

torch.set_num_threads(2)


def load(model_dir, ckpt='model.pt'):
    d = Path(model_dir)
    tok = BPETokenizer.load(d / 'tokenizer.json')
    ck = torch.load(d / ckpt, map_location='cpu', weights_only=False)
    cfg = ck['config']
    model = GPT(cfg['vocab_size'], d=cfg['d'], n_layer=cfg['n_layer'], n_head=cfg['n_head'], ctx=cfg['ctx'])
    model.load_state_dict(ck['model'])
    model.eval()
    return model, tok, ck


def analyze(model, tok, code, name='Input.cs', max_new=260, temperature=0.6, top_k=40):
    prompt = build_prompt(name, code)
    ids = tok.encode(prompt)
    ids = ids[-(model.ctx - 32):]
    x = torch.tensor([ids], dtype=torch.long)
    t0 = time.time()
    out = model.generate(x, max_new_tokens=max_new, temperature=temperature, top_k=top_k, stop_id=END, rep_penalty=1.12)
    dt = time.time() - t0
    new = out[0, len(ids):].tolist()
    text = tok.decode(new).replace('<|end|>', '').strip()
    return text, len(new) / max(dt, 1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default=str(ROOT / 'ckpt'))
    ap.add_argument('--file')
    ap.add_argument('--code')
    ap.add_argument('--temp', type=float, default=0.6)
    ap.add_argument('--tokens', type=int, default=260)
    ap.add_argument('--ckpt', default='model.pt')
    args = ap.parse_args()

    model, tok, ck = load(args.model, args.ckpt)
    if args.file:
        p = Path(args.file)
        code = p.read_text(encoding='utf-8', errors='ignore')
        name = p.name
    else:
        code = args.code or 'public class A : MonoBehaviour { }'
        name = 'Input.cs'

    text, tps = analyze(model, tok, code, name, max_new=args.tokens, temperature=args.temp)
    print('=' * 64)
    print(f'{name}  ·  {ck["step"]} step checkpoint · {tps:.1f} tok/s')
    print('=' * 64)
    print(text)


if __name__ == '__main__':
    main()
