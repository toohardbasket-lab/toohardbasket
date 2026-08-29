"""
build_ledger_v2.py — the Ledger: every Senate committee report currently
awaiting a government response.

This is the file the site reads, and it is assembled from two sources that
cover different eras:

  1. data/ledger.csv — the President of the Senate's twice-yearly schedule of
     outstanding responses, already reconciled by build_ledger.py against
     responses tabled since the schedule date. Only rows still marked
     `outstanding` are carried through. This is the only source for reports
     tabled before the live tracker's coverage begins.

  2. ledger/tracker_<date>.txt — a dump of the Senate's live tracker of reports
     awaiting a response, one entry per line as
     `DD-MM-YYYY ~ Committee ~ Report title`. Covers 2022 onward.

Until this script existed, data/ledger_v2.csv was a hand-assembled artefact
that nothing could regenerate, so the site's headline figure could not be
recomputed and silently went stale — the Freedom of Information Amendment
(New Arrangements) Bill 2014 report was still being published as the longest
outstanding five months after it was answered on 12 March 2026.

Usage:
    python build_ledger_v2.py                     # newest tracker dump
    python build_ledger_v2.py ledger/tracker_2026-08-25.txt
Writes data/ledger_v2.csv and prints a summary.
"""
from __future__ import annotations

import csv
import glob
import os
import pathlib
import re
import statistics
import sys
import time
from datetime import date, datetime

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
OUT = DATA / "ledger_v2.csv"

FIELDS = ["days_outstanding", "report_tabled", "committee", "title",
          "interim_response", "interim_report", "source", "notes"]

TRACKER_LINE = re.compile(r"^(\d{2}-\d{2}-\d{4}) ~ (.+?) ~ (.+)$")
# A committee's own interim report — distinct from an interim *response* by the
# government. Both are still outstanding; they are flagged, never excluded.
INTERIM_REPORT = re.compile(r"\binterim report\b", re.I)


def norm_tokens(s: str) -> frozenset[str]:
    return frozenset(w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if len(w) > 3)


def latest_tracker() -> pathlib.Path:
    files = sorted(glob.glob(str(HERE / "ledger" / "tracker_*.txt")))
    if not files:
        raise SystemExit("no ledger/tracker_*.txt dump found — refusing to build")
    return pathlib.Path(files[-1])


def from_schedule() -> list[dict]:
    path = DATA / "ledger.csv"
    if not path.exists():
        raise SystemExit(f"{path} missing — run build_ledger.py first")
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["status"] != "outstanding" or not r["report_tabled"]:
                continue
            rows.append({
                "report_tabled": r["report_tabled"],
                "committee": r["committee"],
                "title": r["title"],
                "interim_response": r["interim_received"].strip().lower() == "true",
                "source": "presidents_schedule",
                "notes": r.get("notes", ""),
            })
    return rows


def from_tracker(path: pathlib.Path) -> list[dict]:
    rows, malformed = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = TRACKER_LINE.match(line)
        if not m:
            malformed += 1
            continue
        tabled, committee, title = m.groups()
        rows.append({
            "report_tabled": datetime.strptime(tabled, "%d-%m-%Y").date().isoformat(),
            "committee": committee.strip(),
            "title": title.strip(),
            "interim_response": False,     # the tracker does not record this
            "source": f"aph_tracker_{path.stem.replace('tracker_', '')}",
            "notes": "",
        })
    if malformed:
        print(f"warning: {malformed} tracker lines did not parse", file=sys.stderr)
    return rows


def write_rows(rows: list[dict]) -> None:
    tmp = OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    for attempt in range(5):
        try:
            os.replace(tmp, OUT)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(1.5)


def main(argv: list[str]) -> int:
    tracker_path = pathlib.Path(argv[1]) if len(argv) > 1 else latest_tracker()
    today = date.today()

    schedule = from_schedule()
    tracker = from_tracker(tracker_path)

    # Refuse to publish on an empty source rather than silently halving the count.
    if not schedule or not tracker:
        print(f"schedule={len(schedule)} tracker={len(tracker)} — one source is empty, "
              "refusing to write", file=sys.stderr)
        return 1

    # The tracker is the more current record, so it wins any overlap. Match on
    # tabling date plus title tokens; the two sources word titles differently.
    seen: dict[tuple[str, frozenset[str]], dict] = {}
    duplicates = 0
    for row in tracker + schedule:
        key = (row["report_tabled"], norm_tokens(row["title"]))
        if key in seen:
            duplicates += 1
            seen[key]["notes"] += f"also listed in {row['source']}; "
            continue
        seen[key] = row

    rows = []
    for r in seen.values():
        tabled = date.fromisoformat(r["report_tabled"])
        rows.append({
            "days_outstanding": (today - tabled).days,
            "report_tabled": r["report_tabled"],
            "committee": r["committee"],
            "title": r["title"],
            "interim_response": r["interim_response"],
            "interim_report": bool(INTERIM_REPORT.search(r["title"])),
            "source": r["source"],
            "notes": r["notes"],
        })
    rows.sort(key=lambda r: -r["days_outstanding"])
    write_rows(rows)

    waits = [r["days_outstanding"] for r in rows]
    interim_reports = sum(1 for r in rows if r["interim_report"])
    interim_responses = sum(1 for r in rows if r["interim_response"])
    print(f"as at {today}: {len(rows)} reports outstanding "
          f"({len(schedule)} from the President's schedule, {len(tracker)} from the "
          f"tracker dump {tracker_path.name}, {duplicates} listed in both)")
    print(f"oldest {max(waits):,} days | median {statistics.median(waits):,.0f} | "
          f">1 year {sum(1 for d in waits if d > 365)} | >5 years {sum(1 for d in waits if d > 1826)}")
    print(f"{interim_reports} are interim reports; {interim_responses} have had an interim response")
    print("\nlongest outstanding:")
    for r in rows[:8]:
        flags = "".join(["[interim response] " if r["interim_response"] else "",
                         "[interim report] " if r["interim_report"] else ""])
        print(f"  {r['days_outstanding']:>6,}d  {r['report_tabled']}  {flags}{r['title'][:66]}")
    print(f"\nwrote {OUT} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
