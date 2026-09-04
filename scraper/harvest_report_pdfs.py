"""Download and read the reports on the registers, so their recommendations
can join the index.

A report on a register has not been answered, so no government response quotes
its recommendations. The report itself is the only source. Every report on
either register that carries a Tabled Documents id has a PDF there, and none of
them links to a committee web page, so the PDF is the route that covers the
whole register rather than part of it.

Text is cached under raw/report_text/ and tracked, like the response text: the
evidence behind a published quotation belongs in the repository, and it means a
re-parse costs nothing and downloads nothing.

    python harvest_report_pdfs.py              # the reports on the registers
    python harvest_report_pdfs.py --answered   # the reports whose response quotes
                                               # none of their recommendations
"""
from __future__ import annotations

import csv
import io
import pathlib
import sys
import time

import requests

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "report_text"
API = "https://otd.aph.gov.au/public-api/api"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Origin": "https://www.aph.gov.au",
    "Referer": "https://www.aph.gov.au/",
}


def register_report_ids() -> list[str]:
    ids: list[str] = []
    for name in ("ledger_v2.csv", "house_ledger.csv"):
        for r in csv.DictReader(open(DATA / name, encoding="utf-8-sig")):
            if r.get("report_otd_id") and r["report_otd_id"] not in ids:
                ids.append(r["report_otd_id"])
    return sorted(ids, key=int)


def answered_quietly_report_ids() -> list[str]:
    """The reports answered by a response that quotes none of their
    recommendations — see link_responses_to_reports.py. The response gives
    the index nothing to show, so the report is read instead, exactly as a
    report still on a register is. Needs recommendations.csv as
    extract_recommendations.py has just written it, and the pairing file.
    """
    pairs = DATA / "response_reports.csv"
    recs = DATA / "recommendations.csv"
    if not pairs.exists() or not recs.exists():
        return []
    quoted = {r["source_id"] for r in csv.DictReader(open(recs, encoding="utf-8-sig"))
              if r["source"] == "response"}
    excluded = {r["id"] for r in csv.DictReader(open(DATA / "scope_exclusions.csv", encoding="utf-8-sig"))}
    ids: list[str] = []
    for r in csv.DictReader(open(pairs, encoding="utf-8-sig")):
        if r["report_id"] and r["response_id"] not in quoted and r["response_id"] not in excluded:
            if r["report_id"] not in ids:
                ids.append(r["report_id"])
    return sorted(ids, key=int)


def fetch(session: requests.Session, doc_id: str) -> tuple[str, str]:
    """Returns (status, note). Text lands in the cache; nothing is returned."""
    import pdfplumber
    out = TEXT / f"{doc_id}.txt"
    if out.exists():
        return "cached", ""
    meta = session.get(f"{API}/documents/{doc_id}", headers=HEADERS, timeout=60
                       ).json()["document"]
    pdfs = [f for f in (meta.get("files") or []) if f["name"].lower().endswith(".pdf")]
    if not pdfs:
        return "skipped", "no pdf"
    data = session.get(f"{API}/documents/{doc_id}/files/{pdfs[0]['fileId']}",
                       headers=HEADERS, timeout=300).content
    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    body = "\n".join(pages)
    if len(body.strip()) < 500:
        return "skipped", "no text layer"
    TEXT.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return "read", f"{len(pdf.pages)}pp"


def main(argv: list[str]) -> int:
    answered = "--answered" in argv
    argv = [a for a in argv if a != "--answered"]
    ids = answered_quietly_report_ids() if answered else register_report_ids()
    if len(argv) > 1:
        ids = ids[:int(argv[1])]
    session = requests.Session()
    done: dict[str, int] = {}
    for i, doc_id in enumerate(ids, 1):
        try:
            status, note = fetch(session, doc_id)
        except Exception as e:
            status, note = "failed", str(e)[:70]
        done[status] = done.get(status, 0) + 1
        if status != "cached":
            print(f"  {i}/{len(ids)} {doc_id}: {status} {note}", flush=True)
        time.sleep(0.2)
    print(f"\n{len(ids)} reports {'answered without their recommendations being quoted' if answered else 'on the registers'}: " +
          ", ".join(f"{v} {k}" for k, v in sorted(done.items())))
    print(f"text cache: {len(list(TEXT.glob('*.txt')))} files in {TEXT}")
    return 0 if done.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
