"""arXiv API collector (infrastructure-grade, supports backfill by submittedDate)."""
import time
import urllib.parse
import xml.etree.ElementTree as ET

from ..http import fetch
from ..keywords import is_candidate, erdos_numbers

API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}

MATH_CATS = ["math.CO", "math.NT", "math.MG", "math.PR", "math.LO", "math.GM", "math.HO",
             "math.CA", "math.GR", "math.AG", "math.AC", "math.DS", "math.FA", "math.GT",
             "math.LA", "math.OC", "math.RT", "math.ST", "math.MP", "math.CV", "math.SP"]
AI_TERMS = ['"large language model"', '"language model"', "LLM", "GPT", "ChatGPT", "Gemini",
            "AlphaProof", "AlphaEvolve", "Aristotle", '"artificial intelligence"',
            '"AI-assisted"', '"AI-generated"', "autoformalization", '"reasoning model"']
DISCOVERY_TERMS = ["Erdos", '"open problem"', "conjecture", '"Erdős"', "counterexample",
                   '"theorem proving"', "Lean"]

QUERIES = {
    # math papers that mention AI systems
    "math_x_ai": "({}) AND ({})".format(
        " OR ".join(f"cat:{c}" for c in MATH_CATS),
        " OR ".join(f"abs:{t}" for t in AI_TERMS)),
    # AI papers that tackle open math problems
    "ai_x_openproblems": "(cat:cs.AI OR cat:cs.LG OR cat:cs.CL) AND ({})".format(
        " OR ".join(f"abs:{t}" for t in DISCOVERY_TERMS)),
}


def _date(d):
    return d.replace("-", "")


def collect(since, until, log, page_size=200, max_pages=10):
    out = []
    for qname, q in QUERIES.items():
        full = f"({q}) AND submittedDate:[{_date(since)}0000 TO {_date(until)}2359]"
        for page in range(max_pages):
            params = {"search_query": full, "start": page * page_size,
                      "max_results": page_size, "sortBy": "submittedDate", "sortOrder": "ascending"}
            body = fetch(API + "?" + urllib.parse.urlencode(params), log, backoff=10)
            time.sleep(3.5)  # arXiv asks for >=3s between calls
            if body is None:
                break
            root = ET.fromstring(body)
            entries = root.findall("a:entry", NS)
            if page == 0:
                total = root.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
                log.notes.append(f"{qname}: totalResults={total.text if total is not None else '?'}")
            for e in entries:
                log.items_seen += 1
                title = " ".join((e.findtext("a:title", "", NS) or "").split())
                abstract = " ".join((e.findtext("a:summary", "", NS) or "").split())
                text = f"{title}. {abstract}"
                ok, ai, math = is_candidate(text)
                if not ok:
                    continue
                out.append({
                    "id": "arxiv:" + (e.findtext("a:id", "", NS).rsplit("/", 1)[-1]),
                    "source": "arxiv",
                    "query": qname,
                    "title": title,
                    "url": e.findtext("a:id", "", NS),
                    "date": (e.findtext("a:published", "", NS) or "")[:10],
                    "summary": abstract[:1500],
                    "ai_terms": ai,
                    "math_terms": math,
                    "erdos_numbers": erdos_numbers(text),
                })
            if len(entries) < page_size:
                break
    log.candidates = len(out)
    return out
