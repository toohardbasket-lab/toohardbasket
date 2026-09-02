"""Recommendations from the reports on the registers — the unanswered ones.

These have no government response to quote them, so the report itself is the
source. A committee report sets its recommendations out twice: a list at the
front, and again as headings in the chapter that argues for each. The two carry
the same words, and the front list is the cleaner one because it stops where
the recommendation stops. Some reports print the label twice in a row as well,
so rather than trusting the order, every heading is read and for each number
the SHORTEST usable text is kept — the longest runs on into the argument, which
would put the chapter's reasoning inside the committee's recommendation.

Dissenting reports, minority reports and additional comments carry their own
recommendations, and a report's back pages are full of them. Where the text or
the surrounding heading names an author other than the committee, that is
recorded, and the site shows it rather than calling it the committee's.

Appends to data/recommendations.csv, which extract_recommendations.py writes
first from the response documents.
"""
from __future__ import annotations

import csv
import pathlib
import re

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "report_text"
OUT = DATA / "recommendations.csv"

HEAD = re.compile(r"^[ \t]*Recommendation[ \t]+(\d{1,3}(?:\.\d{1,3})?)[ \t]*:?[ \t]*$",
                  re.I | re.M)
NOISE = re.compile(r"^\s*(\d{1,4}|[ivxlcIVXLC]{1,7})\s*$", re.M)
PARA_NO = re.compile(r"^\s*\d{1,2}\.\d{1,3}\s+")
# Where a recommendation has plainly ended and the report has moved on.
END = re.compile(r"\n\s*(Chapter\s+\d|CHAPTER\s+\d|List of Recommendations|Contents|"
                 r"Committee\s+View|Appendix\s+\d|Attachment\s+\d|"
                 r"Additional\s+Comments|Dissenting\s+Report|Minority\s+Report|"
                 r"Members\s+of\s+the\s+Committee)\b")
# The sections whose recommendations are not the committee's. Anchored to a
# whole line: the contents page lists "Dissenting Report" too, and matching it
# there put every recommendation in the report inside a dissent it is not in.
# The Senate writes these headings either way round — "Coalition Senators'
# Additional Comments" and "Additional Comments - Coalition Senators" are both
# current house style, and the Aged Care Bill report carries three of the second
# form. Expecting only the first left 23 Coalition recommendations published as
# the committee's.
_PARTY = (r"(?:ALP|Labor|Coalition|Liberal|Nationals?|Greens|Australian\s+Greens|"
          r"One\s+Nation|Opposition|Government)(?:\s+(?:Senators?|Members?|Party))?")
_KIND = (r"Dissenting\s+(?:Report|Recommendations?)|Minority\s+Report|"
         r"Additional\s+(?:Comments|Remarks|Recommendations?)")
SECTION = re.compile(
    rf"^[ \t]*("
    rf"(?:{_PARTY}(?:'|’)?s?\s+)?(?:{_KIND})"        # party first, or bare
    rf"|(?:{_KIND})\s*[-–—:]\s*(?:{_PARTY}|Senator\s+[A-Z][A-Za-z'’-]+)"
    rf"|(?:{_KIND})\s+(?:by|from)\s+(?:{_PARTY}|Senator\s+[A-Z][A-Za-z'’-]+)"
    rf")[ \t]*[-–—:]?[ \t]*(?:Senator\s+[A-Z][A-Za-z'’-]+)?[ \t]*\d*[ \t]*$",
    re.I | re.M)

# A recommendation that names its own author, wherever it sits. The section
# heading is not enough on its own: a report's dissent can begin without a
# heading this recognises, and its recommendations restart at 1, so a party's
# "Recommendation 1" collides with the committee's. The responses side has
# always applied this test; the reports side did not, and three recommendations
# beginning "Coalition Senators recommend" were published as a committee's.
NAMES_AUTHOR = re.compile(
    rf"\b({_PARTY}\s+(?:Senators?|Members?)?\s*recommends?"
    rf"|{_PARTY}\s+(?:Senators?|Members?)"
    r"|Senator\s+[A-Z][a-z]+)\b", re.I)
# Only where it OPENS the recommendation. A dissent says who is speaking before
# it says what it wants — "Coalition Senators note…", "The Australian Greens
# recommend…" — whereas a committee recommendation that happens to mention a
# senator does so further in, and is not a dissent.
AUTHOR_WINDOW = 100

# A report signs off after its recommendations. Everything from the signature
# block on belongs to the document, not to what was recommended.
SIGNOFF = re.compile(r"\b(?:Senator|Mr|Ms|Mrs|Dr|Hon)\.?\s+[A-Z][A-Za-z'’-]+"
                     r"(?:\s+[A-Z][A-Za-z'’-]+){0,3}\s+(?:MP\s+)?"
                     r"(?:Chair|Deputy\s+Chair|Presiding\s+Member)\b")
LEADERS = re.compile(r"[.…]{6,}")
LIST_MARKER = re.compile(r"(?<![\w'’])\(?[a-h]\)?[.)]")
STRAY = re.compile(r"(?<![\w'’])[B-HJ-Zb-hj-z](?![\w'’])")
SAYS_RECOMMEND = re.compile(r"\brecommend|\bshould\b|\bmust\b|\bthat the\b", re.I)

