"""
coverage_candidates.py — find responses that state how many recommendations a
committee made, and then address few or none of them individually.

Coverage is the question worth asking: for each recommendation a committee
made, did the response state a position on it? Measuring that properly means
parsing every report for its recommendations, which is a large build. But for
the cases that matter most, the response supplies the denominator itself —
"the Government notes the 31 recommendations made by the Committee",
"40 recommendations, 35 of which are contained within dissenting reports".

So this ranks candidates for a hand-verified coverage table: responses with a
large self-stated recommendation count and few individually addressed. It is a
CANDIDATE GENERATOR, not a measurement — every published row must be checked
by eye, because counting "Recommendation N" mentions is noisy in both
directions (a pro-forma template repeats per recommendation and scores high
while saying nothing; dissenting reports restart their numbering and collapse
the distinct count).

What the table should claim is traceability, not action: the response does not
put on the record what happened to each recommendation. Never assert that
nothing was done — record what the government points to instead, and link it.

Usage:
    python coverage_candidates.py
Writes qa/coverage_candidates_<date>.csv
"""
from __future__ import annotations

import csv
import datetime
import glob
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
QA = HERE / "qa"
TEXT = HERE / "raw" / "otd_text"

STATED = [
    re.compile(r"\b(?:the|its|made|making|contains?|containing)\s+(\d{1,3})\s+(?:wide-ranging\s+|substantive\s+)?recommendations", re.I),
    re.compile(r"\b(\d{1,3})\s+recommendations\s+(?:were\s+)?(?:made|contained|set out|put forward)", re.I),
]
REC_N = re.compile(r"\brecommendation\s+(\d{1,3})\b", re.I)
# Out of scope: these answer no committee report (see link_responses.py).
OUT_OF_SCOPE = re.compile(r"status of government responses|486O|Ombudsman|royal commission|"
                          r"independent (review|national security)|\bINSLM\b", re.I)


def text_for(doc_id: str) -> str:
    hits = glob.glob(str(TEXT / f"{doc_id}_*.txt"))
    return pathlib.Path(hits[0]).read_text(encoding="utf-8", errors="replace") if hits else ""


def main(argv: list[str]) -> int:
    rows = list(csv.DictReader(open(DATA / "response_documents.csv",
                                    newline="", encoding="utf-8-sig")))
    out = []
    for r in rows:
        if OUT_OF_SCOPE.search(r["title"]):
            continue
        t = text_for(r["id"])
        if not t:
            continue
        stated = [int(m) for p in STATED for m in p.findall(t) if 1 <= int(m) <= 200]
        if not stated:
            continue
        n = max(stated)
        addressed = len({int(m) for m in REC_N.findall(t)})
        out.append({
            "id": r["id"],
            "stated_recommendations": n,
            "distinct_rec_numbers": addressed,
            "gap": n - addressed,
            "classification": r["classification"],
            "chars": int(r["text_length"] or 0),
            "tabled": (r["tabled_senate"] or r["tabled_house"] or "")[:10],
            "department": r["department"][:60],
            "title": r["title"],
            "url": r["url"],
        })

    out.sort(key=lambda x: (-x["gap"], -x["stated_recommendations"]))
    QA.mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()
    path = QA / f"coverage_candidates_{today}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)

    print(f"{len(out)} responses state a recommendation count\n")
    print(f"{'stated':>6} {'seen':>5} {'gap':>5}  {'class':<17} {'tabled':<11} title")
    for x in out[:22]:
        print(f"{x['stated_recommendations']:>6} {x['distinct_rec_numbers']:>5} {x['gap']:>5}  "
              f"{x['classification'].replace('_',' '):<17} {x['tabled']:<11} {x['title'][:62]}")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
