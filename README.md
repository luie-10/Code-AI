# Code-AI — Unity C# 해석 + 소형 코드 모델

Unity C# 코드의 상속·역할·변수 흐름을 정적 분석하고, 그 결과를 LLM이 서술하는 도구 모음입니다.

## 구성

| 폴더 | 내용 |
|---|---|
| `unitylens/` | v1 — 단일 파일 정적 분석기 (`UnityLens.html`) |
| `unitylens-v4/` | v4 — 파서 추적 + AI 해설 카드(요약/변수 흐름/리스크), LLM 연결 |
| `minillm/` | MiniUnityLLM 학습·평가 코드 (v1~v3.2) |
| `results/` | v3.1 / v3.2 / v3.3 실측 리포트와 평가 원자료 |

## 현재 결과 (실제 GitHub 코드 held-out 10클래스/42필드)

| 지표 | v3 | v3.1 | v3.2 (후보 선택) |
|---|---|---|---|
| 필드 재현율 | 0.0% | 11.9% | **74.7%** (100클래스) |
| 필드 정밀도 | 0.0% | 100% | **84.8%** (100클래스) |

- v3.2 구조: 파서가 필드 후보를 만들고, 모델이 후보별 `Y/N`을 선택.
- v3.3: 평가셋을 100클래스로 확대. 임계값 튜닝은 효과 없음(최적 threshold 0.00).
- 한계: 메서드 단위 정밀도 31.9%, LLM 실제 호출 미검증.

## 실행

```bash
# UnityLens v4: 브라우저에서 unitylens-v4/UnityLens.html 열기
# 재빌드
cd unitylens-v4 && python3 build.py

# v3.2 학습/평가 (CPU)
cd minillm && python3 finetune_select.py && python3 eval_select.py
```

체크포인트(`*.pt`)는 용량 때문에 제외했습니다. 학습 스크립트로 재생성할 수 있습니다.
