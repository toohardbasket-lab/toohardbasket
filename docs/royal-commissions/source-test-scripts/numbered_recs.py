"""Recommendations from a royal commission report, by their own numbering.

Both reports in this test print their recommendations the same way and neither
way is the one extract_report_recommendations.py knows: the label and the
recommendation's own title are on one line, and the text runs from there to the
next such line.

    Recommendation 10.1: Design policies and processes with emphasis on the people
    Services Australia design its policies and processes with a primary emphasis…

    Recommendation 6.31 Embed the right to equitable access to health services
    a) The Australian Commission on Safety and Quality in Health Care should:…

This reads that shape and reports where each recommendation stops, so the
source test can say whether the boundaries are the report's own rather than
guessed at. It is evidence for the finding, not a pipeline step.

    python3 numbered_recs.py <text file> [--rows]
"""
import pathlib
import re
import sys

HEAD = re.compile(r"(?m)^Recommendation\s+(\d{1,3}\.\d{1,3})\s*:?\s+(\S.*)$")

body = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
marks = [(m.group(1), m.group(2), m.start(), m.end()) for m in HEAD.finditer(body)]

best: dict[str, str] = {}
for i, (label, title, start, end) in enumerate(marks):
    stop = marks[i + 1][2] if i + 1 < len(marks) else len(body)
    text = " ".join(body[end:stop].split())
    # A number is printed twice — once in the list at the front, once as the
    # chapter heading that argues for it. The shorter is the list's, which
    # stops where the recommendation stops; the longer runs into the argument.
    if label not in best or len(text) < len(best[label]):
        best[label] = text
last = marks[-1][0] if marks else ""

key = lambda s: [int(p) for p in s.split(".")]   # noqa: E731
if "--rows" in sys.argv:
    for label in sorted(best, key=key):
        print(f"{label}\t{len(best[label]):5d}\t{best[label][:110]}")
lengths = sorted(len(v) for v in best.values())
print(f"# {len(marks)} headings, {len(best)} distinct recommendation numbers in {sys.argv[1]}")
if lengths:
    bounded = sorted(len(v) for k, v in best.items() if k != last)
    print(f"# every one but the last stops at the next heading: shortest "
          f"{bounded[0]} characters, median {bounded[len(bounded)//2]}, "
          f"longest {bounded[-1]}")
    print(f"# the last, {last}, has no heading after it and runs to the end of the "
          f"file: {len(best[last])} characters")
