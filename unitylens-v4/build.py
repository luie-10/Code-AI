#!/usr/bin/env python3
"""Assemble the single-file UnityLens app from shell.html + app.css + analyzer.js + ui.js."""
import json
import pathlib

root = pathlib.Path(__file__).parent
src = pathlib.Path('/home/user/workspace/unity_in')

files = sorted(src.glob('*.cs'))
samples = {"sources": [{"name": f.name, "code": f.read_text(encoding='utf-8')} for f in files]}

html = (root / 'shell.html').read_text(encoding='utf-8')
html = html.replace('/*__CSS__*/', (root / 'app.css').read_text(encoding='utf-8'))
html = html.replace('/*__SAMPLES__*/', json.dumps(samples, ensure_ascii=False))
html = html.replace('/*__ANALYZER__*/', (root / 'analyzer.js').read_text(encoding='utf-8'))
html = html.replace('/*__EXPLAINER__*/', (root / 'explainer.js').read_text(encoding='utf-8'))
html = html.replace('/*__UI__*/', (root / 'ui.js').read_text(encoding='utf-8'))

out = root / 'UnityLens.html'
out.write_text(html, encoding='utf-8')
print(f'built {out} ({out.stat().st_size/1024:.1f} KB), {len(files)} samples')
