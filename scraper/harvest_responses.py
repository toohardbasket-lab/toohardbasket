"""harvest_responses.py — keep the list of tabled government responses current.

The step that takes an answered report off a register reads
data/response_documents.csv. Until now the only thing that wrote that file was
otd_sweep.py, which downloads and classifies every response and needs OCR, and
which nobody had put in the weekly job. So the registers were rebuilt every
Tuesday against a list of responses that was refreshed by hand, and a response
tabled in a sitting week would not be seen until someone remembered. The House
register has no second source of responses at all, which is how six answered
reports came to be published as waiting.

This is the missing half: a metadata-only sweep of the Tabled Documents
register for government responses tabled since the newest one on file. No
downloads, no OCR, no classification — the removal step needs an id, a title
and a tabling date, and nothing more. The closure analysis stays with
otd_sweep.py, where the reading of documents belongs.

Rows added here carry an empty classification, which is honest: the document
has been seen, not read. otd_sweep.py fills that in when it next runs.

Usage: python harvest_responses.py [--since YYYY-MM-DD]
Writes data/response_documents.csv in place.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import urllib.request
from datetime import date, timedelta

# How far back to re-read the register each run. See main() — the watermark
# alone loses anything back-dated onto a day already seen.
LOOK_BACK_DAYS = 30

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
OUT = DATA / "response_documents.csv"
SEARCH = "https://otd.aph.gov.au/public-api/api/search"
DOC_URL = "https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{id}"


def search(page: int, size: int = 100) -> dict:
    payload = {
        "searchTerm": "", "documentCategories": [], "documentTypes": ["Government response"],
        "departments": [], "parliamentNumbers": [], "isDisallowable": [],
        "sortBy": 1, "sortDirection": 1, "pageSize": size, "currentPage": page,
        "tableHouse": True, "tableSenate": True,
    }
    req = urllib.request.Request(SEARCH, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    # A 200 whose shape has changed must not read as a quiet week. Without this,
    # a renamed field would make every page yield no results, the step would
    # print "nothing new" and exit 0, and the registers would go on publishing
    # answered reports as waiting for as long as nobody noticed.
    if not isinstance(data, dict) or "results" not in data:
        raise SystemExit(
            f"The Tabled Documents search returned a {type(data).__name__} with keys "
            f"{sorted(data)[:8] if isinstance(data, dict) else '—'}; expected an object "
            "with 'results'. The API has changed shape. Stopping rather than reporting "
            "no new responses.")
    rs = data.get("results")
    if rs and not all(isinstance(d, dict) and "id" in d for d in rs):
        raise SystemExit("The search returned results without an 'id'. The API has changed "
                         "shape. Stopping rather than reporting no new responses.")
    return data


def iso(value) -> str:
    return (value or "")[:10]


def main(argv: list[str]) -> int:
    with OUT.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys())
    known = {r["id"] for r in rows}
    seen_to = max((max(r["tabled_senate"], r["tabled_house"]) for r in rows), default="")
    # A month's look-back, not "everything after the newest date on file". A
    # document tabled on a day already on file but added to the register a week
    # later would otherwise be skipped for ever, silently, because its date is
    # not after the watermark. Ids are de-duplicated a few lines down, so
    # re-reading a month of metadata costs nothing but the same seven calls.
    default_since = ""
    if seen_to:
        default_since = (date.fromisoformat(seen_to[:10]) - timedelta(days=LOOK_BACK_DAYS)).isoformat()
    since = argv[argv.index("--since") + 1] if "--since" in argv else default_since
    print(f"{len(rows)} responses on file, latest tabled {seen_to[:10] or 'unknown'}; "
          f"re-reading everything tabled after {since or 'the beginning'}")

    found, pages = [], search(1).get("pageCount", 1)
    for page in range(1, pages + 1):
        results = search(page).get("results") or []
        if not results:
            break
        for d in results:
            doc_id = str(d["id"])
            tabled = max(iso(d.get("tabledSenate")), iso(d.get("tabledHouse")))
            if doc_id in known or not tabled or tabled <= since:
                continue
            found.append({
                "id": doc_id, "classification": "", "template_hits": "",
                "notes_recommendation": "", "accept_support_agree": "", "text_length": "",
                "title": d.get("title") or "", "author": d.get("author") or "",
                "department": d.get("department") or "",
                "tabled_senate": iso(d.get("tabledSenate")),
                "tabled_house": iso(d.get("tabledHouse")),
                "parliament": d.get("parliamentNumber") or "", "file": "",
                "url": DOC_URL.format(id=doc_id),
            })
            known.add(doc_id)

    if not found:
        print("nothing new")
        return 0

    # A sweep that suddenly finds hundreds is a changed API, not a busy week.
    if len(found) > 200:
        print(f"{len(found)} new responses — implausible, refusing to write", file=sys.stderr)
        return 1

    for r in sorted(found, key=lambda r: max(r["tabled_senate"], r["tabled_house"])):
        print(f"  {max(r['tabled_senate'], r['tabled_house'])}  OTD {r['id']}  {r['title'][:64]}")
    rows.extend(found)
    tmp = OUT.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(OUT)
    print(f"added {len(found)}; {len(rows)} responses on file as at {date.today()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
