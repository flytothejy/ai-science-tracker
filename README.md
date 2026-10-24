# ai-science-tracker

AI가 과학·수학 연구에 얼마나, 어떤 수준으로 들어오고 있는지 추적하는 서비스의 PoC.
첫 검증 대상은 수학(에르되시 문제)이며, 핵심 질문은 **각 단계가 구상대로 자동화되는가**입니다.

## 파이프라인

| 단계 | 내용 | 상태 |
|---|---|---|
| 1. 수집 | 인프라급 소스(arXiv, OpenAlex, 에르되시 DB)와 랩·전문가 피드에서 후보 수집, 규칙 필터 | 구현·검증 중 |
| 2. 조사 | 후보별로 에이전트가 "AI 기여 + 근거"를 조사 | 1단계 규모 측정 후 결정 |
| 3. 판정 | 외부 신호(Lean 형식 검증, DOI 게재, 반박)로 상태 갱신 | 예정 |

## 소스

| 소스 | 등급 | 백필 | 용도 |
|---|---|---|---|
| arXiv API | 인프라 | 가능 | 수학×AI 논문 |
| OpenAlex | 인프라 | 가능 | 저널·프리프린트 |
| 에르되시 DB (`teorth/erdosproblems`) | 커뮤니티 데이터 | 커밋 비교로 가능 | 상태·Lean 형식화 신호 |
| OpenAI 뉴스, DeepMind 블로그 | 1차 발표 | 피드 범위 내 | 랩 발표 |
| Quanta, Tao 블로그 | 매체·전문가 | 부분 가능 | 맥락·전문가 반응 |

## 실행

```bash
pip install -r requirements.txt
python -m tracker.collect --since 2026-01-01 --until 2026-01-31   # 기간 재현
python -m validation.replay --since 2026-01-01 --until 2026-01-31 --case 281
python -m tracker.collect --daily                                   # 일일 운영
```

GitHub Actions(`collect`)가 매일 05:43 KST에 일일 수집을 돌리고, 수동 실행 시 기간을 넣으면 재현 검증 리포트를 `reports/`에 남깁니다.

## 검증 방법

커뮤니티 위키 'AI contributions to Erdős problems'(2026-06-30 동결)를 정답지로 삼아,
과거 구간을 재현했을 때 우리 수집기가 위키 사례를 몇 %나 잡는지(재현율)로 1단계를 채점합니다.

## 출력

- `data/candidates/<run>.jsonl` — 2단계로 넘길 후보
- `data/runs/<run>.json` — 소스별 작동 기록(요청 수, 응답 코드, 실패)
- `reports/replay_<run>.md` — 재현 검증 리포트
