# MiniUnityLLM v3 — real code

GitHub Unity 프로젝트 12개에서 1,391개 스크립트(2,089 타입)를 모아 재학습한 버전입니다. 합성 데이터는 사용하지 않았습니다.

| 지표 (실제 held-out 10 클래스) | v2 (합성) | v3 (실제) |
|---|---|---|
| 상속 | 50.0% | **70.0%** |
| 필드 재현율 | 0.0% | **0.0%** |
| 필드 정밀도 | 0.0% | 0.0% |
| 형식 준수 | 69.0% | **97.6%** |
| 역할 | 35.7% | 38.1% |

## 실행

```bash
python eval_real.py --model ckpt_v3 --ckpt last.pt
```

가중치: `ckpt_v3/last.pt` (43MB, 11.07M params, ctx 448).
학습: `train2.py --samples data/real_samples.json --tokenizer ckpt_v2/tokenizer.json --out ckpt_v3 --ctx 448`

## 데이터 수집

`filter_real.py`가 GitHub tarball에서 추출한 .cs를 필터링합니다(Editor/Plugins/Tests 제외, 클래스 선언 포함, 300~20,000자, 중복 해시 제거).

자세한 내용은 `report_v3.html`.
