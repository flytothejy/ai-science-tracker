# 데이터 모델

서비스는 **수집 → 주기적 구조화 → 구조 기반 응답·알림**으로 돌아간다.
데이터는 네 층으로 나누고, 위층은 반드시 아래층의 ID를 가리킨다.

```
사용자 층      구독 · 관점 · 피드백 · 질문 기록 · 발송 기록        (비공개 DB)
   │ 가리킴
구조화 층      주제 → 상태 버전 → 사건 → 검증 이력                 (Git: store/)
   │ 근거 ID
근거 층        원문 발췌 (사건 판정의 근거)                        (Git: 발췌 / R2: 원문)
   │ 원자료 ID
원자료 층      뉴스 제목·요약, 논문 초록, 피드 항목                 (R2, 시범 중엔 Git)
```

## 원칙

1. **덮어쓰지 않는다.** 원자료와 근거는 추가만 한다. 상태는 새 버전을 쌓고, 사건의 검증 단계는 이력으로 남긴다. "어느 날 우리가 뭐라고 했는가"를 언제든 재현할 수 있어야 한다.
2. **모든 판정은 근거로 이어진다.** 상태 항목 → 사건 → 근거 → 원자료가 ID로 연결된다. 연결이 끊긴 판정은 발행하지 않는다.
3. **검증 단계는 오르내린다.** 철회·반박·선행 문헌 발견은 단계를 내리는 사건이며, 오를 때와 같은 무게로 기록하고 알린다.
4. **사용자 데이터는 공개 저장소에 두지 않는다.** 구조화 층은 공개해도 되지만 사용자 층은 비공개 DB에만 둔다.
5. **원문은 내부용, 화면에는 발췌만.** 저작권 때문에 원문 전체는 비공개 저장소에만 두고, 화면에는 짧은 발췌와 링크만 낸다.

## ID 규칙

| 대상 | 형식 | 예 |
|---|---|---|
| 원자료 | `raw:` + 원본 식별자의 sha1 앞 12자리 | `raw:3f9a1c0b27de` |
| 근거 | `ev:` + URL의 sha1 앞 12자리 | `ev:91b0e2c4aa10` |
| 주제 | 슬러그 | `quantum-computing` |
| 상태 버전 | `<주제>@<기준일>` | `quantum-computing@2026-09-30` |
| 사건 | `<주제>/<YYYY-MM>/<번호>` | `quantum-computing/2026-10/e1` |

원본 식별자(arXiv ID, 기사 GUID 등)는 `source_id`로 함께 보관한다. 같은 원본은 언제 수집해도 같은 ID가 된다.

## 1. 원자료 층 — `raw/<YYYY>/<MM>/<source>.jsonl`

```json
{"id": "raw:3f9a1c0b27de", "source": "news|arxiv|feed", "source_id": "gnews:CBMi...",
 "outlet": "electrive.com", "title": "...", "url": "...", "published": "2026-10-14",
 "collected_at": "2026-10-24T20:43:00Z", "snippet": "최대 1,500자", "topics": ["solid-state-battery"]}
```

- 한 원자료가 여러 주제에 걸칠 수 있다(`topics` 배열).
- 규모: 주제 3개 기준 월 1,500건, 1~2MB.

## 2. 근거 층 — `store/evidence/<YYYY>/<MM>.jsonl` (+ 원문은 R2 `evidence/<id>.txt`)

```json
{"id": "ev:91b0e2c4aa10", "url": "...", "kind": "press_release|paper|preprint|filing|journal_news|news|blog",
 "publisher": "Quantinuum", "published": "2026-10-19", "fetched_at": "...",
 "excerpts": [{"text": "짧은 인용(최대 2문장)", "locator": "섹션·문단 위치"}],
 "fulltext_ref": "r2://evidence/ev:91b0e2c4aa10.txt", "status": "excerpted|url_only|blocked"}
```

- `status`가 `url_only`이면 URL만 있고 발췌가 없는 상태다. 발행 전에 발췌를 채워야 한다.
- `blocked`는 열람 실패. 판정이 2차 보도에 의존했다는 표시가 된다.

## 3. 구조화 층 — `store/topics/<주제>/`

### 주제 정의 — `topics/<주제>.yaml` (기존 그대로)
상태를 무엇으로 정의하는지(지표, 단계, 사건 유형, 검증 단계)를 담는다.

