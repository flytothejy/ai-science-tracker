"""Topic-level collection: gather everything that might change a topic's state.

  python -m tracker.topics --since 2026-10-01 --until 2026-10-24 [--topic solid-state-battery]

For each topics/<id>.yaml:
  - arXiv: the topic's query over submittedDate
  - Google News RSS: each news query, split into weekly windows (the feed caps at 100 items)
  - topic feeds (lab blogs etc.), kept only if they mention the topic

Writes data/topics/<id>/candidates_<since>_<until>.jsonl and a run log.
"""
import argparse
import glob
import html
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, timedelta, datetime, timezone
from email.utils import parsedate_to_datetime

import yaml

from .http import SourceLog, fetch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARXIV = "https://export.arxiv.org/api/query"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
TAG_RE = re.compile(r"<[^>]+>")


def _clean(s):
    return " ".join(html.unescape(TAG_RE.sub(" ", s or "")).split())


def load_topics(only=None):
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "topics", "*.yaml"))):
        t = yaml.safe_load(open(p))
        if not only or t["id"] in only:
            out.append(t)
    return out


def arxiv(topic, since, until, log, page_size=200, max_pages=5):
    q = topic["sources"].get("arxiv_query")
    if not q:
        return []
    full = f"({q}) AND submittedDate:[{since.replace('-', '')}0000 TO {until.replace('-', '')}2359]"
    out = []
    for page in range(max_pages):
        params = {"search_query": full, "start": page * page_size, "max_results": page_size,
                  "sortBy": "submittedDate", "sortOrder": "ascending"}
        body = fetch(ARXIV + "?" + urllib.parse.urlencode(params), log, backoff=10)
        time.sleep(3.5)
        if body is None:
            break
        entries = ET.fromstring(body).findall("a:entry", ATOM)
        for e in entries:
            log.items_seen += 1
            out.append({
                "id": "arxiv:" + e.findtext("a:id", "", ATOM).rsplit("/", 1)[-1],
                "source": "arxiv",
                "title": _clean(e.findtext("a:title", "", ATOM)),
                "url": e.findtext("a:id", "", ATOM),
                "date": (e.findtext("a:published", "", ATOM) or "")[:10],
                "summary": _clean(e.findtext("a:summary", "", ATOM))[:1500],
            })
        if len(entries) < page_size:
            break
    return out


def _weeks(since, until):
    s, u = date.fromisoformat(since), date.fromisoformat(until)
    while s <= u:
        e = min(s + timedelta(days=6), u)
        yield s, e
        s = e + timedelta(days=1)


def google_news(topic, since, until, log):
    out = []
    for q in topic["sources"].get("news_queries", []):
        korean = bool(re.search(r"[가-힣]", q))
        loc = "hl=ko&gl=KR&ceid=KR:ko" if korean else "hl=en-US&gl=US&ceid=US:en"
        for s, e in _weeks(since, until):
            # Google's before: is exclusive
            term = f"{q} after:{s.isoformat()} before:{(e + timedelta(days=1)).isoformat()}"
            url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(term) + "&" + loc
            body = fetch(url, log, headers={"User-Agent": "Mozilla/5.0"})
            time.sleep(1)
            if body is None:
                continue
            items = ET.fromstring(body).findall(".//item")
            if len(items) >= 100:
                log.notes.append(f"cap hit: '{q}' {s}..{e}")
            for it in items:
                log.items_seen += 1
                try:
                    d = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
                except Exception:
                    d = None
                out.append({
                    "id": "gnews:" + (it.findtext("guid") or it.findtext("link")),
                    "source": "news",
                    "outlet": it.findtext("source") or "",
                    "query": q,
                    "title": _clean(it.findtext("title")),
                    "url": it.findtext("link"),
                    "date": d,
                    "summary": _clean(it.findtext("description"))[:500],
                })
    return out


def feeds(topic, since, until, log):
    kw = [w.lower() for q in topic["sources"].get("news_queries", []) for w in [q.split()[0]]]
    names = [topic["name_ko"]] + [p.lower() for p in topic.get("players_watch", [])][:0]
    out = []
    for url in topic["sources"].get("feeds", []):
        body = fetch(url, log, retries=1)
        if body is None:
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            log.failures.append(f"parse error {url}: {e}")
            continue
        for it in root.iter("item"):
            log.items_seen += 1
            try:
                d = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
            except Exception:
                continue
            if not (since <= d <= until):
                continue
            text = _clean(it.findtext("title")) + " " + _clean(it.findtext("description"))
            if not any(k in text.lower() for k in kw) and topic["id"] != "ai-math":
                continue
            out.append({"id": f"feed:{it.findtext('link')}", "source": "feed", "title": _clean(it.findtext("title")),
                        "url": it.findtext("link"), "date": d, "summary": text[:1500]})
    return out


def run(since, until, only=None):
    summary = {"since": since, "until": until,
               "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "environment": "github-actions" if os.environ.get("GITHUB_ACTIONS") else "local",
               "topics": {}}
    for t in load_topics(only):
        cands, logs = [], []
        for name, fn in (("arxiv", arxiv), ("news", google_news), ("feeds", feeds)):
            log = SourceLog(f"{t['id']}:{name}")
            try:
                cands.extend(fn(t, since, until, log))
            except Exception as e:
                log.failures.append(f"crash: {type(e).__name__}: {e}")
            logs.append(log.to_dict())
        seen, uniq = set(), []
        for c in cands:
            key = c["id"]
            if key in seen:
                continue
            seen.add(key)
            uniq.append(c)
        for lg in logs:
            lg["candidates"] = sum(1 for c in uniq if lg["source"].endswith(c["source"]) or
                                   (c["source"] == "feed" and lg["source"].endswith("feeds")))
        d = os.path.join(ROOT, "data", "topics", t["id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"candidates_{since}_{until}.jsonl"), "w") as f:
            for c in sorted(uniq, key=lambda c: c.get("date") or ""):
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        summary["topics"][t["id"]] = {"candidates": len(uniq), "sources": logs}
        print(f"[{t['id']}] {len(uniq)} candidates; " +
              "; ".join(f"{l['source'].split(':')[1]} seen={l['items_seen']} ok={l['ok']} {l['failures'][:1]}"
                        for l in logs), flush=True)
    os.makedirs(os.path.join(ROOT, "data", "topics"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "topics", f"run_{since}_{until}.json"), "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--topic", nargs="*")
    a = ap.parse_args()
    run(a.since, a.until, a.topic)


if __name__ == "__main__":
    main()
