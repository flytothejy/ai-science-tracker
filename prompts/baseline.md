# 기준 상태(베이스라인) 조사 지침

You build the baseline "state page" for ONE technology/problem topic, as of a given date.
The topic definition (what counts as state, metrics, milestones, event types, players) is in
`topics/<id>.yaml`. Read it first and fill the state it defines.

## Rules

- **As-of date is strict.** Describe the state exactly as it stood on the as-of date.
  Do not use or mention anything that happened after it, even if you find it.
  When a source is dated later, use it only to learn about earlier events, and cite the
  original earlier source if you can.
- Prefer primary sources: company press releases and technical papers, peer-reviewed
  journals, arXiv, and reputable science/industry press (Nature News, Science, IEEE
  Spectrum, Quanta, C&EN, Electrek, The Elec, etc.).
- Every number and every milestone needs: the value, who, when, cell/platform level (as
  the topic defines), verification level, and a URL you actually opened.
- Separate claims from verified results. A company announcement is `company_claim` until
  something independent exists.
- If you could not confirm something, leave it out or mark it `unconfirmed` — never guess.
- Budget: about 15 searches and 20 fetches.

## Output

Write two files under `topics/<id>/`:

1. `baseline_<asof>.json`:
```json
{
  "topic": "<id>",
  "as_of": "YYYY-MM-DD",
  "headline_ko": "한 문장 현재 상태",
  "metrics": [{"id": "...", "value": 0, "unit": "...", "who": "...", "date": "YYYY-MM-DD",
               "level": "...", "verification": "...", "url": "...", "note_ko": "..."}],
  "milestones_or_stages": [{"id": "...", "who": "...", "date": "...", "status": "achieved|claimed|not_yet",
                            "verification": "...", "url": "...", "note_ko": "..."}],
  "open_issues": [{"issue_ko": "...", "status_ko": "...", "url": "..."}],
  "watch_next_ko": ["다음에 상태를 바꿀 만한 예정 사건"],
  "searches_used": 0, "fetches_used": 0
}
```
2. `baseline_<asof>.md`: the same content as a Korean state page a non-specialist engineer can
   read in 3 minutes — headline, a table of current records/stages with verification level,
   open issues, what to watch next, and sources.