### 상태 버전 — `store/topics/<주제>/state/<기준일>.json`

```json
{"id": "quantum-computing@2026-10-24", "topic": "quantum-computing", "as_of": "2026-10-24",
 "previous": "quantum-computing@2026-09-30", "headline_ko": "...",
 "plain": {"one_line_ko": "...", "why_it_matters_ko": "...", "how_trustworthy_ko": "...",
           "perspectives": {"engineer": "...", "researcher": "...", "investor": "..."}},
 "metrics": [{"id": "logical_error_per_cycle", "value": 5e-6, "unit": "...", "who": "...", "date": "...",
              "level": "...", "verification": "paper_preprint", "event": "quantum-computing/2026-10/e1",
              "evidence": ["ev:..."], "note_ko": "..."}],
 "stages": [{"id": "...", "status": "achieved|claimed|not_yet", "verification": "...",
             "event": null, "evidence": ["ev:..."]}],
 "open_issues": [...], "watch_next_ko": [...],
 "changed_by": ["quantum-computing/2026-10/e1"]}
```

- 기준 상태는 `event` 대신 `evidence`만 가질 수 있다. 이후 버전에서 값이 바뀐 항목은 반드시 바꾼 `event`를 가리킨다.
- `plain`은 타 분야 독자용 쉬운 말 층이다. 관점별 문장은 미리 만들어 두고, 질문 시 생성하지 않는다.

### 사건 — `store/topics/<주제>/events/<YYYY-MM>.jsonl`

```json
{"id": "quantum-computing/2026-10/e1", "topic": "quantum-computing", "date": "2026-10-16",
 "who": "Quantinuum", "type": "record", "title_ko": "...",
 "changes_state": "yes|no|check", "field": "logical_error_per_cycle", "old": "1.43e-3", "new": "5e-6",
 "level": "...", "caveat_ko": "...",
 "verification_history": [{"at": "2026-10-16", "level": "paper_preprint", "evidence": ["ev:..."]}],
 "evidence": ["ev:..."], "raw": ["raw:...", "..."], "coverage": 17}
```

- `verification_history`는 추가만 한다. 마지막 항목이 현재 검증 단계다.
- `coverage`(관련 원자료 수)와 `changes_state`를 함께 보면 "보도량 대비 실제 변화"가 나온다.

### 실행 기록 — `store/runs/<실행ID>.json`
수집·판정 실행마다 소스별 작동 여부, 건수, 비용(토큰·검색 수)을 남긴다(기존 `data/runs`와 같은 역할).

## 4. 사용자 층 — 비공개 DB (예: Cloudflare D1)

```sql
users(id, created_at, channel, channel_ref, perspective, locale)
subscriptions(user_id, topic, created_at, mode)            -- mode: instant | weekly
questions(id, user_id, asked_at, text, matched_topic, outcome)  -- outcome: answered | not_tracked | out_of_scope
topic_requests(topic_text, normalized, count, first_at, last_at)
feedback(user_id, target_id, kind, note, at)               -- kind: interested | not_interested | wrong
deliveries(user_id, event_id, channel, sent_at, status)
```

- `questions`와 `topic_requests`는 다음에 추적할 주제를 정하는 수요 데이터가 된다.
- `feedback.kind = wrong`은 사람 검수 대기열로 들어간다.

## 저장 위치 요약

| 층 | 시범 | 운영 |
|---|---|---|
| 원자료 | Git `raw/` | R2 |
| 근거 발췌 | Git `store/evidence/` | Git |
| 근거 원문 | 저장 안 함 | R2 비공개 |
| 구조화 | Git `store/topics/` | Git (공개 가능, 변경 이력이 곧 감사 기록) |
| 사용자 | 없음 | D1 등 비공개 DB |

## 검사 규칙 (`python -m tracker.store check`)

- 모든 사건의 `raw`가 원자료 층에 존재한다.
- `changes_state = yes`인 사건은 근거가 1개 이상이고, 근거 중 하나는 `excerpted`다.
- 상태 버전의 바뀐 항목은 `changes_state = yes` 사건을 가리킨다.
- 상태 버전의 `previous`가 존재한다.
- 사건의 `verification_history`는 날짜순이다.