MIN_CHARS, MAX_CHARS = 40, 1500


def tidy(raw: str) -> str:
    cut = END.search(raw)
    if cut:
        raw = raw[:cut.start()]
    sign = SIGNOFF.search(raw)
    if sign:
        raw = raw[:sign.start()]
    raw = NOISE.sub("", raw[:MAX_CHARS * 2])
    raw = PARA_NO.sub("", raw.strip())
    raw = re.sub(r"[ \t]*\n[ \t]*", " ", raw)
    return re.sub(r"\s{2,}", " ", raw).strip(" .:;-—–•")[:MAX_CHARS]


def bad(text: str) -> bool:
    return bool(LEADERS.search(text)) or len(STRAY.findall(LIST_MARKER.sub(" ", text))) >= 2


def author_at(body: str, position: int) -> str:
    """The last dissent or minority heading before this recommendation, if any.

    A report's committee recommendations come first; the dissenting and
    additional sections follow. So the nearest such heading above a
    recommendation is the section it sits in.
    """
    last = None
    for m in SECTION.finditer(body, 0, position):
        last = m
    if last is None:
        return ""
    return author_label(last.group(1))


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
    t = re.sub(r"\s+", " ", phrase or "").strip()
    t = _AUTHOR_TAIL.sub("", t)
    t = _AUTHOR_HEAD.sub("", t)
    return t.strip(" ,;:—–-")


def author_of(text: str, body: str, position: int) -> str:
    """Who made this recommendation, by its own words first and its section second."""
    named = NAMES_AUTHOR.search(text[:AUTHOR_WINDOW])
    if named:
        return author_label(named.group(1))
    return author_at(body, position)


def recommendations_in(body: str) -> list[dict]:
    marks = [(m.group(1), m.start(), m.end()) for m in HEAD.finditer(body)]
    best: dict[str, dict] = {}
    for i, (label, start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        text = tidy(body[end:stop])
        if not (MIN_CHARS <= len(text) <= MAX_CHARS) or bad(text):
            continue
        if not SAYS_RECOMMEND.search(text):
            continue
        author = author_of(text, body, start)
        keep = best.get(label)
        # A dissent restarts its numbering, so one report can hold two
        # "Recommendation 1" — the committee's and a party's. The committee's
        # wins the number outright, whatever the lengths: publishing a party's
        # demand as a committee's is the worst mistake this file can make.
        # Shortest text decides only between candidates of the same authorship.
        if keep is None:
            better = True
        elif bool(keep["recommended_by"]) != bool(author):
            better = not author
        else:
            better = len(text) < len(keep["recommendation"])
        if better:
            best[label] = {"label": label, "recommendation": text,
                           "recommended_by": author}
    return [best[k] for k in sorted(best, key=lambda s: [int(p) for p in s.split(".")])]


def register_rows() -> dict[str, dict]:
    seen: dict[str, dict] = {}
    for name, chamber in (("ledger_v2.csv", "senate"), ("house_ledger.csv", "house")):
        for r in csv.DictReader(open(DATA / name, encoding="utf-8-sig")):
            rid = r.get("report_otd_id")
            if rid and rid not in seen:
                seen[rid] = {**r, "chamber": chamber}
    return seen


def main() -> int:
    reports = register_rows()
    existing = list(csv.DictReader(open(OUT, encoding="utf-8-sig")))
    fields = list(existing[0].keys())
    rows, empty = [], 0
    for rid, meta in reports.items():
        path = TEXT / f"{rid}.txt"
        if not path.exists():
            empty += 1
            continue
        found = recommendations_in(path.read_text(encoding="utf-8", errors="replace"))
        if not found:
            empty += 1
            continue
        for f in found:
            rows.append({
                "source": "report",
                "source_id": rid,
                "label": f["label"],
                "recommended_by": f["recommended_by"],
                "document_has_other_authors": "yes" if SECTION.search(
                    (TEXT / f"{rid}.txt").read_text(encoding="utf-8", errors="replace")) else "",
                "recommendation": f["recommendation"],
                "government_words": "",
                "response_classification": "awaiting a response",
                "committee": meta.get("committee", ""),
                "department": "",
                "document_title": meta.get("title", ""),
                "tabled": meta.get("report_tabled", ""),
                "chamber": meta["chamber"],
                "url": meta.get("report_url", ""),
            })
    if not rows:
        print("REFUSING: no recommendations extracted from any report")
        return 1
    merged = existing + [{k: r.get(k, "") for k in fields} for r in rows]
    tmp = OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(merged)
    tmp.replace(OUT)
    flagged = sum(1 for r in rows if r["recommended_by"])
    print(f"{len(rows)} recommendations from {len(reports) - empty} of {len(reports)} "
          f"reports on the registers")
    print(f"  {flagged} name a dissenting, minority or party author rather than the committee")
    print(f"  {empty} reports yielded none")
    print(f"{len(merged)} rows in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
