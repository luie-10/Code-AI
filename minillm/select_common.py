#!/usr/bin/env python3
"""v3.8 shared pieces for the Y/N field selector (v3.2~v3.7 scripts each had their own copy).

- 데이터 분할: train(val=False) / test(val 클래스 앞 100개) / dev(나머지) — v3.3~v3.7과 동일
- 질의 생성: 헤더(CLASS/FIELDS)와 FIELD 질의는 항상 남기고 코드 본문만 자름(smart)
- 점수: logit(Y) - logit(N), 길이순 배치로 패딩 최소화
- 지표: 클래스 단위 합집합 재현율/정밀도/F1, dev 임계값 탐색, 부트스트랩 95% CI
"""
import json
import os
import random
from pathlib import Path

import torch

from common import ROOT, BPETokenizer
from model import GPT

N_TEST = 100
THR_GRID = [x / 4 for x in range(-16, 17)]  # -4.0 ~ 4.0, 0.25 간격 (v3.7 보정과 같은 간격)


# ---------- prompt parsing ----------
def fields(prompt):
    for line in prompt.splitlines():
        if line.startswith('FIELDS:'):
            b = line.split(':', 1)[1].strip()
            if b == '없음' or not b:
                return []
            return [x.split(':')[0].strip() for x in b.split(',') if x.strip()]
    return []


def vars_of(target):
    for line in target.splitlines():
        if line.startswith('변수:'):
            b = line.split(':', 1)[1].strip()
            if b == '없음' or not b:
                return set()
            return {p.strip().split(' ')[0] for p in b.split(',') if p.strip()}
    return set()


# ---------- query encoding ----------
class QueryEncoder:
    """Encodes `prompt + FIELD: f` within ctx.

    tail  : v3.2~v3.7 방식. 앞을 잘라 CLASS/FIELDS 줄이 먼저 사라짐.
    smart : 헤더와 질의는 유지하고 코드 본문 끝을 자름.
    """

    def __init__(self, tok, ctx, mode='smart', reserve=16):
        self.tok, self.budget, self.mode = tok, ctx - reserve, mode
        self._parts = {}
        self._cut = tok.encode('\n// ... (truncated)\n')

    def _split(self, prompt):
        if prompt not in self._parts:
            body_head = prompt.find('```cs\n')
            body_end = prompt.rfind('\n```')
            asst = prompt.rfind('<|assistant|>')
            if body_head < 0 or body_end <= body_head or asst < body_end:
                self._parts[prompt] = None
            else:
                h = body_head + len('```cs\n')
                self._parts[prompt] = (self.tok.encode(prompt[:h]), self.tok.encode(prompt[h:body_end]),
                                       prompt[body_end:asst])
        return self._parts[prompt]

    def __call__(self, prompt, field):
        q = f'FIELD: {field}\n<|assistant|>'
        parts = self._split(prompt) if self.mode == 'smart' else None
        if parts is None:
            return self.tok.encode(prompt.replace('<|assistant|>', q))[-self.budget:]
        head, body, close = parts
        tail = self.tok.encode(close + q + '\n')
        room = self.budget - len(head) - len(tail)
        if len(body) > room:
            body = body[:max(0, room - len(self._cut))] + self._cut
        return (head + body + tail)[-self.budget:]


# ---------- data ----------
def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def load_splits(data_path, labels_path, extra=()):
    """Returns (train_samples, dev_classes, test_classes, gold)."""
    raw = load_json(data_path)
    gold = {t['name']: t for t in load_json(labels_path)['types'] if t['kind'] == 'class'}
    by = {}
    for s in raw:
        if s['val']:
            by.setdefault((s['file'], s['type']), []).append(s)
    allc = [(k, v) for k, v in by.items() if k[1] in gold]
    test, dev = allc[:N_TEST], allc[N_TEST:]
    held = {k[1] for k, _ in allc}
    train = [s for s in raw if not s['val']]
    dropped = 0
    for p in extra:
        for s in load_json(p):
            if s.get('val') or s['type'] in held:
                dropped += 1
                continue
            train.append(s)
    return train, dev, test, gold, dropped


def build_pairs(samples, enc):
    pos, neg = [], []
    for s in samples:
        vs = vars_of(s['target'])
        for f in fields(s['prompt']):
            (pos if f in vs else neg).append(enc(s['prompt'], f))
    return pos, neg


