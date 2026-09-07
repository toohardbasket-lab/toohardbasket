"""extract_rc_positions.py — what the government said about each recommendation.

extract_rc_recommendations.py has the recommendations, in the commission's own
words. This has the other half: for each of them, the government's words and
whether they state a position. Nothing is inferred. Where the response does not
address a recommendation, the row says so; it is not counted as a refusal and
it is not counted as an acceptance.

The two responses read so far answer in two different grammars, and the source
test of 6 September 2026 established both.

A prose response answers the way a committee response does, and coverage.py
already reads it:

    Recommendation 11.1: Clear documentation of exclusion criteria
    Services Australia should ensure that ...
    The Government accepts this recommendation.
    The Government supports the need for clear documentation ...

A block response answers with a label on a line of its own, under a line
naming which governments are answering:

    Response to Recommendation 6.41
    Responsibility: Australian, state and territory governments
    ACT and WA: Accept in principle
    Commonwealth, NSW, QLD, NT, SA, TAS, VIC: Subject to
    further consideration

Which grammar a document uses is read from the document, not configured: a
response carrying "Responsibility:" lines with labels under them is read as
blocks, and everything else as prose.

Four things about the block grammar that a rule has to handle, all of them
found in the Disability Royal Commission's response:

  * A block can answer a range at once — "Response to Recommendations
    4.1–4.21" — so the heading's numbers are expanded, ranges and lists alike.
  * A recommendation can be answered a lettered part at a time, with different
    verdicts for different parts. The row is still one recommendation. Where
    the parts disagree it sorts as "in part or in principle", which is what
    the vocabulary already means, and every exact label is kept beside it.
  * One block can carry the Commonwealth's verdict and the states' separately.
    Which is the Commonwealth's is decided by the left-hand side of the label:
    "Response", "Joint response", "Australian Government Response" and
    "Commonwealth" speak for it, and a list of states that does not name the
    Commonwealth does not. The states' verdicts are recorded beside it, because
    the document says them, but the register's figures are the Commonwealth's.
  * A label wraps across a line where the page is narrow — "Subject to" then
    "further consideration" — and is rejoined.

The verdict vocabulary is the register's existing one and is not extended for
this: coverage.py sorts the government's own word into accepted, in part or in
principle, and not accepted. A label it does not recognise states no position —
"Note" and "Subject to further consideration" both do — and the row is noted,
with the government's exact words kept and shown.

    python3 extract_rc_positions.py
    python3 extract_rc_positions.py --commission robodebt

Reads  data/rc_recommendations.csv, data/rc_documents.csv, raw/rc_text/
Writes data/rc_positions.csv  one row per recommendation per response
       data/rc_position_counts.csv  the totals, per response
"""
from __future__ import annotations

import collections
import csv
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "rc_text"
RECOMMENDATIONS = DATA / "rc_recommendations.csv"
DOCUMENTS = DATA / "rc_documents.csv"
OUT = DATA / "rc_positions.csv"
COUNTS = DATA / "rc_position_counts.csv"

sys.path.insert(0, str(HERE))
import coverage as cov                    # noqa: E402
import extract_recommendations as ex      # noqa: E402

# --- the block grammar ------------------------------------------------------
BLOCK_HEAD = re.compile(r"(?m)^[ \t]*Response to Recommendations?[ \t]+(.+?)[ \t]*$", re.I)
RESPONSIBILITY = re.compile(r"(?m)^[ \t]*Responsibility:[ \t]*(.+?)[ \t]*$", re.I)
# "<who>: <verdict>" — a short left side, a short right side, no colon in it.
VERDICT_LINE = re.compile(r"^([A-Za-z][A-Za-z,’' .\-()0-9]{0,70}?):[ \t]*([A-Z][^:]{0,60})$")
# A label the page has wrapped: the rest of it is a short lower-case line.
CONTINUATION = re.compile(r"^[a-z][^:]{0,40}$")
# Whose verdict it is. "Response" and "Joint response" speak for every
# government answering, the Commonwealth among them.
COMMONWEALTH = re.compile(r"^(?:response|joint\s+response|australian\s+government\s+response"
                          r"|commonwealth)\b", re.I)
NUMBER = re.compile(r"\d+\.\d+")

STATES = ("position", "noted", "not addressed", "unreadable")
GOV_CHARS = 900

