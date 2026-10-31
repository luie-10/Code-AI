# MiniUnityLLM v3.8 — 학습 파이프라인 정비

v3.2~v3.7은 버전마다 일회성 스크립트(finetune_select / train_big / train_early / train_v37 …)를 새로 만들었고, 그 과정에서 아래 문제가 생겼습니다. v3.8은 모델 구조는 그대로 두고 **학습·평가 파이프라인**을 하나로 합쳐 이 문제들을 막습니다.

> 결과: **아직 실측 전**입니다. 아래 명령으로 학습한 뒤 `results/report_v3_8.md`에 기록하세요.

## v3.7까지의 문제 → v3.8 해결

| 문제 | 원인 | v3.8 |
|---|---|---|
| v3.5 최고 체크포인트 소실 | 같은 `last.pt`에 덮어씀 | `best.pt`/`last.pt` 분리, 원자적 저장, 기존 출력 폴더면 실행 거부 |
| 체크포인트 선택 기준이 최종 지표와 다름 | v3.7은 메서드 단위 홀드아웃 F1로 선택 | **dev 클래스 F1(임계값 보정 후)** 로 선택. test 100클래스는 학습 중 보지 않음 |
| 750 step에서 시간 상한으로 끊김 | 재개 기능 없음 | `last.pt`에 옵티마이저·RNG 저장, `--resume`으로 이어서 학습 |
| 임계값을 따로 탐색해야 함 | 학습 후 eval_ens.py에서 수동 보정 | 매 평가마다 dev에서 보정, 임계값을 체크포인트에 저장 → 평가가 자동 사용 |
| Y/N 학습 신호가 약함 | collate가 프롬프트 전체에 LM 손실을 걸어 정답 2토큰이 묻힘 | `--loss mix`(기본): 정답 손실 + 0.1 × 프롬프트 LM 손실. `answer`/`all`로 비교 가능 |
| 긴 메서드에서 CLASS/FIELDS 줄이 사라짐 | 토큰 앞부분을 잘라냄 | `--trunc smart`(기본): 헤더와 질의는 유지하고 코드 본문 끝만 자름 |
| +0.019 같은 작은 차이를 판단할 근거 없음 | 점 추정만 보고 | 클래스 부트스트랩 95% CI, `--compare`로 두 모델 쌍대 비교 |
| 추가 데이터가 평가 클래스와 겹칠 위험 | 수동 관리 | `--extra` 샘플 중 dev/test 클래스 이름은 자동 제외 |
| v3.6·v3.7 스크립트 누락 | 저장소에 커밋 안 됨 | 하나의 `train_select.py`로 v3.2(미세조정)~v3.7(scratch·추가 데이터) 설정 재현 |

데이터 분할(train=`val=False`, test=val 클래스 앞 100개, dev=나머지 82개)과 클래스당 5메서드 상한은 v3.3~v3.7과 같아서 숫자를 그대로 비교할 수 있습니다.

## 파일

| 파일 | 역할 |
|---|---|
| `select_common.py` | 분할·질의 인코딩·점수·지표·임계값·부트스트랩 (기존 6개 스크립트의 중복 코드 통합) |
| `train_select.py` | 학습 (dev 선택, 재개, early stopping, 손실/절단 옵션) |
| `eval_select38.py` | test 평가 + 95% CI, `--compare` 쌍대 부트스트랩 |

## 실행

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
cd minillm

# 25.77M from scratch (v3.5~v3.7과 같은 크기)
python train_select.py --out ckpt_v3_8 --steps 3000 --time-cap 1500
python train_select.py --out ckpt_v3_8 --resume            # 시간 상한 뒤 이어서

# v3.7처럼 추가 데이터 사용 (학습 전용)
python train_select.py --out ckpt_v3_8b --extra data/new_samples.json

# 평가 (체크포인트에 저장된 dev 임계값 사용)
python eval_select38.py --ckpt ckpt_v3_8/best.pt
python eval_select38.py --ckpt ckpt_v3_8/best.pt --compare ckpt_v3_7/best.pt
```

v3.7 이전 체크포인트는 `--trunc tail`로 학습됐으므로 평가 시 자동으로 `tail`을 쓰고, 저장된 임계값이 없으면 dev에서 다시 고릅니다.

## 권장 실험 순서

1. `--loss all --trunc tail` — v3.7 학습 방식 재현(기준선)
2. `--loss mix` / `--loss answer` — 손실 변경 효과
3. `--trunc smart` — 절단 방식 효과
4. 가장 좋은 설정 + `--extra`

각 단계는 `--compare`로 직전 단계와 비교하고, `diff_ci95`가 0을 포함하면 개선으로 보지 않습니다.

## 검증 범위

합성 데이터(1,416 메서드, 0.17M~0.6M 모델)로 학습·재개·early stopping·미세조정·평가·비교·옛 체크포인트 평가가 모두 동작하는 것과, 손실이 7.2 → 0.27로 내려가며 Y/N을 학습하는 것까지 확인했습니다. 실제 `real_samples.json`과 25.77M 모델로는 아직 돌려보지 않았습니다.
