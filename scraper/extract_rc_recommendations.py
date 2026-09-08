"""extract_rc_recommendations.py — what a royal commission recommended, in its words.

The committee register reads recommendations out of the government's response,
because the committee's own report is usually unreachable. Royal commissions
are the other way round: the report is tabled, so the recommendation is taken
from the commission itself and the government's answer is a separate question.

How a royal commission prints a recommendation, and why the existing report
step reads nothing:

    Recommendation 10.1: Design policies and processes with emphasis on the
    Services Australia design its policies and processes with a primary...

    Recommendation 6.31 Embed the right to equitable access to health services
    a) The Australian Commission on Safety and Quality in Health Care should:

extract_report_recommendations.py expects the number alone on its line, which
is how a Senate committee prints it. Both of these put the number and the
recommendation's own heading on one line, with or without a colon, so that step
finds nothing at all in either report.

The heading is separated from the recommendation, and the report itself says
where the line falls. In print the two are told apart by type and by nothing
else: Robodebt sets a heading in Calibri-Bold above a Calibri body of the same
size, and the Disability report sets one in DINPro-Medium 13pt above an Arial
11pt body. Plain text throws that away, which is why the first version of this
file ran them together — "Review and update of disability strategies and plans
State and territory governments should review and update their..." — and no
punctuation rule can recover it, because a heading wraps onto a second line as
often as not and carries no full stop either way.

So harvest_rc_text.py keeps the typography beside the text, one row per line,
and the heading is the run of lines set the way the label line is set. No font
is named anywhere in this file: the rule is that a heading is whatever the
label is set in, and the recommendation begins where that changes. Where the
sidecar is missing, or the heading it finds is not where the text begins, the
row keeps the whole block as it did before and the heading column is empty —
the split is never guessed at.

Where a recommendation stops:

  * at the next recommendation's heading, which is where 55 of Robodebt's 56
    and 221 of the Disability Royal Commission's 222 stop;
  * or at the report's next section heading, which the typography sidecar
    finds: a heading set in the same face as the recommendation headings and at
    a larger size. That is what ends the last recommendation in a list, and
    nothing in the words themselves says so — Robodebt's 23.8 is followed by
    "Closing observations", which is a heading in print and an ordinary line of
    text once the type is thrown away;
  * or at the first thing the report names after its list — Glossary, Appendix,
    Contents, a chapter or a volume — which is the fallback where there is no
    sidecar;
  * and if none of those is found before MAX_CHARS, the row is written with no
    text and a note saying its boundary could not be found. It is not guessed
    at and it is not dropped.

Where a number appears more than once — a contents page, the list at the front,
the chapter that argues for it — the shortest usable text is kept, as the
committee side already does: the longest runs on into the argument.

Counts are checked against the report's own. Robodebt says it makes 57 and
prints 56; that disagreement is recorded, in both directions, and neither
number is adopted.

    python3 extract_rc_recommendations.py
    python3 extract_rc_recommendations.py --commission robodebt

Reads  data/rc_documents.csv and raw/rc_text/
Writes data/rc_recommendations.csv        one row per recommendation
       data/rc_recommendation_counts.csv  what was found against what is stated
"""
from __future__ import annotations

import bisect
import csv
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "rc_text"
DOCUMENTS = DATA / "rc_documents.csv"
COMMISSIONS = DATA / "royal_commissions.csv"
OUT = DATA / "rc_recommendations.csv"
COUNTS = DATA / "rc_recommendation_counts.csv"

# The label and the recommendation's own heading, on one line. Reports do this
# three ways and which one a report uses is read from the report rather than
# configured, because getting it wrong either way is silent. Robodebt and the
# Disability Royal Commission number by chapter — "Recommendation 20.5:
# Administrative Review Council". Defence and Veteran Suicide numbers straight
# through — "Recommendation 61: Establish a brain injury program". The Royal
# Commission on Antisemitism and Social Cohesion gives its recommendations no
# titles at all: "Recommendation 1" on a line of its own, and the
# recommendation underneath.
#
# Reading them all at once is not an option. A bare number is a citation of
# somebody else's numbering in the first two reports — the Defence interim
# report cites the Productivity Commission's three times — and a line carrying
# nothing but a number is common enough that admitting it everywhere put five
# of the Disability report's headings under the wrong text.
# A title never begins in lower case, or with the punctuation that closes a
# bracket or a clause. What does is a sentence the page broke before a number:
# "The Government will consider / Recommendation 7.26 as part of its review",
# "should support / Recommendation 72 by expanding its efforts", "against
# culture, health and wellbeing targets (see / Recommendation 11) as part of
# the check". Read as headings, the first two put a heading over the wrong
# words and the third ended a recommendation before its own answer.
SHAPES = (
    ("numbered by chapter", r"(\d{1,3}\.\d{1,3})[ \t]*:?[ \t]+(?![a-z.)\],;])(\S.*)"),
    ("numbered straight through", r"(\d{1,3})[ \t]*:?[ \t]+(?![a-z.)\],;])(\S.*)"),
    ("numbered straight through, with no titles", r"(\d{1,3})[ \t]*()"),
)


