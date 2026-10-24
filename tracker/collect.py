"""Step 1 — collect candidates from all sources for a date window.

  python -m tracker.collect --since 2026-01-01 --until 2026-01-31   # replay
  python -m tracker.collect --daily                                 # yesterday..today, with dedupe

Writes:
  data/candidates/<run_id>.jsonl   candidates that pass the rule filter
  data/runs/<run_id>.json          per-source health (did each step work?)
"""
import argparse
import json
import os
import time
from datetime import date, timedelta, datetime, timezone

from .http import SourceLog
from .keywords import tier
from .sources import arxiv, openalex, feeds, erdos

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def run(since, until, daily=False, only=None, with_openalex=False):
    run_id = f"{since}_{until}" + ("_daily" if daily else "")
    logs, cands = [], []

    def go(name, fn):
        if only and name not in only:
            return
        log = SourceLog(name)
        t0 = time.time()
        try:
            cands.extend(fn(log))
        except Exception as e:
            log.failures.append(f"crash: {type(e).__name__}: {e}")
        d = log.to_dict()
        d["seconds"] = round(time.time() - t0, 1)
        logs.append(d)
        print(f"[{name}] ok={d['ok']} req={d['requests']} codes={d['status_counts']} "
              f"seen={d['items_seen']} cand={d['candidates']} {d['notes']} {d['failures'][:2]}", flush=True)

    go("arxiv", lambda l: arxiv.collect(since, until, l))
    # OpenAlex is mostly noise for detection (and pages past 1 need auth); kept for step 3
    if with_openalex:
        go("openalex", lambda l: openalex.collect(since, until, l))
    for name in feeds.FEEDS:
        go(name, lambda l, n=name: feeds.collect_one(n, since, until, l))
    snap = os.path.join(DATA, "state", "erdos_snapshot.json") if daily else None
    go("erdos_db", lambda l: erdos.collect(since, until, l, snapshot_path=snap))

    # de-duplicate (by id, and across runs in daily mode)
    seen_path = os.path.join(DATA, "state", "seen_ids.txt")
    seen = set()
    if daily and os.path.exists(seen_path):
        with open(seen_path) as f:
            seen = set(x.strip() for x in f)
    uniq, ids = [], set()
    for c in cands:
        if c["id"] in ids or c["id"] in seen:
            continue
        ids.add(c["id"])
        c["tier"] = tier(c)
        uniq.append(c)

    os.makedirs(os.path.join(DATA, "candidates"), exist_ok=True)
    os.makedirs(os.path.join(DATA, "runs"), exist_ok=True)
    with open(os.path.join(DATA, "candidates", f"{run_id}.jsonl"), "w") as f:
        for c in sorted(uniq, key=lambda c: (c.get("date") or "", c["source"])):
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    summary = {
        "run_id": run_id,
        "since": since,
        "until": until,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": "github-actions" if os.environ.get("GITHUB_ACTIONS") else "local",
        "candidates_total": len(uniq),
        "tiers": {t: sum(1 for c in uniq if c["tier"] == t) for t in "SAB"},
        "sources": logs,
    }
    with open(os.path.join(DATA, "runs", f"{run_id}.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if daily:
        os.makedirs(os.path.dirname(seen_path), exist_ok=True)
        with open(seen_path, "a") as f:
            for c in uniq:
                f.write(c["id"] + "\n")
    print(f"total candidates: {len(uniq)} -> data/candidates/{run_id}.jsonl")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--only", nargs="*", help="run only these sources")
    ap.add_argument("--with-openalex", action="store_true")
    a = ap.parse_args()
    if a.daily:
        today = date.today()
        since, until = (today - timedelta(days=1)).isoformat(), today.isoformat()
    else:
        since, until = a.since, a.until
    run(since, until, daily=a.daily, only=a.only, with_openalex=a.with_openalex)


if __name__ == "__main__":
    main()
