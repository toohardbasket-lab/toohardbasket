"""Which recommendations name a government other than the Commonwealth.

A recommendation addressed to more than one government cannot be answered by
the Commonwealth alone, so the register has to know which ones those are. This
is the cheapest mechanical test: does the recommendation's own text name a
state or territory. It is a floor — a recommendation can be addressed jointly
without naming anyone — and where the response says who is responsible, that
line is the better source.

    python3 names_a_state.py <report text file>
"""
import pathlib
import re
import sys

HEAD = re.compile(r"(?m)^Recommendation\s+(\d{1,3}\.\d{1,3})\s*:?\s+\S.*$")
STATE = re.compile(r"\b(New South Wales|Victoria|Queensland|South Australia|Western Australia"
                   r"|Tasmania|Northern Territory|Australian Capital Territory"
                   r"|NSW|QLD|VIC|WA|SA|TAS|NT|ACT"
                   r"|states? and territor(?:y|ies)|state and territory)\b")

body = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
marks = [(m.group(1), m.start(), m.end()) for m in HEAD.finditer(body)]
named, seen = [], {}
for i, (label, start, end) in enumerate(marks):
    stop = marks[i + 1][0 if False else 1] if i + 1 < len(marks) else len(body)
    text = body[start:stop][:4000]
    if label in seen:
        continue
    seen[label] = True
    m = STATE.search(text)
    if m:
        named.append((label, m.group(0)))
print(f"# {len(seen)} distinct recommendations in {sys.argv[1]}")
print(f"# {len(named)} name a state or territory in their own text")
for label, word in named:
    print(f"{label}\t{word}")
