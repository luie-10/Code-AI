import base64, io, json, zipfile
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).parent
m3 = json.loads((ROOT/'data/eval_v3.json').read_text())['metrics']
m2r = json.loads((ROOT/'data/eval_v2_real.json').read_text())['metrics']
rows = json.loads((ROOT/'data/eval_v3.json').read_text())['rows']
s3 = json.loads((ROOT/'ckpt_v3/summary.json').read_text())
s2 = json.loads((ROOT/'ckpt_v2/summary.json').read_text())
v1 = json.loads((ROOT/'data/eval.json').read_text())['metrics']

h = json.loads((ROOT/'ckpt_v3/loss.json').read_text())
tr = [(x['step'], x['train']) for x in h if 'train' in x]
va = [(x['step'], x['val']) for x in h if 'val' in x]
fig, ax = plt.subplots(figsize=(9, 3.2), dpi=170)
fig.patch.set_facecolor('#0d1512'); ax.set_facecolor('#0d1512')
ax.plot([a for a,_ in tr],[b for _,b in tr], color='#5ec8ac', lw=1.4, label='train')
ax.plot([a for a,_ in va],[b for _,b in va], color='#d9a84e', lw=1.8, marker='o', ms=3, label='validation (real held-out)')
for sp in ('top','right'): ax.spines[sp].set_visible(False)
for sp in ('left','bottom'): ax.spines[sp].set_color('#2c4437')
ax.tick_params(colors='#63796c', labelsize=8); ax.grid(color='#1c2b23', lw=.6)
ax.xaxis.set_major_locator(MaxNLocator(6)); ax.set_xlabel('step', color='#63796c', fontsize=8)
ax.set_ylabel('cross-entropy', color='#63796c', fontsize=8)
leg = ax.legend(frameon=False, fontsize=8, loc='upper right')
for t in leg.get_texts(): t.set_color('#93a89a')
fig.tight_layout(); buf = io.BytesIO(); fig.savefig(buf, format='png', facecolor=fig.get_facecolor(), bbox_inches='tight')
png = base64.b64encode(buf.getvalue()).decode()

def esc(s): return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
def pct(x): return f'{x*100:.1f}%'
samples = ''.join(
    f'<div class="sample"><div class="shead"><span class="sfile">{esc(r["type"])} · {esc(r["file"])}</span>'
    f'<span class="smeta">base {"O" if r["base_ok"] else "X"} · fields {len(set(r["fields"]) & set(r["gold_fields"]))}/{len(r["gold_fields"])}</span></div>'
    f'<pre>{esc(r["sample"])}</pre></div>' for r in rows[:3])

