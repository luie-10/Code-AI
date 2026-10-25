#!/usr/bin/env python3
"""v3.1: copy-focused fine-tune — upweight the 변수 line, oversample field-bearing samples."""
import json, math, random, shutil, time
from pathlib import Path
import torch
from common import BPETokenizer, ROOT
from model import GPT

torch.set_num_threads(2)
STEPS = 600; BATCH = 6; LR = 2.5e-4; CTX = 448; W = 3.0

tok = BPETokenizer.load(ROOT / 'ckpt_v3' / 'tokenizer.json')
ck = torch.load(ROOT / 'ckpt_v3' / 'last.pt', map_location='cpu', weights_only=False)
cfg = ck['config']
model = GPT(cfg['vocab_size'], d=cfg['d'], n_layer=cfg['n_layer'], n_head=cfg['n_head'], ctx=cfg['ctx'])
model.load_state_dict(ck['model'])

raw = json.loads((ROOT / 'data' / 'real_samples.json').read_text(encoding='utf-8'))
tr = [s for s in raw if not s['val']]
var_s = [s for s in tr if '변수: 없음' not in s['target']]
tr = tr + var_s + var_s  # 3x weight on field-bearing methods

def enc(prompt, target):
    p = tok.encode(prompt); t = tok.encode(target)
    w = [1.0] * len(t)
    i = target.find('변수:')
    if i >= 0:
        j = target.find('\n', i); j = len(target) if j < 0 else j
        a = len(tok.encode(target[:i])); b = len(tok.encode(target[i:j]))
        for k in range(a, min(len(t), a + b)): w[k] = W
    return p, t, w

data = []
for s in tr:
    p, t, w = enc(s['prompt'], s['target'])
    data.append((p, t, w))
print(f'fine-tune samples {len(data)} (var-bearing {len(var_s)})', flush=True)

def collate(batch):
    seqs, labs, msks = [], [], []
    for p, t, w in batch:
        ids = (p + t)[:CTX]; lab = ([-100]*len(p) + list(t))[:CTX]; msk = ([0.0]*len(p) + w)[:CTX]
        seqs.append(ids); labs.append(lab); msks.append(msk)
    L = max(len(x) for x in seqs)
    pad = tok.special_ids['<|pad|>']
    inp = torch.full((len(seqs), L), pad, dtype=torch.long); lb = torch.full((len(seqs), L), -100, dtype=torch.long)
    mk = torch.zeros((len(seqs), L))
    for i, (ids, l, m) in enumerate(zip(seqs, labs, msks)):
        inp[i, :len(ids)] = torch.tensor(ids)
        if len(ids) > 1:
            lb[i, :len(ids)-1] = torch.tensor(ids[1:]); mk[i, :len(ids)-1] = torch.tensor(m[1:])
    return inp, lb, mk

opt = torch.optim.AdamW(model.parameters(), lr=LR, betas=(0.9, 0.95), weight_decay=0.02)
def lr_at(i):
    if i < 40: return LR * (i + 1) / 40
    p = (i - 40) / max(1, STEPS - 40)
    return LR * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * p)))
t0 = time.time(); model.train()
for step in range(1, STEPS + 1):
    for g in opt.param_groups: g['lr'] = lr_at(step)
    inp, lab, msk = collate([random.choice(data) for _ in range(BATCH)])
    _, loss = model(inp, lab, msk)
    opt.zero_grad(set_to_none=True); loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    if step % 50 == 0 or step == 1:
        print(f'step {step}/{STEPS} loss {loss.item():.4f} {time.time()-t0:.0f}s', flush=True)

out = ROOT / 'ckpt_v3_1'; out.mkdir(exist_ok=True)
torch.save({'model': model.state_dict(), 'config': cfg, 'step': STEPS, 'val': None}, out / 'last.pt')
shutil.copy(ROOT / 'ckpt_v3' / 'tokenizer.json', out / 'tokenizer.json')
print('saved', out, flush=True)

# qualitative check
model.eval()
s = var_s[0]; ids = tok.encode(s['prompt'])[:cfg['ctx']-40]
y = model.generate(torch.tensor([ids]), max_new_tokens=110, temperature=0.25, top_k=20,
                   stop_id=tok.special_ids['<|end|>'], rep_penalty=1.15)
print('--- sample before/after ---')
print('GOLD:', s['target'].strip())
print('PRED:', tok.decode(y[0, len(ids):].tolist()).replace('<|end|>','').strip())
