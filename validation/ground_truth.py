"""Ground truth from the community 'AI contributions to Erdős problems' wiki.

The wiki was human-curated and froze on 2026-06-30, which makes it a labelled
answer key for replaying any window up to that date.
"""
import json
import os
import re
from datetime import datetime

from tracker.http import SourceLog, fetch

URL = ("https://raw.githubusercontent.com/wiki/teorth/erdosproblems/"
       "AI-contributions-to-Erd%C5%91s-problems.md")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "ground_truth", "erdos_ai_wiki.json")

SECTION_RE = re.compile(r"^###\s+(\d\([a-d]\))\.\s+(.*)$")
NUM_RE = re.compile(r"\[\[(\d{1,4})\]\]")
DATE_RE = re.compile(r"(\d{1,2})\s+([A-Z][a-z]{2}),?\s+(\d{4})")
OUTCOME = {"🟢": "full", "🟡": "partial", "🔴": "incorrect", "⚪": "unverified"}


def _date(cell):
    m = DATE_RE.search(cell or "")
    if not m:
        return None
    try:
        return datetime.strptime(" ".join(m.groups()), "%d %b %Y").date().isoformat()
    except ValueError:
        return None


def parse(md):
    rows, section, header = [], None, None
    for line in md.splitlines():
        sm = SECTION_RE.match(line.strip())
        if sm:
            section, header = sm.group(1), None
            continue
        if not line.startswith("|") or section is None:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "Problem":
            header = cells
            continue
        if header is None or set("".join(cells)) <= set("-: "):
            continue
        nums = NUM_RE.findall(cells[0])
        if not nums:
            continue
        col = {h: (cells[i] if i < len(cells) else "") for i, h in enumerate(header)}
        outcome = next((v for k, v in OUTCOME.items() if k in col.get("Outcome", "")), None)
        for n in nums:
            rows.append({
                "number": int(n),
                "section": section,
                "primary": section.startswith("1"),
                "ai_systems": col.get("AI systems", ""),
                "date": _date(col.get("Date", "")),
                "outcome": outcome,
            })
    return rows


def load(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        with open(CACHE) as f:
            return json.load(f)
    log = SourceLog("ground_truth")
    body = fetch(URL, log)
    if body is None:
        raise RuntimeError(f"ground truth fetch failed: {log.failures}")
    rows = parse(body.decode("utf-8"))
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    return rows


if __name__ == "__main__":
    rows = load(refresh=True)
    from collections import Counter
    print(len(rows), Counter(r["section"] for r in rows))
    print([r for r in rows if r["number"] == 281])
