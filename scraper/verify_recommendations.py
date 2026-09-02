"""Check every published recommendation back against the document it came from.

The failure that matters is not a garbled quotation — those are visible. It is
the right words under the wrong number: a journalist who quotes "recommendation
8" of a report that numbered it 29 has been misled by this site, and nothing on
the page would show it.

So every row is looked for in its source: a distinctive slice of the text, and
a label above that slice matching the row's own number. Rows that fail are
REMOVED, not flagged. The index is then verified by construction — everything
in it was found, verbatim, under the number it claims — and the count of what
was dropped is published rather than quietly absorbed.

Two things the check must allow for. A report can number several
recommendations that open with the same forty words (the Public Works Committee
approves each project in identical language), so every occurrence of the text
is considered, not the first. And a document quotes its recommendations more
than once — a contents list, a summary, the body — so finding the text under
the right label anywhere in the document is enough.
"""
from __future__ import annotations

import collections
import csv
import pathlib
import re

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
REPORTS = HERE / "raw" / "report_text"
RESPONSES = HERE / "raw" / "otd_text"
FILE = DATA / "recommendations.csv"

LABEL = re.compile(r"Recommendation\s*(?:no\.?\s*)?(\d{1,3}(?:\.\d{1,3})?)", re.I)
LOOKBACK = 400
_cache: dict[str, str] = {}


def source_text(row: dict) -> str:
    key = f"{row['source']}:{row['source_id']}"
    if key in _cache:
        return _cache[key]
    if row["source"] == "report":
        path = REPORTS / f"{row['source_id']}.txt"
        body = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    else:
        files = sorted(RESPONSES.glob(f"{row['source_id']}_*.txt"))
        body = files[0].read_text(encoding="utf-8", errors="replace") if files else ""
    _cache[key] = re.sub(r"\s+", " ", body)
    return _cache[key]


def verdict(row: dict) -> str:
    body = source_text(row)
    if not body:
        return "source text missing"
    text = re.sub(r"\s+", " ", row["recommendation"])
    # Skip the boilerplate opening — "The committee recommends that the
    # Australian Government" is shared by hundreds of rows — and take a slice
    # from the middle, which is what makes one recommendation distinctive.
    probe = text[40:170] if len(text) > 190 else text[-100:]
    if len(probe) < 30:
        return "too short to verify"
    want = row["label"].lstrip("0")
    seen, start, anywhere = [], 0, False
    while True:
        at = body.find(probe, start)
        if at < 0:
            break
        anywhere = True
        start = at + 1
        labels = LABEL.findall(body[max(0, at - LOOKBACK):at])
        if labels:
            seen.append(labels[-1].lstrip("0"))
            if labels[-1].lstrip("0") == want:
                return "verified"
    if not anywhere:
        return "text not in source"
    return "no label above it" if not seen else "label does not match"


def main() -> int:
    rows = list(csv.DictReader(open(FILE, encoding="utf-8-sig")))
    if not rows:
        print("REFUSING: the index is empty")
        return 1
    tally = collections.Counter()
    kept, dropped = [], []
    for r in rows:
        v = verdict(r)
        tally[v] += 1
        (kept if v == "verified" else dropped).append({**r, "why": v})

    print(f"{len(rows)} recommendations checked against their source documents")
    for why, n in tally.most_common():
        print(f"  {n:>5}  {why}")

    if not kept:
        print("REFUSING: nothing verified — the check itself is broken")
        return 1
    share = len(kept) / len(rows)
    if share < 0.5:
        print(f"REFUSING: only {share*100:.0f}% verified. That is a broken check or a "
              "broken extractor, not a dataset to publish.")
        return 1

    fields = [k for k in rows[0]]
    tmp = FILE.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{k: r[k] for k in fields} for r in kept])
    tmp.replace(FILE)

    out = DATA / "recommendations_dropped.csv"
    if dropped:
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields + ["why"])
            w.writeheader()
            w.writerows(dropped)
    print(f"\nkept {len(kept)} ({share*100:.1f}%), dropped {len(dropped)}")
    print(f"wrote {FILE}" + (f" and {out}" if dropped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
