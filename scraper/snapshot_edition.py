"""snapshot_edition.py — keep a dated record of what the registers said.

Every weekly build changes the registers, and every page prints the date of
the data behind it — but a number quoted from this site in an estimates
hearing needs to stay reachable at the page that showed it, whatever this
week's run does. So each build writes one small file, data/editions/<date>.json,
holding what the registers and the closure figures were on that date, and the
site publishes it at /as-at/<date>/. The file is written before the
publishability gate, so an edition exists only for a build that was fit to
publish, and the commit that carries it is tagged edition-<date> so the whole
dataset behind the page can be found in the repository.

Edition files are never rewritten: a second run on the same date replaces that
date's file (the later build is the one that was published); an earlier date's
file is left alone.

    python snapshot_edition.py
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
OUT = DATA / "editions"


def read(name: str) -> list[dict]:
    with open(DATA / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def senate_status(r: dict) -> str:
    # Mirrors statusOf() on the Senate page.
    return ("Being considered" if truthy(r["being_considered"])
            else "Answered in part" if truthy(r["partial_response"])
            else "Interim response" if truthy(r["interim_response"])
            else "Nothing received")


def house_status(r: dict) -> str:
    # Mirrors statusOf() on the House page.
    return ("Answered in part" if truthy(r["partial_response"])
            else "Being considered" if truthy(r["being_considered"])
            else "Nothing received" if truthy(r["overdue"])
            else "Not yet due")


def register(name: str, ledger: str, meta_name: str, status) -> dict:
    rows = read(ledger)
    meta = json.loads((DATA / meta_name).read_text(encoding="utf-8"))
    rows.sort(key=lambda r: -int(r["days_outstanding"]))
    return {
        "schedule_as_at": meta["as_at"],
        "schedule_tabled": meta["tabled"],
        "schedule_url": meta["otd_url"],
        "outstanding_at_schedule": meta["outstanding_at_schedule"],
        "answered_since_schedule": meta.get("answered_since_schedule", 0),
        "outstanding": len(rows),
        "overdue": sum(1 for r in rows if truthy(r["overdue"])),
        "being_considered": sum(1 for r in rows if truthy(r["being_considered"])),
        "longest_days": max((int(r["days_outstanding"]) for r in rows), default=0),
        "rows": [{
            "title": r["title"], "committee": r["committee"], "tabled": r["report_tabled"],
            "days": int(r["days_outstanding"]), "status": status(r),
            "url": r.get("report_url", "") or "",
            "both": truthy(r.get("also_on_other_register", "")),
        } for r in rows],
    }


def coverage_totals() -> dict:
    """The stated-position totals for this build, from coverage_summary.json,
    so an edition records what the responses page said as well as what the
    registers said. Absent (an older dataset) reads as an empty dict."""
    f = DATA / "coverage_summary.json"
    if not f.exists():
        return {}
    s = json.loads(f.read_text(encoding="utf-8"))
    t = s.get("total", {})
    return {k: t.get(k) for k in ("responses", "recommendations", "position_stated",
                                  "accepted", "in_part_or_in_principle", "not_accepted",
                                  "noted_no_position", "form_letter",
                                  "not_addressed_individually", "unreadable", "coverage")}


def main() -> int:
    senate_meta = json.loads((DATA / "ledger_meta.json").read_text(encoding="utf-8"))
    house_meta = json.loads((DATA / "house_ledger_meta.json").read_text(encoding="utf-8"))
    date = senate_meta.get("rebuilt") or senate_meta["as_at"]
    checked = sorted(d for d in (senate_meta.get("responses_checked_to"),
                                 house_meta.get("responses_checked_to")) if d)

    excluded = {r["id"] for r in read("scope_exclusions.csv")}
    docs = [r for r in read("response_documents.csv") if r["id"] not in excluded]
    tabled = lambda r: (r["tabled_senate"] or r["tabled_house"])[:10]
    recs = read("recommendations.csv") if (DATA / "recommendations.csv").exists() else []

    edition = {
        "date": date,
        "responses_checked_to": checked[0] if checked else "",
        "dataset_tag": f"edition-{date}",
        "senate": register("senate", "ledger_v2.csv", "ledger_meta.json", senate_status),
        "house": register("house", "house_ledger.csv", "house_ledger_meta.json", house_status),
        "corpus": {
            "documents_read": len(docs),
            "form_letter_closures": sum(1 for r in docs if r["classification"] == "proforma_closure"),
            "read_from": min(tabled(r) for r in docs),
            "read_to": max(tabled(r) for r in docs),
        },
        "recommendations": {
            "rows": len(recs),
            "awaiting_a_response": sum(1 for r in recs if r["response_classification"] == "awaiting a response"),
        },
        "coverage": coverage_totals(),
        "on_both_registers": senate_meta.get("on_both_registers") or house_meta.get("on_both_registers") or 0,
    }
    if edition["senate"]["outstanding"] == 0 or edition["house"]["outstanding"] == 0:
        print("REFUSING: an empty register is not an edition", file=sys.stderr)
        return 1

    OUT.mkdir(exist_ok=True)
    path = OUT / f"{date}.json"
    path.write_text(json.dumps(edition, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"edition {date}: Senate {edition['senate']['outstanding']}, House "
          f"{edition['house']['outstanding']}, responses checked to "
          f"{edition['responses_checked_to']} -> {path.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