def class_queries(classes, enc, per_class=5):
    """Flatten classes into (type, field, ids) rows — same 5-method cap as eval_big/eval_ens.
    Also returns every class type, so classes with no candidates still count their gold fields."""
    rows, types = [], []
    for (_, ty), items in classes:
        types.append(ty)
        for s in items[:per_class]:
            for f in fields(s['prompt']):
                rows.append((ty, f, enc(s["prompt"], f)))
    return rows, types


# ---------- model ----------
def yes_no_ids(tok):
    return tok.encode('Y')[0], tok.encode('N')[0]


def load_selector(path, device='cpu'):
    ck = torch.load(path, map_location=device, weights_only=False)
    c = ck['config']
    m = GPT(c['vocab_size'], d=c['d'], n_layer=c['n_layer'], n_head=c['n_head'], ctx=c['ctx'], dropout=0.0)
    m.load_state_dict(ck['model'])
    m.to(device).eval()
    return m, ck


@torch.inference_mode()
def score(model, rows, pad, yes, no, batch=16, device='cpu'):
    """logit(Y)-logit(N) for each row's last position. Length-sorted batches cut padding."""
    order = sorted(range(len(rows)), key=lambda i: len(rows[i][2]))
    out = [0.0] * len(rows)
    was_training = model.training
    model.eval()
    for i in range(0, len(order), batch):
        idx = order[i:i + batch]
        seqs = [rows[j][2] for j in idx]
        L = max(len(s) for s in seqs)
        inp = torch.full((len(seqs), L), pad, dtype=torch.long)
        for k, s in enumerate(seqs):
            inp[k, :len(s)] = torch.tensor(s)
        lg, _ = model(inp.to(device))
        z = lg[torch.arange(len(seqs)), torch.tensor([len(s) - 1 for s in seqs])]
        for j, v in zip(idx, (z[:, yes] - z[:, no]).tolist()):
            out[j] = v
    if was_training:
        model.train()
    return out


# ---------- metrics ----------
def per_class(rows, scores, thr, gold, types):
    """[(hit, pred, gold_n)] per class (in `types` order), union of selected fields over its methods."""
    sel = {ty: set() for ty in types}
    for (ty, f, _), s in zip(rows, scores):
        if s > thr:
            sel[ty].add(f)
    out = []
    for ty, fs in sel.items():
        gm = {f['name'] for f in gold[ty]['fields'] if f['usages']}
        out.append((len(fs & gm), len(fs), len(gm)))
    return out


def prf(counts):
    hit = sum(c[0] for c in counts); pred = sum(c[1] for c in counts); gn = sum(c[2] for c in counts)
    r = hit / max(1, gn); p = hit / max(1, pred)
    return {'recall': r, 'precision': p, 'f1': 2 * r * p / max(1e-9, r + p), 'hit': hit, 'pred': pred, 'gold': gn}


def best_threshold(rows, scores, gold, types, grid=THR_GRID):
    """Max F1 on these rows; ties go to the threshold closest to 0."""
    best = None
    for th in grid:
        f1 = prf(per_class(rows, scores, th, gold, types))['f1']
        key = (round(f1, 9), -abs(th))
        if best is None or key > best[0]:
            best = (key, th)
    return best[1], best[0][0]


def bootstrap_f1(counts, reps=2000, seed=0, other=None):
    """95% CI of class-resampled F1. With `other` (same classes, same order), CI of F1 difference."""
    rng = random.Random(seed)
    n = len(counts)
    vals = []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        f = prf([counts[i] for i in idx])['f1']
        if other is not None:
            f -= prf([other[i] for i in idx])['f1']
        vals.append(f)
    vals.sort()
    return vals[int(0.025 * reps)], vals[int(0.975 * reps) - 1]


def round_metrics(m, nd=3):
    return {k: (round(v, nd) if isinstance(v, float) else v) for k, v in m.items()}


# ---------- io ----------
def atomic_save(obj, path):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    torch.save(obj, tmp)
    os.replace(tmp, path)


def load_tokenizer(path=None):
    return BPETokenizer.load(path or ROOT / 'ckpt_v3' / 'tokenizer.json')
