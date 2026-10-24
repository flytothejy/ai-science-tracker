"""Score a step-1 run against the frozen wiki ground truth and write a Korean report.

  python -m validation.replay --since 2026-01-01 --until 2026-01-31 [--case 281]
"""
import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import date

from .ground_truth import load

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT_SOURCES_LABEL = {"arxiv": "arXiv", "openalex": "OpenAlex", "openai_news": "OpenAI 뉴스",
                      "deepmind_blog": "DeepMind 블로그", "quanta": "Quanta", "tao_blog": "Tao 블로그",
                      "erdos_db": "에르되시 DB"}


def _pct(a, b):
    return f"{(100 * a / b):.0f}%" if b else "-"


def score(since, until, case=None, run_id=None):
    run_id = run_id or f"{since}_{until}"
    cand_path = os.path.join(ROOT, "data", "candidates", f"{run_id}.jsonl")
    run_path = os.path.join(ROOT, "data", "runs", f"{run_id}.json")
    cands = [json.loads(l) for l in open(cand_path)]
    run = json.load(open(run_path))
    gt_all = load()

    gt = [r for r in gt_all if r["primary"] and r["date"] and since <= r["date"] <= until
          and r["outcome"] in ("full", "partial")]
    gt_nums = sorted({r["number"] for r in gt})
    gt_any_nums = {r["number"] for r in gt_all}

    by_num = defaultdict(set)
    for c in cands:
        for n in c.get("erdos_numbers", []):
            by_num[n].add(c["source"])

    rows, caught_any, caught_text, caught_status = [], 0, 0, 0
    for n in gt_nums:
        srcs = by_num.get(n, set())
        text = srcs - {"erdos_db"}
        st = "erdos_db" in srcs
        caught_any += bool(srcs)
        caught_text += bool(text)
        caught_status += st
        info = [r for r in gt if r["number"] == n][0]
        rows.append((n, info, st, sorted(text)))

    status_events = [c for c in cands if c["source"] == "erdos_db"]
    status_ai = [c for c in status_events if c["erdos_numbers"][0] in gt_any_nums]
    text_cands = [c for c in cands if c["source"] != "erdos_db"]
    text_with_num = [c for c in text_cands if c.get("erdos_numbers")]

    days = (date.fromisoformat(until) - date.fromisoformat(since)).days + 1
    weeks = days / 7
    per_src = Counter(c["source"] for c in cands)

    L = []
    L.append(f"# 1단계(수집) 재현 검증 — {since} ~ {until}\n")
    L.append(f"- 실행 환경: `{run['environment']}` · 실행 시각: {run['ran_at']}")
    L.append(f"- 정답지: 커뮤니티 'AI contributions to Erdős problems' 위키(2026-06-30 동결), "
             f"구간 내 1차 기여(1a~1d) 중 성공·부분성공 **{len(gt_nums)}개 문제**\n")

    L.append("## 1. 소스별 작동 여부\n")
    L.append("| 소스 | 작동 | 요청 | 응답 코드 | 본 항목 | 후보 | 비고 |")
    L.append("|---|---|---|---|---|---|---|")
    for s in run["sources"]:
        mark = "✅" if s["ok"] else "❌"
        notes = "; ".join(s["notes"] + s["failures"][:2]).replace("|", "/")
        L.append(f"| {TEXT_SOURCES_LABEL.get(s['source'], s['source'])} | {mark} | {s['requests']} | "
                 f"{s['status_counts']} | {s['items_seen']} | {s['candidates']} | {notes[:200]} |")

    L.append("\n## 2. 정답지 대비 재현율\n")
    L.append(f"- **어떤 경로로든 포착: {caught_any}/{len(gt_nums)} ({_pct(caught_any, len(gt_nums))})**")
    L.append(f"- 상태 신호(에르되시 DB)로 포착: {caught_status}/{len(gt_nums)} ({_pct(caught_status, len(gt_nums))})"
             " — 'AI 기여' 정보는 없음")
    L.append(f"- 텍스트 소스(논문·블로그)에서 문제 번호까지 포착: {caught_text}/{len(gt_nums)} "
             f"({_pct(caught_text, len(gt_nums))}) — 'AI 기여' 근거가 함께 잡힘\n")

    if case is not None:
        r = [x for x in rows if x[0] == case]
        L.append(f"### 사례 #{case}\n")
        if r:
            n, info, st, text = r[0]
            L.append(f"- 정답지: {info['section']} · {info['ai_systems']} · {info['date']} · {info['outcome']}")
            L.append(f"- 상태 신호 포착: {'✅' if st else '❌'}")
            L.append(f"- 텍스트 포착: {', '.join(TEXT_SOURCES_LABEL.get(t, t) for t in text) or '❌ 없음'}")
            for c in cands:
                if case in c.get("erdos_numbers", []):
                    L.append(f"  - [{TEXT_SOURCES_LABEL.get(c['source'], c['source'])}] {c['date']} "
                             f"[{c['title'][:90]}]({c['url']})")
        else:
            L.append("- 구간 내 정답지에 없음")
        L.append("")

    L.append("<details><summary>문제별 상세</summary>\n")
    L.append("| # | 정답지 구분 | AI | 날짜 | 결과 | 상태 신호 | 텍스트 소스 |")
    L.append("|---|---|---|---|---|---|---|")
    for n, info, st, text in rows:
        L.append(f"| {n} | {info['section']} | {info['ai_systems'][:40]} | {info['date']} | {info['outcome']} | "
                 f"{'✅' if st else '—'} | {', '.join(TEXT_SOURCES_LABEL.get(t, t) for t in text) or '—'} |")
    L.append("\n</details>\n")

    L.append("## 3. 후보 규모 (2단계 작업량 추정용)\n")
    L.append(f"- 기간 {days}일 ({weeks:.1f}주), 후보 총 {len(cands)}건 → **주당 약 {len(cands) / weeks:.0f}건**")
    for s, n in per_src.most_common():
        L.append(f"  - {TEXT_SOURCES_LABEL.get(s, s)}: {n}건")
    L.append(f"- 에르되시 상태 이벤트 {len(status_events)}건 중 위키에 AI 기여 기록이 있는 문제: "
             f"{len(status_ai)}건 ({_pct(len(status_ai), len(status_events))}) — 나머지는 2단계가 'AI 무관'으로 걸러내야 함")
    L.append(f"- 텍스트 후보 {len(text_cands)}건 중 에르되시 번호가 명시된 것: {len(text_with_num)}건\n")

    L.append("## 4. 한계\n")
    L.append("- 에르되시 DB의 `last_update`는 문제별 최신 변경만 남아서, 구간 이후 다시 갱신된 문제는 재현에서 빠집니다. "
             "실운영(일일 스냅샷 비교)에서는 이 문제가 없습니다.")
    L.append("- 정답지는 에르되시 문제에 한정됩니다. 다른 분야의 재현율은 이 리포트로 측정되지 않습니다.")

    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
    out = os.path.join(ROOT, "reports", f"replay_{run_id}.md")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:3]))
    print(f"recall any={caught_any}/{len(gt_nums)} status={caught_status} text={caught_text} -> {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--case", type=int)
    a = ap.parse_args()
    score(a.since, a.until, a.case)


if __name__ == "__main__":
    main()
