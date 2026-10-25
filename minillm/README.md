# MiniUnityLLM

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

최종 지표(held-out 24개): 상속 정확도 96%, 필드 재현율 1%, 역할 재현율 58%, 형식 준수 88%.

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
