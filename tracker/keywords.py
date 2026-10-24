"""Cheap rule-based pre-filter that decides what goes on to step 2 (agent research).

A text is a candidate when it mentions an AI system AND a research-math signal.
Keeping this filter tight is what keeps step-2 cost down.
"""
import re

AI_RE = re.compile(
    r"\b("
    r"large[- ]language[- ]models?|LLMs?|language[- ]models?|reasoning[- ]models?|"
    r"GPT-?\d[\w.]*|ChatGPT|o\d(?:-pro)?|Gemini(?:\s+(?:Deep\s+Think|\d[\w.]*))?|Claude|Grok|DeepSeek|"
    r"AlphaProof|AlphaEvolve|AlphaGeometry|Aristotle|Kimina|Goedel-Prover|Seed-Prover|"
    r"artificial intelligence|AI[- ](?:assisted|generated|discovered|systems?|models?|agents?|tools?)|"
    r"machine[- ]learning|deep[- ]learning|neural networks?|autoformali[sz]\w*|"
    r"automated theorem prov\w*|AI\b"
    r")",
    re.IGNORECASE,
)
# "AI" alone matched case-sensitively to avoid words like "ai" in other languages
AI_CASE_SENSITIVE_RE = re.compile(r"\bAI\b")

MATH_RE = re.compile(
    r"\b("
    r"Erd(?:[őöo]|oe)s|conjectures?|open problems?|unsolved|theorems?|proofs?|proved|disproved|"
    r"counterexamples?|lemmas?|mathlib|formali[sz]\w*|combinatori\w*|number theory|"
    r"discrete geometry|graph theory|mathematic\w*"
    r")\b",
    re.IGNORECASE,
)

ERDOS_NUM_RES = [
    re.compile(r"erd(?:[őöo]|oe)s\s+problems?\s*(?:#|no\.?\s*|number\s*)?(\d{1,4})\b", re.IGNORECASE),
    re.compile(r"erdosproblems\.com/(?:forum/thread/)?(\d{1,4})\b", re.IGNORECASE),
    re.compile(r"erd(?:[őöo]|oe)s\s*#\s*(\d{1,4})\b", re.IGNORECASE),
    re.compile(r"problem\s*#\s*(\d{1,4})\b[^.]{0,80}erd(?:[őöo]|oe)s|erd(?:[őöo]|oe)s[^.]{0,80}problem\s*#\s*(\d{1,4})\b", re.IGNORECASE),
]


def ai_hits(text):
    hits = set()
    for m in AI_RE.finditer(text or ""):
        tok = m.group(0)
        if tok.lower() == "ai" and not AI_CASE_SENSITIVE_RE.fullmatch(tok):
            continue
        hits.add(tok)
    return sorted(hits)


# "Lean" (the proof assistant) only when capitalised, so "a lean team" does not match
LEAN_RE = re.compile(r"\bLean(?:\s?4)?\b(?!\s+(?:startup|team|manufacturing|budget))")


def math_hits(text):
    hits = {m.group(0) for m in MATH_RE.finditer(text or "")}
    hits |= {m.group(0) for m in LEAN_RE.finditer(text or "")}
    return sorted(hits)


def erdos_numbers(text):
    nums = set()
    for r in ERDOS_NUM_RES:
        for m in r.finditer(text or ""):
            for g in m.groups():
                if g:
                    nums.add(int(g))
    return sorted(n for n in nums if 1 <= n <= 2000)


def is_candidate(text, require_math=True):
    a = ai_hits(text)
    m = math_hits(text)
    return bool(a) and (bool(m) or not require_math), a, m


# Tier A = text that claims a result (worth full agent research); B = everything else (cheap triage)
CLAIM_RE = re.compile(
    r"Erd(?:[őöo]|oe)s(?![-–\s]+R[ée]nyi)|conjecture|open problem|unsolved|resolution|resolv|"
    r"solv(?:e|es|ed|ing)\b|counterexample|disprov|discover|new (?:bound|construction)|"
    r"(?:lower|upper) bound|case study|breakthrough",
    re.IGNORECASE,
)


LAB_SOURCES = {"openai_news", "deepmind_blog"}


def tier(c):
    if c.get("source") == "erdos_db":
        return "S"  # status signal
    if c.get("erdos_numbers") or CLAIM_RE.search(c.get("title", "")):
        return "A"
    # first-party lab announcements about mathematics are always worth full research
    if c.get("source") in LAB_SOURCES and re.search(r"math|proof|theorem", c.get("title", ""), re.I):
        return "A"
    return "B"
