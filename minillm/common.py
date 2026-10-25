#!/usr/bin/env python3
"""Shared pieces: byte-level BPE tokenizer, prompt/target formatting, dataset."""
import json
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
SPECIALS = ['<|pad|>', '<|user|>', '<|assistant|>', '<|end|>']
PAD, USER, ASSISTANT, END = range(4)


class BPETokenizer:
    def __init__(self, merges=None):
        self.merges = [tuple(m) for m in (merges or [])]
        self.rank = {p: i for i, p in enumerate(self.merges)}
        self.special_ids = {s: 256 + len(self.merges) + i for i, s in enumerate(SPECIALS)}
        self.vocab_size = 256 + len(self.merges) + len(SPECIALS)
        self._cache = {}
        self._build_expand()

    def _build_expand(self):
        self.expand = {}

        def get(i):
            if i < 256:
                return bytes([i])
            if i in self.expand:
                return self.expand[i]
            a, b = self.merges[i - 256]
            v = get(a) + get(b)
            self.expand[i] = v
            return v

        for i in range(256, 256 + len(self.merges)):
            get(i)

    # ---------- training ----------
    @classmethod
    def train(cls, text, vocab_size=700, verbose=True):
        ids = list(text.encode('utf-8'))
        merges = []
        while 256 + len(merges) < vocab_size:
            counts = Counter(zip(ids, ids[1:]))
            if not counts:
                break
            (a, b), c = counts.most_common(1)[0]
            if c < 3:
                break
            merges.append((a, b))
            new_id = 256 + len(merges) - 1
            out = []
            i = 0
            while i < len(ids):
                if i < len(ids) - 1 and ids[i] == a and ids[i + 1] == b:
                    out.append(new_id)
                    i += 2
                else:
                    out.append(ids[i])
                    i += 1
            ids = out
            if verbose and len(merges) % 100 == 0:
                print(f'  bpe merge {len(merges)} vocab={256+len(merges)} tokens={len(ids)}')
        return cls(merges)

    # ---------- coding ----------
    def encode(self, text):
        parts = re.split(r'(<\|(?:pad|user|assistant|end)\|>)', text)
        out = []
        for p in parts:
            if not p:
                continue
            if p in self.special_ids:
                out.append(self.special_ids[p])
            else:
                out.extend(self._encode_plain(p))
        return out

    def _encode_plain(self, text):
        ids = list(text.encode('utf-8'))
        while len(ids) > 1:
            best = None
            for i in range(len(ids) - 1):
                r = self.rank.get((ids[i], ids[i + 1]))
                if r is not None and (best is None or r < best[0]):
                    best = (r, i)
            if best is None:
                break
            r, _ = best
            a, b = self.merges[r]
            new_id = 256 + r
            out = []
            i = 0
            while i < len(ids):
                if i < len(ids) - 1 and ids[i] == a and ids[i + 1] == b:
                    out.append(new_id)
                    i += 2
                else:
                    out.append(ids[i])
                    i += 1
            ids = out
        return ids

    def decode(self, ids):
        buf = b''
        for i in ids:
            if i < 0 or i >= self.vocab_size:
                continue
            if i < 256:
                buf += bytes([i])
            elif i < 256 + len(self.merges):
                buf += self.expand[i]
            else:
                s = SPECIALS[i - 256 - len(self.merges)]
                buf += s.encode('utf-8')
        return buf.decode('utf-8', errors='ignore')

    # ---------- io ----------
    def save(self, path):
        Path(path).write_text(json.dumps({'merges': self.merges}), encoding='utf-8')

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text(encoding='utf-8'))['merges'])


def fmt_target(t):
    lines = []
    base = t['base'] or '없음'
    if t.get('interfaces'):
        base += ' + ' + ', '.join(t['interfaces'])
    lines.append('상속: ' + base)
    roles = [r['name'] for r in sorted(t['roles'], key=lambda x: -x['score'])][:2]
    lines.append('역할: ' + (' / '.join(roles) if roles else '일반 타입'))

    if t['fields']:
        lines.append('필드:')
        for f in t['fields'][:10]:
            us = f['usages']
            reads = [u for u in us if u['rw'] != 'write']
            writes = [u for u in us if u['rw'] != 'read']
            bits = [f['type'] + (' [SerializeField]' if f['serialized'] else '')]
            if reads:
                ms = []
                for u in reads:
                    if u['method'] not in ms:
                        ms.append(u['method'])
                bits.append(f'읽기 {len(reads)}회 (' + ', '.join(ms[:3]) + ')')
            if writes:
                ms = []
                for u in writes:
                    if u['method'] not in ms:
                        ms.append(u['method'])
                bits.append(f'쓰기 {len(writes)}회 (' + ', '.join(ms[:3]) + ')')
            if not us:
                bits.append('사용 없음')
            lines.append('- ' + f['name'] + ': ' + ', '.join(bits))

    if t['methods']:
        names = [m['name'] for m in t['methods']][:10]
        lines.append('메서드: ' + ', '.join(names))

    issues = [i['title'] for i in t['issues']][:2]
    if issues:
        lines.append('주의: ' + ' / '.join(issues))
    return '\n'.join(lines)


def build_prompt(file_name, code, max_chars=2200):
    code = code.strip()
    if len(code) > max_chars:
        code = code[:max_chars].rsplit('\n', 1)[0] + '\n// ... (truncated)'
    return f'<|user|>\nFILE: {file_name}\n```cs\n{code}\n```\n<|assistant|>\n'


def load_dataset(tokenizer, ctx=448, val_stride=17, seed=7):
    labels = json.loads((ROOT / 'data' / 'labels.json').read_text(encoding='utf-8'))
    by_file = {}
    for t in labels['types']:
        by_file.setdefault(t['file'], []).append(t)

    samples = []
    files = sorted(by_file.keys())
    for idx, fname in enumerate(files):
        if fname.startswith(('pool_', 'enemy_')) or 'Homing' in fname:
            is_val = True
        else:
            is_val = (idx % val_stride == 0)
        code = (ROOT / 'data' / 'scripts' / fname).read_text(encoding='utf-8', errors='ignore')
        for t in by_file[fname]:
            prompt = build_prompt(fname, code)
            target = fmt_target(t) + '\n<|end|>'
            p_ids = tokenizer.encode(prompt)
            t_ids = tokenizer.encode(target)
            if len(p_ids) + len(t_ids) > ctx:
                # keep the tail of the code by trimming the prompt body
                overflow = len(p_ids) + len(t_ids) - ctx
                p_ids = p_ids[:-overflow - 1]
            samples.append({'prompt': p_ids, 'target': t_ids, 'file': fname, 'type': t['name'], 'val': is_val})
    random.Random(seed).shuffle(samples)
    return samples
