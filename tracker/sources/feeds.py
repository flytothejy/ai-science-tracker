"""RSS/Atom collectors for lab blogs, science media and expert blogs.

Most of these feeds only expose recent items, so they cannot be backfilled —
the run log records how far back each feed actually reached, which tells us
which sources must be captured daily to avoid missing events.
"""
import html
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from ..http import fetch
from ..keywords import is_candidate, erdos_numbers

FEEDS = {
    "openai_news": {"url": "https://openai.com/news/rss.xml", "backfill": None},
    "deepmind_blog": {"url": "https://deepmind.google/blog/rss.xml", "backfill": None},
    "quanta": {"url": "https://www.quantamagazine.org/feed/", "backfill": "paged"},
    # WordPress month-archive feeds allow true backfill
    "tao_blog": {"url": "https://terrytao.wordpress.com/feed/",
                 "backfill": "month", "month_url": "https://terrytao.wordpress.com/{y}/{m:02d}/feed/"},
}

TAG_RE = re.compile(r"<[^>]+>")
NS = {"atom": "http://www.w3.org/2005/Atom", "content": "http://purl.org/rss/1.0/modules/content/"}


def _text(s):
    return " ".join(html.unescape(TAG_RE.sub(" ", s or "")).split())


def _parse_date(s):
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).date()
    except Exception:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None


def _items(body):
    root = ET.fromstring(body)
    for it in root.iter("item"):
        yield {
            "title": _text(it.findtext("title")),
            "link": (it.findtext("link") or "").strip(),
            "date": _parse_date(it.findtext("pubDate")),
            "text": _text(it.findtext("content:encoded", "", NS) or it.findtext("description")),
        }
    for it in root.iter("{http://www.w3.org/2005/Atom}entry"):
        link = it.find("atom:link", NS)
        yield {
            "title": _text(it.findtext("atom:title", "", NS)),
            "link": link.get("href") if link is not None else "",
            "date": _parse_date(it.findtext("atom:published", "", NS) or it.findtext("atom:updated", "", NS)),
            "text": _text(it.findtext("atom:content", "", NS) or it.findtext("atom:summary", "", NS)),
        }


def _months(since, until):
    y, m = since.year, since.month
    while (y, m) <= (until.year, until.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def _urls(cfg, since, until):
    if cfg["backfill"] == "month":
        for y, m in _months(since, until):
            yield cfg["month_url"].format(y=y, m=m)
            for p in range(2, 6):
                yield cfg["month_url"].format(y=y, m=m) + f"?paged={p}"
    elif cfg["backfill"] == "paged":
        yield cfg["url"]
        for p in range(2, 120):
            yield cfg["url"] + f"?paged={p}"
    else:
        yield cfg["url"]


def collect_one(name, since_s, until_s, log):
    cfg = FEEDS[name]
    since, until = date.fromisoformat(since_s), date.fromisoformat(until_s)
    out, oldest, seen_links = [], None, set()
    for url in _urls(cfg, since, until):
        body = fetch(url, log, retries=1)
        if body is None:
            if "paged=" in url:  # running past the last page is normal
                log.failures = [f for f in log.failures if "paged=" not in f]
                break
            continue
        try:
            items = list(_items(body))
        except ET.ParseError as e:
            log.failures.append(f"parse error {url}: {e}")
            break
        if not items:
            break
        page_oldest = None
        for it in items:
            if it["link"] in seen_links:
                continue
            seen_links.add(it["link"])
            log.items_seen += 1
            d = it["date"]
            if d:
                oldest = d if oldest is None or d < oldest else oldest
                page_oldest = d if page_oldest is None or d < page_oldest else page_oldest
            if d is None or not (since <= d <= until):
                continue
            full = f"{it['title']}. {it['text']}"
            ok, ai, math = is_candidate(full)
            if not ok:
                continue
            out.append({
                "id": f"{name}:{it['link']}",
                "source": name,
                "title": it["title"],
                "url": it["link"],
                "date": d.isoformat(),
                "summary": it["text"][:1500],
                "ai_terms": ai,
                "math_terms": math,
                "erdos_numbers": erdos_numbers(full),
            })
        if cfg["backfill"] == "paged" and page_oldest and page_oldest < since:
            break
    reach = oldest.isoformat() if oldest else "none"
    log.notes.append(f"oldest item reached: {reach}")
    if oldest is None or (cfg["backfill"] != "month" and oldest > since):
        log.notes.append(f"BACKFILL GAP: feed does not reach back to {since_s}")
    log.candidates = len(out)
    return out
