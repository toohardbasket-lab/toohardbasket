"""build_status_history.py — what the President has said about each report, edition by edition.

The register can say what the government says about a report today. It cannot,
from one document, say how long it has been saying it — and "the response is
being considered" said once is a status, while the same sentence in nine
consecutive reports over four years is something else.

Every President's report on the Tabled Documents register is the same document
in a new edition, so the parser that reads the current one reads all nine. This
walks them in order and records, for each report, what the President said about
it each time.

Two outputs:

  data/status_history.csv     one row per report per edition: the status as the
                              President recorded it, and the flags derived from
                              it. The evidence behind any duration claim.

  data/schedule_snapshots.csv one row per edition: what he actually recorded as
                              outstanding on that date. This is an OBSERVED
                              backlog, where the history chart's older points
                              are reconstructed from tabling dates — and the two
                              are not the same number, which is worth knowing.

Reports are matched between editions on their tabling date and the words of
their title. Where a title is written differently in a later edition the run
breaks, and the streak is reported short rather than long: a claim about how
many editions in a row must never be generous.

Usage:
    python harvest_schedules.py && python build_status_history.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import re
import sys

import build_ledger as ledger

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
LEDGER = HERE / "ledger"

NOISE = set("""report reports inquiry inquiries into the of and for on an australian australia
government response responses committee committees final first second interim""".split())


def key(row: dict) -> tuple:
    words = {w for w in re.sub(r"[^a-z0-9]+", " ", row["title"].lower()).split() if len(w) > 3}
    return (row["report_tabled"], frozenset(words - NOISE) or frozenset(words))


def main() -> int:
    paths = sorted(LEDGER.glob("presidents_*.pdf"))
    if len(paths) < 2:
        print("need at least two President's reports — run harvest_schedules.py first",
              file=sys.stderr)
        return 1

    editions, history = [], []
    for path in paths:
        as_at = dt.date.fromisoformat(path.stem.replace("presidents_", ""))
        rows = ledger.parse_schedule(str(path), as_at)
        answered = [r for r in rows
                    if r["response_received"] or r["complete_response"]]
        outstanding = [r for r in rows if r not in answered]
        editions.append({
            "as_at": as_at.isoformat(), "pdf": path.name, "listed": len(rows),
            "answered": len(answered), "outstanding": len(outstanding),
            "being_considered": sum(1 for r in outstanding if r["being_considered"]),
        })
        for r in rows:
            history.append({
                "as_at": as_at.isoformat(),
                "report_tabled": r["report_tabled"],
                "committee": r["committee"],
                "title": r["title"],
                "status": r["schedule_status"],
                "being_considered": r["being_considered"],
                "answered": bool(r["response_received"] or r["complete_response"]),
            })
        print(f"  {as_at}  listed {len(rows):>4}  outstanding {len(outstanding):>4}  "
              f"being considered {editions[-1]['being_considered']:>4}")

    with (DATA / "status_history.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(history[0].keys()))
        w.writeheader(); w.writerows(history)
    with (DATA / "schedule_snapshots.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(editions[0].keys()))
        w.writeheader(); w.writerows(editions)

    # How long has each report on today's register been called "being considered"?
    # Counted backwards from the newest edition and stopping at the first edition
    # that does not say it, so the number is a run of consecutive reports and not
    # a total.
    order = [e["as_at"] for e in editions]
    seen: dict[tuple, dict[str, dict]] = {}
    for h in history:
        seen.setdefault(key(h), {})[h["as_at"]] = h

    current = DATA / "ledger_v2.csv"
    streaks = []
    with current.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            runs = seen.get(key(row), {})
            n = 0
            for as_at in reversed(order):
                h = runs.get(as_at)
                if h and h["being_considered"]:
                    n += 1
                else:
                    break
            if n:
                streaks.append((n, order[-n], row))

    streaks.sort(key=lambda s: (-s[0], s[2]["report_tabled"]))
    meta_path = DATA / "ledger_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    full = [s for s in streaks if s[0] == len(editions)]
    meta.update({
        "editions_read": len(editions),
        "editions_from": editions[0]["as_at"],
        "being_considered_every_edition": len(full),
        "longest_being_considered_run": streaks[0][0] if streaks else 0,
    })
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    with (DATA / "being_considered_runs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["editions_in_a_row", "since", "report_tabled", "committee", "title"])
        for n, since, r in streaks:
            w.writerow([n, since, r["report_tabled"], r["committee"], r["title"]])

    print(f"\n{len(editions)} editions read, {editions[0]['as_at']} to {editions[-1]['as_at']}")
    print(f"{len(full)} of the {sum(1 for _ in streaks)} reports with a run have been called "
          f"\"being considered\" in every one of them")
    for n, since, r in streaks[:6]:
        print(f"  {n} editions in a row (since {since})  {r['report_tabled']}  {r['title'][:56]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
