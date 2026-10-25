"""A small decoder-only transformer (GPT), written from scratch in PyTorch."""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class CausalSelfAttention(nn.Module):
    def __init__(self, d, n_head, dropout):
        super().__init__()
        assert d % n_head == 0
        self.n_head = n_head
        self.qkv = nn.Linear(d, 3 * d, bias=False)
        self.proj = nn.Linear(d, d, bias=False)
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        B, T, C = x.shape
        q, k, v = self.qkv(x).split(C, dim=2)
        q = q.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        k = k.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        v = v.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True, dropout_p=0.0)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.drop(self.proj(y))


class MLP(nn.Module):
    def __init__(self, d, dropout):
        super().__init__()
        self.fc = nn.Linear(d, 4 * d, bias=False)
        self.proj = nn.Linear(4 * d, d, bias=False)
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        return self.drop(self.proj(F.gelu(self.fc(x))))


class Block(nn.Module):
    def __init__(self, d, n_head, dropout):
        super().__init__()
        self.ln1 = nn.LayerNorm(d)
        self.attn = CausalSelfAttention(d, n_head, dropout)
        self.ln2 = nn.LayerNorm(d)
        self.mlp = MLP(d, dropout)

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.mlp(self.ln2(x))
        return x


class GPT(nn.Module):
    def __init__(self, vocab_size, d=160, n_layer=4, n_head=4, ctx=448, dropout=0.0):
        super().__init__()
        self.ctx = ctx
        self.wte = nn.Embedding(vocab_size, d)
        self.wpe = nn.Embedding(ctx, d)
        self.blocks = nn.ModuleList([Block(d, n_head, dropout) for _ in range(n_layer)])
        self.ln_f = nn.LayerNorm(d)
        self.head = nn.Linear(d, vocab_size, bias=False)
        self.head.weight = self.wte.weight
        self.apply(self._init)
        for name, p in self.named_parameters():
            if name.endswith('proj.weight'):
                nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * n_layer))

    def _init(self, m):
        if isinstance(m, nn.Linear):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
        elif isinstance(m, nn.Embedding):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)

    def num_params(self):
        return sum(p.numel() for p in self.parameters())

    def forward(self, idx, targets=None, loss_mask=None):
        B, T = idx.shape
        pos = torch.arange(T, device=idx.device)
        x = self.wte(idx) + self.wpe(pos)[None, :, :]
        for b in self.blocks:
            x = b(x)
        logits = self.head(self.ln_f(x))
        loss = None
        if targets is not None:
            if loss_mask is None:
                loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1), ignore_index=-100)
            else:
                flat = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.view(-1), ignore_index=-100, reduction='none')
                m = loss_mask.view(-1).float()
                loss = (flat * m).sum() / m.sum().clamp(min=1)
        return logits, loss

    @torch.no_grad()
    def generate(self, idx, max_new_tokens=256, temperature=0.7, top_k=40, stop_id=None, rep_penalty=1.0):
        for _ in range(max_new_tokens):
            idx_cond = idx[:, -self.ctx:]
            logits, _ = self(idx_cond)
            logits = logits[:, -1, :] / max(temperature, 1e-6)
            if rep_penalty != 1.0:
                for b in range(idx.shape[0]):
                    for tok in set(idx[b, -64:].tolist()):
                        if logits[b, tok] > 0:
                            logits[b, tok] /= rep_penalty
            if top_k:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = -float('inf')
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, 1)
            idx = torch.cat([idx, nxt], dim=1)
            if stop_id is not None and nxt.item() == stop_id:
                break
        return idx
