"""
build_ledger_v2.py — the Ledger: every Senate committee report currently
awaiting a government response.

This is the file the site reads. It has one primary source and one fallback,
and the difference between them is the whole point:

  1. data/ledger.csv — the President of the Senate's twice-yearly report to the
     Senate on the status of government responses, already reconciled by
     build_ledger.py against responses tabled since the schedule date. Only
     rows still marked `outstanding` are carried through.

     This is the register. It is the presiding officer's own record, it is
     citable, and publishing exactly what it lists needs no rule of ours. The
     House register works the same way from the Speaker's schedule, so the two
     report the same thing the same way.

  2. ledger/tracker_<date>.txt — a dump of the Senate's live tracker of reports
     awaiting a response, one entry per line as
     `DD-MM-YYYY ~ Committee ~ Report title`.

     The tracker is carried ONLY for reports tabled after the schedule's as-at
     date — the window the President has not yet reported on. Everything the
     schedule covers, the schedule decides; the tracker cannot add to,
     subtract from or override it. Rows carried this way keep a `source` of
     `aph_tracker_<date>` so every row on the site names where it came from.

     The tracker is a pasted dump, not a harvest: it is not reproducible from
     a URL, so it must never become the register's backbone. Before this rule,
     162 of the site's 181 rows came from the dump and only 19 from the
     President — the site was publishing an unattributable artefact under a
     citable name.

What neither source has: reports tabled after the later of the schedule date
and the tracker dump. The site has to say so.

Until build_ledger.py existed, data/ledger_v2.csv was a hand-assembled artefact
that nothing could regenerate, so the site's headline figure could not be
recomputed and silently went stale — the Freedom of Information Amendment
(New Arrangements) Bill 2014 report was still being published as the longest
outstanding five months after it was answered on 12 March 2026.

Usage:
    python build_ledger.py && python build_ledger_v2.py
    python build_ledger_v2.py ledger/tracker_2026-08-25.txt
Writes data/ledger_v2.csv, updates data/ledger_meta.json, prints a summary.
"""
from __future__ import annotations

import csv
import glob
import json
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
          "interim_response", "being_considered", "partial_response",
          "overdue", "interim_report", "source", "notes"]


def past_deadline(tabled: date, today: date) -> bool:
    """Three months from tabling, counted as calendar months, not 90 days.

    The Senate's rule has no carve-outs, so this can be computed. The House's
    rule excludes any period when the House was dissolved, which is why the
    House builder takes the Speaker's verdict instead of working it out.
    """
    month = tabled.month + 3
    year = tabled.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(tabled.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0)
                           else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return today > date(year, month, day)

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
                "being_considered": r.get("being_considered", "").strip().lower() == "true",
                "partial_response": r.get("partial_response", "").strip().lower() == "true",
                "source": "presidents_schedule",
                "notes": r.get("notes", ""),
            })
    return rows


def schedule_as_at() -> date:
    meta = DATA / "ledger_meta.json"
    if not meta.exists():
        raise SystemExit(f"{meta} missing — run build_ledger.py first")
    return date.fromisoformat(json.loads(meta.read_text(encoding="utf-8"))["as_at"])


def from_tracker(path: pathlib.Path, after: date) -> list[dict]:
    """Tracker rows for the window the President has not yet reported on."""
    rows, malformed, covered = [], 0, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = TRACKER_LINE.match(line)
        if not m:
            malformed += 1
            continue
        tabled, committee, title = m.groups()
        tabled_date = datetime.strptime(tabled, "%d-%m-%Y").date()
        if tabled_date <= after:
            covered += 1          # the President's schedule already decides this one
            continue
        rows.append({
            "report_tabled": tabled_date.isoformat(),
            "committee": committee.strip(),
            "title": title.strip(),
            "interim_response": False,     # the tracker records none of these
            "being_considered": False,
            "partial_response": False,
            "source": f"aph_tracker_{path.stem.replace('tracker_', '')}",
            "notes": "",
        })
    if malformed:
        print(f"warning: {malformed} tracker lines did not parse", file=sys.stderr)
    print(f"tracker {path.name}: {covered} rows the schedule already covers, "
          f"{len(rows)} tabled after {after}")
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

    as_at = schedule_as_at()
    schedule = from_schedule()
    tracker = from_tracker(tracker_path, as_at)

    # The schedule is the register. An empty one means something upstream broke,
    # and publishing a halved count is worse than publishing nothing.
    if len(schedule) < 50:
        print(f"schedule={len(schedule)} rows — implausibly few, refusing to write",
              file=sys.stderr)
        return 1

    # The President's schedule wins any overlap: it is the citable record, and
    # by construction the tracker only carries what the schedule cannot cover.
    seen: dict[tuple[str, frozenset[str]], dict] = {}
    duplicates = 0
    for row in schedule + tracker:
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
            "being_considered": r["being_considered"],
            "partial_response": r["partial_response"],
            "overdue": past_deadline(tabled, today),
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
          f"({len(schedule)} from the President's report as at {as_at}, "
          f"{len(tracker)} carried from the tracker dump {tracker_path.name} for "
          f"reports tabled since, {duplicates} listed in both)")
    if not tracker:
        print("  the tracker adds nothing this build — every row is the President's")
    print(f"oldest {max(waits):,} days | median {statistics.median(waits):,.0f} | "
          f">1 year {sum(1 for d in waits if d > 365)} | >5 years {sum(1 for d in waits if d > 1826)}")
    considered = sum(1 for r in rows if r["being_considered"])
    partial = sum(1 for r in rows if r["partial_response"])
    overdue = sum(1 for r in rows if r["overdue"])
    print(f"{overdue} are past the three-month deadline; {len(rows) - overdue} are not yet due")
    print(f"{interim_reports} are interim reports; {interim_responses} have had an "
          f"interim response, of which {considered} are recorded only as \"the "
          f"Government's response is being considered\"; {partial} have been answered "
          "in part")
    print("\nlongest outstanding:")
    for r in rows[:8]:
        flags = "".join(["[interim response] " if r["interim_response"] else "",
                         "[interim report] " if r["interim_report"] else ""])
        print(f"  {r['days_outstanding']:>6,}d  {r['report_tabled']}  {flags}{r['title'][:66]}")
    meta_path = DATA / "ledger_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({
        "rows": len(rows),
        "from_schedule": len(schedule),
        "from_tracker": len(tracker),
        "overdue": overdue,
        "not_yet_due": len(rows) - overdue,
        "being_considered": considered,
        "partial_response": partial,
        "tracker_dump": tracker_path.name if tracker else "",
        "tracker_dumped": tracker_path.stem.replace("tracker_", ""),
        "covers_to": max([as_at.isoformat()] + [r["report_tabled"] for r in tracker]),
        "rebuilt": today.isoformat(),
    })
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"\nwrote {OUT} ({len(rows)} rows) and updated {meta_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
