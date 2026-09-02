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
    {"name": "senate", "ledger": "ledger_v2.csv", "meta": "ledger_meta.json",
     "already": "ledger.csv"},
    {"name": "house", "ledger": "house_ledger.csv", "meta": "house_ledger_meta.json"},
]


def already_removed(reg: dict) -> list[dict]:
    """Reports the register's own builder took off before this step ran.

    The Senate builder reconciles the President's schedule against the Senate's
    own register of responses and marks anything answered since the as-at date
    "answered_since_schedule"; those rows never reach ledger_v2.csv. They are
    real removals with a real date, and the page's count includes them, so the
    page's list has to include them too.

    They carry no Tabled Documents id — the Senate's register records the
    response, not the document — so they are published with the register page
    that records them as their evidence, and a basis that says so.
    """
    name = reg.get("already")
    if not name or not (DATA / name).exists():
        return []
    out = []
    with (DATA / name).open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("status") != "answered_since_schedule" or not r.get("response_tabled"):
                continue
            out.append({
                "report_tabled": r.get("report_tabled", ""),
                "committee": r.get("committee", ""),
                "title": r.get("title", ""),
                "report_otd_id": "",
                "response_id": "",
                "response_tabled": r["response_tabled"],
                "response_title": r.get("response_inquiry", ""),
                "response_source": r.get("response_source", ""),
                "removal_basis": "Senate response register",
            })
    return out


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

        kept, removed = answered_since.apply(rows, as_at, reg["name"])
        earlier = already_removed(reg)
        answered_since.report(removed, reg["name"], earlier)
        total += len(removed)

        # Record how current the response list is on every run, removals or
        # not: a build that removed nothing because it saw nothing looks
        # identical, from the outside, to a build that removed nothing because
        # there was nothing to remove.
        meta["responses_checked_to"] = answered_since.checked_to()
        # Written whether or not this step removed anything, because the
        # builder's own removals are published either way and the page's count
        # and the page's list have to be the same number on every run.
        meta["answered_since_schedule"] = len(removed) + len(earlier)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        if not removed:
            # The register is unchanged, but the earlier removals still have to
            # be published; report() has already written them.
            continue

        # The guard is on the weak evidence, not on the total. Any number of
        # removals is plausible when the Parliament's own link says the report
        # was answered, or when someone checked it and wrote down why — a
        # register catching up after a clear-out should not be blocked. What
        # is never plausible is a pile of removals resting on nothing but
        # matching words, which is how a matching bug would present.
        guessed = [r for r in removed if r["removal_basis"] == "title match"]
        if len(guessed) > max(2, len(rows) // 10):
            print(f"  {len(guessed)} of {len(removed)} removals rest on a title "
                  f"match alone, against {len(rows)} rows — implausible, refusing "
                  "to write", file=sys.stderr)
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
            #
            # It is computed, not accumulated. Adding this run's removals to
            # whatever the meta already said made the figure depend on how many
            # times the step had been run since the last full rebuild, and the
            # page's list — which is rewritten from scratch every time — did
            # not. One number, from the same two lists the page renders.
            "answered_since_schedule": len(removed) + len(earlier),
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
