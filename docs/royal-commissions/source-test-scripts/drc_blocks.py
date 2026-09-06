"""The shape of the Disability Royal Commission response, counted.

The response does not answer in prose the way a committee response does. Each
answer is a block: a heading naming the recommendation or recommendations, a
line saying which governments are responsible, and then the verdict as a label
on its own line — one line where the Commonwealth answers alone, several where
it does not:

    Response to Recommendation 6.41
    Responsibility: Australian, state and territory governments
    ACT and WA: Accept in principle
    Commonwealth, NSW, QLD, NT, SA, TAS, VIC: Subject to
    further consideration

So the verdict is a label, not a sentence; a block can answer a range of
recommendations at once ("Response to Recommendations 4.1–4.21"); a
recommendation can be answered in more than one block, a lettered part at a
time; and one block can carry one verdict for the Commonwealth and another for
the states. This counts each of those, so the source test can say what a rule
would have to read rather than describe it.

    python3 drc_blocks.py <response text> [<report text>] [--rows]

With a report text as well, it also says which of the report's recommendations
the response does not answer.

A block is a "Responsibility:" line and the "<who>: <verdict>" labels beneath
it. Its recommendations are those named in the nearest heading above it.
"""
import collections
import pathlib
import re
import sys

args = [a for a in sys.argv[1:] if not a.startswith("--")]
lines = pathlib.Path(args[0]).read_text(encoding="utf-8", errors="replace").splitlines()

HEAD = re.compile(r"^Response to Recommendations?\s+(.+?)\s*$", re.I)
RESP = re.compile(r"^Responsibility:\s*(.+?)\s*$", re.I)
# A verdict label: a short "who: what" line whose right-hand side is short.
VERDICT_LINE = re.compile(r"^([A-Za-z][A-Za-z,’' .\-()0-9]{0,70}?):\s*([A-Z][^:]{0,60})\s*$")
NUM = re.compile(r"\d+\.\d+")


def labels_in(heading: str) -> list[str]:
    """The recommendations a heading names, with ranges expanded.

    "6.24–6.25" and "11.1 to 11.2" are ranges; "7.8 and 7.10" and
    "7.2, 7.3, 7.6 and 7.13" are lists. A range runs within one chapter.
    """
    out: list[str] = []
    for part in re.split(r",|\band\b", heading):
        nums = NUM.findall(part)
        rng = re.search(r"(\d+)\.(\d+)\s*(?:–|—|-|\bto\b)\s*(\d+)\.(\d+)", part)
        if rng and rng.group(1) == rng.group(3):
            out += [f"{rng.group(1)}.{n}" for n in
                    range(int(rng.group(2)), int(rng.group(4)) + 1)]
        else:
            out += nums
    seen: list[str] = []
    for n in out:
        if n not in seen:
            seen.append(n)
    return seen


blocks, heading = [], []
for i, line in enumerate(lines):
    h = HEAD.match(line.strip())
    if h:
        heading = labels_in(h.group(1))
    r = RESP.match(line.strip())
    if not r:
        continue
    verdicts = []
    for nxt in lines[i + 1:i + 6]:
        v = VERDICT_LINE.match(nxt.strip())
        if not v:
            break
        verdicts.append((v.group(1).strip(), v.group(2).strip()))
    blocks.append({"labels": heading, "responsibility": r.group(1), "verdicts": verdicts})

# Whose verdict is it? A rule, not a judgement. The left-hand side of a verdict
# label either names the Commonwealth ("Commonwealth", "Australian Government
# Response"), or speaks for every responsible government at once ("Response",
# "Joint response"), or names states only — in which case the line is not a
# position for the Commonwealth's part.
COMMONWEALTH = re.compile(r"^(?:response|joint\s+response|australian\s+government\s+response"
                          r"|commonwealth)\b", re.I)
STATES_ONLY = re.compile(r"^(?:ACT|NSW|NT|QLD|SA|TAS|VIC|WA)\b", re.I)
for b in blocks:
    b["commonwealth"] = [v for w, v in b["verdicts"] if COMMONWEALTH.match(w)]

if "--rows" in sys.argv:
    for b in blocks:
        print(",".join(b["labels"]) + "\t" + b["responsibility"] + "\t"
              + " | ".join(f"{w}={v}" for w, v in b["verdicts"]))

answered = {n for b in blocks for n in b["labels"]}
cw = {n for b in blocks if b["commonwealth"] for n in b["labels"]}
print(f"# {len(blocks)} response blocks, naming {len(answered)} recommendations between them")
print(f"# {len([b for b in blocks if len(b['labels']) > 1])} blocks answer more than one "
      "recommendation at once")
print(f"# {len(cw)} recommendations get a verdict for the Commonwealth's part under the rule above")
print("# responsibility lines:")
for k, v in collections.Counter(b["responsibility"] for b in blocks).most_common():
    print(f"#   {v:4d}  {k}")
print("# who the verdict is attributed to:")
for k, v in collections.Counter(w for b in blocks for w, _ in b["verdicts"]).most_common():
    print(f"#   {v:4d}  {k}")
print("# verdict words, exactly as the response writes them:")
for k, v in collections.Counter(v for b in blocks for _, v in b["verdicts"]).most_common():
    print(f"#   {v:4d}  {k}")

if len(args) > 1:
    report = set(NUM.findall(pathlib.Path(args[1]).read_text(encoding="utf-8", errors="replace")))
    report = {n for n in report if re.search(r"(?i)Recommendation\s+" + re.escape(n),
              pathlib.Path(args[1]).read_text(encoding="utf-8", errors="replace"))}
    key = lambda s: [int(p) for p in s.split(".")]   # noqa: E731
    print(f"# the report makes {len(report)} numbered recommendations")
    print(f"# {len(report - answered)} of them are not named by any response block:")
    print("#   " + " ".join(sorted(report - answered, key=key)))
