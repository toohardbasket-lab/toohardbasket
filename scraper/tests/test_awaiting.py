"""One rule for who the government owes an answer to.

The site published two headline figures that disagreed with each other. The
stated-position figure — 1,030 of 3,504, the 29 per cent — excluded
recommendations made by a dissenting report or a member's additional comments,
and said why: a government answers the committee, not the minority. The
awaiting figure on the search page counted them, because it asked whether a
response existed before it asked whose recommendation it was, and 131 of the
1,193 it published were somebody's dissent.

Both figures now apply the same rule. These tests keep them applying it, and
keep the three places that compute it agreeing on the answer.
"""
from __future__ import annotations

import csv
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCRAPER = HERE.parent
DATA = SCRAPER / "data"

PASS, FAIL = [], []


def check(name: str, cond, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def rd(name: str) -> list[dict]:
    p = DATA / name
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


recs = rd("recommendations.csv")
author = lambda r: (r.get("recommended_by") or "").strip()
unanswered = lambda r: r.get("response_classification") == "awaiting a response"

naive = [r for r in recs if unanswered(r)]
owed = [r for r in naive if not author(r)]

check("the index holds recommendations that are not the committee's",
      len(naive) > len(owed),
      "nothing is attributed to a dissent, so this suite cannot detect the fault it exists for")
check("no recommendation counted as owed an answer belongs to somebody else",
      all(not author(r) for r in owed))

# --- the producers must agree --------------------------------------------------
out = subprocess.run([sys.executable, str(SCRAPER / "brief_figures.py"), "--json"],
                     capture_output=True, text=True, cwd=SCRAPER)
if out.returncode == 0:
    f = json.loads(out.stdout).get("recommendations_index", {})
    check("brief_figures counts the same recommendations as owed an answer",
          f.get("awaiting_a_response") == len(owed),
          f"brief_figures {f.get('awaiting_a_response')}, expected {len(owed)}")
else:
    check("brief_figures.py runs", False, out.stderr[-200:])

# --- and coverage must not put an authored recommendation in the awaiting bucket
# recommendation_positions.csv is written by coverage.py, so this runs after it.
pos = rd("recommendation_positions.csv")
if pos:
    stray = [r for r in pos if r.get("state") == "awaiting" and (r.get("recommended_by") or "").strip()]
    check("coverage puts an authored recommendation in the dissent bucket, not awaiting",
          not stray, f"{len(stray)} rows are counted as awaiting and attributed to somebody")
    check("the dissent bucket is not empty",
          any(r.get("state") == "dissent" for r in pos))
else:
    print("SKIP recommendation_positions.csv is not present; run coverage.py first")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for x in FAIL:
        print("  FAILED:", x)
    sys.exit(1)
print("all tests passed")
