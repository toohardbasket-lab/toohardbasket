"""Which responses were laid out in a way the text extraction could not follow.

A government response printed in two columns — the committee's recommendation
on the left, the government's answer on the right — comes out of the PDF read
across the columns rather than down them:

    Accepted in-principle. The committee recommends that the The Government is
    committed to deterring Australian Government establish a small wage theft,
    and ensuring that where it does claims tribunal…

Every word of that is genuinely in the document, so verify_recommendations.py
passes it: the row it checks really does appear in the text it names. The
sentence was written by nobody. Nothing else in the pipeline can see it either,
because every other check asks whether the words are the document's, and these
words are.

What gives it away is not any one sentence but the document. A two-column
layout spoils most of a response or none of it, so the question is asked per
document and not per row: where most of a document's recommendations show the
signal, the layout is the cause and every row from it is suspect, including the
ones that happen to read cleanly.

The rows are not withdrawn. The site publishes what the document says and marks
what it cannot vouch for — the same decision taken about bullets that arrive as
the letter "e". A quotation a reader can see is wrong, beside a note saying so
and a link to the PDF, is worth more than a silent gap. It is also the only
form of this that is checkable.

Run:  python layout_check.py
Out:  data/layout_suspect.csv, data/layout_suspect.json
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
import extract_recommendations as E  # noqa: E402

# A document is called suspect on two conditions together. The share alone is
# no use: a response with one recommendation is at 100 per cent the moment that
# one row is flagged, which says nothing about its layout. The count alone is no
# use either: a long response can carry three odd rows and be perfectly laid out.
LEAST_ROWS = 3
LEAST_SHARE = 0.5


# A signal before the committee starts speaking is not a splice. Many reports
# print a short heading above each recommendation — "Wage-setting practices",
# "National Construction Industry Forum" — and the layout runs it into the
# sentence below, so the quotation opens with the document's own heading. Untidy,
# and not wrong: the words are the document's and they are about that
# recommendation. Trimming them would mean guessing where a heading ends.
#
# A column break is different. It lands INSIDE the committee's sentence, after
# it has begun:
#
#     The committee recommends that the The Government is committed to
#     deterring Australian Government establish a small wage theft…
#
# So the test is not how far into the text the signal falls but which side of
# the committee's opening words it falls on. Position alone was tried first and
# got both ends wrong: it excused the two heading run-ins and it excused the one
# document that is genuinely unreadable, whose splices start early.
# Where the committee's own sentence begins. Not every report writes "The
# Committee recommends" — many put the demand straight into the imperative,
# "The Australian Government should actively monitor wage-setting practices" —
# and the heading sits above that just the same.
SENTENCE_END = re.compile(r"[.!?]\s+$")
SUBORDINATE = re.compile(r"\b(?:after|before|when|where|whereby|while|if|unless|until|once|"
                         r"although|though|because|since|as\s+soon\s+as|provided|that)\s+$",
                         re.I)

OPENS = re.compile(r"\bthe\s+(?:committee|sub-committee)\s+recommends?\b"
                   r"|\bcommittee(?:'s|’s)?\s+recommendation\b"
                   r"|\bthe\s+(?:australian\s+)?government\s+"
                   r"(?:should|must|consider|establish|amend|introduce|review|ensure|provide)\b"
                   r"|\bthat\s+the\s+(?:australian\s+)?government\b", re.I)


def suspect(text: str) -> str:
    """Why this row looks like text read across a column break, or ''."""
    opener = OPENS.search(text)
    floor = opener.end() if opener else 0

    def inside(m):
        return bool(m) and m.start() >= floor

    if inside(E.SPLICE.search(text)):
        return "an article or preposition followed by a word that can only start a sentence"
    if inside(E.SPLICE_SENTENCE.search(text)):
        return "a sentence beginning where no full stop introduced it"
    for m in E.GOV_REPORTING.finditer(text):
        if not inside(m):
            continue
        before = text[max(0, m.start() - 40):m.start()]
        # A full stop before it is a sentence boundary, so this is the
        # government's answer left on the end of the committee's words — a split
        # in the wrong place, which is a different fault with its own rule, not
        # a column read across.
        if SENTENCE_END.search(before):
            continue
        # "…as soon as practicable after the Australian Government is informed of
        # a proposed amendment, it publish the advice" is one sentence the
        # committee wrote. A subordinating conjunction in front of it is the tell.
        if SUBORDINATE.search(before):
            continue
        return "the government reporting what it did, inside the committee's words"
    return ""


def main() -> int:
    path = DATA / "recommendations.csv"
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["source"] == "response"]

    flagged: dict[str, list[dict]] = collections.defaultdict(list)
    total = collections.Counter()
    for r in rows:
        total[r["source_id"]] += 1
        why = suspect(r["recommendation"])
        if why:
            flagged[r["source_id"]].append({"label": r["label"], "why": why})

    documents = []
    for doc, hits in sorted(flagged.items(), key=lambda kv: -len(kv[1])):
        share = len(hits) / total[doc]
        if len(hits) >= LEAST_ROWS and share >= LEAST_SHARE:
            first = next(r for r in rows if r["source_id"] == doc)
            documents.append({"document": doc, "flagged": len(hits),
                              "rows": total[doc], "share": round(share, 3),
                              "title": first["document_title"],
                              "url": first["response_url"]})

    suspect_docs = {d["document"] for d in documents}
    out = []
    for r in rows:
        if r["source_id"] in suspect_docs:
            out.append({
                "document": r["source_id"],
                "label": r["label"],
                "row_itself_flagged": "yes" if suspect(r["recommendation"]) else "",
                "title": r["document_title"],
                "url": r["response_url"],
                "recommendation": " ".join(r["recommendation"].split())[:400],
            })

    with (DATA / "layout_suspect.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["document", "label", "row_itself_flagged",
                                          "title", "url", "recommendation"])
        w.writeheader()
        w.writerows(out)

    # The rows flagged in documents that did NOT meet the test are reported as a
    # number and nothing else. They are one or two odd sentences in an otherwise
    # sound document, and calling a whole response unreliable on that evidence
    # would be the overreach this file exists to avoid.
    elsewhere = sum(len(h) for d, h in flagged.items() if d not in suspect_docs)

    (DATA / "layout_suspect.json").write_text(json.dumps({
        "measured": dt.date.today().isoformat(),
        "least_rows": LEAST_ROWS,
        "least_share": LEAST_SHARE,
        "documents": len(documents),
        "rows_in_those_documents": len(out),
        "rows_flagged_in_those_documents": sum(d["flagged"] for d in documents),
        "rows_flagged_elsewhere": elsewhere,
        "response_rows_read": len(rows),
        "by_document": documents,
    }, indent=2) + "\n", encoding="utf-8")

    print(f"{len(rows)} published recommendations read from responses")
    print(f"{len(documents)} documents the extraction could not follow, "
          f"{len(out)} rows between them:")
    for d in documents:
        print(f"    OTD {d['document']:>6}  {d['flagged']:>3} of {d['rows']:>3} rows flagged")
    print(f"{elsewhere} flagged rows sit in documents that did not meet the test "
          f"({LEAST_ROWS}+ rows and half the document) and are left alone")
    print("wrote layout_suspect.csv and layout_suspect.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
