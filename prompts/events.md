# 변화 감지 지침 (event detection)

You turn one month of raw items for ONE topic into a short list of events, and decide which
events change the topic's state.

Inputs:
- the topic definition `topics/<id>.yaml` (event types, metrics, levels, verification levels)
- the baseline state `topics/<id>/baseline_<asof>.json` (the state before the window)
- the raw items `data/topics/<id>/candidates_<since>_<until>.jsonl` (papers, news, feeds)

## Procedure

1. **Triage.** Drop items that are not about this topic, or are commentary/explainers/
   market reports with no new fact (e.g. "market will grow to $X by 2032", generic
   explainers, opinion pieces, stock tips). Keep items that report a new result,
   announcement, test, delay, rebuttal, or milestone.
2. **Cluster.** Merge items about the same underlying fact (same company + same claim, same
   paper) into one event. Keep the earliest date and all item ids.
3. **Compare with the baseline.** For each event, decide:
   - `changes_state`: `yes` (beats a recorded metric at the same level, reaches a new stage
     or milestone, or a setback/rebuttal that lowers a recorded claim), `no` (consistent with
     what the baseline already says, or below the recorded bests), or `check` (could change
     the state but the facts in the items are not enough).
   - which baseline field it touches, old value → new value.
4. **Verify the `yes` and `check` events.** Open the primary source with WebSearch/WebFetch
   (company release, paper, journal). Set the verification level from the topic file. Never
   upgrade a company announcement to `independent_test` without an independent source.
   Budget: at most 12 searches and 15 fetches in total.
5. **Be honest about hype.** If coverage volume is high but the fact is old or minor, say so.
   If an "advantage" or "record" claim has a known rebuttal or a caveat (lab cell vs product,
   physical vs logical qubits), state the caveat in the event.

## Output

Write `topics/<id>/events_<since>_<until>.json`:

```json
{
  "topic": "<id>", "since": "...", "until": "...",
  "items_total": 0, "items_kept_after_triage": 0, "events_total": 0,
  "events": [
    {"event_id": "e1", "date": "YYYY-MM-DD", "who": "...", "type": "<event type from topic>",
     "title_ko": "한 줄 요약", "changes_state": "yes|no|check",
     "field": "<metric/stage id or null>", "old": "...", "new": "...",
     "level": "...", "verification": "...",
     "caveat_ko": "과장 방지를 위한 단서", "item_ids": ["..."], "item_count": 0,
     "primary_url": "..."}
  ],
  "searches_used": 0, "fetches_used": 0
}
```

and `topics/<id>/digest_<since>_<until>.md`: a Korean digest for a busy engineer —
"이번 달 상태가 바뀐 것" (only `yes` events, each with before → after, verification level and
caveat), "확인 중" (`check` events), "화제였지만 상태는 그대로" (high-coverage `no` events,
with one line on why), and the updated one-paragraph state headline.
