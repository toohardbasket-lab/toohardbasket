"""harvest_schedules.py — every President's report, not just the latest one.

The register publishes what the President records today. What he recorded last
year, and the year before, is on the same public register and says something
the current edition cannot: how long the government has been saying the same
thing about a report.

There are nine of these reports on the Tabled Documents register, twice a year
from June 2022 (OTD's index does not go back further). Each is the same
document in a new edition, so the parser that reads the current one reads all
of them.

Downloads any President's report not already in ledger/ as
presidents_<as-at>.pdf. Cached: a schedule that has been tabled never changes.

Usage: python harvest_schedules.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime

HERE = pathlib.Path(__file__).parent
LEDGER = HERE / "ledger"
SEARCH = "https://otd.aph.gov.au/public-api/api/search"
DOC = "https://otd.aph.gov.au/public-api/api/documents/{id}"
FILE = "https://otd.aph.gov.au/public-api/api/documents/{id}/files/{file_id}"

TITLE = re.compile(
    r"president.{0,3}s report to the senate on the status of government responses", re.I)
AS_AT = re.compile(r"as at (\d{1,2} [A-Za-z]+ \d{4})", re.I)


def _post(payload: dict) -> dict:
    req = urllib.request.Request(SEARCH, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url), timeout=180) as r:
        return r.read()


def find_all() -> list[dict]:
    base = {"searchTerm": "", "documentCategories": ["Presented by the President"],
            "documentTypes": [], "departments": [], "parliamentNumbers": [],
            "isDisallowable": [], "sortBy": 1, "sortDirection": 1,
            "pageSize": 100, "currentPage": 1, "tableHouse": True, "tableSenate": True}
    pages = _post(base).get("pageCount", 1)
    out = []
    for page in range(1, pages + 1):
        for d in (_post({**base, "currentPage": page}).get("results") or []):
            if not TITLE.search(d["title"]):
                continue
            m = AS_AT.search(d["title"])
            if not m:
                continue
            try:
                as_at = datetime.strptime(m.group(1), "%d %B %Y").date()
            except ValueError:
                continue
            out.append({"as_at": as_at, "doc_id": d["id"], "title": d["title"],
                        "files": d.get("files") or []})
    return sorted(out, key=lambda s: s["as_at"])


def main() -> int:
    LEDGER.mkdir(exist_ok=True)
    schedules = find_all()
    print(f"{len(schedules)} President's reports on the Tabled Documents register, "
          f"{schedules[0]['as_at']} to {schedules[-1]['as_at']}")
    got = 0
    for s in schedules:
        path = LEDGER / f"presidents_{s['as_at'].isoformat()}.pdf"
        if path.exists() and path.stat().st_size > 40_000:
            continue
        files = s["files"] or (json.loads(_get(DOC.format(id=s["doc_id"])))
                               .get("document", {}).get("files") or [])
        pdf = next((f for f in files if f["name"].lower().endswith(".pdf")), None)
        if not pdf:
            print(f"  {s['as_at']}: no PDF on OTD "
                  f"({', '.join(f['name'] for f in files) or 'no files'})", file=sys.stderr)
            continue
        path.write_bytes(_get(FILE.format(id=s["doc_id"], file_id=pdf["fileId"])))
        print(f"  {s['as_at']}  OTD {s['doc_id']}  {path.stat().st_size // 1024}KB")
        got += 1
    print(f"{got} downloaded; {len(list(LEDGER.glob('presidents_*.pdf')))} on disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
