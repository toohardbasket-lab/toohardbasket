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
#
# Three forms, and the second is the one that was missing. Many responses answer
# with a bare verdict — "Supported.", "Agreed in principle.", "Noted" — before
# any prose, so a handover that only knew the sentence forms left the verdict
# and the whole answer sitting inside the committee's recommendation. 385 rows
# ended in a government verdict word, and the page then told the reader the
# response recorded no separate words for it, which was false.
#
# The sentence forms are now anchored to a sentence start. Unanchored, a
# committee recommendation containing "…to ensure that the government has a
# complete picture" was split at "the government has", and the rest of what the
# committee asked for was published as the government's answer.
HANDOVER = re.compile(
    r"(^\s*(?:australian\s+)?government(?:'s|’s)?\s+response\b"
    r"|(?:^|(?<=[.;:!?])\s{1,3})(?:australian\s+)?government(?:'s|’s)?\s+response\b"
    r"|^\s*response\s*:"
    r"|(?:^|(?<=[.;:!?])\s{1,3})the\s+government\s+(?:notes|accepts|accepted|agrees|"
    r"agreed|supports|supported|does\s+not|will|has)\b"
    r"|(?:^|(?<=[.;:!?])\s{1,3})(?:not\s+)?(?:agreed|noted|supported|accepted|"
    r"partially\s+(?:agreed|supported))(?:\s+in\s+(?:principle|part))?\s*[.\n]"
    r")", re.I | re.M)

# A label the split leaves at the head of the government's words.
GOV_LABEL = re.compile(r"^\s*(?:australian\s+)?government(?:'s|’s)?\s+response\s*[:.\-–—]?\s*"
                       r"|^\s*response\s*[:.\-–—]\s*", re.I)

# A recommendation that still ends in the government's verdict has been split in
# the wrong place; publishing it would put the answer inside the question.
ENDS_IN_VERDICT = re.compile(
    r"\b(?:not\s+)?(?:agreed|noted|supported|accepted|partially\s+(?:agreed|supported))"
    r"(?:\s+in\s+(?:principle|part))?\s*\.?\s*$", re.I)
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
# The party may be named without the word "Senators" — "The Australian Greens
# recommend…" is how sixty rows in this corpus open — and the House says
# "Members". Requiring "Senators" left 60 Greens recommendations published as
# committees'. The heading forms also appear either way round: "Coalition
# Senators' Additional Comments" and "Additional Comments - Coalition Senators".
PARTY = (r"(?:the\s+)?(?:ALP|Labor|Coalition|Liberal|Nationals?|Greens|"
         r"Australian\s+Greens|One\s+Nation|Opposition|Government)"
         r"(?:\s+(?:Senators?|Members?|Party))?")
DISSENT = re.compile(
    rf"\b({PARTY}\s+(?:Senators?|Members?)?\s*recommends?\b"
    rf"|{PARTY}\s+(?:Senators?|Members?)\b"
    r"|Senator\s+[A-Z][a-z]+"
    r"|dissenting\s+(?:report|recommendation)|minority\s+report"
    r"|additional\s+(?:comments|remarks))", re.I)
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


# How far above a recommendation to look for the heading that names its author.
# The author patterns match the phrase that names the author, and that phrase
# often carries the verb it was found by — "the Australian Greens recommend".
# What is published is the author, not the sentence, so the verb and the
# leading article come off. Broadening the patterns to catch "the Greens
# recommend" (they had required the word "Senators", and missed sixty rows)
# is what made this necessary.
_AUTHOR_TAIL = re.compile(r"\s+(?:recommends?|recommended|proposed?|made)\s*$", re.I)
_AUTHOR_HEAD = re.compile(r"^\s*the\s+", re.I)


def author_label(phrase: str) -> str:
    """Normalise a matched author phrase to the name alone."""
    s = re.sub(r"\s+", " ", phrase or "").strip()
    s = _AUTHOR_TAIL.sub("", s)
    s = _AUTHOR_HEAD.sub("", s)
    return s.strip(" ,;:—–-")


HEADING_WINDOW = 250

# A label mentioned inside a sentence — "...recommendation 7 from the Tax
# dispute inquiry report and recommends that..." — is a cross-reference, not
# the heading of a recommendation being quoted. A real one follows the end of
# something: a full stop, a bullet, a line break, or the start of the document.
MID_SENTENCE = re.compile(r"[a-z,;(]\s*$")


