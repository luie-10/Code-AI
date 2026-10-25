#!/usr/bin/env python3
"""Build the v1 vs v2 comparison report and package v2."""
import base64
import io
import json
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).parent
v1 = json.loads((ROOT / 'data' / 'eval.json').read_text())['metrics']
v2 = json.loads((ROOT / 'data' / 'eval_v2.json').read_text())
m2 = v2['metrics']
rows = v2['rows']
s2 = json.loads((ROOT / 'ckpt_v2' / 'summary.json').read_text())
s1 = json.loads((ROOT / 'ckpt' / 'summary.json').read_text())

# loss curves for both runs
fig, axs = plt.subplots(1, 2, figsize=(11, 3.4), dpi=170)
fig.patch.set_facecolor('#0d1512')
for ax in axs:
    ax.set_facecolor('#0d1512')
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color('#2c4437')
    ax.tick_params(colors='#63796c', labelsize=8)
    ax.grid(color='#1c2b23', lw=.6)
    ax.xaxis.set_major_locator(MaxNLocator(5))

def curve(ax, path, title, color):
    h = json.loads(Path(path).read_text())
    tr = [(x['step'], x['train']) for x in h if 'train' in x]
    va = [(x['step'], x['val']) for x in h if 'val' in x]
    ax.plot([a for a, _ in tr], [b for _, b in tr], color=color, lw=1.4, label='train')
    ax.plot([a for a, _ in va], [b for _, b in va], color='#d9a84e', lw=1.6, marker='o', ms=2.5, label='val')
    ax.set_title(title, color='#93a89a', fontsize=9, loc='left')
    leg = ax.legend(frameon=False, fontsize=7, loc='upper right')
    for t in leg.get_texts():
        t.set_color('#93a89a')

curve(axs[0], ROOT / 'ckpt' / 'loss.json', 'v1 · 1.42M · class-level', '#5ec8ac')
curve(axs[1], ROOT / 'ckpt_v2' / 'loss.json', 'v2 · 11.0M · method-level', '#5ec8ac')
fig.tight_layout()
buf = io.BytesIO()
fig.savefig(buf, format='png', facecolor=fig.get_facecolor(), bbox_inches='tight')
png = base64.b64encode(buf.getvalue()).decode()


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


samples = ''.join(
    f'<div class="sample"><div class="shead"><span class="sfile">{esc(r["type"])} · {esc(r["file"])}</span>'
    f'<span class="smeta">base {"O" if r["base_ok"] else "X"} · fields {len(set(r["fields"]) & set(r["gold_fields"]))}/{len(r["gold_fields"])}</span></div>'
    f'<pre>{esc(r["sample"])}</pre></div>'
    for r in rows[:3]
)

def pct(x):
    return f'{x*100:.1f}%'

