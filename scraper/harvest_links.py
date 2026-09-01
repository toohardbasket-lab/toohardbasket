"""harvest_links.py — OTD's own report-to-response links.

Every government response document on the Tabled Documents register may carry
`documentLinks`, and each link names the committee report it answers:

    {"linkedDocumentId": 10074, "finalGovernmentResponseId": 17576,
     "committeeDocumentId": 10074, "linkedDocumentTitle": "..."}

That is the Parliament's own statement of which response answers which report.
It beats any title match we can write, and it is the only thing safe enough to
remove a row from a register with. Coverage is partial — most response records
carry no links at all — so it supplements title matching rather than replacing
it, and a row is only ever removed when a link or a tight title match says so.

The links live on the response record, not the report record: fetching a
committee report returns an empty documentLinks list. They also sit at the top
level of the API payload, beside `document`, not inside it.

Reads data/response_documents.csv for the ids, writes data/response_report_links.csv
(one row per link). Caches, so re-running only fetches ids it has not seen.

Usage: python harvest_links.py [--refetch]
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
SRC = DATA / "response_documents.csv"
OUT = DATA / "response_report_links.csv"
SEEN = DATA / "response_report_links_seen.txt"
DOC = "https://otd.aph.gov.au/public-api/api/documents/{doc_id}"

FIELDS = ["response_id", "response_title", "report_id", "report_title", "link_id"]


def fetch(doc_id: str) -> tuple[str, list[dict] | None]:
    """Returns the document's links, or None if the fetch failed.

    `documentLinks` is a sibling of `document` in the payload, not a field
    inside it. Reading it from the wrong level returns an empty list for every
    document and silently produces a link file with nothing in it.
    """
    req = urllib.request.Request(DOC.format(doc_id=doc_id),
                                 headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.load(r)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"  {doc_id}: {e}", file=sys.stderr, flush=True)
        return doc_id, None
    return doc_id, payload.get("documentLinks") or []


def main(argv: list[str]) -> int:
    refetch = "--refetch" in argv
    ids = {}
    with open(SRC, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ids[r["id"]] = r["title"]

    seen: set[str] = set()
    rows: list[dict] = []
    if not refetch and OUT.exists() and SEEN.exists():
        seen = set(SEEN.read_text(encoding="utf-8").split())
        with open(OUT, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

    todo = [i for i in ids if i not in seen]
    print(f"{len(ids)} response documents, {len(seen)} already fetched, "
          f"{len(todo)} to go", flush=True)

    # One request per document and no bulk endpoint, so fetch them in parallel.
    # Eight at a time keeps the whole sweep inside a single run.
    with ThreadPoolExecutor(max_workers=8) as pool:
        for doc_id, links in pool.map(fetch, todo):
            if links is None:
                continue
            for l in links:
                rows.append({
                    "response_id": doc_id,
                    "response_title": ids[doc_id],
                    "report_id": l.get("committeeDocumentId") or l.get("linkedDocumentId") or "",
                    "report_title": l.get("linkedDocumentTitle") or "",
                    "link_id": l.get("linkId") or "",
                })
            seen.add(doc_id)

    _write(rows, seen)
    linked = len({r["response_id"] for r in rows})
    print(f"wrote {OUT.name}: {len(rows)} links across {linked} of {len(ids)} "
          f"response documents ({linked / max(1, len(ids)):.0%} coverage)")
    return 0


def _write(rows: list[dict], seen: set[str]) -> None:
    rows = sorted(rows, key=lambda r: (int(r["response_id"]), str(r["link_id"])))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    SEEN.write_text("\n".join(sorted(seen, key=int)) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
