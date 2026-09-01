"""prune_answered.py — take off each register the reports that have been answered.

A presiding officer's schedule is a snapshot. The Senate's was printed as at
30 June 2026 and the House's the same day, and the government has gone on
tabling responses ever since. Publishing those reports as unanswered is the one
error that would fairly discredit the whole register, so this step runs over
both registers, finds every row a government response document has since
answered, and removes it — naming the response, its Tabled Documents id, and the
date it was tabled, so anyone can check the removal as easily as the row.

Runs after link_reports.py, because the strongest evidence is an id-level link
between a report and its response and the rows need their report ids first.

    python build_ledger.py && python build_ledger_v2.py
    python build_house_ledger.py
    python link_reports.py
    python prune_answered.py

Writes data/answered_since_<register>.csv for each register — the removals, with
their evidence — rewrites the register CSVs, and updates the meta files so the
site's counts and the rows it renders cannot disagree.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from datetime import date

import answered_since

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

REGISTERS = [
    {"name": "senate", "ledger": "ledger_v2.csv", "meta": "ledger_meta.json"},
    {"name": "house", "ledger": "house_ledger.csv", "meta": "house_ledger_meta.json"},
]


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def main() -> int:
    total = 0
    for reg in REGISTERS:
        led = DATA / reg["ledger"]
        meta_path = DATA / reg["meta"]
        if not led.exists() or not meta_path.exists():
            print(f"{reg['name']}: not built yet, skipped")
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        as_at = date.fromisoformat(meta["as_at"])
        with led.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
            fields = list(rows[0].keys()) if rows else []

        kept, removed = answered_since.apply(rows, as_at)
        answered_since.report(removed, reg["name"])
        total += len(removed)
        if not removed:
            continue

        # A register that loses a third of its rows in one build is a matching
        # bug, not a burst of government diligence. Refuse rather than publish.
        if len(removed) > max(3, len(rows) // 4):
            print(f"  {len(removed)} of {len(rows)} rows removed — implausible, "
                  "refusing to write", file=sys.stderr)
            return 1

        tmp = led.with_suffix(".csv.tmp")
        with tmp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(kept)
        tmp.replace(led)

        meta.update({
            "rows": len(kept),
            "overdue": sum(1 for r in kept if truthy(r.get("overdue"))),
            "not_yet_due": sum(1 for r in kept if not truthy(r.get("overdue"))),
            "being_considered": sum(1 for r in kept if truthy(r.get("being_considered"))),
            "partial_response": sum(1 for r in kept if truthy(r.get("partial_response"))),
            # The Senate's builder already removes what its own source of
            # responses covers; this adds what the tabled-documents register
            # shows on top of it, so the site's one figure is the total.
            "answered_since_schedule": meta.get("answered_since_schedule", 0) + len(removed),
            "removed_by_response_documents": len(removed),
            "answered_since_schedule_file": f"answered_since_{reg['name']}.csv",
            "covers_responses_to": max(r["response_tabled"] for r in removed),
            "pruned": date.today().isoformat(),
        })
        if any(r.get("source") for r in kept):
            meta["from_schedule"] = sum(1 for r in kept
                                        if r.get("source") == "presidents_schedule")
            meta["from_tracker"] = sum(1 for r in kept
                                       if str(r.get("source", "")).startswith("aph_tracker"))
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        print(f"  {reg['ledger']}: {len(rows)} -> {len(kept)} rows; "
              f"{meta['overdue']} overdue")

    print(f"\n{total} row(s) removed across both registers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
