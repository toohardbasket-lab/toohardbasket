"""harvest_rc_reports.py — read the royal commission reports, and keep the text.

harvest_royal_commissions.py says which tabled documents are a commission's
report. This downloads those documents and keeps their text, so a
recommendation can be published in the commission's own words rather than in a
government's transcription of them.

It reads a PDF the way harvest_report_pdfs.py does — pdfplumber, page by page,
joined with a newline — and for a reason that was measured rather than assumed.
pdftotext is forty times faster and was tried: on the Disability Royal
Commission's recommendations volume it finds 202 of the 222 recommendation
headings, because twenty of them wrap differently under it. pdfplumber finds
all 222. Speed is not worth twenty recommendations.

Both reports in the source test of 6 September 2026 carry a native text layer
and neither needs OCR. Four of Robodebt's 364 front-matter pages and three of
the Disability executive summary's 356 come back empty; those are covers and
dividers.

Text is cached under raw/rc_report_text/<document id>_<file id>.txt and is
tracked, like the response and report text already in the repository: the
evidence behind a published quotation belongs here, and a re-parse then costs
nothing and downloads nothing. A document published as several files gets one
text file per file — the Disability Royal Commission's first volume is three
books, and its seventh is four.

These reports are long: the tabled Robodebt report is 1,039 pages and takes
more than two minutes to read, which is longer than some shells allow. So a
file is read in chunks against a time budget, the chunks are kept beside the
text until the file is finished, and running the step again carries on where it
stopped. Nothing is published from a half-read file.

By default it reads the report documents marked in rc_seed.csv as carrying the
recommendations, because that is what this register needs and because a royal
commission report can be very long: the Disability Royal Commission's twelve
volumes run to some thousands of pages, and all 222 of its recommendations are
set out in the thirteenth document. The extraction step checks what it found
against the number the report itself states, so a recommendation that lived
only in a volume would show up as a shortfall rather than as nothing. --all
reads every report document.

    python3 harvest_rc_reports.py                          # the recommendation volumes
    python3 harvest_rc_reports.py --commission robodebt    # one commission, repeatable
    python3 harvest_rc_reports.py --only 3444              # one document
    python3 harvest_rc_reports.py --seconds 300            # a longer budget per run
    python3 harvest_rc_reports.py --all                    # every report document
    python3 harvest_rc_reports.py --list                   # what is read and what is not
"""
from __future__ import annotations

import csv
import io
import pathlib
import re
import sys
import time

import requests

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "rc_report_text"
PARTS = TEXT / "parts"
DOCUMENTS = DATA / "rc_documents.csv"
FILE = "https://otd.aph.gov.au/public-api/api/documents/{id}/files/{file_id}"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Origin": "https://www.aph.gov.au",
    "Referer": "https://www.aph.gov.au/",
}
# Below this a PDF has no text layer worth the name and would need OCR. That is
# a fact about the document, not a failure of this step: it is named, nothing is
# written, and the extraction will have nothing from it and will say so.
FEWEST_CHARACTERS = 500
DEFAULT_SECONDS = 90
PART = re.compile(r"\.part-(\d+)-(\d+)\.txt$")


def reports(argv: list[str]) -> list[dict]:
    """The report documents to read, and the PDF files each is published as."""
    wanted = {argv[i + 1] for i, a in enumerate(argv) if a == "--commission"}
    only = argv[argv.index("--only") + 1] if "--only" in argv else ""
    out = []
    with DOCUMENTS.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["role"] != "report":
                continue
            if "--all" not in argv and not (r.get("carries_recommendations") or "").strip():
                continue
            if wanted and r["commission_id"] not in wanted:
                continue
            if only and r["id"] != only:
                continue
            for pair in (r["files"] or "").split(";"):
                file_id, _, name = pair.strip().partition("|")
                if file_id and name.lower().endswith(".pdf"):
                    out.append({**r, "file_id": file_id, "file_name": name})
    return out


def cached(job: dict) -> pathlib.Path:
    return TEXT / f"{job['id']}_{job['file_id']}.txt"


def parts_of(job: dict) -> list[pathlib.Path]:
    """The chunks read so far, in page order."""
    found = list(PARTS.glob(f"{job['id']}_{job['file_id']}.part-*.txt")) if PARTS.exists() else []
    return sorted(found, key=lambda p: int(PART.search(p.name).group(1)))


def read_from(job: dict) -> int:
    """The page to start at: one past the end of the last chunk."""
    done = parts_of(job)
    return int(PART.search(done[-1].name).group(2)) if done else 0


def download(session: requests.Session, job: dict) -> bytes:
    return session.get(FILE.format(id=job["id"], file_id=job["file_id"]),
                       headers=HEADERS, timeout=300).content


def read_pages(data: bytes, start: int, seconds: int) -> tuple[str, int, int, int]:
    """Read from page `start` until the budget is spent. Returns text and counts."""
    import pdfplumber
    pages, blank, until = [], 0, time.monotonic() + seconds
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        total = len(pdf.pages)
        for page in pdf.pages[start:]:
            text = page.extract_text() or ""
            pages.append(text)
            blank += 0 if text.strip() else 1
            if time.monotonic() > until:
                break
    return "\n".join(pages), start + len(pages), total, blank


def finish(job: dict) -> int:
    """Join the chunks into the cached text and take the chunks away."""
    done = parts_of(job)
    body = "\n".join(p.read_text(encoding="utf-8") for p in done)
    if len(body.strip()) < FEWEST_CHARACTERS:
        print(f"{job['id']}_{job['file_id']}: no text layer — nothing written", file=sys.stderr)
    else:
        cached(job).write_text(body, encoding="utf-8")
    for p in done:
        p.unlink()
    return len(body)


def main(argv: list[str]) -> int:
    jobs = reports(argv)
    if not jobs:
        print("no report documents match", file=sys.stderr)
        return 1
    if "--list" in argv:
        for j in jobs:
            path = cached(j)
            if path.exists():
                state = f"{path.stat().st_size:>10,} bytes"
            elif parts_of(j):
                state = f"part read to page {read_from(j)}"
            else:
                state = "not read"
            print(f"{j['id']:>6} {j['file_id']:>6}  {state:>22}  {j['file_name'][:56]}")
        done = sum(1 for j in jobs if cached(j).exists())
        print(f"{done} of {len(jobs)} files read")
        return 0

    seconds = int(argv[argv.index("--seconds") + 1]) if "--seconds" in argv else DEFAULT_SECONDS
    TEXT.mkdir(parents=True, exist_ok=True)
    PARTS.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    finished, unfinished = [], []
    until = time.monotonic() + seconds
    for job in jobs:
        if cached(job).exists():
            continue
        if time.monotonic() > until:
            break
        start = read_from(job)
        data = download(session, job)
        body, read_to, total, blank = read_pages(data, start, int(until - time.monotonic()))
        (PARTS / f"{job['id']}_{job['file_id']}.part-{start}-{read_to}.txt").write_text(
            body, encoding="utf-8")
        if read_to >= total:
            size = finish(job)
            finished.append(job)
            print(f"{job['id']}_{job['file_id']}: {total} pages, {size:,} characters, "
                  f"{blank} pages with no text in this run  {job['file_name'][:44]}")
        else:
            unfinished.append(job)
            print(f"{job['id']}_{job['file_id']}: read to page {read_to} of {total}; "
                  "run again to carry on")

    waiting = [j for j in jobs if not cached(j).exists()]
    print(f"{len(finished)} finished this run, {len(jobs) - len(waiting)} of {len(jobs)} "
          f"files read in all, {len(waiting)} still to read")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
