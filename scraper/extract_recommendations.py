"""Every recommendation a government response quotes, with what it said back.

The point of this file is a searchable index: type "domestic violence" and see
the recommendations a committee actually made on it, and — in the government's
own words, not ours — what became of each one.

Where the text comes from, and why it is trustworthy:

A government response quotes the committee's recommendation and then answers
it. So the recommendation text is IN the response document. That matters,
because the obvious route — go to the committee's report — is closed: the
Tabled Documents system's own report-to-response links reach one response in
two hundred and sixty, and matching by title finds a confident report for six.
Reading the response instead needs no link at all.

The trade is provenance. This is the recommendation as the GOVERNMENT
reproduced it, not as the committee wrote it. For a reader that is arguably
the stronger version — it is the department's own transcription — but the site
must say so, and does.

What a row is: one recommendation, its number, the text the response quotes,
the government's words about it, and the document both came from. No status
label is invented. A reader who wants to know what happened to a recommendation
reads the sentence the government wrote about it.
"""
from __future__ import annotations

import collections
import csv
import pathlib
import re

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "otd_text"
OUT = DATA / "recommendations.csv"

# "Recommendation 7", "Recommendation 3.2", "Recommendation No. 4:".
LABEL = re.compile(r"\bRecommendation\s*(?:no\.?\s*)?(\d{1,3}(?:\.\d{1,3})?)\b\s*:?", re.I)
# Where the quoted recommendation stops and the government starts talking.
HANDOVER = re.compile(
    r"((?:australian\s+)?government(?:'s|’s)?\s+response|^\s*response\s*:|"
    r"the\s+government\s+(?:notes|accepts|accepted|agrees|agreed|supports|supported|"
    r"does\s+not|will|has))", re.I | re.M)
# A contents page, not a recommendation.
LEADERS = re.compile(r"[.…]{6,}")
SAYS_RECOMMEND = re.compile(r"\brecommend", re.I)
# pdfplumber sometimes breaks words apart: "do es not su pport", "The C ommittee".
# A stray single letter is the tell; "a" and "I" are the only real ones in English.
# A list marker — "a.", "(b)", "c)" — is a stray single letter that belongs
# there, so it is not evidence of a broken extraction.
LIST_MARKER = re.compile(r"(?<![\w'’])\(?[a-h]\)?[.)]")
STRAY = re.compile(r"(?<![\w'’])[B-HJ-Zb-hj-z](?![\w'’])")
# The report's own paragraph number, printed before the recommendation.
PARA_NO = re.compile(r"^\d{1,2}\.\d{1,3}\s+")
# Some documents print the number again immediately after the heading: "20:".
REPEAT_NO = re.compile(r"^\d{1,3}(?:\.\d{1,3})?\s*[:.]\s+")

# Not every recommendation in a report is the committee's. Dissenting reports,
# minority reports and additional comments carry their own, and attributing a
# party's recommendation to a committee would be a serious misstatement — the
# maritime response closed one from a dissenting report. Where the quoted text
# names its author, that is recorded and the site says so.
DISSENT = re.compile(
    r"\b((?:ALP|Labor|Coalition|Liberal|National|Greens|Opposition|Government)\s+"
    r"Senators?|Senator\s+[A-Z][a-z]+|dissenting\s+report|minority\s+report|"
    r"additional\s+comments)\b", re.I)
# A bare label left dangling at the end by the split, or a lone footnote number.
TRAILING = re.compile(r"(\s+(Response|Government\s+response|Australian\s+Government"
                      r"\s+response)\s*:?\s*|\s+\d{1,3})\s*$", re.I)
# Where the government's answer plainly ends and the document moves on.
GOV_END = re.compile(r"(Response\s+to\s+the\s+recommendations?|Recommendation\s+\d|"
                     r"^\s*(Chapter|Appendix|Attachment)\s+\d)", re.I | re.M)

MIN_CHARS, MAX_CHARS = 60, 2000

# The committee is in the response's title, not its author field — the author
# is the department that wrote the answer. Calling a department a committee
# would attribute the recommendation to the body that declined it.
COMMITTEE = re.compile(
    r"response(?:s)?\s+to\s+(?:the\s+)?(.*?)\s*(?:\breport\b|\binquiry\b|:|$)", re.I)
COMMITTEE_WORD = re.compile(r"committee|commission", re.I)


def committee_from(title: str) -> str:
    m = COMMITTEE.search(title or "")
    if not m:
        return ""
    name = re.sub(r"\s+", " ", m.group(1)).strip(" ,:–—-")
    if not COMMITTEE_WORD.search(name) or len(name) > 120:
        return ""
    return name
GOV_CHARS = 900


def tidy(s: str) -> str:
    """Normalise the whitespace and take off what the page layout left behind.

    The paragraph number is the report's, not part of what was recommended, and
    a trailing "Response" is the label of the next block that the split caught.
    Everything between them is left exactly as the document has it.
    """
    s = re.sub(r"\s+", " ", s).strip(" .:;-—–•")
    s = REPEAT_NO.sub("", PARA_NO.sub("", s))
    for _ in range(3):
        trimmed = TRAILING.sub("", s).strip(" .:;-—–•")
        if trimmed == s:
            break
        s = trimmed
    return s