html = f'''<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MiniUnityLLM v3 — 실제 코드 리포트</title>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0a100e;--panel:#101a16;--line:#21332a;--ink:#e9efe5;--dim:#93a89a;--faint:#63796c;--gold:#d9a84e;--read:#5ec8ac;--write:#ef7452}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(800px 420px at 8% -6%,rgba(94,200,172,.07),transparent 60%),var(--bg);color:var(--ink);font-family:"IBM Plex Sans KR",system-ui,sans-serif;font-size:14px;line-height:1.65}}
.wrap{{max-width:1080px;margin:0 auto;padding:46px 26px 70px}}
.eyebrow{{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint)}}
h1{{font-family:Archivo,sans-serif;font-size:42px;letter-spacing:-.03em;margin:8px 0 10px}}h1 span{{color:var(--read)}}
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
<div class="eyebrow">v3 · trained on real github code</div>
<h1>합성 데이터를 걷어내고 <span>실제 코드</span>로</h1>
<p class="lede">GitHub의 Unity 프로젝트 12개에서 <b>1,391개 스크립트</b>(2,089 타입)를 수집해 다시 학습했습니다. 합성 16개 아키타입은 학습에서 완전히 제외했고, 평가는 <b>처음 보는 실제 클래스 10개</b>에서 메서드별 추론을 집계해 측정했습니다.</p>
<div class="grid">
<div class="stat"><b>1,391</b><span>real .cs files</span></div>
<div class="stat"><b>4,187</b><span>train methods</span></div>
<div class="stat"><b>{s3["minutes"]:.1f} min</b><span>train time (CPU)</span></div>
<div class="stat"><b>{pct(m3["field_recall"])}</b><span>field recall (real)</span></div>
</div>

<h2>같은 실제 코드에서 v2 vs v3</h2>
<div class="card"><table>
<tr><th>지표</th><th>v2 (합성 학습)</th><th>v3 (실제 학습)</th><th>변화</th></tr>
<tr><td>상속 정확도</td><td><b>{pct(m2r["base_acc"])}</b></td><td><b class="up">{pct(m3["base_acc"])}</b></td><td class="up">+{(m3["base_acc"]-m2r["base_acc"])*100:.1f}pp</td></tr>
<tr><td>필드 재현율</td><td><b>{pct(m2r["field_recall"])}</b></td><td><b class="up">{pct(m3["field_recall"])}</b></td><td class="up">+{(m3["field_recall"]-m2r["field_recall"])*100:.1f}pp</td></tr>
<tr><td>필드 정밀도</td><td><b>{pct(m2r["field_precision"])}</b></td><td><b>{pct(m3["field_precision"])}</b></td><td>{(m3["field_precision"]-m2r["field_precision"])*100:+.1f}pp</td></tr>
<tr><td>형식 준수</td><td><b>{pct(m2r["format_rate"])}</b></td><td><b>{pct(m3["format_rate"])}</b></td><td>{(m3["format_rate"]-m2r["format_rate"])*100:+.1f}pp</td></tr>
<tr><td>메서드 역할</td><td><b>{pct(m2r["role_acc"])}</b></td><td><b>{pct(m3["role_acc"])}</b></td><td>{(m3["role_acc"]-m2r["role_acc"])*100:+.1f}pp</td></tr>
</table>
<p class="note" style="margin-top:14px">합성 데이터로만 학습한 v2는 실제 코드에서 <b>형식부터 무너집니다</b>(형식 {pct(m2r["format_rate"])}). v3는 같은 11M 파라미터인데도 상속 {pct(m3["base_acc"])}, 형식 {pct(m3["format_rate"])}로 버팁니다. 모델 크기보다 <b>데이터 분포</b>가 훨씬 중요하다는 걸 그대로 보여주는 결과입니다.</p>
<p class="note good" style="margin-top:10px">v2의 합성 검증 손실 0.0023은 실제 코드에서 재현되지 않았습니다(v3 실제 검증 손실 {s3["best_val"]:.4f}). 이전 리포트에서 "착시"라고 적었던 부분이 수치로 확인됐습니다.</p>
</div>

<h2>학습 곡선 (실제 코드)</h2>
<div class="card"><img src="data:image/png;base64,{png}" alt="v3 loss"></div>

<h2>생성 예시 (held-out 실제 클래스)</h2>
{samples}

<h2>코퍼스</h2>
<ul>
<li><b>12 repos</b> — BoatAttack, EndlessRunnerSampleGame, Boss Room(co-op), 2d-extras, EntityComponentSystemSamples, ml-agents, Netcode, Klak, Skinner, Markerless, Mirror, NoiseBall</li>
<li><b>1,391 파일 / 2,089 타입 / 647 MonoBehaviour</b> — Editor·Plugins·Tests 경로 제외, 중복 해시 제거, 300~20,000자</li>
<li>평가용 600 메서드 샘플은 파일 단위로 분리(182 파일)해 학습에서 제외</li>
</ul>

<h2>한계</h2>
<ul>
<li>상속 정확도는 클래스 헤더를 프롬프트에 그대로 주기 때문에 후하게 나옵니다. 진짜 실력은 필드 재현율({pct(m3["field_recall"])})과 정밀도({pct(m3["field_precision"])})입니다.</li>
<li>역할 라벨은 여전히 규칙 기반입니다. 모델이 역할을 "이해"한 것이 아니라 라벨 규칙을 모방합니다.</li>
<li>실제 코드는 라이선스가 제각각입니다. 학습 가중치를 배포·상업적으로 쓸 때는 각 저장소 라이선스를 확인해야 합니다.</li>
<li>정확한 정적 분석은 여전히 UnityLens가 우위입니다. 이 모델은 "11M 파라미터가 실제 코드에서 어디까지 버티는가"의 기록입니다.</li>
</ul>
</div></body></html>'''
(ROOT/'report_v3.html').write_text(html, encoding='utf-8')

readme = f'''# MiniUnityLLM v3 — real code

GitHub Unity 프로젝트 12개에서 1,391개 스크립트(2,089 타입)를 모아 재학습한 버전입니다. 합성 데이터는 사용하지 않았습니다.

| 지표 (실제 held-out 10 클래스) | v2 (합성) | v3 (실제) |
|---|---|---|
| 상속 | {pct(m2r["base_acc"])} | **{pct(m3["base_acc"])}** |
| 필드 재현율 | {pct(m2r["field_recall"])} | **{pct(m3["field_recall"])}** |
| 필드 정밀도 | {pct(m2r["field_precision"])} | {pct(m3["field_precision"])} |
| 형식 준수 | {pct(m2r["format_rate"])} | **{pct(m3["format_rate"])}** |
| 역할 | {pct(m2r["role_acc"])} | {pct(m3["role_acc"])} |

## 실행

```bash
python eval_real.py --model ckpt_v3 --ckpt last.pt
```

가중치: `ckpt_v3/last.pt` (43MB, 11.07M params, ctx 448).
학습: `train2.py --samples data/real_samples.json --tokenizer ckpt_v2/tokenizer.json --out ckpt_v3 --ctx 448`

## 데이터 수집

`filter_real.py`가 GitHub tarball에서 추출한 .cs를 필터링합니다(Editor/Plugins/Tests 제외, 클래스 선언 포함, 300~20,000자, 중복 해시 제거).

자세한 내용은 `report_v3.html`.
'''
(ROOT/'README_v3.md').write_text(readme, encoding='utf-8')

zp = ROOT/'MiniUnityLLM-v3.zip'
if zp.exists(): zp.unlink()
skip = {'best.pt', 'method_tokens.pt', 'ckpt_v3_tokens.pt', 'MiniUnityLLM.zip', 'MiniUnityLLM-v2.zip', 'MiniUnityLLM-v3.zip', 'labels.json', 'labels2.json', 'labels_real.json', 'method_samples.json', 'real_samples.json'}
with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob('*')):
        if p.is_dir() or '__pycache__' in p.parts or p.name in skip: continue
        if p.suffix == '.png': continue
        if 'scripts' in p.parts: continue
        if p.parts[-2:-1] and p.parts[-2] == 'ckpt_v2': continue
        z.write(p, p.relative_to(ROOT))
print('v3', round(zp.stat().st_size/1e6,1), 'MB', m3)