FIELDS = ["commission_id", "label", "response_id", "response_tabled", "response_url",
          "state", "verdict", "government_label", "other_governments",
          "government_words", "note"]
COUNT_FIELDS = ["commission_id", "response_id", "grammar", "recommendations", "position",
                "noted", "not addressed", "unreadable", "accepted",
                "in part or in principle", "not accepted"]


def labels_in(heading: str) -> list[str]:
    """The recommendations a block heading names, with ranges expanded.

    "6.24–6.25" and "11.1 to 11.2" are ranges; "7.8 and 7.10" and
    "7.2, 7.3, 7.6 and 7.13" are lists. A range runs within one chapter, and
    one that does not is left as the two numbers it names rather than guessed
    at.
    """
    out: list[str] = []
    for part in re.split(r",|\band\b", heading):
        span = re.search(r"(\d+)\.(\d+)\s*(?:–|—|-|\bto\b)\s*(\d+)\.(\d+)", part)
        if span and span.group(1) == span.group(3) and int(span.group(2)) <= int(span.group(4)):
            out += [f"{span.group(1)}.{n}"
                    for n in range(int(span.group(2)), int(span.group(4)) + 1)]
        else:
            out += NUMBER.findall(part)
    seen: list[str] = []
    for n in out:
        if n not in seen:
            seen.append(n)
    return seen


def blocks_in(body: str) -> list[dict]:
    """Every answer block: which recommendations, who is responsible, what they said."""
    lines = body.splitlines()
    heading: list[str] = []
    out = []
    for i, line in enumerate(lines):
        head = BLOCK_HEAD.match(line)
        if head:
            heading = labels_in(head.group(1))
        if not RESPONSIBILITY.match(line):
            continue
        verdicts = []
        j = i + 1
        while j < len(lines):
            m = VERDICT_LINE.match(lines[j].strip())
            if not m:
                break
            who, said = m.group(1).strip(), m.group(2).strip()
            # A label the page wrapped: take the rest of it from the next line.
            if j + 1 < len(lines) and CONTINUATION.match(lines[j + 1].strip()):
                said = f"{said} {lines[j + 1].strip()}"
                j += 1
            verdicts.append((who, said))
            j += 1
        words = " ".join(" ".join(lines[j:j + 12]).split())[:GOV_CHARS]
        out.append({"labels": list(heading),
                    "responsibility": RESPONSIBILITY.match(line).group(1),
                    "verdicts": verdicts, "words": words})
    return out


def from_blocks(body: str) -> dict[str, dict]:
    """label -> the Commonwealth's position, with the other governments' beside it."""
    found: dict[str, dict] = {}
    for block in blocks_in(body):
        mine = [said for who, said in block["verdicts"] if COMMONWEALTH.match(who)]
        others = [f"{who}: {said}" for who, said in block["verdicts"]
                  if not COMMONWEALTH.match(who)]
        verdicts = [cov.verdict(said) for said in mine]
        stated = [v for v in verdicts if v]
        if not mine:
            state, verdict = "noted", ""
        elif not stated:
            # Every label is one the vocabulary does not recognise: "Note",
            # "Subject to further consideration". The words are kept; no
            # position is claimed from them.
            state, verdict = "noted", ""
        elif len(set(verdicts)) == 1:
            state, verdict = "position", stated[0]
        else:
            # The parts disagree, or some part states nothing. One
            # recommendation, answered partly — which is what the existing
            # vocabulary already means.
            state, verdict = "position", "in part or in principle"
        for label in block["labels"]:
            keep = found.get(label)
            if keep and keep["state"] == "position" and state != "position":
                continue
            found[label] = {
                "state": state, "verdict": verdict,
                "government_label": "; ".join(mine),
                "other_governments": "; ".join(others),
                "government_words": block["words"],
                "note": ("answered with the states and territories together"
                         if "state" in block["responsibility"].lower() else ""),
            }
    return found


# --- the prose grammar ------------------------------------------------------
LABEL = re.compile(r"(?i)\bRecommendation[ \t]+(\d{1,3}\.\d{1,3})\b")


