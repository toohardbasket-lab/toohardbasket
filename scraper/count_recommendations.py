"""How many recommendations a form-letter closure actually disposed of.

The closure count — how many REPORTS were closed with the template — is exact
and is what the site leads with. This asks the harder question underneath it:
how many individual recommendations went with them.

The obvious answer is wrong. Counting the sentence "the Government notes this
recommendation" across the corpus gives a number, but that sentence is not
reliably one per recommendation. Forty-five closures do not contain it at all —
they dispose of a whole report in a line. Others use it once for a report with
twenty-eight recommendations. Others repeat it in a summary table and again in
the body.

Checking it against the committee's own report, which is the authoritative
count, is not currently possible: the Tabled Documents system's own
report-to-response links reach one of the closures, and title matching finds a
confident report for six.

So this counts only what a document proves about itself. A closure is counted
when its recommendation labels run 1..N with no gaps — or chapter.n with each
chapter running from 1 — AND the notes sentence appears exactly N times, AND
N is at least two. Everything else is excluded and the reason recorded.

The two-recommendation floor is not fussiness. Document 5902 is laid out as a
table, so its recommendations carry no "Recommendation N" heading at all and
the text extraction interleaves the columns; it satisfied every other test with
one recommendation and has at least five. Requiring two removes that whole
class of false positive at a cost of twenty-two documents and twenty-two
recommendations.

What comes out is a floor, and a large one: it excludes more closures than it
counts, including every one of the forty-five that closed a report without
noting a single recommendation. The site must present it as a floor.

Writes data/recommendation_counts.csv — every closure, its numbers, and why it
is or is not counted — so the figure can be checked document by document.
"""
from __future__ import annotations

import collections
import csv
import pathlib
import re

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "otd_text"
OUT = DATA / "recommendation_counts.csv"

# "Recommendation 7", "Recommendation 3.2", "Recommendation No. 4". The chapter
# form matters: reading "Recommendation 3.2" as recommendation 3 collapsed the
# forty-nine recommendations of document 6668 into nine and made seventy
# well-formed documents look inconsistent.
LABEL = re.compile(r"\brecommendation\s*(?:no\.?\s*)?(\d{1,3})(?:\.(\d{1,3}))?\b", re.I)
NOTES = re.compile(r"notes?\s+th(is|e|ese)\s+recommendation", re.I)

MIN_RECOMMENDATIONS = 2


def text_for(doc_id: str) -> str:
    files = sorted(TEXT.glob(f"{doc_id}_*.txt"))
    return files[0].read_text(encoding="utf-8", errors="replace") if files else ""


def labels_in(body: str) -> tuple[int, bool]:
    """How many distinct recommendations the document labels, and whether the
    labelling is complete — a run with a gap means the extraction lost some."""
    flat = {(int(m.group(1)), int(m.group(2)) if m.group(2) else -1)
            for m in LABEL.finditer(body)}
    plain = sorted(a for a, b in flat if b == -1)
    chapters: dict[int, list[int]] = collections.defaultdict(list)
    for a, b in flat:
        if b != -1:
            chapters[a].append(b)
    if chapters:
        # Mixed plain and chapter numbering in one document is not a scheme we
        # can read confidently, so it is not counted.
        contiguous = not plain and all(
            sorted(v) == list(range(1, len(v) + 1)) for v in chapters.values())
        return sum(len(v) for v in chapters.values()), contiguous
    return len(plain), plain == list(range(1, len(plain) + 1))


def main() -> int:
    excluded = {r["id"] for r in csv.DictReader(
        open(DATA / "scope_exclusions.csv", encoding="utf-8-sig"))}
    rows = [r for r in csv.DictReader(
        open(DATA / "response_documents.csv", encoding="utf-8-sig"))
        if r["id"] not in excluded and r["classification"] == "proforma_closure"]

    out = []
    for r in rows:
        body = text_for(r["id"])
        notes = len(NOTES.findall(body))
        n, contiguous = labels_in(body)
        if not body:
            why = "no cached text"
        elif n == 0:
            why = "no recommendation labels in the text"
        elif not contiguous:
            why = "labels do not run without gaps"
        elif notes != n:
            why = f"{notes} notes sentences against {n} labels"
        elif n < MIN_RECOMMENDATIONS:
            why = "a single label, which a table layout can fake"
        else:
            why = ""
        out.append({
            "id": r["id"],
            "tabled": r["tabled_senate"] or r["tabled_house"],
            "notes_sentences": notes,
            "labels": n,
            "labels_contiguous": "yes" if contiguous and n else "no",
            "counted": "yes" if not why else "no",
            "recommendations_counted": n if not why else 0,
            "excluded_because": why,
            "title": r["title"],
            "url": r["url"],
        })

    out.sort(key=lambda r: int(r["id"]))
    tmp = OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    tmp.replace(OUT)

    counted = [r for r in out if r["counted"] == "yes"]
    floor = sum(r["recommendations_counted"] for r in counted)
    sentences = sum(r["notes_sentences"] for r in out)
    print(f"{len(out)} form-letter closures")
    print(f"  {len(counted)} counted, holding {floor} recommendations — the floor")
    print(f"  {len(out) - len(counted)} not counted:")
    # The disagreement reason carries the two numbers per document, which is
    # what the CSV is for; the summary groups them so it stays readable.
    reasons = collections.Counter(
        "the notes sentences and the labels disagree" if r["excluded_because"][:1].isdigit()
        else r["excluded_because"]
        for r in out if r["excluded_because"])
    for why, n in reasons.most_common():
        print(f"      {n:>4}  {why}")
    print(f"  {sentences} notes sentences across the whole corpus "
          f"(a count of a sentence, never of recommendations)")
    print(f"wrote {OUT}")

    # The floor must not quietly become most of the corpus without anyone
    # noticing that the method changed.
    if floor > sentences:
        print("REFUSING: the floor exceeds the sentence count, which cannot happen")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
