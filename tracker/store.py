"""Data store: migrate pilot outputs into the layered model (docs/data-model.md) and check it.

  python -m tracker.store migrate     # pilot files -> raw/ and store/
  python -m tracker.store check       # integrity rules -> reports/store_check.md
"""
import argparse
import glob
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
STORE = os.path.join(ROOT, "store")


def h(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def raw_id(source_id):
    return "raw:" + h(source_id)


def ev_id(url):
    return "ev:" + h(url.strip())


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _read_jsonl(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


KIND_BY_HOST = [
    (r"arxiv\.org", "preprint"),
    (r"sec\.gov", "filing"),
    (r"(nature|science|cell|aps|acs|wiley|springer|sciencedirect|iop)\.", "journal"),
    (r"news\.google\.com", "news"),
    (r"wordpress\.com|blog", "blog"),
    (r"wikipedia\.org", "encyclopedia"),
]


def _kind(url):
    host = urlparse(url).netloc.lower()
    for pat, kind in KIND_BY_HOST:
        if re.search(pat, host):
            return kind
    return "web"


def normalize_field(field):
    """Map free-form field names from the pilot ("milestones_or_stages.x / note") to a state item id."""
    if not field:
        return None
    f = field.split("/")[0].strip()
    for prefix in ("milestones_or_stages.", "milestones.", "stages.", "metrics."):
        if f.startswith(prefix):
            f = f[len(prefix):]
    return f.strip()


def _source_of(old_id, source):
    if source in ("arxiv", "news", "feed"):
        return source
    return "feed" if old_id.startswith("feed:") else source


# ---------------------------------------------------------------------------
# migrate
# ---------------------------------------------------------------------------

def migrate():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_by_id, old_to_raw = {}, {}

    # 1. raw layer from topic candidates
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "topics", "*", "candidates_*.jsonl"))):
        topic = path.split(os.sep)[-2]
        for c in _read_jsonl(path):
            rid = raw_id(c["id"])
            old_to_raw[(topic, c["id"])] = rid
            if rid in raw_by_id:
                if topic not in raw_by_id[rid]["topics"]:
                    raw_by_id[rid]["topics"].append(topic)
                continue
            raw_by_id[rid] = {
                "id": rid, "source": _source_of(c["id"], c.get("source")), "source_id": c["id"],
                "outlet": c.get("outlet") or c.get("venue") or "", "title": c.get("title", ""),
                "url": c.get("url", ""), "published": c.get("date"), "collected_at": now,
                "snippet": (c.get("summary") or "")[:1500], "topics": [topic],
            }
    buckets = defaultdict(list)
    for r in raw_by_id.values():
        ym = (r["published"] or "unknown")[:7].replace("-", "/") if r["published"] else "unknown"
        buckets[(ym, r["source"])].append(r)
    for (ym, source), rows in buckets.items():
        _write_jsonl(os.path.join(RAW, ym, f"{source}.jsonl"), sorted(rows, key=lambda r: r["published"] or ""))

    evidence = {}

    def add_ev(url, published=None, publisher=None):
        if not url or not url.startswith("http"):
            return None
        eid = ev_id(url)
        if eid not in evidence:
            evidence[eid] = {"id": eid, "url": url, "kind": _kind(url), "publisher": publisher or urlparse(url).netloc,
                             "published": published, "fetched_at": None, "excerpts": [],
                             "fulltext_ref": None, "status": "url_only"}
        return eid

    unapplied = []
    for ypath in sorted(glob.glob(os.path.join(ROOT, "topics", "*.yaml"))):
        topic = os.path.basename(ypath)[:-5]
        tdir = os.path.join(ROOT, "topics", topic)
        base_p = os.path.join(tdir, "baseline_2026-09-30.json")
        if not os.path.exists(base_p):
            continue
        base = json.load(open(base_p))

        # 2. baseline state
        def conv_metric(m):
            return {"id": m["id"], "value": m.get("value"), "unit": m.get("unit"), "who": m.get("who"),
                    "date": m.get("date"), "level": m.get("level"), "verification": m.get("verification"),
                    "event": None, "evidence": [e for e in [add_ev(m.get("url", ""), m.get("date"))] if e],
                    "note_ko": m.get("note_ko")}

        def conv_stage(s):
            return {"id": s["id"], "who": s.get("who"), "date": s.get("date"), "status": s.get("status"),
                    "verification": s.get("verification"), "event": None,
                    "evidence": [e for e in [add_ev(s.get("url", ""), s.get("date"))] if e],
                    "note_ko": s.get("note_ko")}

        state0 = {
            "id": f"{topic}@{base['as_of']}", "topic": topic, "as_of": base["as_of"], "previous": None,
            "headline_ko": base.get("headline_ko"),
            "plain": {"one_line_ko": None, "why_it_matters_ko": None, "how_trustworthy_ko": None, "perspectives": {}},
            "metrics": [conv_metric(m) for m in base.get("metrics", [])],
            "stages": [conv_stage(s) for s in base.get("milestones_or_stages", [])],
            "open_issues": [{"issue_ko": o.get("issue_ko"), "status_ko": o.get("status_ko"),
                             "evidence": [e for e in [add_ev(o.get("url", ""))] if e]} for o in base.get("open_issues", [])],
            "watch_next_ko": base.get("watch_next_ko", []),
            "changed_by": [],
        }
        _write_json(os.path.join(STORE, "topics", topic, "state", f"{base['as_of']}.json"), state0)

        # 3. events
        for epath in sorted(glob.glob(os.path.join(tdir, "events_*.json"))):
            ev_file = json.load(open(epath))
            since, until = ev_file["since"], ev_file["until"]
            month = since[:7]
            events = []
            for e in ev_file["events"]:
                eid = f"{topic}/{month}/{e['event_id']}"
                evs = [x for x in [add_ev(e.get("primary_url", ""), e.get("date"))] if x]
                raws = [old_to_raw[(topic, i)] for i in e.get("item_ids", []) if (topic, i) in old_to_raw]
                events.append({
                    "id": eid, "topic": topic, "date": e.get("date"), "who": e.get("who"), "type": e.get("type"),
                    "title_ko": e.get("title_ko"), "changes_state": e.get("changes_state"),
                    "field": e.get("field"), "old": e.get("old"), "new": e.get("new"), "level": e.get("level"),
                    "caveat_ko": e.get("caveat_ko"),
                    "verification_history": [{"at": e.get("date"), "level": e.get("verification"), "evidence": evs}],
                    "evidence": evs, "raw": raws, "coverage": e.get("item_count") or len(raws),
                })
            _write_jsonl(os.path.join(STORE, "topics", topic, "events", f"{month}.jsonl"), events)

            # 4. next state version = baseline + applied "yes" events
            state1 = json.loads(json.dumps(state0))
            state1["id"] = f"{topic}@{until}"
            state1["as_of"] = until
            state1["previous"] = state0["id"]
            digest_p = os.path.join(tdir, f"digest_{since}_{until}.md")
            state1["headline_ko"] = state0["headline_ko"]
            for e in events:
                if e["changes_state"] != "yes":
                    continue
                state1["changed_by"].append(e["id"])
                field = normalize_field(e["field"])
                target = None
                for coll in ("metrics", "stages"):
                    for item in state1[coll]:
                        if field and item["id"] == field:
                            target = (coll, item)
                if target is None:
                    unapplied.append({"event": e["id"], "field": e["field"], "reason": "field not in baseline"})
                    continue
                coll, item = target
                if coll == "metrics":
                    item["value"] = e["new"]
                else:
                    item["note_ko"] = e["new"]
                    if item.get("status") == "not_yet":
                        item["status"] = "claimed"
                item.update({"date": e["date"], "who": e["who"], "verification": e["verification_history"][-1]["level"],
                             "event": e["id"], "evidence": e["evidence"]})
            _write_json(os.path.join(STORE, "topics", topic, "state", f"{until}.json"), state1)

    ev_buckets = defaultdict(list)
    for ev in evidence.values():
        ev_buckets[(ev["published"] or "unknown")[:7]].append(ev)
    for ym, rows in ev_buckets.items():
        _write_jsonl(os.path.join(STORE, "evidence", f"{ym.replace('-', '/')}.jsonl"), rows)
    _write_json(os.path.join(STORE, "migration_notes.json"), {"migrated_at": now, "unapplied_events": unapplied})
    print(f"raw={len(raw_by_id)} evidence={len(evidence)} unapplied={len(unapplied)}")


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def check():
    raw_ids = {r["id"] for p in glob.glob(os.path.join(RAW, "**", "*.jsonl"), recursive=True) for r in _read_jsonl(p)}
    evidence = {e["id"]: e for p in glob.glob(os.path.join(STORE, "evidence", "**", "*.jsonl"), recursive=True)
                for e in _read_jsonl(p)}
    issues = defaultdict(list)
    stats = defaultdict(lambda: defaultdict(int))
    for tdir in sorted(glob.glob(os.path.join(STORE, "topics", "*"))):
        topic = os.path.basename(tdir)
        events = {e["id"]: e for p in glob.glob(os.path.join(tdir, "events", "*.jsonl")) for e in _read_jsonl(p)}
        st = stats[topic]
        st["events"] = len(events)
        for e in events.values():
            missing = [r for r in e["raw"] if r not in raw_ids]
            if missing:
                issues[topic].append(f"{e['id']}: 원자료 {len(missing)}건 없음")
            dates = [v["at"] for v in e["verification_history"]]
            if dates != sorted(dates):
                issues[topic].append(f"{e['id']}: 검증 이력 날짜 순서 오류")
            if e["changes_state"] == "yes":
                st["yes"] += 1
                if not e["evidence"]:
                    issues[topic].append(f"{e['id']}: 상태 변화 사건에 근거 없음")
                elif not any(evidence.get(x, {}).get("status") == "excerpted" for x in e["evidence"]):
                    st["yes_without_excerpt"] += 1
        for sp in sorted(glob.glob(os.path.join(tdir, "state", "*.json"))):
            s = json.load(open(sp))
            st["state_versions"] += 1
            if s["previous"] and not os.path.exists(os.path.join(tdir, "state", s["previous"].split("@")[1] + ".json")):
                issues[topic].append(f"{s['id']}: 이전 버전 {s['previous']} 없음")
            for coll in ("metrics", "stages"):
                for item in s[coll]:
                    if not item["evidence"]:
                        st["items_without_evidence"] += 1
                    if item.get("event") and events.get(item["event"], {}).get("changes_state") != "yes":
                        issues[topic].append(f"{s['id']}: {item['id']}가 상태 변화 사건이 아닌 {item['event']}를 가리킴")
            if not (s.get("plain") or {}).get("one_line_ko"):
                st["plain_missing"] += 1
    notes_p = os.path.join(STORE, "migration_notes.json")
    unapplied = json.load(open(notes_p)).get("unapplied_events", []) if os.path.exists(notes_p) else []
    ev_status = defaultdict(int)
    for e in evidence.values():
        ev_status[e["status"]] += 1

    L = ["# 저장소 무결성 검사\n",
         f"- 원자료 {len(raw_ids)}건 · 근거 {len(evidence)}건 (" +
         ", ".join(f"{k} {v}" for k, v in sorted(ev_status.items())) + ")\n",
         "| 주제 | 사건 | 상태 변화 | 발췌 없는 상태 변화 | 상태 버전 | 근거 없는 상태 항목 | 쉬운 말 층 비어 있음 |",
         "|---|---|---|---|---|---|---|"]
    for topic, st in stats.items():
        L.append(f"| {topic} | {st['events']} | {st['yes']} | {st['yes_without_excerpt']} | {st['state_versions']} | "
                 f"{st['items_without_evidence']} | {st['plain_missing']}/{st['state_versions']} |")
    L.append("\n## 연결 오류\n")
    any_issue = False
    for topic, lst in issues.items():
        for i in lst:
            L.append(f"- {topic}: {i}")
            any_issue = True
    if not any_issue:
        L.append("- 없음")
    L.append("\n## 상태에 반영되지 못한 상태 변화 사건\n")
    if unapplied:
        for u in unapplied:
            L.append(f"- `{u['event']}` — 항목 `{u['field']}`: {u['reason']}")
    else:
        L.append("- 없음")
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    out = os.path.join(ROOT, "reports", "store_check.md")
    open(out, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["migrate", "check"])
    a = ap.parse_args()
    migrate() if a.cmd == "migrate" else check()


if __name__ == "__main__":
    main()
