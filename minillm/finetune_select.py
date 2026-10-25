#!/usr/bin/env python3
"""v3.2: parser proposes field candidates, model answers yes/no per candidate."""
import json, math, random, shutil, time
import torch
from common import BPETokenizer, ROOT
from model import GPT

torch.set_num_threads(2)
STEPS, BATCH, LR, CTX = 900, 8, 4e-4, 448

tok = BPETokenizer.load(ROOT/'ckpt_v3'/'tokenizer.json')
ck = torch.load(ROOT/'ckpt_v3'/'last.pt', map_location='cpu', weights_only=False)
cfg = ck['config']
model = GPT(cfg['vocab_size'], d=cfg['d'], n_layer=cfg['n_layer'], n_head=cfg['n_head'], ctx=cfg['ctx'])
model.load_state_dict(ck['model'])

def fields(prompt):
    for line in prompt.splitlines():
        if line.startswith('FIELDS:'):
            b = line.split(':',1)[1].strip()
            if b == '없음' or not b: return []
            return [x.split(':')[0].strip() for x in b.split(',') if x.strip()]
    return []

def vars_of(target):
    for line in target.splitlines():
        if line.startswith('변수:'):
            b = line.split(':',1)[1].strip()
            if b == '없음' or not b: return []
            return [p.strip().split(' ')[0] for p in b.split(',') if p.strip()]
    return []

YES = tok.encode('Y'); NO = tok.encode('N')
print('yes ids', YES, 'no ids', NO, flush=True)

def make(s, fname, label):
    p = s['prompt'].replace('<|assistant|>', f'FIELD: {fname}\n<|assistant|>')
    pi = tok.encode(p)[-(CTX-16):]
    ti = tok.encode(('Y' if label else 'N') + '<|end|>')
    return pi, ti

raw = json.loads((ROOT/'data'/'real_samples.json').read_text(encoding='utf-8'))
tr = [s for s in raw if not s['val']]
pos, neg = [], []
for s in tr:
    fs = fields(s['prompt']); vs = set(vars_of(s['target']))
    for f in fs:
        (pos if f in vs else neg).append(make(s, f, f in vs))
print(f'pos {len(pos)} neg {len(neg)}', flush=True)

def collate(batch):
    seqs, labs = [], []
    for p, t in batch:
        ids = (p+t)[:CTX]
        seqs.append(ids); labs.append(([-100]*len(p)+list(t))[:CTX])
    L = max(len(x) for x in seqs); pad = tok.special_ids['<|pad|>']
    inp = torch.full((len(seqs),L), pad, dtype=torch.long); lb = torch.full((len(seqs),L), -100, dtype=torch.long)
    for i,(ids,l) in enumerate(zip(seqs,labs)):
        inp[i,:len(ids)] = torch.tensor(ids)
        if len(ids)>1: lb[i,:len(ids)-1] = torch.tensor(ids[1:])
    return inp, lb

opt = torch.optim.AdamW(model.parameters(), lr=LR, betas=(0.9,0.95), weight_decay=0.02)
def lr_at(i):
    if i < 50: return LR*(i+1)/50
    p=(i-50)/max(1,STEPS-50)
    return LR*(0.1+0.9*0.5*(1+math.cos(math.pi*p)))
t0=time.time(); model.train()
for step in range(1, STEPS+1):
    for g in opt.param_groups: g['lr']=lr_at(step)
    batch = [random.choice(pos) for _ in range(BATCH//2)] + [random.choice(neg) for _ in range(BATCH//2)]
    inp, lab = collate(batch)
    _, loss = model(inp, lab)
    opt.zero_grad(set_to_none=True); loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    if step % 50 == 0 or step == 1:
        print(f'step {step}/{STEPS} loss {loss.item():.4f} {time.time()-t0:.0f}s', flush=True)

out = ROOT/'ckpt_v3_2_select'; out.mkdir(exist_ok=True)
torch.save({'model': model.state_dict(), 'config': cfg, 'step': STEPS}, out/'last.pt')
shutil.copy(ROOT/'ckpt_v3'/'tokenizer.json', out/'tokenizer.json')
print('saved', out, flush=True)
