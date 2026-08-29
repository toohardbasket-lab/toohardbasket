"""
harvest_reports.py — every committee report tabled, from the OTD API.

The Ledger needs the universe of reports, not just the ones that got an answer:
outstanding = reports tabled − reports with a response. Until now that universe
came from a hand-copied text dump whose source was not recorded, which meant the
site's headline figure could not be re-derived or attributed. This replaces it
with the same public API that otd_sweep.py already uses for responses.

Coverage note: the OTD database effectively begins in mid-2022 (1,239 committee
reports from 1990 vs 1,238 from 2010). Reports tabled before that are only
available from the President of the Senate's schedule, so build_ledger_v2.py
still carries those rows.

Usage:
    python harvest_reports.py
Writes data/committee_reports.csv and prints a summary.
"""
from __future__ import annotations

import csv
import os
import pathlib
import sys
import time
from collections import Counter

import requests

HERE = pathlib.Path(__file__).parent
OUT = HERE / "data" / "committee_reports.csv"

API = "https://otd.aph.gov.au/public-api/api"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Origin": "https://www.aph.gov.au",
    "Referer": "https://www.aph.gov.au/",
}
DATE_FROM = "1990-01-01"
FIELDS = ["id", "tabled_senate", "tabled_house", "committee", "title",
          "additional_type", "parliament", "url"]


def search_all(session: requests.Session) -> list[dict]:
    docs, page, expected = [], 1, None
    while True:
        body = {"pageSize": 100, "currentPage": page, "searchString": "",
                "dateFrom": DATE_FROM, "dateTo": time.strftime("%Y-%m-%d"),
                "documentCategories": [], "documentTypes": ["Committee report"],
                "authors": [], "tableSenate": True, "tableHouse": True,
                "additionalDocumentTypes": [], "departments": [],
                "parliamentNumbers": [], "isDisallowable": [],
                "sortBy": "relevance", "sortDirection": "descending"}
        r = session.post(f"{API}/search", json=body, headers=HEADERS, timeout=30)
        r.raise_for_status()
        j = r.json()
        expected = j["rowCount"]
        docs += j["results"]
        print(f"  page {page}/{j['pageCount']}: {len(docs)}/{expected}")
        if page >= j["pageCount"]:
            break
        page += 1
    # Refuse to write a short harvest rather than silently shrink the Ledger.
    if len(docs) != expected:
        raise SystemExit(f"enumerated {len(docs)} but the API reports {expected}")
    return docs


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
    print(f"harvesting committee reports from {DATE_FROM}...")
    with requests.Session() as s:
        docs = search_all(s)

    rows = []
    for d in docs:
        rows.append({
            "id": d["id"],
            "tabled_senate": (d.get("tabledSenate") or "")[:10],
            "tabled_house": (d.get("tabledHouse") or "")[:10],
            "committee": d.get("author") or d.get("department") or "",
            "title": (d.get("title") or "").strip(),
            "additional_type": d.get("additionalType") or "",
            "parliament": d.get("parliamentNumber") or "",
            "url": f"https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{d['id']}",
        })
    rows.sort(key=lambda r: (r["tabled_senate"] or r["tabled_house"]), reverse=True)
    write_rows(rows)

    dated = [r for r in rows if r["tabled_senate"] or r["tabled_house"]]
    senate_only = [r for r in rows if r["tabled_senate"]]
    print(f"\n{len(rows):,} committee reports "
          f"({len(dated):,} with a tabling date, {len(senate_only):,} tabled in the Senate)")
    print("additional types:", dict(Counter(r["additional_type"] for r in rows if r["additional_type"])))
    span = sorted(r["tabled_senate"] or r["tabled_house"] for r in dated)
    print(f"span: {span[0]} to {span[-1]}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
