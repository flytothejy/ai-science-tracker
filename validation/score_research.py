"""Score step-2 pilot outputs against the expected labels and write a Korean report.

Expected labels come from the frozen wiki where it covers the candidate; the rest are
reviewed by hand and recorded here with a note, so every verdict is traceable.
"""
import json
import os
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PILOT = os.path.join(ROOT, "data", "research", "pilot")

# idx -> expected (label source, is_ai, contribution, outcome). None = judged manually.
EXPECTED = {
    0: ("wiki", True, "1b_alongside_literature", "full"),     # #281
    1: ("wiki", True, "1c_building_on_literature", "full"),   # #224
    2: ("wiki-absent", False, None, None),                    # #570 not in wiki
    3: ("wiki-absent", False, None, None),                    # #834 not in wiki
    4: ("wiki", True, "1b_alongside_literature", "full"),     # #728 writeup
    5: None, 6: None, 7: None, 8: None, 9: None,
}

SEARCH_USD = 0.01          # web search: $10 / 1,000
SONNET_IN, SONNET_OUT = 2.0, 10.0   # $/M tokens (Sonnet 5.5)


def load():
    rows = []
    for i in range(10):
        inp = json.load(open(os.path.join(PILOT, f"in_{i}.json")))
        out_p = os.path.join(PILOT, f"out_{i}.json")
        out = json.load(open(out_p)) if os.path.exists(out_p) else None
        usage_p = os.path.join(PILOT, f"usage_{i}.json")
        usage = json.load(open(usage_p)) if os.path.exists(usage_p) else {}
        rows.append((i, inp, out, usage))
    return rows


def verdict(i, out, manual):
    exp = EXPECTED.get(i)
    if out is None:
        return "❌ 결과 없음", None
    if exp is None:
        m = manual.get(str(i), {})
        return m.get("verdict", "검토 필요"), m.get("note")
    src, is_ai, contrib, outcome = exp
    ok_ai = bool(out.get("is_ai_contribution")) == is_ai
    if not is_ai:
        return ("✅" if ok_ai else "❌") + " AI 기여 여부", f"기대: AI 기여 없음 ({src})"
    ok_c = out.get("contribution") == contrib
    ok_o = out.get("outcome") == outcome
    marks = f"{'✅' if ok_ai else '❌'} 여부 · {'✅' if ok_c else '⚠️'} 구분 · {'✅' if ok_o else '⚠️'} 결과"
    return marks, f"기대: {contrib}/{outcome} ({src}) · 답: {out.get('contribution')}/{out.get('outcome')}"


def main():
    manual = json.load(open(os.path.join(PILOT, "manual_review.json")))
    rows = load()
    L = ["# 2단계(조사) 시범 결과 — 10건\n"]
    L.append("같은 지침(`prompts/research.md`)을 받은 조사 에이전트(Sonnet)가 후보 1건씩 독립 조사. "
             "정답지 위키는 사용 금지.\n")
    L.append("| # | 등급 | 후보 | AI 기여 판정 | 구분/결과 | 상태 | 채점 | 검색 | 열람 | 토큰 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    tot_s = tot_f = tot_t = n = 0
    for i, inp, out, usage in rows:
        v, note = verdict(i, out, manual)
        o = out or {}
        title = inp.get("title", "")[:48].replace("|", "/")
        L.append(f"| {i} | {inp.get('tier')} | {title} | {'예' if o.get('is_ai_contribution') else '아니오'} | "
                 f"{o.get('contribution')}/{o.get('outcome')} | {o.get('status')} | {v} | "
                 f"{o.get('searches_used', '-')} | {o.get('fetches_used', '-')} | {usage.get('subagent_tokens', '-')} |")
        if out:
            tot_s += o.get("searches_used", 0)
            tot_f += o.get("fetches_used", 0)
            tot_t += usage.get("subagent_tokens", 0)
            n += 1
    L.append("\n### 채점 메모\n")
    for i, inp, out, usage in rows:
        v, note = verdict(i, out, manual)
        if note:
            L.append(f"- **{i}** {note}")
    avg_s, avg_t = tot_s / n, tot_t / n
    # tokens reported are totals (mostly input context); assume ~92% input / 8% output
    cost = avg_s * SEARCH_USD + avg_t * 0.92 * SONNET_IN / 1e6 + avg_t * 0.08 * SONNET_OUT / 1e6
    L.append("\n### 실측 비용\n")
    L.append(f"- 건당 평균: 검색 {avg_s:.1f}회, 열람 {tot_f / n:.1f}회, 토큰 약 {avg_t / 1000:.0f}k")
    L.append(f"- 건당 비용 추정: **약 ${cost:.2f}** (Sonnet 5.5 단가, 토큰의 92%를 입력으로 가정)")
    L.append("- 측정된 토큰에는 이 작업 환경의 에이전트 기본 컨텍스트가 포함돼 있어, "
             "지침만 넣는 운영용 호출에서는 더 작아질 가능성이 높습니다.")
    ap = os.path.join(PILOT, "analysis.md")
    if os.path.exists(ap):
        L.append(open(ap).read())
    out_p = os.path.join(ROOT, "reports", "step2_pilot.md")
    os.makedirs(os.path.dirname(out_p), exist_ok=True)
    open(out_p, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
