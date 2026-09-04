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
# Rows where the automatic match is wrong or impossible, corrected by hand with
# the reasoning written down beside them. A wrong link is a visible error on a
# public register, so these are kept in the data rather than in code.
OVERRIDES = DATA / "report_links_manual.csv"
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
# The words every committee name carries. What is left after them is the name:
# "Impact of Climate Risk on Insurance—Senate Select" and "Select Committee on
# the Impact of Climate Risk on Insurance Premiums and Availability" agree on
# impact, climate, risk and insurance; "Public works—Joint Standing" and the
# Community Affairs Legislation Committee agree on nothing.
COMMITTEE_NOISE = {
    "committee", "committees", "joint", "standing", "select", "statutory",
    "senate", "house", "representatives", "parliamentary", "references",
    "legislation", "affairs", "inquiry", "into", "the", "and",
}
# Public Accounts and Audit, Public Works and Treaties number their reports, and
# the number is the single most reliable thing about the title: "Report 488" and
# "Report 506" are both "Commonwealth financial statements" once the years are
# stripped, and confusing them would be a bad link on a public register.
REPORT_NO = re.compile(r"\breport\s+(?:no\.?\s*)?(\d{2,4})\b", re.I)


def tokens(text: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split() if len(w) > 3}


def distinctive(text: str) -> set[str]:
    return {t for t in tokens(text) - TITLE_NOISE if not YEAR.match(t)}


def committee_tokens(text: str) -> set[str]:
    return tokens(text) - COMMITTEE_NOISE


def committees_agree(row_committee: str, candidate_committee: str) -> bool:
    """Whether the register's committee and the document's author can be the
    same body. Either side blank is not a disagreement — the schedules and the
    index do not both name the committee on every row — but two names that
    share no word are, whatever the titles say."""
    a, b = committee_tokens(row_committee), committee_tokens(candidate_committee)
    return not a or not b or bool(a & b)


def same_committee(row_committee: str, candidate_committee: str) -> bool:
    """The stronger test, for a row whose title says nothing: the document's
    author carries the register's name for the committee nearly whole. One
    shared word is not enough — the NDIS committee and the Select Committee on
    the Impact of Climate Risk on Insurance share "insurance"."""
    a, b = committee_tokens(row_committee), committee_tokens(candidate_committee)
    return bool(a) and bool(b) and len(a & b) / len(a) >= 0.75


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
                "committee": r.get("committee") or "",
                "date": dt.date.fromisoformat(tabled[:10]),
                "key": distinctive(r["title"]),
                "all": tokens(r["title"]),
            })
    return out


def report_number(title: str) -> str | None:
    m = REPORT_NO.search(title or "")
    return m.group(1) if m else None


def best_match(title: str, tabled: dt.date, reports: list[dict],
               committee: str = "") -> tuple[dict | None, float]:
    """The report this row refers to, or nothing.

    Two records of the same report rarely agree exactly. The chambers table it
    on different days — sometimes months apart, when one house is not sitting —
    and each writes the title its own way, with a colon where the other has an
    em dash. So the date is a sanity band rather than a key, and the title is
    compared on its distinctive words once the scaffolding is stripped out.

    A numbered report is the easy case and is treated as one: where both records
    carry a report number, that number decides it, and a mismatch rules the
    candidate out however similar the words are.

    A title that is only scaffolding — a select committee's "Report", a bill
    committee's "Interim report" — carries nothing to compare, and comparing it
    anyway is how three register rows came to link to Public Works Committee
    reports tabled the same day: one shared word, "report", against a one-word
    title, is a perfect score. Such a row is linked only to a document of the
    same committee tabled the same day, and only if there is exactly one.
    """
    key, whole = distinctive(title), tokens(title)
    number = report_number(title)
    best, best_score = None, 0.0
    same_day: list[dict] = []
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
            # The committee is the one thing the schedule and the index both
            # name. A title match against a document of another committee is
            # a coincidence of wording, not the report.
            if not committees_agree(committee, r["committee"]):
                continue
            if not key:
                if gap == 0 and same_committee(committee, r["committee"]):
                    same_day.append(r)
                continue
            shared = key & r["key"]
            d_ratio = len(shared) / min(len(key), len(r["key"])) if key and r["key"] else 0.0
            f_shared = whole & r["all"]
            f_ratio = (len(f_shared) / min(len(whole), len(r["all"]))
                       if whole and r["all"] else 0.0)
            if not ((len(shared) >= 2 and d_ratio >= 0.6)
                    or (f_ratio >= 0.8 and len(f_shared) >= 2)):
                continue
            score = max(d_ratio, f_ratio) - gap / 1000
        if score > best_score:
            best, best_score = r, score
    if best is None and len(same_day) == 1:
        return same_day[0], 0.5
    return best, best_score


