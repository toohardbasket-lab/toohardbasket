"""Apply coverage.py's position test to a whole segment rather than to the
government's words alone.

extract_recommendations.py has to separate the recommendation from the answer
before coverage.py can be asked anything, and where that separation fails the
row is lost. This asks the narrower question the source test needs: between
one recommendation heading and the next, does the document use a verdict word
of the register's family at all?

It is a floor, not a substitute: a verdict word inside the quoted
recommendation would count here and should not. It says whether the words are
in the document, not whether the pipeline can attribute them.

    python3 verdict_by_segment.py <text file> [--rows]
"""
import collections
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scraper"))

import coverage as cov   # noqa: E402

body = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
LABEL = re.compile(r"(?i)\bRecommendation\s+(\d{1,3}\.\d{1,3})\b")

marks = [(m.group(1), m.start(), m.end()) for m in LABEL.finditer(body)]
best: dict[str, str] = {}
for i, (label, start, end) in enumerate(marks):
    stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
    segment = " ".join(body[end:stop].split())
    v = cov.verdict(segment, label) if cov.position(segment, label) else ""
    # Where a number appears more than once, the segment that states a verdict
    # is the answer; the others are the contents page or a cross-reference.
    if v or label not in best:
        best[label] = best.get(label) or v

key = lambda s: [int(p) for p in s.split(".")]   # noqa: E731
if "--rows" in sys.argv:
    for label in sorted(best, key=key):
        print(f"{label}\t{best[label] or '(no verdict word)'}")
counts = collections.Counter(v or "(no verdict word)" for v in best.values())
print(f"# {len(best)} distinct recommendation numbers in {sys.argv[1]}")
for k, v in counts.most_common():
    print(f"#   {v:4d}  {k}")
