"""What the register's own two steps make of a royal commission response.

Nothing here is new logic. extract_recommendations.py splits a response into
what was recommended and what the government said back; coverage.py decides
whether those words state a position, and sorts the government's verdict word
three ways. This runs both over one text file and prints the result, so the
source test can say what the existing code does with a document it has never
seen rather than guess at it.

    python3 positions.py <text file> [--rows]

Prints one line per recommendation with --rows; always prints the totals.
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scraper"))

import extract_recommendations as ex   # noqa: E402
import coverage as cov                 # noqa: E402

body = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
found = ex.recommendations_in(body)

states, verdicts = {}, {}
rows = []
for label in sorted(found, key=lambda s: [int(p) for p in s.split(".")]):
    asked, said, author = found[label]
    row = {"source": "response", "government_words": said, "label": label}
    st = cov.state(row)
    vd = cov.verdict(said, label) if st == "position" else ""
    states[st] = states.get(st, 0) + 1
    if vd:
        verdicts[vd] = verdicts.get(vd, 0) + 1
    rows.append((label, st, vd, author, " ".join(said.split())[:70]))

if "--rows" in sys.argv:
    for label, st, vd, author, said in rows:
        print(f"{label}\t{st}\t{vd}\t{author}\t{said}")
print(f"# {len(found)} recommendations split out of {sys.argv[1]}")
print(f"# states:   {dict(sorted(states.items()))}")
print(f"# verdicts: {dict(sorted(verdicts.items()))}")
if ex.dropped:
    print(f"# dropped by the split: {dict(ex.dropped)}")
