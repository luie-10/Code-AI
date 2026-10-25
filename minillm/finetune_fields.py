#!/usr/bin/env python3
"""v3.2: dedicated field-use head — copy field names from the prompt FIELDS list."""
import json, math, random, shutil, time
import torch
from common import BPETokenizer, ROOT
from model import GPT

torch.set_num_threads(2)
STEPS, BATCH, LR, CTX = 400, 8, 3e-4, 448

tok = BPETokenizer.load(ROOT/'ckpt_v3'/'tokenizer.json')
ck = torch.load(ROOT/'ckpt_v3'/'last.pt', map_location='cpu', weights_only=False)
cfg = ck['config']
model = GPT(cfg['vocab_size'], d=cfg['d'], n_layer=cfg['n_layer'], n_head=cfg['n_head'], ctx=cfg['ctx'])
model.load_state_dict(ck['model'])

def var_names(target):
    for line in target.splitlines():
        if line.startswith('변수:'):
            b = line.split(':',1)[1].strip()
            if b == '없음' or not b: return []
            return [p.strip().split(' ')[0] for p in b.split(',') if p.strip()]
    return []

raw = json.loads((ROOT/'data'/'real_samples.json').read_text(encoding='utf-8'))
tr = [s for s in raw if not s['val']]
data = []
for s in tr:
    names = var_names(s['target'])
    p = s['prompt'].replace('<|assistant|>', 'TASK: USED_FIELDS\n<|assistant|>')
    t = (', '.join(names) if names else '없음') + '<|end|>'
    data.append((tok.encode(p), tok.encode(t)))
print('field-head samples', len(data), flush=True)

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
    if i < 30: return LR*(i+1)/30
    p = (i-30)/max(1,STEPS-30)
    return LR*(0.1+0.9*0.5*(1+math.cos(math.pi*p)))
t0=time.time(); model.train()
for step in range(1, STEPS+1):
    for g in opt.param_groups: g['lr'] = lr_at(step)
    inp, lab = collate([random.choice(data) for _ in range(BATCH)])
    _, loss = model(inp, lab)
    opt.zero_grad(set_to_none=True); loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
    if step % 50 == 0 or step == 1:
        print(f'step {step}/{STEPS} loss {loss.item():.4f} {time.time()-t0:.0f}s', flush=True)

out = ROOT/'ckpt_v3_2'; out.mkdir(exist_ok=True)
torch.save({'model': model.state_dict(), 'config': cfg, 'step': STEPS}, out/'last.pt')
shutil.copy(ROOT/'ckpt_v3'/'tokenizer.json', out/'tokenizer.json')
print('saved', out, flush=True)

model.eval()
for s in [x for x in tr if var_names(x['target'])][:3]:
    p = s['prompt'].replace('<|assistant|>', 'TASK: USED_FIELDS\n<|assistant|>')
    ids = tok.encode(p)[:cfg['ctx']-32]
    y = model.generate(torch.tensor([ids]), max_new_tokens=40, temperature=0.2, top_k=20,
                       stop_id=tok.special_ids['<|end|>'], rep_penalty=1.1)
    print('GOLD', var_names(s['target']), '| PRED', tok.decode(y[0,len(ids):].tolist()).replace('<|end|>','').strip(), flush=True)
