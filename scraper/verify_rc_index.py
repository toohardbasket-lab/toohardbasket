"""Check every published royal commission row back against its own document.

The committee side has verify_recommendations.py and this is the same job for
this index, for the same reason it gives: the failure that matters is not a
garbled quotation, which is visible, but the right words under the wrong
number. A reader who quotes "recommendation 6.31" of a report that numbered it
6.30 has been misled by this site, and nothing on the page would show it.

This index is more exposed to that than the committee one, not less. Three
separate rules decide what text ends up under a number: the shortest of several
occurrences wins, the heading is split off by the type it is set in, and the
recommendation is bounded by the report's next section heading, found the same
way. The count check that runs beside this one only counts — it would not
notice a recommendation carrying its neighbour's words — and the unit tests run
on made-up fixtures rather than on the two reports.

So every row is looked for in the document it names: a distinctive slice of the
recommendation, the row's own heading above that slice, and the row's own label
above that. A row that cannot be found that way is REMOVED and counted, not
flagged, so that what remains is verified by construction.

The government's words are checked the same way, against the heading the
response itself puts over them: its own block, or the block that answers the
range its number falls inside. The government's label has to be stated under
that heading too, as the whole of what the document states and not the opening
of it, because "Accept" printed where the document says "Accept in principle"
is the one misstatement on this side that would matter most.

    python3 verify_rc_index.py --control

is the answer to the obvious objection, that a check written from the same
documents as the extraction will pass whatever the extraction did. It gives
each row a neighbour's number, heading and words and reports how much of that
this refuses. What it does not refuse is worth reading: a few rows the response
answers in one block share their words honestly, and the check cannot tell
those apart from a mistake, so it says how many there were rather than claiming
a clean sweep.

    python3 verify_rc_index.py
    python3 verify_rc_index.py --check     # report, change nothing
    python3 verify_rc_index.py --control   # check the check, change nothing

Reads  data/rc_recommendations.csv, data/rc_positions.csv, raw/rc_text/
Writes both files with the unverified rows removed, plus
       data/rc_index_dropped.csv  every row removed, with the reason
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
POSITIONS = DATA / "rc_positions.csv"
COUNTS = DATA / "rc_recommendation_counts.csv"
COMMISSIONS = DATA / "royal_commissions.csv"
DOCUMENTS = DATA / "rc_documents.csv"
DROPPED = DATA / "rc_index_dropped.csv"

sys.path.insert(0, str(HERE))
from extract_rc_recommendations import running_head   # noqa: E402

LABEL = re.compile(r"Recommendation\s+(\d{1,3}\.\d{1,3})", re.I)
# How far above a slice to look for the label that governs it. A recommendation
# runs to a few thousand characters, so this is the whole of a long one.
LOOKBACK = 4000
# Below this a slice is not distinctive enough to prove anything.
SHORTEST_PROBE = 30

# Where a response document puts the recommendation it is about to answer, on
# a line of its own. The two documents do it two ways: the disability response
# heads each answer "Response to Recommendation 4.22" or, for a range,
# "Response to Recommendations 4.1-4.21"; the robodebt response prints no such
# heading and instead reprints the recommendation under "Recommendation 20.5:
# Administrative Review Council" and answers underneath it. Both forms are
# read, so a prose response gets the same treatment as a block one.
#
# Capitalised, and at the start of a line. The same words appear mid-sentence
# as a cross-reference — "as outlined in response to recommendation 6.6" — and
# where the line happens to break just before one, case is the only thing left
# that tells the two apart. Read case-blind, a sentence in the robodebt
# response manufactured a heading for recommendation 20.5.
HEADING = re.compile(r"^(?:Response to )?Recommendations?\s+(\d{1,3}\.\d{1,3}[^\n]*)", re.M)
# The numbers a heading names, and nothing after them. A title can carry digits
# of its own — "Recommendation 17.1: Amend section 5.1 of the Act" — so the run
# of labels is read from the start of the heading and stops at the first thing
# that is not another label or a separator between two.
LABEL_RUN = re.compile(r"\d{1,3}\.\d{1,3}"
                       r"(?:\s*(?:[,\u2013\u2014-]|and|to)\s*\d{1,3}\.\d{1,3})*")

_cache: dict[str, str] = {}
_lines: dict[str, str] = {}
_titles: dict[str, str] = {}


def source_text(document_id: str, name: str = "") -> str:
    """The document as one line, with its running head taken out.

    The head is removed here for the same reason it is removed from what gets
    published: it is the page's furniture, not the report's words, and it sits
    in the middle of any recommendation that crosses a page. Removing it from
    both sides is what lets the two be compared at all.
    """
    key = f"{document_id}|{name}"
    if key in _cache:
        return _cache[key]
    body = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(TEXT.glob(f"{document_id}_*.txt"))
                     if not p.name.endswith(".lines.tsv"))
    body = re.sub(r"\s+", " ", body)
    if name.strip():
        body = re.sub(r"\s{2,}", " ", running_head(name).sub(" ", body))
    _cache[key] = body
    return body


def probe_of(text: str) -> str:
    """A distinctive slice: the middle of a long row, the end of a short one."""
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[40:200] if len(clean) > 220 else clean[-120:]


def title_of(document_id: str) -> str:
    if not _titles:
        for d in read(DOCUMENTS):
            _titles[d["id"]] = d.get("title", "")
    return _titles.get(document_id, "")


def response_text(document_id: str) -> str:
    """The response with its line breaks kept and its running head taken out.

    Everywhere else in this file the document is flattened to one line, because
    a recommendation that crosses a page break is one sentence and the line
    endings are noise. Here they are the evidence. A block response states its
    verdict on a line of its own — "Response: Accept in principle" — and the
    end of that line is the only thing in the document that says where the
    label stops. Flattened, "Accept" reads as the opening of "Accept in
    principle", and passing that off as the government's word is the single
    misstatement on this side that would matter most.

    The running head goes for the same reason it goes from the report: it is
    the page's furniture, it lands in the middle of any answer that crosses a
    page, and a comparison that left it in one text and not the other would be
    comparing typesetting. Which lines those are is not a judgement this makes
    — it is the document saying its own name, so the lines that begin the way
    the register's title for it begins, printed on at least three pages, come
    out. Written here rather than borrowed from the extractor, so that a fault
    in that rule shows up as a mismatch instead of being agreed to twice.
    """
    if document_id in _lines:
        return _lines[document_id]
    body = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(TEXT.glob(f"{document_id}_*.txt"))
                     if not p.name.endswith(".lines.tsv"))
    body = re.sub(r"[^\S\n]+", " ", body)
    lines = [line.strip() for line in body.split("\n")]
    words = re.sub(r"\[.*?\]", " ", title_of(document_id)).split()
    if len(words) >= 3:
        stem = re.compile(r"\s+".join(re.escape(w) for w in words[:3]), re.I)
        # The page number sits before the head on a left-hand page and after
        # it on a right-hand one; both are the same line.
        number = re.compile(r"^\s*\d{1,4}\s+|\s+\d{1,4}\s*$")
        bare = [number.sub("", line).strip() for line in lines]
        seen = collections.Counter(
            b for b in bare
            if b and len(b) <= 120 and not b.endswith(".") and stem.match(b))
        head = {k for k, n in seen.items() if k and n >= 3}
        lines = [line for line, b in zip(lines, bare) if b not in head]
    body = re.sub(r"\n{2,}", "\n", "\n".join(lines))
    _lines[document_id] = body
    return body


def loosely(text: str) -> re.Pattern:
    """`text`, matched across whatever line breaks the document happens to have."""
    return re.compile(r"\s+".join(re.escape(w) for w in text.split()))


def states_label(segment: str, label: str) -> bool:
    """Does this segment state that verdict, as its own verdict?

    Two things have to hold and each is here for a document that broke without
    it. The verdict follows a colon — the document writes "Response: Accept in
    principle", and where two governments answer apart, "ACT and WA: Accept in
    principle" — so text found in the middle of a sentence is not a verdict.
    And the verdict has to end where the row says it ends: "Accept" is the
    opening of "Accept in principle", and reporting the first as the
    government's word when the document says the second is the one
    misstatement on this side that would matter most. What follows a finished
    verdict is a new sentence; what follows half of one is the rest of it, in
    lower case.

    The verdict itself may be broken over two lines, and one is: the
    disability response sets out "Commonwealth, NSW, QLD, NT, SA, TAS, VIC:
    Subject to / further consideration". So the line ending cannot be the test.
    """
    for m in loosely(label).finditer(segment):
        if not segment[:m.start()].rstrip().endswith(":"):
            continue
        after = segment[m.end():].lstrip()
        if after[:1].islower():
            continue
        return True
    return False


def labels_named(heading: str) -> set[str]:
    """Every recommendation a heading is the answer to, or nothing if it is not
    a heading at all.

    The numbers are written five ways in the disability response — one number,
    "4.1-4.21", "6.6 and 6.7", "6.6 to 6.9", and a comma list — and a range
    stands for every number in it, which is the whole point of it: those
    recommendations have no answer anywhere else.

    What follows the numbers is what says whether this is a heading. A heading
    either stops there, or gives the recommendation's title, which starts with
    a capital or a colon. A sentence that a line break happened to split -
    "The Government will consider / Recommendation 7.26 as part of its review
    of the Disability Discrimination Act" - carries on in lower case, and its
    second line is not a heading however much it looks like one at the start of
    a line.
    """
    run = LABEL_RUN.match(heading.strip())
    if not run:
        return set()
    if heading.strip()[run.end():].lstrip()[:1].islower():
        return set()
    text = run.group(0)
    numbers = re.findall(r"\d{1,3}\.\d{1,3}", text)
    if len(numbers) == 2 and re.search(r"\d\s*(?:[\u2013\u2014-]|to)\s*\d", text):
        (first, low), (second, high) = (tuple(int(x) for x in n.split(".")) for n in numbers)
        if first == second and low <= high:
            return {f"{first}.{n}" for n in range(low, high + 1)}
    return set(numbers)


# A line that carries a block's own particulars rather than its answer:
# "Responsibility: Australian, state and territory governments", "Response:
# Accept", "Joint Response to 6.31 (a): Accept". Short, and opening with a name
# and a colon.
PARTICULAR = re.compile(r"[A-Z][^:\n]{0,60}:")


def is_particular(line: str) -> bool:
    return len(line) < 120 and PARTICULAR.match(line.strip()) is not None


def windows(body: str, label: str) -> list[tuple[int, int]]:
    """The parts of the response that say they are about this recommendation.

    A heading runs to the next one, with one exception that the document
    forces: two headings printed back to back, with nothing between them but
    the particulars, answer together underneath the second. The disability
    response does that for "Response to Recommendations 7.18, 7.19, 7.21, 7.22
    and 7.23" followed immediately by "Response to Recommendation 7.20", where
    six recommendations share one body, and again wherever a block is broken
    into "Recommendation 6.31 (a)" and "(b)". Ending the first window at the
    second heading would put five rows' words outside every window they could
    be in, which is a finding about this file's typesetting, not about the
    government's answer.

    There can be more than one window: the response reprints recommendation 4.1
    under its own heading and then answers it inside "Response to
    Recommendations 4.1-4.21", so both are offered and check_position takes
    whichever holds up.
    """
    heads = [(m.start(), named) for m in HEADING.finditer(body)
             if (named := labels_named(m.group(1)))]
    out = []
    for i, (start, named) in enumerate(heads):
        if label not in named:
            continue
        end, here = len(body), start
        for nxt, _ in heads[i + 1:]:
            between = body[body.index("\n", here) + 1:nxt].split("\n")
            if all(is_particular(line) for line in between if line.strip()):
                here = nxt        # printed back to back; the body below is both answers
                continue
            end = nxt
            break
        out.append((start, end))
    return out


def check_recommendation(row: dict, name: str) -> str:
    body = source_text(row["source_id"], name)
    if not body:
        return "source text missing"
    if not row["recommendation"]:
        return "no text to check"
    probe = probe_of(row["recommendation"])
    if len(probe) < SHORTEST_PROBE:
        return "too short to verify"
    heading = re.sub(r"\s+", " ", row.get("heading") or "").strip()
    want = row["label"]
    seen, start, anywhere, label_matched = [], 0, False, False
    while True:
        at = body.find(probe, start)
        if at < 0:
            break
        anywhere = True
        start = at + 1
        above = body[max(0, at - LOOKBACK):at]
        labels = LABEL.findall(above)
        if not labels:
            continue
        seen.append(labels[-1])
        if labels[-1] != want:
            continue
        label_matched = True
        # The heading the row publishes has to be the one the report puts over
        # these words, not one from further up the page.
        if heading:
            after_label = above[above.rfind(labels[-1]) + len(labels[-1]):]
            if heading not in after_label:
                continue
        return "verified"
    if not anywhere:
        return "text not in the document"
    if not seen:
        return "no label above it"
    # Which failure to report: the number is the one that misleads a reader, so
    # a row whose nearest label is somebody else's is a label failure even
    # though its heading does not fit either.
    if not label_matched:
        return "label does not match"
    return "heading does not sit above the text"


def check_position(row: dict) -> str:
    if row["state"] == "not addressed":
        return "verified"
    body = response_text(row["response_id"])
    if not body:
        return "source text missing"
    # A recommendation answered a lettered part at a time carries one label per
    # part, joined for display. Each has to be the government's own word; the
    # joined string never appears anywhere and checking for it proves nothing.
    labels = [x.strip() for x in (row.get("government_label") or "").split(";") if x.strip()]
    words = probe_of(row.get("government_words") or "")
    if not words:
        return "no words to check"

    here = windows(body, row["label"])
    for lo, hi in (here or [(0, len(body))]):
        segment = body[lo:hi]
        # A prose response states no verdict; its label is a fragment of the
        # sentence it is making — "The Government accepts" — so it is looked
        # for as it stands, and the sentence around it is the check.
        if not all(loosely(label).search(segment)
                   if label.lower().startswith("the government") else states_label(segment, label)
                   for label in labels):
            continue
        if not loosely(words).search(segment):
            continue
        return "verified"

    # Which failure to report. If the words are somewhere in the response but
    # not under this recommendation's own block, they are somebody else's
    # answer, and that is worth saying differently from words the government
    # never wrote.
    if not loosely(words).search(body):
        return "the government's words are not in the document"
    if here and not any(loosely(words).search(body[lo:hi]) for lo, hi in here):
        return "the words sit under another recommendation's heading"
    return "the government's label is not in the document"


def control() -> int:
    """Check the check: hand every row its neighbour's number, heading and words.

    A verifier built from the same two documents as the extractor is open to
    the obvious objection that it will pass whatever the extractor did, and
    passing everything on its first run is what that would look like. So this
    breaks each row in the three ways that matter and counts what survives.
    Nothing here is written down; it is run to be read.
    """
    names = {c["commission_id"]: c["name"] for c in read(COMMISSIONS)}
    recs = read(RECOMMENDATIONS)
    answered = [p for p in read(POSITIONS) if p["state"] != "not addressed"]
    for step in (1, 37):
        pairs = [(a, b) for a, b in zip(recs, recs[step:])
                 if a["commission_id"] == b["commission_id"]]
        for field in ("label", "heading"):
            passed = sum(check_recommendation({**a, field: b[field]},
                                              names.get(a["commission_id"], "")) == "verified"
                         for a, b in pairs)
            print(f"{len(pairs) - passed} of {len(pairs)} recommendations refuse the "
                  f"{field} of the row {step} further on")
        # Rows whose words are word for word a neighbour's are left out: the
        # response really did answer them together, and swapping the two swaps
        # nothing.
        ppairs = [(a, b) for a, b in zip(answered, answered[step:])
                  if a["commission_id"] == b["commission_id"]
                  and b["government_words"] and a["government_words"] != b["government_words"]]
        kept = [(a["commission_id"], a["label"], b["label"]) for a, b in ppairs
                if check_position({**a, "government_words": b["government_words"]}) == "verified"]
        print(f"{len(ppairs) - len(kept)} of {len(ppairs)} positions refuse the government's "
              f"words from the row {step} further on")
        for c, one, other in kept:
            print(f"    kept: {c} {one} passes with {other}'s words")
    return 0


def read(path: pathlib.Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    tmp.replace(path)


def main(argv: list[str]) -> int:
    if "--control" in argv:
        return control()
    check_only = "--check" in argv
    names = {c["commission_id"]: c["name"] for c in read(COMMISSIONS)}
    recs = read(RECOMMENDATIONS)
    positions = read(POSITIONS)
    if not recs:
        print("REFUSING: the index is empty", file=sys.stderr)
        return 1

    tally, kept, dropped = collections.Counter(), [], []
    for r in recs:
        why = check_recommendation(r, names.get(r["commission_id"], ""))
        tally[why] += 1
        (kept if why == "verified" else dropped).append({**r, "part": "recommendation",
                                                         "why": why})
    print(f"{len(recs)} recommendations checked against the reports")
    for why, n in tally.most_common():
        print(f"  {n:>5}  {why}")

    verified = {(r["commission_id"], r["label"]) for r in kept}
    ptally, pkept = collections.Counter(), []
    for p in positions:
        if (p["commission_id"], p["label"]) not in verified:
            dropped.append({**p, "part": "position",
                            "why": "its recommendation was not verified"})
            continue
        why = check_position(p)
        ptally[why] += 1
        (pkept if why == "verified" else dropped).append({**p, "part": "position", "why": why})
    print(f"{len(positions)} positions checked against the responses")
    for why, n in ptally.most_common():
        print(f"  {n:>5}  {why}")

    if not kept:
        print("REFUSING: nothing verified — that is a broken check, not a clean index",
              file=sys.stderr)
        return 1
    share = len(kept) / len(recs)
    if share < 0.9:
        print(f"REFUSING: only {share * 100:.0f}% of recommendations verified. This index is "
              "built from two documents by rules written against them, so anything short of "
              "nearly all of it is a broken rule, not a difficult document.", file=sys.stderr)
        return 1

    if check_only:
        print("--check: nothing written")
        return 0

    write(RECOMMENDATIONS, list(recs[0]), kept)
    write(POSITIONS, list(positions[0]), pkept)
    if dropped:
        fields = sorted({k for d in dropped for k in d}, key=lambda k: (k != "part", k != "why", k))
        write(DROPPED, fields, dropped)
    elif DROPPED.exists():
        DROPPED.unlink()

    # The counts file says what the reports state against what was found; what
    # was found is now what survived this check.
    counts = read(COUNTS) if COUNTS.exists() else []
    if counts:
        by_commission = collections.Counter(r["commission_id"] for r in kept)
        for c in counts:
            c["found"] = by_commission[c["commission_id"]]
            c["agree"] = "yes" if c["stated"] and str(c["found"]) == c["stated"] else (
                "no" if c["stated"] else "")
        write(COUNTS, list(counts[0]) + ([] if "dropped" in counts[0] else ["dropped"]),
              [{**c, "dropped": sum(1 for d in dropped if d["part"] == "recommendation"
                                    and d["commission_id"] == c["commission_id"])}
               for c in counts])
    print(f"{len(kept)} recommendations and {len(pkept)} positions published; "
          f"{len(dropped)} rows removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
