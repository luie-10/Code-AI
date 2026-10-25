#!/usr/bin/env python3
"""Build the training report, loss curve, README and distributable zip."""
import base64
import io
import json
import subprocess
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).parent
CKPT = ROOT / 'ckpt'

# 1) run evaluation + samples -------------------------------------------------
subprocess.run(['python3', 'eval_model.py'], cwd=ROOT, check=True, capture_output=True, text=True)
ev = json.loads((ROOT / 'data' / 'eval.json').read_text(encoding='utf-8'))
metrics = ev['metrics']

import sys
sys.path.insert(0, str(ROOT))
from chat import analyze, load  # noqa: E402

model, tok, ck = load(str(CKPT), 'model.pt')
PICKS = ['BulletMove.cs', 'HomingBullet.cs', 'PlayerShooting.cs', 'pool_03.cs']
samples = []
for f in PICKS:
    code = (ROOT / 'data' / 'scripts' / f).read_text(encoding='utf-8', errors='ignore')
    text, tps = analyze(model, tok, code, f, max_new=220, temperature=0.4)
    samples.append({'file': f, 'out': text, 'tps': round(tps, 1)})
(ROOT / 'data' / 'samples.json').write_text(json.dumps(samples, ensure_ascii=False, indent=1), encoding='utf-8')

# 2) loss curve ---------------------------------------------------------------
hist = json.loads((CKPT / 'loss.json').read_text())
tr = [(h['step'], h['train']) for h in hist if 'train' in h]
va = [(h['step'], h['val']) for h in hist if 'val' in h]
summary = json.loads((CKPT / 'summary.json').read_text())

fig, ax = plt.subplots(figsize=(9, 3.6), dpi=170)
fig.patch.set_facecolor('#0d1512')
ax.set_facecolor('#0d1512')
ax.plot([x for x, _ in tr], [y for _, y in tr], color='#5ec8ac', lw=1.6, label='train')
ax.plot([x for x, _ in va], [y for _, y in va], color='#d9a84e', lw=1.8, marker='o', ms=3, label='validation (held-out)')
best = min(va, key=lambda p: p[1])
ax.scatter([best[0]], [best[1]], s=42, facecolor='none', edgecolor='#ef7452', lw=1.4, zorder=5)
ax.annotate(f'best val {best[1]:.3f}', (best[0], best[1]), xytext=(8, 12), textcoords='offset points',
            color='#ef7452', fontsize=8, fontfamily='monospace')
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
for s in ('left', 'bottom'):
    ax.spines[s].set_color('#2c4437')
ax.tick_params(colors='#63796c', labelsize=8)
ax.set_xlabel('step', color='#63796c', fontsize=8)
ax.set_ylabel('cross-entropy', color='#63796c', fontsize=8)
ax.grid(color='#1c2b23', lw=.6)
ax.xaxis.set_major_locator(MaxNLocator(6))
leg = ax.legend(frameon=False, fontsize=8, loc='upper left')
for t in leg.get_texts():
    t.set_color('#93a89a')
fig.tight_layout()
buf = io.BytesIO()
fig.savefig(buf, format='png', facecolor=fig.get_facecolor(), bbox_inches='tight')
png_b64 = base64.b64encode(buf.getvalue()).decode()
(ROOT / 'ckpt' / 'loss.png').write_bytes(buf.getvalue())

# 3) report html --------------------------------------------------------------
def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def sample_block(s):
    return f'<div class="sample"><div class="shead"><span class="sfile">{esc(s["file"])}</span><span class="smeta">{s["tps"]} tok/s · temp 0.4</span></div><pre>{esc(s["out"])}</pre></div>'

