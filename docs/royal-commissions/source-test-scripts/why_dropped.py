"""Why extract_recommendations.py leaves a quoted recommendation out.

positions.py reports how many recommendations the existing split reads. This
reports the ones it does not, and which of its tests refused each — so the
finding can say what would have to change rather than that it "did not work".

    python3 why_dropped.py <response text file>
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scraper"))

import extract_recommendations as ex   # noqa: E402

body = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
got = ex.recommendations_in(body)
key = lambda s: [int(p) for p in s.split(".")]   # noqa: E731
labels = sorted({m for m in re.findall(r"(?i)Recommendation\s+(\d{1,3}\.\d{1,3})", body)}, key=key)
missing = [x for x in labels if x not in got]

marks = [(m.group(1), m.start(), m.end()) for m in ex.LABEL.finditer(body)]
seen = set()
for i, (lab, start, end) in enumerate(marks):
    if lab not in missing or lab in seen:
        continue
    stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
    seg = body[end:stop]
    hand = ex.HANDOVER.search(seg)
    asked = ex.tidy(seg[:hand.start()] if hand else seg)
    why = []
    if not ex.is_heading(body, start):
        why.append("read as a cross-reference rather than a heading")
    if not (ex.MIN_CHARS <= len(asked) <= ex.MAX_CHARS):
        why.append(f"quoted text is {len(asked)} characters, outside {ex.MIN_CHARS}-{ex.MAX_CHARS}")
    if ex.ENDS_IN_VERDICT.search(asked):
        why.append("ends in the government's verdict")
    if not ex.SAYS_RECOMMEND.search(asked):
        why.append("does not use a word the recommendation test looks for")
    if ex.looks_extracted_badly(asked):
        why.append("read as a broken extraction (two or more stray single letters)")
    if not hand:
        why.append("no handover to the government's words")
    if not why:
        continue
    seen.add(lab)
    print(f"{lab}\t{'; '.join(why)}")
    print(f"\topens: {asked[:110]}")
print(f"# {len(labels)} recommendation numbers in the document, {len(got)} read, "
      f"{len(missing)} not read: {missing}")