def load_overrides(ledger: str, reports: list[dict]) -> dict[str, dict]:
    if not OVERRIDES.exists():
        return {}
    out = {}
    by_id = {r["id"]: r for r in reports}
    with OVERRIDES.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["ledger"] != ledger:
                continue
            hit = by_id.get(r["report_otd_id"])
            if hit:
                # Two select committees can both title their report "Report",
                # so an override may carry the tabling date as well; a row
                # matches on the pair when the date is given, on the title
                # alone when it is not.
                out[(r["title"].strip(), (r.get("report_tabled") or "").strip())] = hit
            else:
                print(f"      override for {r['title'][:40]!r} names OTD "
                      f"{r['report_otd_id']}, which is not in the report index",
                      file=sys.stderr)
    return out


# The reports collected by hand because the Tabled Documents index does not
# reach them — see harvest_manual_reports.py. Keyed the way the register names
# a report: its tabling date and its title, normalised.
COLLECTED = DATA / "reports_manual.csv"


def _norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def load_collected() -> dict[tuple[str, str], str]:
    """(tabled, normalised title) -> the page the report was collected from.

    The committee's own page for the report where the manifest records one;
    otherwise the PDF itself. A manifest row with neither yields nothing, and
    the register row stays unlinked rather than pointing somewhere vague.
    """
    if not COLLECTED.exists():
        return {}
    out: dict[tuple[str, str], str] = {}
    with COLLECTED.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            url = (r.get("report_page_url") or "").strip() or (r.get("pdf_direct_url") or "").strip()
            if not url:
                continue
            out[(r["report_tabled"], _norm_title(r["title"]))] = url
            # A joint report is one document presented to each chamber on its
            # own day, and the manifest keeps one row for it under one of those
            # days. The other register's row carries the other date, so the
            # title alone is kept as a second key. Only 26 hand-collected
            # reports exist and no two share a title, so this cannot cross
            # two reports; it is not the rule for the 1,200-report index.
            out.setdefault(("", _norm_title(r["title"])), url)
            # And the numbered reports by their number, which the two
            # presiding officers agree on even when they punctuate the rest
            # of the title differently.
            num = _report_number(r["title"])
            if num:
                out.setdefault(("#", num), url)
    return out


def _report_number(title: str) -> str:
    m = re.match(r"\s*report\s+(\d{1,4})\b", title or "", re.I)
    return m.group(1) if m else ""


def link(path: pathlib.Path, reports: list[dict], verbose: bool) -> tuple[int, int, list]:
    if not path.exists():
        print(f"  {path.name}: not built yet, skipped")
        return 0, 0, []
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return 0, 0, []

    overrides = load_overrides(path.name, reports)
    collected = load_collected()
    matched, unmatched, overridden, by_hand = 0, [], 0, 0
    for row in rows:
        tabled = dt.date.fromisoformat(row["report_tabled"])
        hit, _ = best_match(row["title"], tabled, reports, row.get("committee") or "")
        forced = (overrides.get((row["title"].strip(), row["report_tabled"]))
                  or overrides.get((row["title"].strip(), "")))
        if forced is not None:
            if forced is not hit:
                overridden += 1
            hit = forced
        row["report_otd_id"] = hit["id"] if hit else ""
        row["report_url"] = hit["url"] if hit else ""
        if hit:
            matched += 1
            continue
        # Nothing in the Tabled Documents index — usually because the report
        # predates it. The report may still have been collected by hand from
        # its committee's own page, and that page is a link a reader can
        # follow; the row keeps an empty OTD id so the two kinds of link stay
        # distinguishable in the data.
        page = (collected.get((row["report_tabled"], _norm_title(row["title"])))
                or collected.get(("", _norm_title(row["title"])))
                or (collected.get(("#", _report_number(row["title"]))) if _report_number(row["title"]) else None))
        if page:
            row["report_url"] = page
            by_hand += 1
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
    print(f"  {path.name}: {matched} of {len(rows)} linked to the Tabled Documents index"
          + (f", {by_hand} to the committee page the report was collected from" if by_hand else "")
          + f"; {len(unmatched)} not ({before} tabled before OTD's index begins)"
          + (f"; {overridden} corrected by hand" if overridden else ""))
    if verbose and unmatched:
        for title, d in sorted(unmatched, key=lambda x: x[1]):
            era = "pre-2022" if d < COVERAGE_FROM else "in coverage — check"
            print(f"      {d}  [{era}]  {title[:66]}")
    return matched + by_hand, len(rows), unmatched


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
              f"({total_hit * 100 // total_rows}%) — to the Tabled Documents index, "
              "or to the committee page a report was collected from")
    return 0


if __name__ == "__main__":
    sys.exit(main())