def looks_extracted_badly(s: str) -> bool:
    """True when the text is an artefact rather than a sentence.

    Broken words are the tell that matters: a PDF that returns "The C ommittee"
    has mangled the rest too, and a mangled quotation of what a committee asked
    for is worse than no quotation. Two stray single letters is the threshold —
    one can be a list marker or an initial.
    """
    return bool(LEADERS.search(s)) or len(STRAY.findall(LIST_MARKER.sub(" ", s))) >= 2


# A label mentioned inside a sentence — "...recommendation 7 from the Tax
# dispute inquiry report and recommends that..." — is a cross-reference, not
# the heading of a recommendation being quoted. A real one follows the end of
# something: a full stop, a bullet, a line break, or the start of the document.
MID_SENTENCE = re.compile(r"[a-z,;(]\s*$")


def is_heading(body: str, start: int) -> bool:
    return not MID_SENTENCE.search(body[max(0, start - 60):start])


def recommendations_in(body: str) -> dict[str, tuple[str, str]]:
    """Recommendation number -> (what the committee asked, what the government said).

    Where a label appears more than once — a contents entry, a summary table and
    the body — the SHORTEST usable quotation is kept. The longest runs on into
    whatever follows it, which would import the government's argument into the
    committee's words.
    """
    marks = [(m.group(1), m.start(), m.end()) for m in LABEL.finditer(body)]
    best: dict[str, tuple[str, str]] = {}
    for i, (label, start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        segment = body[end:stop]
        if not is_heading(body, start):
            continue
        hand = HANDOVER.search(segment)
        asked = tidy(segment[:hand.start()] if hand else segment)
        # From the START of the handover, not the end: cutting after it leaves
        # "committed to establish..." where the government wrote "The Government
        # is committed to establish...".
        raw_said = segment[hand.start():] if hand else ""
        stop_at = GOV_END.search(raw_said, 1)
        if stop_at:
            raw_said = raw_said[:stop_at.start()]
        said = tidy(raw_said)[:GOV_CHARS]
        if not (MIN_CHARS <= len(asked) <= MAX_CHARS):
            continue
        if not SAYS_RECOMMEND.search(asked) or looks_extracted_badly(asked):
            continue
        if label not in best or len(asked) < len(best[label][0]):
            best[label] = (asked, "" if looks_extracted_badly(said) else said)
    return best


def text_for(doc_id: str) -> str:
    files = sorted(TEXT.glob(f"{doc_id}_*.txt"))
    if not files:
        return ""
    return re.sub(r"[ \t]+", " ", files[0].read_text(encoding="utf-8", errors="replace"))


def main() -> int:
    excluded = {r["id"] for r in csv.DictReader(
        open(DATA / "scope_exclusions.csv", encoding="utf-8-sig"))}
    docs = [r for r in csv.DictReader(
        open(DATA / "response_documents.csv", encoding="utf-8-sig"))
        if r["id"] not in excluded]

    rows, empty = [], 0
    for d in docs:
        found = recommendations_in(text_for(d["id"]))
        if not found:
            empty += 1
            continue
        for label, (asked, said) in sorted(
                found.items(), key=lambda kv: [int(p) for p in kv[0].split(".")]):
            author = DISSENT.search(asked)
            rows.append({
                "source": "response",
                "source_id": d["id"],
                "label": label,
                "recommended_by": author.group(1) if author else "",
                "recommendation": asked,
                "government_words": said,
                "response_classification": d["classification"],
                "committee": committee_from(d["title"]),
                "department": d["author"] or "",
                "document_title": d["title"],
                "tabled": d["tabled_senate"] or d["tabled_house"],
                "chamber": "senate" if d["tabled_senate"] else "house",
                "url": d["url"],
            })

    if not rows:
        print("REFUSING: no recommendations extracted at all")
        return 1
    rows.sort(key=lambda r: (int(r["source_id"]), [int(p) for p in r["label"].split(".")]))
    tmp = OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    tmp.replace(OUT)

    per = collections.Counter(r["response_classification"] for r in rows)
    docs_with = len({r["source_id"] for r in rows})
    print(f"{len(rows)} recommendations from {docs_with} of {len(docs)} response documents")
    for k, v in per.most_common():
        print(f"  {k:<18} {v:>5}")
    named = sum(1 for r in rows if r["committee"])
    print(f"  {named} name the committee that made them ({named/len(rows)*100:.0f}%)")
    flagged = sum(1 for r in rows if r["recommended_by"])
    print(f"  {flagged} name a dissenting, minority or party author rather than the committee")
    with_gov = sum(1 for r in rows if r["government_words"])
    print(f"  {with_gov} carry the government's own words ({with_gov/len(rows)*100:.0f}%)")
    print(f"  {empty} documents yielded none")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