def is_heading(body: str, start: int) -> bool:
    return not MID_SENTENCE.search(body[max(0, start - 60):start])


dropped: collections.Counter = collections.Counter()


def recommendations_in(body: str) -> dict[str, tuple[str, str]]:
    """Recommendation number -> (what the committee asked, what the government said).

    Where a label appears more than once — a contents entry, a summary table and
    the body — the SHORTEST usable quotation is kept. The longest runs on into
    whatever follows it, which would import the government's argument into the
    committee's words.
    """
    marks = [(m.group(1), m.start(), m.end()) for m in LABEL.finditer(body)]
    best: dict[str, tuple[str, str, str]] = {}
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
        said = tidy(GOV_LABEL.sub("", raw_said.strip()))[:GOV_CHARS]
        if not (MIN_CHARS <= len(asked) <= MAX_CHARS):
            continue
        # The split failed if the government's verdict is still inside the
        # committee's words, or its answer begins mid-sentence. Publishing
        # either misrepresents who said what, so the row is dropped and
        # counted rather than shown.
        if ENDS_IN_VERDICT.search(asked):
            dropped["the government's verdict is inside the recommendation"] += 1
            continue
        if said and said[0].islower():
            dropped["the government's words begin mid-sentence"] += 1
            continue
        if not SAYS_RECOMMEND.search(asked) or looks_extracted_badly(asked):
            continue
        # Who is speaking. The recommendation's own words first, then the
        # heading above it: a dissent often announces itself once — "Dissenting
        # Recommendation - Senator Babet - Recommendation 10" — and says nothing
        # about its author in the recommendation itself.
        named = DISSENT.search(asked) or DISSENT.search(body[max(0, start - HEADING_WINDOW):start])
        author = author_label(named.group(1)) if named else ""

        keep = best.get(label)
        # A dissent restarts its numbering, so one document holds two
        # "Recommendation 1". The committee's takes the number outright;
        # length decides only between candidates of the same authorship.
        if keep is None:
            better = True
        elif bool(keep[2]) != bool(author):
            better = not author
        else:
            better = len(asked) < len(keep[0])
        if better:
            best[label] = (asked, "" if looks_extracted_badly(said) else said, author)
    return best


# Some documents mark a dissent only in prose — "The Australian Greens made a
# further 22 recommendations" — with no heading above the recommendations
# themselves and nothing in their wording. No per-row test can reach those. What
# can be said is that the document contains recommendations that are not the
# committee's, and the page says so on every row from it, so a reader is never
# told a document is unanimous when it is not.
DOC_HAS_OTHERS = re.compile(
    rf"{PARTY}\s+(?:Senators?|Members?)?\s*(?:made|make|recommends?|proposed?)"
    r"|dissenting\s+(?:report|recommendation)|minority\s+report"
    r"|additional\s+(?:comments|recommendations)", re.I)


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
        body = text_for(d["id"])
        others = bool(DOC_HAS_OTHERS.search(body))
        found = recommendations_in(body)
        if not found:
            empty += 1
            continue
        for label, (asked, said, author) in sorted(
                found.items(), key=lambda kv: [int(p) for p in kv[0].split(".")]):
            rows.append({
                "source": "response",
                "source_id": d["id"],
                "label": label,
                "recommended_by": author,
                "document_has_other_authors": "yes" if others else "",
                "recommendation": asked,
                "government_words": said,
                "response_classification": d["classification"],
                "committee": committee_from(d["title"]),
                "department": d["author"] or "",
                "document_title": d["title"],
                "tabled": d["tabled_senate"] or d["tabled_house"],
                "chamber": "senate" if d["tabled_senate"] else "house",
                "url": d["url"],
                # How the document behind this row was obtained. Empty means the
                # ordinary route: fetched from the Parliament's Tabled Documents
                # API by the weekly job. The only other value marks a report
                # collected by hand because that register holds nothing before
                # 2022 — see harvest_manual_reports.py. It is carried into the
                # published data so the provenance of every row is checkable.
                "collection": "",
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
    if dropped:
        print("  not published, because the split could not be trusted:")
        for why, n in dropped.most_common():
            print(f"      {n:>5}  {why}")
    docs_others = len({r["source_id"] for r in rows if r["document_has_other_authors"]})
    print(f"  {docs_others} documents also contain dissenting, minority or additional "
          "recommendations, flagged at the document level")
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