html = f'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MiniUnityLLM — 학습 리포트</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a100e;--panel:#101a16;--line:#21332a;--ink:#e9efe5;--dim:#93a89a;--faint:#63796c;--gold:#d9a84e;--read:#5ec8ac;--write:#ef7452}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(800px 400px at 10% -5%,rgba(217,168,78,.08),transparent 60%),var(--bg);color:var(--ink);font-family:"IBM Plex Sans KR",system-ui,sans-serif;font-size:14px;line-height:1.65}}
.wrap{{max-width:1080px;margin:0 auto;padding:48px 26px 80px}}
.eyebrow{{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint)}}
h1{{font-family:Archivo,sans-serif;font-size:40px;letter-spacing:-.03em;margin:8px 0 10px}}h1 span{{color:var(--gold)}}
.lede{{color:var(--dim);max-width:64ch}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0}}
.stat{{border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:14px}}
.stat b{{display:block;font-family:Archivo;font-size:26px;line-height:1.1}}.stat span{{font-size:9.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--faint)}}
h2{{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim);font-weight:500;margin:34px 0 12px;border-top:1px solid var(--line);padding-top:18px}}
.card{{border:1px solid var(--line);background:var(--panel);border-radius:12px;padding:18px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}td{{padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.05)}}td:first-child{{color:var(--faint);width:180px}}td b{{font-family:"IBM Plex Mono",monospace;font-weight:500}}
img{{width:100%;border-radius:10px;border:1px solid var(--line);display:block}}
.sample{{border:1px solid var(--line);border-radius:10px;margin-bottom:12px;overflow:hidden;background:#0a110e}}
.shead{{display:flex;justify-content:space-between;padding:9px 14px;border-bottom:1px solid var(--line);background:var(--panel)}}
.sfile{{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--gold)}}.smeta{{font-size:10px;color:var(--faint)}}
pre{{margin:0;padding:14px;font-family:"IBM Plex Mono",monospace;font-size:11.5px;line-height:1.7;color:#c9d6c9;white-space:pre-wrap}}
.note{{border-left:2px solid var(--write);background:rgba(239,116,82,.06);padding:14px 16px;border-radius:0 8px 8px 0;color:var(--dim);font-size:12.5px}}
.metric{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}
.metric div{{border:1px solid var(--line);border-radius:9px;padding:12px}}
.metric b{{font-family:Archivo;font-size:22px;display:block}}.metric span{{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint)}}
code{{font-family:"IBM Plex Mono",monospace;font-size:.92em;color:#e7d3a8}}
ul{{color:var(--dim);font-size:13px}}li{{margin:5px 0}}
</style></head><body><div class="wrap">
<div class="eyebrow">from scratch · decoder-only transformer</div>
<h1>MiniUnity<span>LLM</span></h1>
<p class="lede">Unity C# 코드를 입력받아 상속·역할·변수 흐름을 문장으로 생성하는 <b>1.42M 파라미터 LLM</b>. 바이트 BPE 토크나이저부터 어텐션 블록, 학습 루프까지 전부 이 프로젝트 안에서 직접 구현하고 CPU에서 학습했습니다. 교사(teacher)는 앞서 만든 규칙 기반 분석기 UnityLens입니다.</p>
<div class="grid">
<div class="stat"><b>{summary["params"]/1e6:.2f}M</b><span>parameters</span></div>
<div class="stat"><b>{summary["train_samples"]}</b><span>train pairs</span></div>
<div class="stat"><b>{metrics["format_rate"]*100:.0f}%</b><span>format validity</span></div>
<div class="stat"><b>{summary["minutes"]:.1f} min</b><span>CPU training</span></div>
</div>

<h2>모델 사양</h2>
<div class="card"><table>
<tr><td>구조</td><td><b>decoder-only GPT</b> · pre-LN · GELU · weight tying</td></tr>
<tr><td>레이어 / 차원 / 헤드</td><td><b>{summary["config"]["layers"]} / {summary["config"]["d"]} / {summary["config"]["heads"]}</b></td></tr>
<tr><td>문맥 길이</td><td><b>{summary["config"]["ctx"]} tokens</b></td></tr>
<tr><td>토크나이저</td><td><b>byte-level BPE</b> · vocab {summary["config"]["vocab"]} · 448 merges 직접 학습</td></tr>
<tr><td>학습</td><td><b>AdamW</b> · cosine + warmup · grad clip 1.0 · dropout 0.1</td></tr>
<tr><td>데이터</td><td><b>554개 스크립트</b> (합성 544 + 사용자 코드 10) · 555 타입 · 라벨은 UnityLens가 생성</td></tr>
<tr><td>하드웨어</td><td><b>CPU 2코어</b> · PyTorch 2.14 · 배치 6</td></tr>
</table></div>

<h2>학습 곡선</h2>
<div class="card"><img src="data:image/png;base64,{png_b64}" alt="loss curve">
<p class="eyebrow" style="margin:10px 0 0">validation = 학습에서 제외한 합성 스크립트 98개</p></div>

<h2>정량 평가 (held-out 24개)</h2>
<div class="metric">
<div><b>{metrics["base_acc"]*100:.0f}%</b><span>상속 정확도</span></div>
<div><b>{metrics["field_recall"]*100:.0f}%</b><span>필드 재현율</span></div>
<div><b>{metrics["role_recall"]*100:.0f}%</b><span>역할 재현율</span></div>
</div>
<p class="note" style="margin-top:14px">솔직한 결론: <b>형식과 상속은 학습했지만 내용은 아직 약합니다.</b> 상속 정확도 {metrics["base_acc"]*100:.0f}%, 형식 준수 {metrics["format_rate"]*100:.0f}%까지 올라왔지만 필드 이름 재현은 {metrics["field_recall"]*100:.1f}%에 그칩니다. 1.4M 파라미터·555개 예제로는 처음 보는 코드의 변수명을 안정적으로 옮겨 적지 못하고, 긴 파일에서는 토큰 반복이 생깁니다. <b>실사용 코드 해석기로는 부적합</b>하며, 정확한 분석이 필요하면 UnityLens(규칙 기반)를 쓰고 이 모델은 "LLM을 밑바닥부터 만든다"는 실험으로 봐야 합니다.</p>

<h2>생성 예시</h2>
{''.join(sample_block(s) for s in samples)}

<h2>구성</h2>
<ul>
<li><code>common.py</code> — BPE 토크나이저(학습/인코딩/디코딩), 프롬프트·라벨 포맷</li>
<li><code>model.py</code> — CausalSelfAttention · MLP · Block · GPT (샘플링 포함)</li>
<li><code>train.py</code> — 학습 루프, cosine 스케줄, val 평가, 체크포인트</li>
<li><code>chat.py</code> — C# 파일 → 분석 텍스트 생성 CLI</li>
<li><code>eval_model.py</code> — 상속/필드/역할/형식 지표</li>
<li><code>data_gen.py</code> — 16개 아키타입 × 34 변형 = 544개 합성 스크립트</li>
<li><code>analyze_batch.js</code> — UnityLens 분석기로 라벨 생성 (teacher)</li>
<li><code>ckpt/model.pt</code> — 학습된 가중치 · <code>ckpt/tokenizer.json</code> — BPE 병합 규칙</li>
</ul>
</div></body></html>'''
(ROOT / 'report.html').write_text(html, encoding='utf-8')

# 4) README ------------------------------------------------------------------
readme = f'''# MiniUnityLLM

Unity C# 코드를 읽고 분석문을 생성하는 **1.42M 파라미터 LLM**을 밑바닥부터 구현·학습한 프로젝트입니다.
바이트 BPE 토크나이저, decoder-only Transformer, AdamW 학습 루프, 샘플링까지 외부 LLM 라이브러리 없이 PyTorch만 사용합니다.

## 빠른 시작

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
python chat.py --file MyScript.cs
```

```
============================================================
MyScript.cs  ·  1400 step checkpoint · 128.6 tok/s
============================================================
상속: MonoBehaviour
역할: 이동 제어 / 수명 관리
...
```

## 다시 학습하기

```bash
python data_gen.py                 # 544개 합성 스크립트 생성
node analyze_batch.js data/scripts data/labels.json
python train.py --steps 1400 --batch 6 --dropout 0.1
```

## 평가

```bash
python eval_model.py
```

최종 지표(held-out 24개): 상속 정확도 {metrics["base_acc"]*100:.0f}%, 필드 재현율 {metrics["field_recall"]*100:.0f}%, 역할 재현율 {metrics["role_recall"]*100:.0f}%, 형식 준수 {metrics["format_rate"]*100:.0f}%.

## 한계

- 1.42M 파라미터 · 555 학습 예제. **실제 코드 해석기로 쓰기에는 부족합니다.**
- 긴 파일에서 토큰 반복이 발생합니다(rep penalty 1.12 적용).
- 학습 데이터에 포함된 10개 파일은 외운 수준으로 재현하고, 처음 보는 코드는 형식만 흉내 냅니다.
- 정확한 정적 분석이 필요하면 `UnityLens.html`(규칙 기반)을 사용하세요.

## 파일

| 파일 | 역할 |
|---|---|
| `ckpt/model.pt` | 학습된 가중치 (5.7MB) |
| `ckpt/tokenizer.json` | BPE 병합 규칙 |
| `report.html` | 학습 리포트 (곡선·지표·생성 예시) |
| `train.log`, `train2.log` | 학습 로그 |

## 라이선스 / 데이터

합성 스크립트는 `data_gen.py`가 생성하며, 라벨은 UnityLens 분석기가 만든 것입니다. 사용자가 제공한 10개 스크립트가 학습 데이터에 포함되어 있습니다.
'''
(ROOT / 'README.md').write_text(readme, encoding='utf-8')

# 5) zip ---------------------------------------------------------------------
zp = ROOT / 'MiniUnityLLM.zip'
if zp.exists():
    zp.unlink()
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_dir() or '__pycache__' in p.parts or p.name == zp.name:
            continue
        if p.suffix in ('.png',) and p.name != 'loss.png':
            continue
        z.write(p, p.relative_to(ROOT))
print('report + zip done', zp.stat().st_size / 1e6, 'MB', metrics)
