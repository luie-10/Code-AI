import hashlib
#!/usr/bin/env python3
"""Build function-level (one method) training samples from the analyzed corpus."""
import json
import random
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent
random.seed(11)

labels = json.loads((ROOT / 'data' / 'labels_real.json').read_text(encoding='utf-8'))['types']
line_cache = {}


def lines_of(f):
    if f not in line_cache:
        line_cache[f] = (ROOT / 'data' / 'real_scripts' / f).read_text(encoding='utf-8', errors='ignore').split('\n')
    return line_cache[f]


ROLE_RULES = [
    (('Awake', 'Start', 'OnEnable', 'Reset'), '초기화'),
    (('Update', 'FixedUpdate', 'LateUpdate'), '프레임 갱신'),
    (('OnTriggerEnter', 'OnTriggerExit', 'OnCollisionEnter', 'OnCollisionExit'), '충돌 처리'),
    (('OnPointerEnter', 'OnPointerExit', 'OnPointerClick'), 'UI 반응'),
]
CALL_RE = re.compile(r'\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+|[A-Z][A-Za-z0-9_]*)\s*\(')
CALL_IGNORE = {'if', 'for', 'foreach', 'while', 'switch', 'catch', 'using', 'return', 'new', 'nameof', 'typeof'}


def method_role(name, body):
    for names, role in ROLE_RULES:
        if name.startswith(names):
            return role
    if 'Instantiate' in body:
        return '오브젝트 생성'
    if 'Destroy(' in body:
        return '오브젝트 제거'
    if any(k in body for k in ('Translate', 'MovePosition', 'MoveTowards', 'position =')):
        return '이동'
    return '동작 수행'


def calls_of(body):
    out = []
    for m in CALL_RE.finditer(body):
        c = m.group(1)
        if c in CALL_IGNORE:
            continue
        if c not in out and not c.startswith(('Vector', 'Mathf')):
            out.append(c)
    return out[:3]


def method_warning(name, body):
    if name.startswith(('Update', 'FixedUpdate')) and 'FindGameObjectsWithTag' in body:
        return '매 프레임 탐색'
    if 'GetComponent<' in body and '!= null' not in body and '== null' not in body:
        return 'GetComponent null 미검사'
    return '없음'


samples = []
val_files = set()
for t in labels:
    if t['kind'] != 'class' or not t['methods']:
        continue
    src = lines_of(t['file'])
    base = t['base'] or '없음'
    if t.get('interfaces'):
        base += ' + ' + ', '.join(t['interfaces'])
    field_desc = ', '.join(f"{f['name']}:{f['type']}" for f in t['fields'][:12]) or '없음'
    for m in t['methods']:
        s, e = m['startLine'], m['endLine']
        if e <= s or e - s > 55 or m['name'] in ('Update',) and e - s > 40:
            continue
        body = '\n'.join(src[s - 1:e])
        role = method_role(m['name'], body)
        vars_ = []
        for f in t['fields']:
            us = [u for u in f['usages'] if u['method'] == m['name']]
            if not us:
                continue
            r = len([u for u in us if u['rw'] != 'write'])
            w = len([u for u in us if u['rw'] != 'read'])
            if r and w:
                vars_.append(f'{f["name"]} 읽기 {r}회 쓰기 {w}회')
            elif w:
                vars_.append(f'{f["name"]} 쓰기 {w}회')
            else:
                vars_.append(f'{f["name"]} 읽기 {r}회')
        prompt = (f"<|user|>\nCLASS: {t['name']} : {base}\nFIELDS: {field_desc}\n"
                  f"METHOD: {m['name']}\n```cs\n{body}\n```\n<|assistant|>\n")
        target = (f"상속: {base}\n메서드: {m['name']}\n역할: {role}\n"
                  f"변수: {', '.join(vars_) if vars_ else '없음'}\n"
                  f"호출: {', '.join(calls_of(body)) if calls_of(body) else '없음'}\n"
                  f"주의: {method_warning(m['name'], body)}\n<|end|>")
        is_val = (hashlib.md5(t['file'].encode()).digest()[0] % 100) < 14
        if is_val:
            val_files.add(t['file'])
        samples.append({
            'file': t['file'], 'type': t['name'], 'method': m['name'], 'role': role,
            'fields': [f['name'] for f in t['fields'] if any(u['method'] == m['name'] for u in f['usages'])],
            'prompt': prompt, 'target': target, 'val': is_val
        })

random.shuffle(samples)
train = [s for s in samples if not s['val']][:9000]
val = [s for s in samples if s['val']][:600]
out = train + val
(ROOT / 'data' / 'real_samples.json').write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
print(f'samples total={len(samples)} train={len(train)} val={len(val)} val_files={len(val_files)}')
print('avg prompt chars', sum(len(s["prompt"]) for s in out) / len(out))
print(Counter(s['role'] for s in out).most_common())