def from_prose(body: str) -> dict[str, dict]:
    """label -> the government's words after the recommendation, and their verdict.

    The split is extract_recommendations.py's, which knows where a government
    stops quoting and starts answering, and the verdict is coverage.py's.
    Neither is re-implemented here.
    """
    marks = [(m.group(1), m.start(), m.end()) for m in LABEL.finditer(body)]
    found: dict[str, dict] = {}
    for i, (label, start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        segment = body[end:stop]
        hand = ex.HANDOVER.search(segment)
        if not hand:
            continue
        raw = segment[hand.start():]
        stop_at = ex.GOV_END.search(raw, 1)
        if stop_at:
            raw = raw[:stop_at.start()]
        words = ex.tidy(ex.GOV_LABEL.sub("", raw.strip()))[:GOV_CHARS]
        if not words:
            continue
        state = cov.state({"source": "response", "government_words": words, "label": label})
        verdict = cov.verdict(words, label) if state == "position" else ""
        keep = found.get(label)
        if keep and keep["state"] == "position" and state != "position":
            continue
        found[label] = {"state": state, "verdict": verdict,
                        "government_label": (cov.find(words, label).group(0).strip()
                                             if state == "position" else ""),
                        "other_governments": "", "government_words": words, "note": ""}
    return found


# --- both -------------------------------------------------------------------
def read(path: pathlib.Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    tmp.replace(path)


def text_for(document_id: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(TEXT.glob(f"{document_id}_*.txt")))


def positions_in(body: str) -> tuple[dict[str, dict], str]:
    """The positions a response states, and which grammar it was read as."""
    if blocks_in(body):
        return from_blocks(body), "blocks"
    return from_prose(body), "prose"


def label_key(label: str) -> list[int]:
    return [int(p) for p in label.split(".")]


def main(argv: list[str]) -> int:
    wanted = {argv[i + 1] for i, a in enumerate(argv) if a == "--commission"}
    recommendations = collections.defaultdict(list)
    for r in read(RECOMMENDATIONS):
        if not wanted or r["commission_id"] in wanted:
            recommendations[r["commission_id"]].append(r["label"])
    responses = [d for d in read(DOCUMENTS) if d["role"] == "response"
                 and d["commission_id"] in recommendations]
    if not responses:
        print("no response documents for any commission with recommendations", file=sys.stderr)
        return 1

    rows, counts, unread, empty = [], [], [], []
    for d in sorted(responses, key=lambda d: d["tabled_senate"] or d["tabled_house"]):
        body = text_for(d["id"])
        if not body.strip():
            unread.append(d)
            continue
        found, grammar = positions_in(body)
        if not found:
            empty.append(d)
            continue
        labels = recommendations[d["commission_id"]]
        tally = collections.Counter()
        for label in sorted(labels, key=label_key):
            got = found.get(label)
            if got is None:
                got = {"state": "not addressed", "verdict": "", "government_label": "",
                       "other_governments": "", "government_words": "",
                       "note": "the response does not address this recommendation"}
            tally[got["state"]] += 1
            if got["verdict"]:
                tally[got["verdict"]] += 1
            rows.append({"commission_id": d["commission_id"], "label": label,
                         "response_id": d["id"],
                         "response_tabled": d["tabled_senate"] or d["tabled_house"],
                         "response_url": d["url"], **got})
        counts.append({"commission_id": d["commission_id"], "response_id": d["id"],
                       "grammar": grammar, "recommendations": len(labels),
                       **{k: tally[k] for k in STATES},
                       **{k: tally[k] for k in ("accepted", "in part or in principle",
                                                "not accepted")}})
        print(f"{d['commission_id']}: OTD {d['id']} read as {grammar}; "
              + ", ".join(f"{tally[k]} {k}" for k in STATES if tally[k])
              + (" — " + ", ".join(f"{tally[k]} {k}" for k in
                 ("accepted", "in part or in principle", "not accepted") if tally[k])))

    for d in unread:
        print(f"  OTD {d['id']}: no cached text — run harvest_rc_text.py", file=sys.stderr)
    for d in empty:
        print(f"  OTD {d['id']}: no recommendation was found in it by either grammar",
              file=sys.stderr)
    if unread or empty:
        print(f"REFUSING: {len(unread) + len(empty)} responses could not be read",
              file=sys.stderr)
        return 1

    write(OUT, FIELDS, rows)
    write(COUNTS, COUNT_FIELDS, counts)
    print(f"{len(rows)} positions in {OUT.name}; totals in {COUNTS.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
