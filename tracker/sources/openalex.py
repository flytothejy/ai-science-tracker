"""OpenAlex collector (journals + preprints, supports backfill by publication date)."""
import os
import time
import urllib.parse

import json

from ..http import fetch
from ..keywords import is_candidate, erdos_numbers

API = "https://api.openalex.org/works"
SEARCH = ('"large language model" OR "language model" OR LLM OR GPT OR ChatGPT OR Gemini '
          'OR AlphaProof OR AlphaEvolve OR "artificial intelligence" OR autoformalization')
MATH_FIELD = "26"  # OpenAlex field: Mathematics


def _abstract(inv):
    if not inv:
        return ""
    pos = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    return " ".join(w for _, w in sorted(pos))


def collect(since, until, log, max_pages=10):
    out = []
    cursor = "*"
    mailto = os.environ.get("OPENALEX_MAILTO", "")
    for _ in range(max_pages):
        params = {
            "filter": f"from_publication_date:{since},to_publication_date:{until},"
                      f"primary_topic.field.id:{MATH_FIELD}",
            "search": SEARCH,
            "per-page": 200,
            "cursor": cursor,
            "select": "id,doi,title,publication_date,abstract_inverted_index,primary_location,type",
        }
        if mailto:
            params["mailto"] = mailto
        body = fetch(API + "?" + urllib.parse.urlencode(params), log, backoff=10)
        time.sleep(1)
        if body is None:
            break
        data = json.loads(body)
        if cursor == "*":
            log.notes.append(f"count={data.get('meta', {}).get('count')}")
        for w in data.get("results", []):
            log.items_seen += 1
            title = w.get("title") or ""
            abstract = _abstract(w.get("abstract_inverted_index"))
            text = f"{title}. {abstract}"
            ok, ai, math = is_candidate(text)
            if not ok:
                continue
            loc = (w.get("primary_location") or {}).get("source") or {}
            out.append({
                "id": "openalex:" + w["id"].rsplit("/", 1)[-1],
                "source": "openalex",
                "title": title,
                "url": w.get("doi") or w["id"],
                "doi": w.get("doi"),
                "venue": loc.get("display_name"),
                "type": w.get("type"),
                "date": w.get("publication_date"),
                "summary": abstract[:1500],
                "ai_terms": ai,
                "math_terms": math,
                "erdos_numbers": erdos_numbers(text),
            })
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
    log.candidates = len(out)
    return out
