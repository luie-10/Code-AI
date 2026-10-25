import hashlib, re
from pathlib import Path
SRC = Path('/home/user/workspace/real/x')
OUT = Path('data/real_scripts'); OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob('*.cs'): f.unlink()
EX = ('Editor', 'Tests', 'Test', 'Plugins', 'ThirdParty', 'Samples~', 'Documentation', 'PackageCache')
cands = {}
for p in SRC.rglob('*.cs'):
    if any(x in p.parts for x in EX): continue
    try: code = p.read_text(encoding='utf-8')
    except Exception: continue
    if not (300 <= len(code) <= 20000): continue
    m = re.search(r'\bclass\s+([A-Za-z_]\w*)', code)
    if not m: continue
    if 'MonoBehaviour' in code or 'ScriptableObject' in code: score = 2
    elif 'Assets' in p.parts: score = 1
    else: continue
    h = hashlib.sha1(re.sub(r'\s+', ' ', code).encode()).hexdigest()
    if h in cands: continue
    cands[h] = (score, p, code)
items = sorted(cands.values(), key=lambda x: -x[0])[:1800]
used, rows = set(), []
for score, p, code in items:
    stem = p.stem; name = stem; i = 1
    while name.lower() in used:
        name = f'{stem}_{i}'; i += 1
    used.add(name.lower())
    (OUT / f'{name}.cs').write_text(code, encoding='utf-8')
    rows.append((name, str(p)))
print('picked', len(rows), 'monobehaviour', sum(1 for s, _, _ in items if s == 2), 'repos', len(set(r[1].split('/x/')[1].split('/')[0] for r in rows)))