def head_pattern(shape: str) -> "re.Pattern[str]":
    return re.compile(r"(?m)^[ \t]*Recommendation[ \t]+" + shape + r"$")


HEAD = head_pattern(SHAPES[0][1])

# A contents entry prints its leaders where the title would be. Those are not
# titles, and a report whose only titles are leaders has no titles.
LEADERS = re.compile(r"[.…]{6,}")


def head_in(body: str) -> "re.Pattern[str]":
    """How this report heads its recommendations, counted rather than assumed.

    Whichever shape heads more of them, not counting the contents page. It is
    not close in any report read so far: robodebt 56 by chapter against 1
    straight through, the Disability report 222 against none, the Defence and
    Veteran Suicide interim report 3 against 13, its final report none against
    122, and the Antisemitism report none of either against 14 untitled.
    """
    best, most = HEAD, 0
    for _, shape in SHAPES:
        pattern = head_pattern(shape)
        found = {m.group(1) for m in pattern.finditer(body)
                 if not LEADERS.search(m.group(2) or "")}
        if len(found) > most:
            best, most = pattern, len(found)
    return best


# What a report names after its recommendations. Generic on purpose: a list of
# one report's own section headings would not survive the next report.
END = re.compile(r"\n[ \t]*(Glossary|Glossaries|Appendix\b|Appendices|Annexure|Index\b|"
                 r"Endnotes|Bibliography|Abbreviations|Acronyms|Contents\b|"
                 r"Chapter[ \t]+\d|Volume[ \t]+\d|Part[ \t]+\d|List of [A-Z])")

# Where the report says the recommendation is discussed, printed inside the box
# at the end of it: "(Chapter 13: Oversight of Defence workplace health and
# safety)". It is the report pointing at itself, not part of what was
# recommended, and where the page broke after it the running footer —
# "Recommendations 129" — came along behind it. Eleven of the Defence and
# Veteran Suicide final report's recommendations carried one and ten of those
# carried the footer too; the other 111 had already been cut before it by the
# next section heading, so the same locator was published on some rows and not
# others.
LOCATOR = re.compile(r"\(Chapter\s+\d+:[^)]*\)")

# A paragraph the report numbers: "6.54. In the event of a domestic terrorist
# attack". A recommendation is never one.
NUMBERED_PARAGRAPH = re.compile(r"(?m)^[ \t]*\d{1,2}\.\d{1,3}\.[ \t]")

# A contents page prints its leaders. Nothing else in these reports does.

# The line every page carries, which lands in the middle of a recommendation
# that runs over a page: the commission's name, with the page number before or
# after it — "646 Royal Commission into the Robodebt Scheme", "230 Royal
# Commission into Violence, Abuse, Neglect and Exploitation of People with
# Disability: Final Report". It is built from the commission's own name rather
# than guessed at, so a report this has never seen is no worse off.
def running_head(name: str) -> "re.Pattern[str]":
    title = re.escape(" ".join(name.split()))
    number = r"(?:\d{1,4}|[ivxlcdm]{1,7})"
    return re.compile(rf"\s*(?:{number}\s+)?{title}(?::?\s+Final\s+Report)?(?:\s+{number})?\s*",
                      re.I)

# A heading the report puts between one recommendation and the next — a theme
# in the list at the front, a subheading in the chapter — has no sentence in
# it. Where the text after the last full stop is short and has no sentence
# ending of its own, it belongs to what comes next, not to the recommendation.
TRAILING_HEADING = 80

