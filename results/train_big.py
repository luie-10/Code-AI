#!/usr/bin/env python3
"""v3.5: larger from-scratch selector (33M) — same Y/N candidate task as v3.2."""
import json, math, random, re, shutil, time
import torch
from common import BPETokenizer, ROOT
from model import GPT

torch.set_num_threads(2)
D, LAYERS, HEADS, CTX = 512, 8, 8, 448
STEPS, BATCH, LR = 800, 8, 3e-4
TIME_CAP = 1500

tok = BPETokenizer.load(ROOT/'ckpt_v3'/'tokenizer.json')
model = GPT(tok.vocab_size, d=D, n_layer=LAYERS, n_head=HEADS, ctx=CTX, dropout=0.05)
print('params %.2fM' % (model.num_params()/1e6), flush=True)
YES=tok.encode('Y')[0]; NO=tok.encode('N')[0]

def fields(prompt):
    for line in prompt.splitlines():
        if line.startswith('FIELDS:'):
            b=line.split(':',1)[1].strip()
            if b=='없음' or not b: return []
            return [x.split(':')[0].strip() for x in b.split(',') if x.strip()]
    return []

def vars_of(target):
    for line in target.splitlines():
        if line.startswith('변수:'):
            b=line.split(':',1)[1].strip()
            if b=='없음' or not b: return set()
            return {p.strip().split(' ')[0] for p in b.split(',') if p.strip()}
    return set()

def make(s,f,label):
    p=s['prompt'].replace('<|assistant|>', f'FIELD: {f}\n<|assistant|>')
    return tok.encode(p)[-(CTX-16):], tok.encode(('Y' if label else 'N')+'<|end|>')

raw=json.loads((ROOT/'data'/'real_samples.json').read_text(encoding='utf-8'))
tr=[s for s in raw if not s['val']]
pos,neg=[],[]
for s in tr:
    vs=vars_of(s['target'])
    for f in fields(s['prompt']):
        (pos if f in vs else neg).append(make(s,f,f in vs))
print('pos',len(pos),'neg',len(neg), flush=True)

def collate(batch):
    seqs,labs=[],[]
    for p,t in batch:
        ids=(p+t)[:CTX]; seqs.append(ids); labs.append(([-100]*len(p)+list(t))[:CTX])
    L=max(len(x) for x in seqs); pad=tok.special_ids['<|pad|>']
    inp=torch.full((len(seqs),L),pad,dtype=torch.long); lb=torch.full((len(seqs),L),-100,dtype=torch.long)
    for i,(ids,l) in enumerate(zip(seqs,labs)):
        inp[i,:len(ids)]=torch.tensor(ids)
        if len(ids)>1: lb[i,:len(ids)-1]=torch.tensor(ids[1:])
    return inp,lb

opt=torch.optim.AdamW(model.parameters(), lr=LR, betas=(0.9,0.95), weight_decay=0.02)
def lr_at(i):
    if i<50: return LR*(i+1)/50
    p=(i-50)/max(1,STEPS-50)
    return LR*(0.1+0.9*0.5*(1+math.cos(math.pi*p)))
t0=time.time(); model.train(); done=0
for step in range(1,STEPS+1):
    if time.time()-t0>TIME_CAP:
        print('time cap reached', flush=True); break
    for g in opt.param_groups: g['lr']=lr_at(step)
    batch=[random.choice(pos) for _ in range(4)]+[random.choice(neg) for _ in range(4)]
    inp,lab=collate(batch)
    _,loss=model(inp,lab)
    opt.zero_grad(set_to_none=True); loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(),1.0); opt.step(); done=step
    if step%20==0 or step==1:
        print(f'step {step} loss {loss.item():.4f} {time.time()-t0:.0f}s', flush=True)

out=ROOT/'ckpt_v3_5_big'; out.mkdir(exist_ok=True)
torch.save({'model':model.state_dict(),'config':{'vocab_size':tok.vocab_size,'d':D,'n_layer':LAYERS,'n_head':HEADS,'ctx':CTX},'step':done},out/'last.pt')
shutil.copy(ROOT/'ckpt_v3'/'tokenizer.json', out/'tokenizer.json')
print('saved',out,'steps',done, flush=True)
