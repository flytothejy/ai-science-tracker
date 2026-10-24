# 2단계(조사) 시범 결과 — 10건

같은 지침(`prompts/research.md`)을 받은 조사 에이전트(Sonnet)가 후보 1건씩 독립 조사. 정답지 위키는 사용 금지.

| # | 등급 | 후보 | AI 기여 판정 | 구분/결과 | 상태 | 채점 | 검색 | 열람 | 토큰 |
|---|---|---|---|---|---|---|---|---|---|
| 0 | S | Erdős problem #281 → proved (Lean) | 예 | 1b_alongside_literature/full | expert_confirmed | ✅ 여부 · ✅ 구분 · ✅ 결과 | 2 | 5 | 74442 |
| 1 | S | Erdős problem #224 → proved (Lean) | 예 | 2b_formalization/full | claimed | ✅ 여부 · ⚠️ 구분 · ✅ 결과 | 1 | 2 | 71869 |
| 2 | S | Erdős problem #570 → proved | 아니오 | none/n/a | claimed | ✅ AI 기여 여부 | 3 | 5 | 74064 |
| 3 | S | Erdős problem #834 → solved | 아니오 | none/n/a | claimed | ✅ AI 기여 여부 | 3 | 4 | 72230 |
| 4 | A | Resolution of Erdős Problem #728: a writeup of A | 예 | 1a_standalone/full | formally_verified | ✅ 여부 · ⚠️ 구분 · ✅ 결과 | 1 | 4 | 75095 |
| 5 | A | Semi-Autonomous Mathematics Discovery with Gemin | 예 | 1c_building_on_literature/partial | claimed | ✅ 타당 | 1 | 3 | 73783 |
| 6 | A | Towards Solving the Gilbert-Pollak Conjecture vi | 예 | 1d_collaboration/partial | peer_reviewed | ✅ 타당 | 1 | 3 | 72607 |
| 7 | B | Bruhat intervals that are large hypercubes | 예 | 1d_collaboration/full | claimed | ✅ 타당 (B등급 진짜 사례) | 1 | 2 | 73480 |
| 8 | B | The Art of Being Difficult: Combining Human and  | 예 | 1d_collaboration/unverified | claimed | ✅ 타당 (B등급 진짜 사례) | 1 | 3 | 72667 |
| 9 | B | Sharing AI progress in mathematics | 예 | 1a_standalone/unverified | claimed | ⚠️ 부분 | 1 | 6 | 74478 |

### 채점 메모

- **0** 기대: 1b_alongside_literature/full (wiki) · 답: 1b_alongside_literature/full
- **1** 기대: 1c_building_on_literature/full (wiki) · 답: 2b_formalization/full
- **2** 기대: AI 기여 없음 (wiki-absent)
- **3** 기대: AI 기여 없음 (wiki-absent)
- **4** 기대: 1b_alongside_literature/full (wiki) · 답: 1a_standalone/full
- **5** 다문제 논문을 한 기록으로 정리하고 13개 문제 번호, 저자 스스로 밝힌 오류율(200건 중 137건 오류), 표절 위험까지 포착. 문제별로 1a/2a가 섞여 있어 단일 구분값(1c)은 거칠다 → 다문제 후보는 문제별 하위 기록이 필요
- **6** 에르되시 외 사례. 1d·부분 결과로 적절. 단, ICML 포스터 목록만 보고 동료심사를 참으로 둔 것은 추론 — 판정 규칙을 'DOI 또는 공식 채택 목록'으로 명시해야 함
- **7** AlphaEvolve 패턴 발견 + 사람 증명의 협업으로 정확히 분류. B등급에서 진짜 사례가 나왔으므로 B등급도 분류 단계를 거쳐야 함
- **8** FunSearch 기반 하한 개선을 1d·미검증으로 분류. 에르되시와 무관한 이론전산 사례
- **9** OpenAI 10월 발표를 '미검증 주장'으로 올바르게 분류하고 철회 3건·수정 14건까지 포착. 다만 GitHub 레포를 열지 못해 수치를 2차 출처에 의존. 이런 대량 공개는 레포 구조를 직접 읽는 전용 수집기로 처리해야 함

### 실측 비용

- 건당 평균: 검색 1.5회, 열람 3.7회, 토큰 약 73k
- 건당 비용 추정: **약 $0.21** (Sonnet 5.5 단가, 토큰의 92%를 입력으로 가정)
- 측정된 토큰에는 이 작업 환경의 에이전트 기본 컨텍스트가 포함돼 있어, 지침만 넣는 운영용 호출에서는 더 작아질 가능성이 높습니다.

## 종합

- **AI 기여 여부: 10/10 정확.** AI 무관 대조군 2건(#570 인간 논문, #834)도 올바르게 걸러냄.
- **정답지 구분까지 일치: 1/3** (#281). 나머지 2건은 판단이 갈리는 경계 사례:
  - #224 — 위키는 "문헌 위에 쌓은 AI 결과(1c)", 에이전트는 "1962년 증명의 Lean 형식화(2b)". 포럼 근거상 에이전트 해석도 성립.
  - #728 — 위키는 "기존 문헌과 겹침(1b)", 에이전트는 "단독 해결(1a)". 논문 자체가 '자율 해결'을 주장하고, 이후 발견된 선행 문헌을 에이전트가 찾지 못함.
  - → 세부 구분은 **사람 검수 대상**으로 두고, 자동 판정은 "AI 기여 여부 + 상태 신호"까지만 신뢰하는 게 맞음.
- **B등급에서 진짜 사례 3건**(AlphaEvolve, FunSearch, OpenAI 발표) → B등급을 버리면 안 되고, 저가 분류를 반드시 거쳐야 함.

## 이 환경의 한계 (운영에서 다시 재야 함)

- 이 작업 공간의 웹 열람 허용 목록 때문에 erdosproblems.com 문제 페이지, github.com, arxiv.org/abs 열람이 자주 막혔음. 그래서 #281은 2차 보도에 의존했고, #834는 근거 없이 '미확인'으로 끝남.
- 운영(API 호출)에서는 열람 가능 범위가 다르므로, 정확도와 비용 모두 운영 환경에서 소수 건으로 재측정 필요.

## 설계 변경 사항

1. **대량 공개 전용 수집기**: OpenAI `openai/math` 같은 구조화된 레포는 LLM 없이 직접 읽어 주장 단위로 기록(Lean 파일 유무로 상태 자동 판정).
2. **다문제 후보는 문제별 하위 기록**으로 쪼갬.
3. **동료심사 판정 규칙 명시**: DOI 또는 학회 공식 채택 목록이 있을 때만 참.
4. **랩 공식 발표는 A등급**으로 승격(적용 완료).