# The report's own statement of how many recommendations it makes. Each of the
# two reports read so far says it once.
STATED = re.compile(r"(?:list|total)\s+of\s+(\d{1,3})\s+recommendations", re.I)

# Low on purpose. The shortest recommendation in the two reports read so far
# is 85 characters, and a floor set near that would silently drop a shorter
# one. What a contents entry is caught by is its leaders, not its length.
MIN_CHARS, MAX_CHARS = 25, 6000

FIELDS = ["commission_id", "source", "source_id", "label", "heading", "recommendation",
          "report_title", "report_tabled", "report_url", "note"]
COUNT_FIELDS = ["commission_id", "source_id", "found", "stated", "agree", "note"]


def tidy(raw: str, head: "re.Pattern[str] | None" = None) -> str:
    text = raw.replace("\n", " ")
    if head is not None:
        text = head.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    # Drop a trailing fragment with no sentence in it: the next heading, caught
    # because the report does not punctuate its headings.
    end = max(text.rfind(c) for c in ".!?")
    tail = text[end + 1:].strip()
    if end > MIN_CHARS and 0 < len(tail) <= TRAILING_HEADING:
        text = text[:end + 1]
    return text.strip(" .:;-—–•")


def label_key(label: str) -> list[int]:
    """Sort order. A report numbers one way or the other, never both, so a
    one-part key and a two-part key are never compared with each other."""
    return [int(p) for p in label.split(".")]


def recommendations_in(body: str, name: str = "", stops: list[int] | None = None,
                       headings: dict[str, str] | None = None,
                       label_head: "re.Pattern[str] | None" = None) -> dict[str, dict]:
    """label -> {"recommendation", "note"}; the shortest usable text for each.

    Every occurrence of a number is tried. A recommendation ends at the next
    recommendation's heading, or wherever the report next names something —
    both are needed, because the next heading can be a long way off: Robodebt's
    chapters 1 to 9 make no recommendations, so the last entry in the list at
    the front of the report is followed by 1.2 million characters before the
    next heading appears.
    """
    head = running_head(name) if name.strip() else None
    label_head = label_head or head_in(body)
    stops = stops or []
    headings = headings or {}
    marks = [(m.group(1), m.start(), m.end(), m.group(2) or "") for m in label_head.finditer(body)]
    usable: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    for i, (label, start, end, first_line) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        # The report's next section heading, where it comes before the next
        # recommendation. bisect rather than a search per recommendation: the
        # offsets are found once for the document.
        #
        # Not inside the recommendation's own heading, though. A heading that
        # wraps can have a second line the report also uses as a section
        # heading elsewhere — "with disability" is one — and stopping there
        # would cut a recommendation off in the middle of its own title. The
        # heading's words are known, and a newline stands where a space does,
        # so its end is that many characters past the label.
        after_heading = end - len(first_line) + len(headings.get(label, first_line))
        section = bisect.bisect_right(stops, max(start, after_heading))
        if section < len(stops):
            stop = min(stop, stops[section])
        raw = body[start:stop]
        # Take the label off the front; everything after it is the report's.
        raw = (label_head.sub(lambda m: m.group(2) or "", raw, count=1)
               if label_head.match(raw) else raw)
        cut = END.search(raw)
        if cut:
            raw = raw[:cut.start()]
        where = LOCATOR.search(raw)
        if where:
            raw = raw[:where.start()]
        # The leaders are looked for before the text is tidied: tidying takes
        # the trailing dots off, and a contents entry then reads as a very
        # short recommendation rather than as a contents entry.
        contents_entry = bool(LEADERS.search(raw))
        text = tidy(raw, head)
        usable.setdefault(label, [])
        if contents_entry:
            seen.setdefault(label, "only a contents entry was found for it")
        elif len(text) < MIN_CHARS:
            seen.setdefault(label, "the only text found for it was too short to be a "
                            "recommendation")
        elif len(text) > MAX_CHARS:
            seen[label] = ("the report names nothing between this recommendation and what "
                           "follows it, so where it ends could not be read")
        else:
            usable[label].append(text)

    out: dict[str, dict] = {}
    for label, texts in usable.items():
        # The longest runs on into the argument for the recommendation; the
        # shortest is the list at the front, which stops where it stops.
        out[label] = ({"recommendation": min(texts, key=len), "note": ""} if texts
                      else {"recommendation": "", "note": seen.get(label, "it could not be read")})
    return out


