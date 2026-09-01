"""link_reports.py — give every register row a link to the report itself.

The registers come from the presiding officers' schedules, which name a report
but do not link to it. The Tabled Documents database (OTD) holds the reports,
with a stable page for each, so a row can be linked by matching schedule title
and tabling date against data/committee_reports.csv.

Adds `report_otd_id` and `report_url` to data/ledger_v2.csv and
data/house_ledger.csv, in place. Rows with no confident match are left blank
and the site renders them as plain text: a wrong link on a public register is
worse than no link, and a reader who clicks through to the wrong report has
every reason to distrust the rest of the page.

What limits the match is coverage, not cleverness. OTD's committee-report index
begins in 2022 — 144 reports for that year, none before it apart from a single
2002 outlier — so reports tabled earlier cannot be linked at all, however well
their titles match. That is most of what stays unlinked.

Usage:
    python link_reports.py            # link both registers
    python link_reports.py --report   # also list what did not match, and why
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
REPORTS = DATA / "committee_reports.csv"
LEDGERS = [DATA / "ledger_v2.csv", DATA / "house_ledger.csv"]

# OTD's index starts here; nothing earlier can be linked.
COVERAGE_FROM = dt.date(2022, 1, 1)

# The same scaffolding that has to be stripped before two committee report
# titles can be compared. Left in, "Report", "Inquiry" and "Bill" match
# everything to everything.
TITLE_NOISE = {
    "report", "reports", "inquiry", "inquiries", "into", "interim", "final",
    "first", "second", "third", "fourth", "bill", "bills", "provisions",
    "provision", "related", "amendment", "amendments", "legislation",
    "legislative", "measures", "other", "committee", "australia", "australian",
    "government", "response", "responses", "consequential", "matter",
    "matters", "review",
}
YEAR = re.compile(r"^(19|20)\d{2}$")
# Public Accounts and Audit, Public Works and Treaties number their reports, and
# the number is the single most reliable thing about the title: "Report 488" and
# "Report 506" are both "Commonwealth financial statements" once the years are
# stripped, and confusing them would be a bad link on a public register.
REPORT_NO = re.compile(r"\breport\s+(?:no\.?\s*)?(\d{2,4})\b", re.I)


def tokens(text: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split() if len(w) > 3}


def distinctive(text: str) -> set[str]:
    return {t for t in tokens(text) - TITLE_NOISE if not YEAR.match(t)}


def load_reports() -> list[dict]:
    if not REPORTS.exists():
        sys.exit(f"{REPORTS} missing — run the OTD harvest first.")
    out = []
    with REPORTS.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            tabled = r.get("tabled_senate") or r.get("tabled_house") or ""
            if not tabled or not r.get("url"):
                continue
            out.append({
                "id": r["id"],
                "url": r["url"],
                "title": r["title"],
                "date": dt.date.fromisoformat(tabled[:10]),
                "key": distinctive(r["title"]),
                "all": tokens(r["title"]),
            })
    return out


def report_number(title: str) -> str | None:
    m = REPORT_NO.search(title or "")
    return m.group(1) if m else None


def best_match(title: str, tabled: dt.date, reports: list[dict]) -> tuple[dict | None, float]:
    """The report this row refers to, or nothing.

    Two records of the same report rarely agree exactly. The chambers table it
    on different days — sometimes months apart, when one house is not sitting —
    and each writes the title its own way, with a colon where the other has an
    em dash. So the date is a sanity band rather than a key, and the title is
    compared on its distinctive words once the scaffolding is stripped out.

    A numbered report is the easy case and is treated as one: where both records
    carry a report number, that number decides it, and a mismatch rules the
    candidate out however similar the words are.
    """
    key, whole = distinctive(title), tokens(title)
    number = report_number(title)
    best, best_score = None, 0.0
    for r in reports:
        gap = abs((r["date"] - tabled).days)
        r_number = report_number(r["title"])

        if number and r_number:
            if number != r_number:
                continue                       # a different numbered report
            if gap > 180:
                continue
            shared = key & r["key"]
            ratio = len(shared) / max(1, min(len(key), len(r["key"])))
            if ratio < 0.3:
                continue
            score = 1.0 + ratio - gap / 10_000
        else:
            if gap > 30:
                continue
            shared = key & r["key"]
            d_ratio = len(shared) / min(len(key), len(r["key"])) if key and r["key"] else 0.0
            f_ratio = (len(whole & r["all"]) / min(len(whole), len(r["all"]))
                       if whole and r["all"] else 0.0)
            if not ((len(shared) >= 2 and d_ratio >= 0.6) or f_ratio >= 0.8):
                continue
            score = max(d_ratio, f_ratio) - gap / 1000
        if score > best_score:
            best, best_score = r, score
    return best, best_score


def link(path: pathlib.Path, reports: list[dict], verbose: bool) -> tuple[int, int, list]:
    if not path.exists():
        print(f"  {path.name}: not built yet, skipped")
        return 0, 0, []
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return 0, 0, []

    matched, unmatched = 0, []
    for row in rows:
        tabled = dt.date.fromisoformat(row["report_tabled"])
        hit, _ = best_match(row["title"], tabled, reports)
        row["report_otd_id"] = hit["id"] if hit else ""
        row["report_url"] = hit["url"] if hit else ""
        if hit:
            matched += 1
        else:
            unmatched.append((row["title"], tabled))

    fields = list(rows[0].keys())
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)

    before = sum(1 for _, d in unmatched if d < COVERAGE_FROM)
    print(f"  {path.name}: {matched} of {len(rows)} linked; "
          f"{len(unmatched)} not ({before} tabled before OTD's index begins)")
    if verbose and unmatched:
        for title, d in sorted(unmatched, key=lambda x: x[1]):
            era = "pre-2022" if d < COVERAGE_FROM else "in coverage — check"
            print(f"      {d}  [{era}]  {title[:66]}")
    return matched, len(rows), unmatched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="list every unmatched row")
    args = ap.parse_args()

    reports = load_reports()
    print(f"OTD committee reports available: {len(reports)}")
    total_hit = total_rows = 0
    for path in LEDGERS:
        hit, rows, _ = link(path, reports, args.report)
        total_hit += hit
        total_rows += rows
    if total_rows:
        print(f"linked {total_hit} of {total_rows} register rows "
              f"({total_hit * 100 // total_rows}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
