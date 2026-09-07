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

The heading is not separated from the recommendation here. In the report the
two are told apart by weight — the heading is bold — and a plain text
extraction cannot see weight. A heading also wraps onto the next line often
enough that no punctuation rule tells where it ends. So the row carries what
the report prints, heading and all, rather than a split that would sometimes
cut a recommendation in half.

Where a recommendation stops:

  * at the next recommendation's heading, which is where 55 of Robodebt's 56
    and 221 of the Disability Royal Commission's 222 stop;
  * or, for the last one in a document, at the first thing the report names
    after its list — Glossary, Appendix, Contents, a chapter or a volume;
  * and if neither of those is found before MAX_CHARS, the row is written with
    no text and a note saying its boundary could not be found. It is not
    guessed at and it is not dropped.

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

# The label and the recommendation's own heading, on one line. The chapter
# number is required: a bare "Recommendation 28" in this corpus is a citation
# of another commission's report, and the Disability final report carries two.
HEAD = re.compile(r"(?m)^[ \t]*Recommendation[ \t]+(\d{1,3}\.\d{1,3})[ \t]*:?[ \t]+(\S.*)$")

# What a report names after its recommendations. Generic on purpose: a list of
# one report's own section headings would not survive the next report.
END = re.compile(r"\n[ \t]*(Glossary|Glossaries|Appendix\b|Appendices|Annexure|Index\b|"
                 r"Endnotes|Bibliography|Abbreviations|Acronyms|Contents\b|"
                 r"Chapter[ \t]+\d|Volume[ \t]+\d|Part[ \t]+\d|List of [A-Z])")

# A contents page prints its leaders. Nothing else in these reports does.
LEADERS = re.compile(r"[.…]{6,}")

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

FIELDS = ["commission_id", "source", "source_id", "label", "recommendation",
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
    return [int(p) for p in label.split(".")]


def recommendations_in(body: str, name: str = "") -> dict[str, dict]:
    """label -> {"recommendation", "note"}; the shortest usable text for each.

    Every occurrence of a number is tried. A recommendation ends at the next
    recommendation's heading, or wherever the report next names something —
    both are needed, because the next heading can be a long way off: Robodebt's
    chapters 1 to 9 make no recommendations, so the last entry in the list at
    the front of the report is followed by 1.2 million characters before the
    next heading appears.
    """
    head = running_head(name) if name.strip() else None
    marks = [(m.group(1), m.start(), m.end()) for m in HEAD.finditer(body)]
    usable: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    for i, (label, start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        raw = body[start:stop]
        # Take the label off the front; everything after it is the report's.
        raw = re.sub(r"^[ \t]*Recommendation[ \t]+\d{1,3}\.\d{1,3}[ \t]*:?[ \t]*", "", raw)
        cut = END.search(raw)
        if cut:
            raw = raw[:cut.start()]
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


def text_for(document: dict) -> str:
    """Every cached file of a document, joined as the document is."""
    parts = sorted(TEXT.glob(f"{document['id']}_*.txt"))
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
        found = recommendations_in(body, names.get(d["commission_id"], ""))
        stated, note = stated_total(body)
        for label in sorted(found, key=label_key):
            rows.append({
                "commission_id": d["commission_id"], "source": "report", "source_id": d["id"],
                "label": label, "recommendation": found[label]["recommendation"],
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
              + (f"; {unreadable} whose end could not be read" if unreadable else ""))

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