# A line of the typography sidecar: the font it is mostly set in, its size in
# points, and its text.
LINE = re.compile(r"^([^\t]*)\t(\d+)\t(.*)$")


def _lines(path: pathlib.Path) -> list[tuple[str, int, str]]:
    """The typography sidecar: font, size in points, and text, per line."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(line)
        if m:
            out.append((m.group(1), int(m.group(2)), m.group(3)))
    return out


def section_headings_in(path: pathlib.Path, label_head: "re.Pattern[str] | None" = None) -> list[str]:
    """The report's own section headings, which is where a recommendation stops.

    A section heading is set in the same face as the recommendation headings and
    in a larger size: Calibri-Bold 16 over Calibri-Bold 11 in Robodebt,
    DINPro-Medium 16 over DINPro-Medium 13 in the Disability report. The face has
    to match as well as the size, or the running footer qualifies — Robodebt sets
    its footer in Calibri 12, larger than the 11pt heading — and every
    recommendation that crosses a page would stop at the bottom of it.
    """
    rows = _lines(path)
    label_head = label_head or HEAD
    styles = {(font, size) for font, size, text in rows if label_head.match(text)}
    if not styles:
        return []
    faces = {font for font, _ in styles}
    biggest = max(size for _, size in styles)
    out, run = set(), []
    for font, size, text in rows + [("", 0, "")]:
        if font in faces and size > biggest and text.strip() and not label_head.match(text):
            run.append(text.strip())
            continue
        if run:
            # The whole heading, its wrap included. A section heading that wraps
            # has a second line like "with disability" or "mainstream services",
            # and those turn up as ordinary wrapped lines in the body of a
            # recommendation; matching one on its own truncated twenty-five of
            # them mid-sentence.
            out.add("\n".join(run))
        run = []
    return sorted(out)


def stops_in(body: str, headings: list[str]) -> list[int]:
    """Where in the text each of those headings is a line of its own, in order.

    A whole line, not a line that begins with one. Robodebt sets the single word
    "Services" as a divider in Calibri-Bold 20, and matching it as a prefix
    stopped a dozen recommendations at the first line of their own text —
    "Services Australia design its policies and processes…".

    A numbered paragraph stops a recommendation too, and for the same reason a
    heading does: it is the report resuming. The Antisemitism report numbers
    every paragraph — "6.54. In the event of a domestic terrorist attack" —
    and sets its section headings no larger than its recommendation labels, so
    the typography says nothing and two recommendations ran on with no end.
    None of the other four documents numbers a paragraph at all, and no
    published recommendation in any of them contains one, so this can only cut
    where the report itself says to.
    """
    offsets: list[int] = [m.start() for m in NUMBERED_PARAGRAPH.finditer(body)]
    for heading in headings:
        needle = "\n" + heading + "\n"
        at = body.find(needle)
        while at != -1:
            offsets.append(at)
            at = body.find(needle, at + 1)
        if body.endswith("\n" + heading):
            offsets.append(len(body) - len(heading) - 1)
    return sorted(offsets)


def headings_in(path: pathlib.Path, label_head: "re.Pattern[str] | None" = None) -> dict[str, str]:
    """label -> the recommendation's own heading, as the report sets it.

    The heading is the label's line and any line after it set the same way. It
    stops at the first line set differently, and at the next recommendation,
    which is set the same way and is not a continuation of this one.
    """
    if not path.exists():
        return {}
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(3)))
    label_head = label_head or HEAD
    out: dict[str, str] = {}
    for i, (font, size, text) in enumerate(rows):
        head = label_head.match(text)
        if not head:
            continue
        parts = [head.group(2) or ""]
        for font2, size2, text2 in rows[i + 1:]:
            if (font2, size2) != (font, size) or label_head.match(text2):
                break
            parts.append(text2)
        heading = " ".join(" ".join(parts).split())
        label = head.group(1)
        # A number is printed twice, and the two headings are the same words;
        # the shorter is the one the page did not break oddly.
        if label not in out or len(heading) < len(out[label]):
            out[label] = heading
    return out


def split_heading(text: str, heading: str) -> tuple[str, str]:
    """The heading and what follows it, where the text does begin with it."""
    if not heading:
        return "", text
    trimmed = heading.strip(" .:;-—–•")
    if text.startswith(trimmed):
        return trimmed, text[len(trimmed):].lstrip(" .:;-—–•")
    return "", text


def stated_total(body: str) -> tuple[str, str]:
    """What the report says it recommends, and a note when it says it twice."""
    found = sorted({m.group(1) for m in STATED.finditer(body)})
    if len(found) == 1:
        return found[0], ""
    if not found:
        return "", "the report does not state how many recommendations it makes"
    return "", f"the report states {' and '.join(found)}; neither is adopted"


def read(path: pathlib.Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    tmp.replace(path)


def files_of(document: dict) -> set[str]:
    """The file ids of this record that carry the recommendations, if it says.

    "yes" means the whole record. A list of file ids means those files: the
    Defence and Veteran Suicide final report is seven volumes on one record and
    the recommendations are all in volume 1.
    """
    carries = (document.get("carries_recommendations") or "").strip()
    return set() if carries in ("", "yes") else {x.strip() for x in carries.split(";") if x.strip()}


def text_for(document: dict) -> str:
    """Every cached file of a document that carries recommendations, joined as
    the document is."""
    wanted = files_of(document)
    parts = [p for p in sorted(TEXT.glob(f"{document['id']}_*.txt"))
             if not wanted or p.stem.split("_", 1)[1] in wanted]
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in parts)


def main(argv: list[str]) -> int:
    wanted = {argv[i + 1] for i, a in enumerate(argv) if a == "--commission"}
    names = {c["commission_id"]: c["name"] for c in read(COMMISSIONS)}
    documents = [d for d in read(DOCUMENTS)
                 if d["role"] == "report" and (d.get("carries_recommendations") or "").strip()
                 and (not wanted or d["commission_id"] in wanted)]
    if not documents:
        print("no report document carries recommendations; nothing to read", file=sys.stderr)
        return 1

    rows, counts, unread = [], [], []
    for d in documents:
        body = text_for(d)
        if not body.strip():
            unread.append(d)
            continue
        label_head = head_in(body)
        headings, sections = {}, []
        wanted = files_of(d)
        for path in sorted(TEXT.glob(f"{d['id']}_*.lines.tsv")):
            if wanted and path.name.split("_", 1)[1].removesuffix(".lines.tsv") not in wanted:
                continue
            headings.update(headings_in(path, label_head))
            sections += section_headings_in(path, label_head)
        found = recommendations_in(body, names.get(d["commission_id"], ""),
                                   stops_in(body, sorted(set(sections))), headings, label_head)
        stated, note = stated_total(body)
        unsplit = 0
        for label in sorted(found, key=label_key):
            heading, text = split_heading(found[label]["recommendation"],
                                          headings.get(label, ""))
            if found[label]["recommendation"] and not heading:
                unsplit += 1
            rows.append({
                "commission_id": d["commission_id"], "source": "report", "source_id": d["id"],
                "label": label, "heading": heading, "recommendation": text,
                "report_title": d["title"], "report_tabled": d["tabled_senate"] or d["tabled_house"],
                "report_url": d["url"], "note": found[label]["note"],
            })
        agree = "yes" if stated and str(len(found)) == stated else "no" if stated else ""
        counts.append({"commission_id": d["commission_id"], "source_id": d["id"],
                       "found": len(found), "stated": stated, "agree": agree, "note": note})
        unreadable = sum(1 for label in found if not found[label]["recommendation"])
        print(f"{d['commission_id']}: {len(found)} recommendations from OTD {d['id']}"
              + (f", the report states {stated}" if stated else f" — {note}")
              + (f" — THEY DISAGREE by {abs(len(found) - int(stated))}" if agree == "no" else "")
              + (f"; {unreadable} whose end could not be read" if unreadable else "")
              + (f"; {unsplit} whose heading could not be told from the text" if unsplit else ""))

    for d in unread:
        print(f"  OTD {d['id']}: no cached text — run harvest_rc_text.py", file=sys.stderr)
    if unread:
        print(f"REFUSING: {len(unread)} report documents have not been read", file=sys.stderr)
        return 1
    if not rows:
        print("REFUSING: no recommendations extracted from any report", file=sys.stderr)
        return 1

    write(OUT, FIELDS, rows)
    write(COUNTS, COUNT_FIELDS, counts)
    print(f"{len(rows)} recommendations in {OUT.name}; counts in {COUNTS.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