html = f'''<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MiniUnityLLM v2 — 비교 리포트</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a100e;--panel:#101a16;--line:#21332a;--ink:#e9efe5;--dim:#93a89a;--faint:#63796c;--gold:#d9a84e;--read:#5ec8ac;--write:#ef7452}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(800px 420px at 8% -6%,rgba(217,168,78,.08),transparent 60%),var(--bg);color:var(--ink);font-family:"IBM Plex Sans KR",system-ui,sans-serif;font-size:14px;line-height:1.65}}
.wrap{{max-width:1080px;margin:0 auto;padding:46px 26px 70px}}
.eyebrow{{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint)}}
h1{{font-family:Archivo,sans-serif;font-size:42px;letter-spacing:-.03em;margin:8px 0 10px}}h1 span{{color:var(--gold)}}
.lede{{color:var(--dim);max-width:66ch}}
h2{{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:var(--dim);font-weight:500;margin:32px 0 12px;border-top:1px solid var(--line);padding-top:18px}}
.card{{border:1px solid var(--line);background:var(--panel);border-radius:12px;padding:18px}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th{{text-align:left;font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);font-weight:500;padding:0 10px 8px;border-bottom:1px solid var(--line)}}
td{{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.05);color:var(--dim)}}
td b{{color:var(--ink);font-family:"IBM Plex Mono",monospace;font-weight:500}}
.up{{color:var(--read)}}.down{{color:var(--write)}}
img{{width:100%;border-radius:10px;border:1px solid var(--line);display:block}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}}
.stat{{border:1px solid var(--line);background:var(--panel);border-radius:10px;padding:13px}}
.stat b{{display:block;font-family:Archivo;font-size:24px;line-height:1.1}}.stat span{{font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}}
.sample{{border:1px solid var(--line);border-radius:10px;margin-bottom:10px;overflow:hidden;background:#0a110e}}
.shead{{display:flex;justify-content:space-between;padding:9px 14px;border-bottom:1px solid var(--line);background:var(--panel)}}
.sfile{{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--gold)}}.smeta{{font-size:10px;color:var(--faint)}}
pre{{margin:0;padding:14px;font-family:"IBM Plex Mono",monospace;font-size:11.5px;line-height:1.7;color:#c9d6c9;white-space:pre-wrap}}
.note{{border-left:2px solid var(--write);background:rgba(239,116,82,.06);padding:14px 16px;border-radius:0 8px 8px 0;color:var(--dim);font-size:12.5px}}
.note.good{{border-color:var(--read);background:rgba(94,200,172,.06)}}
ul{{color:var(--dim);font-size:13px}}li{{margin:5px 0}}code{{font-family:"IBM Plex Mono",monospace;font-size:.92em;color:#e7d3a8}}
</style></head><body><div class="wrap">
<div class="eyebrow">retrain report · v1 → v2</div>
<h1>11M 파라미터, <span>함수 단위</span>로 다시 학습</h1>
<p class="lede">① d=384 · 6 layers(11.02M) ② 5,131개 타입 / 9,000 학습 샘플 ③ 메서드 단위 샘플링 + 클래스 집계 평가. 같은 CPU(2코어)에서 14.2분 학습했습니다. 아래 수치는 모두 학습에서 제외한 클래스에서 측정했습니다.</p>

<div class="grid">
<div class="stat"><b>11.02M</b><span>parameters (7.8×)</span></div>
<div class="stat"><b>9,000</b><span>method samples (19.7×)</span></div>
<div class="stat"><b>{s2["minutes"]:.1f} min</b><span>train time</span></div>
<div class="stat"><b>{pct(m2["base_acc"])}</b><span>aggregated base acc</span></div>
</div>

<h2>지표 비교</h2>
<div class="card"><table>
<tr><th>지표</th><th>v1 · 클래스 단위</th><th>v2 · 함수 단위 집계</th><th>변화</th></tr>
<tr><td>상속 정확도</td><td><b>{pct(v1["base_acc"])}</b></td><td><b class="up">{pct(m2["base_acc"])}</b></td><td class="up">+{(m2["base_acc"]-v1["base_acc"])*100:.1f}pp</td></tr>
<tr><td>필드 재현율</td><td><b>{pct(v1["field_recall"])}</b></td><td><b class="up">{pct(m2["field_recall"])}</b></td><td class="up">+{(m2["field_recall"]-v1["field_recall"])*100:.1f}pp</td></tr>
<tr><td>필드 정밀도</td><td><b>{pct(v1["field_precision"])}</b></td><td><b>{pct(m2["field_precision"])}</b></td><td>{(m2["field_precision"]-v1["field_precision"])*100:+.1f}pp</td></tr>
<tr><td>형식 준수</td><td><b>{pct(v1["format_rate"])}</b></td><td><b>{pct(m2["format_rate"])}</b></td><td>{(m2["format_rate"]-v1["format_rate"])*100:+.1f}pp</td></tr>
<tr><td>역할 정확도</td><td><b>{pct(v1["role_recall"])}</b><br><span style="font-size:10px">클래스 역할 재현</span></td><td><b>{pct(m2["role_acc"])}</b><br><span style="font-size:10px">메서드 역할 분류</span></td><td>지표 정의 다름</td></tr>
<tr><td>검증 손실</td><td><b>{s1["best_val"]:.4f}</b></td><td><b>{s2["best_val"]:.4f}</b></td><td class="up">-</td></tr>
</table>
<p class="note good" style="margin-top:14px">효과가 가장 큰 곳은 <b>변수 추적</b>입니다. v1은 필드 이름을 거의 옮기지 못했지만(1.4%), v2는 메서드 하나를 프롬프트로 받아 그 안에서 읽고 쓰는 필드를 정확히 나열합니다(재현율 {pct(m2["field_recall"])}). ③ 함수 단위 샘플링이 문맥 길이 문제를 없앤 직접적인 결과입니다.</p>
<p class="note" style="margin-top:10px">단, v2의 검증 손실 {s2["best_val"]:.4f}은 지나치게 낮습니다. 검증 클래스도 학습과 같은 16개 아키타입의 변형이라 사실상 <b>패턴 외우기</b>에 가깝습니다. 절대 수치를 일반화 성능으로 읽으면 안 되고, v1→v2의 <b>상대 변화</b>만 봐야 합니다.</p>
</div>

<h2>학습 곡선</h2>
<div class="card"><img src="data:image/png;base64,{png}" alt="loss curves"></div>

<h2>생성 예시 (held-out 클래스)</h2>
{samples}

<h2>무엇이 달라졌나</h2>
<ul>
<li><b>모델</b> — d=160/4L/4H 1.42M → d=384/6L/6H <b>11.02M</b>, ctx 448 → 320 (메서드 단위라 짧아도 충분)</li>
<li><b>데이터</b> — 16개 아키타입 × 320 변형 = <b>5,120 스크립트</b> + 사용자 10개 → 14,427 메서드 샘플 중 9,000 학습</li>
<li><b>③ 함수 단위 샘플링</b> — 프롬프트는 <code>CLASS / FIELDS / METHOD + 메서드 본문</code>, 타깃은 <code>상속 / 메서드 / 역할 / 변수 / 호출 / 주의</code>. 추론 시 메서드별 출력을 합집합으로 집계해 클래스 단위 지표를 계산</li>
<li><b>학습</b> — batch 6, lr 5e-4, cosine, dropout 0.1, 1,100 steps, 14.2분 (CPU 2코어)</li>
</ul>

<h2>한계</h2>
<ul>
<li>합성 16개 아키타입이 데이터의 99%입니다. 실제 프로젝트 코드 다양성과는 거리가 있습니다.</li>
<li>메서드 역할은 규칙으로 라벨링한 것이라, 모델은 "역할 분류"를 배운 게 아니라 라벨 규칙을 모방합니다.</li>
<li>클래스 단위 변수 흐름(예: Start에서 쓴 값을 Update에서 읽음)은 여전히 메서드별로 끊겨 보입니다.</li>
<li>정확한 분석이 목적이면 <b>UnityLens(규칙 기반)</b>가 여전히 우위입니다. 이 모델은 "작은 LLM이 어디까지 따라오는가"의 기록입니다.</li>
</ul>
</div></body></html>'''
(ROOT / 'report_v2.html').write_text(html, encoding='utf-8')

