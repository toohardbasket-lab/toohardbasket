"""
build_history.py — the backlog over time.

Emits data/backlog_history.csv, which carries two kinds of row, distinguished
by the `basis` column:

  reconstructed  Computed from today's dataset. For any date D the backlog is
                 the count of reports tabled on or before D with no response
                 tabled by D. These rows are recomputed on every run, so
                 corrections to the source data flow through the whole series.

  observed       A snapshot of the Ledger as it stood on the day this script
                 ran. NEVER recomputed. aph.gov.au is edited retrospectively —
                 tabling dates corrected, entries added and removed — so these
                 rows are the only record of what the official register showed
                 on a given date. Reconstruction cannot recover them, which is
                 why the snapshot is worth taking from the beginning.

Sources:
  data/responses.csv   reports that eventually received a response
  data/ledger_v2.csv   reports still awaiting one

This is a FLOOR, not an exact count. A report that was never responded to and
never appeared on the President's schedule is invisible to both sources, so the
true backlog at any past date was at least the figure given here. The 2000-01
registers do not record report dates, so the series starts in January 2003.

Usage:
    python build_history.py                # rebuild series + append today's snapshot
    python build_history.py --no-snapshot  # rebuild series only
"""
from __future__ import annotations

import calendar
import csv
import os
import pathlib
import statistics
import sys
import time
from datetime import date

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
OUT = DATA / "backlog_history.csv"

SERIES_START = date(2003, 1, 31)
FIELDS = ["as_at", "basis", "backlog", "oldest_days", "median_days",
          "over_1_year", "over_5_years"]


def _parse(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def load_reports() -> tuple[list[tuple[date, date | None]], dict]:
    """Every report we know a tabling date for, with its response date or None."""
    reports: list[tuple[date, date | None]] = []
    skipped_no_date = 0

    responses = DATA / "responses.csv"
    with open(responses, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tabled = _parse(row.get("report_first_tabled", ""))
            if tabled is None:
                skipped_no_date += 1
                continue
            reports.append((tabled, _parse(row.get("response_tabled", ""))))
    n_responded = len(reports)

    ledger = DATA / "ledger_v2.csv"
    with open(ledger, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tabled = _parse(row.get("report_tabled", ""))
            if tabled is None:
                skipped_no_date += 1
                continue
            reports.append((tabled, None))

    stats = {
        "responded": n_responded,
        "outstanding": len(reports) - n_responded,
        "skipped_no_date": skipped_no_date,
    }
    return reports, stats


def backlog_at(reports: list[tuple[date, date | None]], as_at: date) -> dict:
    waits = [(as_at - tabled).days
             for tabled, responded in reports
             if tabled <= as_at and (responded is None or responded > as_at)]
    if not waits:
        return {"backlog": 0, "oldest_days": "", "median_days": "",
                "over_1_year": 0, "over_5_years": 0}
    return {
        "backlog": len(waits),
        "oldest_days": max(waits),
        "median_days": int(round(statistics.median(waits))),
        "over_1_year": sum(1 for d in waits if d > 365),
        "over_5_years": sum(1 for d in waits if d > 1826),
    }


def month_ends(start: date, end: date):
    year, month = start.year, start.month
    while True:
        last_day = calendar.monthrange(year, month)[1]
        current = date(year, month, last_day)
        if current > end:
            return
        yield current
        month += 1
        if month == 13:
            year, month = year + 1, 1


def read_existing_snapshots(today: date) -> list[dict]:
    """Preserve every observed row except one already written for today."""
    if not OUT.exists():
        return []
    kept = []
    with open(OUT, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("basis") == "observed" and row.get("as_at") != today.isoformat():
                kept.append({k: row.get(k, "") for k in FIELDS})
    return kept


def write_rows(rows: list[dict]) -> None:
    """Write via a temp file so a reader (Excel) holding the CSV can't corrupt it."""
    tmp = OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    for attempt in range(5):
        try:
            os.replace(tmp, OUT)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(1.5)


def main(argv: list[str]) -> int:
    take_snapshot = "--no-snapshot" not in argv
    today = date.today()

    reports, stats = load_reports()
    if not reports:
        print("no reports with a tabling date — refusing to write", file=sys.stderr)
        return 1

    # Reconstructed series: every month end from SERIES_START to the last
    # complete month. The current month is excluded because it is not over.
    last_complete = date(today.year, today.month, 1)
    rows = []
    for as_at in month_ends(SERIES_START, last_complete):
        rows.append({"as_at": as_at.isoformat(), "basis": "reconstructed",
                     **backlog_at(reports, as_at)})

    rows.extend(read_existing_snapshots(today))

    if take_snapshot:
        rows.append({"as_at": today.isoformat(), "basis": "observed",
                     **backlog_at(reports, today)})

    rows.sort(key=lambda r: (r["as_at"], r["basis"]))
    write_rows(rows)

    reconstructed = [r for r in rows if r["basis"] == "reconstructed"]
    observed = [r for r in rows if r["basis"] == "observed"]
    peak = max(reconstructed, key=lambda r: r["backlog"])
    print(f"{stats['responded']:,} responded + {stats['outstanding']:,} outstanding "
          f"= {len(reports):,} reports with a tabling date "
          f"({stats['skipped_no_date']} skipped, no date recorded)")
    print(f"series {reconstructed[0]['as_at']} to {reconstructed[-1]['as_at']}: "
          f"{len(reconstructed):,} monthly points, {len(observed)} observed snapshot(s)")
    print(f"peak backlog {peak['backlog']} at {peak['as_at']}; "
          f"latest {reconstructed[-1]['backlog']} "
          f"(oldest {int(reconstructed[-1]['oldest_days']):,} days, "
          f"{reconstructed[-1]['over_5_years']} waiting over five years)")
    print(f"wrote {OUT} ({len(rows):,} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
