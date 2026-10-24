"""Erdős problem database (teorth/erdosproblems data/problems.yaml).

Two modes:
- window: problems whose status.last_update falls in [since, until] (replay; only the
  latest update per problem survives in the YAML, so older changes can be hidden)
- snapshot diff: compare against the previous run's snapshot (live operation)

The YAML carries no AI attribution (the community AI wiki froze on 2026-06-30),
so these events are status signals only; linking them to AI is step 2's job.
"""
import json
import os

import yaml

from ..http import fetch

URL = "https://raw.githubusercontent.com/teorth/erdosproblems/main/data/problems.yaml"
SOLVED = ("proved", "disproved", "solved")


def load(log):
    body = fetch(URL, log)
    if body is None:
        return None
    return yaml.safe_load(body)


def _norm(p):
    st = p.get("status") or {}
    fs = p.get("formal_status") or {}
    return {
        "number": int(str(p.get("number"))),
        "status": st.get("state"),
        "status_updated": str(st.get("last_update") or ""),
        "formal": fs.get("state"),
        "formal_updated": str(fs.get("last_update") or ""),
        "tags": p.get("tags") or [],
    }


STATS_URL = "https://raw.githubusercontent.com/teorth/erdosproblems/main/data/statistics_history.csv"
RAW_AT = "https://raw.githubusercontent.com/teorth/erdosproblems/{sha}/data/problems.yaml"


def _commit_at(rows, day):
    """Last commit on or before `day` (YYYY-MM-DD) from statistics_history.csv."""
    best = None
    for sha, d in rows:
        if d[:10] <= day:
            best = sha
    return best


def replay_diff(since, until, log):
    """True replay: diff the database at the commit before `since` vs the commit at `until`."""
    body = fetch(STATS_URL, log)
    if body is None:
        return None
    rows = []
    for line in body.decode().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) > 2:
            rows.append((parts[0], parts[1]))
    prev_day = (__import__("datetime").date.fromisoformat(since)
                - __import__("datetime").timedelta(days=1)).isoformat()
    a, b = _commit_at(rows, prev_day), _commit_at(rows, until)
    if not a or not b:
        log.notes.append("replay: no commit before window; falling back to last_update")
        return None
    old_body, new_body = fetch(RAW_AT.format(sha=a), log), fetch(RAW_AT.format(sha=b), log)
    if old_body is None or new_body is None:
        return None
    old = {q["number"]: q for q in (_norm(p) for p in yaml.safe_load(old_body))}
    new = [_norm(p) for p in yaml.safe_load(new_body)]
    log.notes.append(f"replay diff {a[:7]}→{b[:7]}")
    out = [ev for p in new if (ev := _transition(old.get(p["number"]), p))]
    return out, len(new)


def _solved(state):
    return bool(state) and state.split()[0] in SOLVED


def _transition(o, p):
    """Only transitions that matter: became solved, or gained a Lean formal proof.
    New problems and other edits (tags, OEIS, wording) are ignored."""
    if o is None:
        return None
    kind = None
    if _solved(p["status"]) and not _solved(o["status"]):
        kind = "became_solved"
    elif p["formal"] == "Lean" and o["formal"] != "Lean":
        kind = "lean_verified"
    if not kind:
        return None
    ev = _event(p, kind)
    ev["previous"] = {"status": o["status"], "formal": o["formal"]}
    return ev


def collect(since, until, log, snapshot_path=None):
    out = []
    if not snapshot_path:
        res = replay_diff(since, until, log)
        if res is not None:
            out, log.items_seen = res
            log.candidates = len(out)
            return out
    data = load(log)
    if data is None:
        return []
    probs = [_norm(p) for p in data]
    log.items_seen = len(probs)
    if not snapshot_path:
        for p in probs:
            if since <= p["status_updated"] <= until and p["status"] and p["status"].split()[0] in SOLVED:
                out.append(_event(p, "status_in_window"))
    if snapshot_path:
        prev = {}
        if os.path.exists(snapshot_path):
            with open(snapshot_path) as f:
                prev = {int(k): v for k, v in json.load(f).items()}
        if prev:
            for p in probs:
                ev = _transition(prev.get(p["number"]), p)
                if ev:
                    out.append(ev)
        else:
            log.notes.append("no previous snapshot; diff starts next run")
        os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
        with open(snapshot_path, "w") as f:
            json.dump({p["number"]: p for p in probs}, f, ensure_ascii=False)
    log.candidates = len(out)
    return out


def _event(p, kind):
    return {
        "id": f"erdos:{p['number']}:{kind}:{p['status_updated']}",
        "source": "erdos_db",
        "kind": kind,
        "title": f"Erdős problem #{p['number']} → {p['status']}",
        "url": f"https://www.erdosproblems.com/{p['number']}",
        "date": p["status_updated"],
        "status": p["status"],
        "formal": p["formal"],
        "formal_updated": p["formal_updated"],
        "erdos_numbers": [p["number"]],
        "ai_terms": [],
    }