readme = f'''# MiniUnityLLM v2

11.02M 파라미터 · 함수(메서드) 단위 샘플링으로 재학습한 버전입니다.

## v1 → v2

| | v1 | v2 |
|---|---|---|
| 파라미터 | 1.42M | **11.02M** (d384/6L/6H) |
| 샘플 | 457 클래스 | **9,000 메서드** (14,427개 중) |
| 데이터 | 555 타입 | **5,131 타입** |
| 검증 상속 정확도 | {pct(v1["base_acc"])} | **{pct(m2["base_acc"])}** |
| 필드 재현율 | {pct(v1["field_recall"])} | **{pct(m2["field_recall"])}** |
| 형식 준수 | {pct(v1["format_rate"])} | **{pct(m2["format_rate"])}** |
| 학습 시간 | 7.4분 | 14.2분 (CPU 2코어) |

## 실행

```bash
python eval2.py last.pt          # 지표 재현
python eval2.py last.pt          # 메서드 단위 추론 + 클래스 집계
```

v2 추론은 `eval2.py`의 `parse`/집계 루틴을 참고하세요. 모델 가중치는 `ckpt_v2/last.pt`.

## 주의

검증 손실 0.0023은 같은 아키타입 변형 데이터 때문이며 실제 일반화 성능이 아닙니다. 자세한 내용은 `report_v2.html`.
'''
(ROOT / 'README_v2.md').write_text(readme, encoding='utf-8')

zp = ROOT / 'MiniUnityLLM-v2.zip'
if zp.exists():
    zp.unlink()
skip = {'best.pt', 'method_tokens.pt', 'MiniUnityLLM.zip', 'MiniUnityLLM-v2.zip', 'labels.json', 'labels2.json', 'method_samples.json'}
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_dir() or '__pycache__' in p.parts or p.name in skip:
            continue
        if p.suffix == '.png':
            continue
        if 'scripts' in p.parts:
            continue
        z.write(p, p.relative_to(ROOT))
print('v2 report + zip', round(zp.stat().st_size / 1e6, 1), 'MB', m2)
