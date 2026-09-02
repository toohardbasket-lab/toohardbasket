"""
otd_sweep.py — the pro-forma sweep.

Downloads EVERY 'Government response' document from the APH Online Tabled
Documents system (2022 onward), extracts its text, and classifies it:
did the government actually respond, or close the report with the
"passage of time" template?

API (mapped 25 Aug 2026 by intercepting the aph.gov.au frontend's calls):
  POST https://otd.aph.gov.au/public-api/api/search
       body: {pageSize, currentPage, searchString, dateFrom, dateTo,
              documentCategories:[], documentTypes:['Government response'],
              authors:[], tableSenate, tableHouse, additionalDocumentTypes:[],
              departments:[], parliamentNumbers:[], isDisallowable:[],
              sortBy:'relevance', sortDirection:'descending'}
       -> {results:[{id,title,...}], rowCount, pageCount, facets}
  GET  https://otd.aph.gov.au/public-api/api/documents/{id}
       -> {document:{title, author, department, typeEnum, tabledSenate,
                     tabledHouse, parliamentNumber, files:[{fileId,name,size}]}}
  GET  https://otd.aph.gov.au/public-api/api/documents/{id}/files/{fileId}
       -> the document bytes (.docx or .pdf)

Usage:
    pip install requests pdfplumber
    python otd_sweep.py               # full sweep (~656 docs, 15-25 min)
    python otd_sweep.py 20            # first 20 only (smoke test)
    python otd_sweep.py --reclassify  # OCR pass over cached 'unreadable' docs
                                      # (needs: pip install pytesseract pypdfium2
                                      #  + the Tesseract engine installed)
    python otd_sweep.py --refresh     # classify only what is new since the last
                                      # run — this is what the weekly job runs,
                                      # and what keeps the published closure
                                      # figures from freezing on the last day
                                      # the full sweep was run by hand
    python otd_sweep.py --rescore     # re-classify EVERY row from the cache —
                                      # run after any change to the classifier
                                      # regexes; text is cached in raw/otd_text/
                                      # so repeat rescores are near-instant

Downloads are cached in raw/otd/ so re-runs are free. --reclassify touches
only the cache — no new downloads — re-reading every row currently marked
'unreadable' with OCR and rewriting the CSV in place.
Output: data/response_documents.csv + a printed summary.
"""
from __future__ import annotations
import csv, io, re, sys, time, pathlib, zipfile
import requests

HERE = pathlib.Path(__file__).parent
CACHE = HERE / "raw" / "otd"
TEXT_CACHE = HERE / "raw" / "otd_text"   # extracted/OCR'd text, so rescoring is instant
OUT = HERE / "data" / "response_documents.csv"
API = "https://otd.aph.gov.au/public-api/api"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Origin": "https://www.aph.gov.au",
    "Referer": "https://www.aph.gov.au/",
}

# The template fingerprint, with light tolerance for wording drift
TEMPLATE_RE = re.compile(
    r"(passage\s+of\s+time|time\s+(that\s+has\s+)?elapsed)"
    r".{0,220}?"
    r"(no\s+longer\s+(be\s+)?(appropriate|required|warranted)|"
    r"not\s+(be\s+)?(appropriate|proposed))",
    re.I | re.S)
NOTES_RE = re.compile(r"notes?\s+th(is|e|ese)\s+recommendation", re.I)
# A recommendation counts as accepted only when the GOVERNMENT is the one
# accepting: either a "the Government supports/accepted/agrees…" sentence, or
# a standalone "Agreed / Supported in principle" response label. Bare verbs
# ('support', 'accept') inside quoted committee recommendations must NOT count
# — responses quote lines like "recommends that the government support…" and
# even org names like 'Support Act' (bug found in Alan's spot-check, docs
# 5815/5912: pure proformas miscalled partial).
ACCEPT_RE = re.compile(
    r"(?<![\w-])government\s+"
    r"(?:(?:has|have|had|is|will|also|therefore|broadly|generally|further|"
    r"fully|partially|strongly|in[\s-]principle)\s+){0,2}"
    r"(?:accepts|accepted|supports|supported|agrees|agreed)\b"
    r"|^\s*(?:government\s+)?(?:response\s*:?\s*)?"
    r"(?:agreed|accepted|supported)"
    r"(?:\s+in\s+(?:principle|part))?\s*\.?\s*$",
    re.I | re.M)


def search_all(session: requests.Session, limit: int | None) -> list[dict]:
    docs, page = [], 1
    while True:
        body = {"pageSize": 100, "currentPage": page, "searchString": "",
                "dateFrom": "2022-07-01", "dateTo": time.strftime("%Y-%m-%d"),
                "documentCategories": [], "documentTypes": ["Government response"],
                "authors": [], "tableSenate": True, "tableHouse": True,
                "additionalDocumentTypes": [], "departments": [],
                "parliamentNumbers": [], "isDisallowable": [],
                "sortBy": "relevance", "sortDirection": "descending"}
        r = session.post(f"{API}/search", json=body, headers=HEADERS, timeout=30)
        r.raise_for_status()
        j = r.json()
        docs += j["results"]
        print(f"search page {page}/{j['pageCount']}: {len(docs)}/{j['rowCount']}")
        if limit and len(docs) >= limit:
            return docs[:limit]
        if page >= j["pageCount"]:
            if len(docs) != j["rowCount"]:
                raise ValueError(f"enumerated {len(docs)} but API says {j['rowCount']}")
            return docs
        page += 1
        time.sleep(0.4)


def fetch_file(session, doc_id: int, file_id: int, name: str) -> bytes:
    ext = pathlib.Path(name).suffix.lower() or ".bin"
    cache = CACHE / f"{doc_id}_{file_id}{ext}"
    if cache.exists():
        return cache.read_bytes()
    r = session.get(f"{API}/documents/{doc_id}/files/{file_id}",
                    headers=HEADERS, timeout=60)
    r.raise_for_status()
    CACHE.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(r.content)
    time.sleep(0.5)
    return r.content


def _tesseract_ready() -> bool:
    """True if pytesseract + the Tesseract engine are both usable."""
    global _TESS
    if _TESS is not None:
        return _TESS
    try:
        import pytesseract, pypdfium2  # noqa: F401
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            # Windows default install path, if not on PATH
            import os
            cand = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(cand):
                pytesseract.pytesseract.tesseract_cmd = cand
                pytesseract.get_tesseract_version()
            else:
                raise
        _TESS = True
    except Exception as e:
        print(f"  (OCR unavailable: {e})")
        _TESS = False
    return _TESS


_TESS: bool | None = None
OCR_MAX_PAGES = 40   # sanity cap; template closures are short anyway


def ocr_pdf(data: bytes) -> str:
    """Rasterise a scanned PDF with pypdfium2 and OCR it with Tesseract."""
    import pytesseract, pypdfium2
    pdf = pypdfium2.PdfDocument(io.BytesIO(data))
    out = []
    try:
        for i, page in enumerate(pdf):
            if i >= OCR_MAX_PAGES:
                out.append(f"[ocr truncated at {OCR_MAX_PAGES} pages]")
                break
            bitmap = page.render(scale=300 / 72)   # ~300 dpi
            out.append(pytesseract.image_to_string(bitmap.to_pil()))
            bitmap.close(); page.close()
    finally:
        pdf.close()
    return "\n".join(out)


def extract_text(data: bytes, name: str, ocr: bool = False) -> str:
    n = name.lower()
    if n.endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        return re.sub(r"<[^>]+>", " ", re.sub(r"<w:p[^>]*>", "\n", xml))
    if n.endswith(".pdf"):
        import pdfplumber
        text = ""
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for pg in pdf.pages:
                text += (pg.extract_text() or "") + "\n"
        if len(text.strip()) < 40 and ocr and _tesseract_ready():
            text = ocr_pdf(data)
        return text
    return ""   # .doc/.rtf etc — flagged unreadable


def classify(text: str) -> tuple[str, int, int, int]:
    if len(text.strip()) < 40:
        return "unreadable", 0, 0, 0
    tmpl = len(TEMPLATE_RE.findall(text))
    notes = len(NOTES_RE.findall(text))
    accepts = len(ACCEPT_RE.findall(text))
    if tmpl and accepts == 0:
        return "proforma_closure", tmpl, notes, accepts
    if tmpl:
        return "partial_proforma", tmpl, notes, accepts
    return "substantive", tmpl, notes, accepts


def write_rows(rows: list[dict]) -> None:
    """Write the CSV via a temp file so a crash can't corrupt it, waiting out
    a Windows file lock (Excel holding the CSV open) instead of losing the run."""
    import os
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    while True:
        try:
            os.replace(tmp, OUT)
            return
        except PermissionError:
            print(f"\n{OUT.name} is locked — close it in Excel, then press Enter to save…")
            try:
                input()
            except EOFError:
                print(f"(results kept in {tmp} — rename it over {OUT.name} manually)")
                return


def cached_text(cache: pathlib.Path) -> str:
    """Text for a cached download — reads the text cache when present,
    otherwise extracts (with OCR fallback) and saves it for next time."""
    tc = TEXT_CACHE / (cache.stem + ".txt")
    if tc.exists():
        return tc.read_text(encoding="utf-8")
    text = extract_text(cache.read_bytes(), cache.name, ocr=True)
    if text.strip():
        TEXT_CACHE.mkdir(parents=True, exist_ok=True)
        tc.write_text(text, encoding="utf-8")
    return text


def reclassify(only_unreadable: bool):
    """Re-run classification over cached files, rewriting the CSV in place.

    only_unreadable=True  (--reclassify): OCR retry of 'unreadable' rows only.
    only_unreadable=False (--rescore):    every row — use after changing the
                                          classifier regexes."""
    if not _tesseract_ready():
        print("Install first:  pip install pytesseract pypdfium2")
        print("plus the Tesseract engine: https://github.com/UB-Mannheim/tesseract/wiki")
        return 1
    with open(OUT, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    todo = ([r for r in rows if r["classification"] == "unreadable"]
            if only_unreadable else rows)
    print(f"{len(todo)} rows to re-classify")
    changed = missing = 0
    for i, r in enumerate(todo, 1):
        caches = sorted(CACHE.glob(f"{r['id']}_*"))
        if not caches:
            print(f"  ! {r['id']} no cached file — run the full sweep first")
            missing += 1
            continue
        text = ""
        for cache in caches:
            try:
                text = cached_text(cache)
            except Exception as e:
                print(f"  ! {r['id']} {cache.name}: {e}")
            if text.strip():
                break
        cls, tmpl, notes, accepts = classify(text)
        if cls != r["classification"]:
            changed += 1
            print(f"  {r['id']}: {r['classification']} -> {cls}  ({r['title'][:55]})")
        r.update({"classification": cls, "template_hits": tmpl,
                  "notes_recommendation": notes, "accept_support_agree": accepts,
                  "text_length": len(text.strip())})
        if i % 50 == 0:
            print(f"  …{i}/{len(todo)}")
    write_rows(rows)

    from collections import Counter
    c = Counter(r["classification"] for r in rows)
    print(f"\n=== RE-CLASSIFICATION DONE: {changed} rows changed class"
          + (f", {missing} missing from cache" if missing else "") + " ===")
    print(f"full dataset now ({len(rows)} responses):")
    for k, v in c.most_common():
        print(f"  {k}: {v} ({v/len(rows)*100:.1f}%)")
    print(f"rewrote {OUT}")
    return 0


def harvest_one(session, doc: dict) -> dict:
    """Download, extract and classify one response document.

    The extracted text is written to the text cache as it goes. That cache is
    tracked in the repository and is what --rescore reads, so a document
    classified by a weekly run can be re-scored later without downloading it
    again — and the evidence behind a published classification is in the
    repository rather than only on whichever machine ran the sweep.
    """
    doc_id = doc["id"]
    meta = session.get(f"{API}/documents/{doc_id}", headers=HEADERS,
                       timeout=30).json()["document"]
    time.sleep(0.3)
    text, fname = "", ""
    for f in meta.get("files") or []:
        fname = f["name"]
        try:
            data = fetch_file(session, doc_id, f["fileId"], f["name"])
            text = extract_text(data, f["name"], ocr=True)
            if text.strip():
                TEXT_CACHE.mkdir(parents=True, exist_ok=True)
                # Same stem as the download cache, so cached_text() and
                # --rescore find it: "<doc id>_<file id>.txt".
                (TEXT_CACHE / f"{doc_id}_{f['fileId']}.txt").write_text(
                    text, encoding="utf-8")
        except Exception as e:
            print(f"  ! {doc_id} {f['name'][:40]}: {e}")
        if text.strip():
            break
    cls, tmpl, notes, accepts = classify(text)
    return {
        "id": doc_id, "classification": cls, "template_hits": tmpl,
        "notes_recommendation": notes, "accept_support_agree": accepts,
        "text_length": len(text.strip()),
        "title": meta["title"], "author": meta.get("author") or "",
        "department": meta.get("department") or "",
        "tabled_senate": (meta.get("tabledSenate") or "")[:10],
        "tabled_house": (meta.get("tabledHouse") or "")[:10],
        "parliament": meta.get("parliamentNumber"), "file": fname,
        "url": f"https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{doc_id}",
    }


# A week that adds more responses than this has not happened since the record
# began; the largest single day on file is 39. A number above the cap means
# something structural changed — a re-scoped search, a re-published back run —
# and the run should stop for a person to look rather than publish it.
REFRESH_CAP = 80


def refresh(force: bool = False) -> int:
    """Classify the response documents tabled since the last run.

    Why enumerate everything rather than ask for a date range: the API's date
    filter is not the tabling date. The corpus holds documents tabled in April
    2022 that a dateFrom of 1 July 2022 still returns, so a window keyed to the
    newest tabling date on file would silently miss anything back-dated. The
    search returns metadata only and costs seven calls, so the whole list is
    enumerated every week and only the unseen ids are downloaded.

    This is the step that stopped the closure figures being frozen on whatever
    day the full sweep was last run by hand. The home page quotes them.
    """
    if not OUT.exists():
        print(f"{OUT} does not exist — run the full sweep first: python otd_sweep.py")
        return 1
    with open(OUT, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    known = {str(r["id"]) for r in rows}

    session = requests.Session()
    docs = search_all(session, None)
    listed = {str(d["id"]) for d in docs}

    # A partial enumeration must never be mistaken for documents disappearing.
    if len(listed) < len(known) * 0.9:
        print(f"REFUSING: OTD listed {len(listed)} documents but we hold {len(known)}. "
              "That is a short read, not a shrinking record.")
        return 1

    gone = known - listed
    if gone:
        print(f"  note: {len(gone)} document(s) we hold are no longer listed by OTD "
              f"({', '.join(sorted(gone)[:8])}). Rows kept; nothing is deleted here.")

    new = [d for d in docs if str(d["id"]) not in known]
    if not new:
        print(f"No new response documents. {len(rows)} on file.")
        return 0
    if len(new) > REFRESH_CAP and not force:
        print(f"REFUSING: {len(new)} new documents, over the cap of {REFRESH_CAP}. "
              "Check what changed, then re-run with --force if it is genuine.")
        return 1

    print(f"{len(new)} new response document(s) to classify")
    added = []
    for i, d in enumerate(new, 1):
        row = harvest_one(session, d)
        added.append(row)
        print(f"  {i}/{len(new)}  {row['id']}  {row['classification']:<17} "
              f"{(row['tabled_senate'] or row['tabled_house'] or '?')}  {row['title'][:60]}")

    merged = rows + [{k: ("" if v is None else v) for k, v in r.items()} for r in added]
    merged.sort(key=lambda r: int(r["id"]))
    write_rows(merged)

    from collections import Counter
    c = Counter(r["classification"] for r in added)
    print(f"\n=== REFRESH DONE: {len(added)} added, {len(merged)} on file ===")
    for k, v in c.most_common():
        print(f"  {k}: {v}")
    unread = [r for r in added if r["classification"] == "unreadable"]
    if unread:
        print(f"\n  {len(unread)} could not be read as text. They are counted in the "
              "corpus and classified as neither closure nor substantive, which "
              "understates the closure count. Run --reclassify with OCR available.")
    print(f"wrote {OUT}")
    return 0


def main(argv):
    if len(argv) > 1 and argv[1] == "--reclassify":
        return reclassify(only_unreadable=True)
    if len(argv) > 1 and argv[1] == "--rescore":
        return reclassify(only_unreadable=False)
    if len(argv) > 1 and argv[1] == "--refresh":
        return refresh(force="--force" in argv)
    limit = int(argv[1]) if len(argv) > 1 else None
    s = requests.Session()
    docs = search_all(s, limit)

    rows = [harvest_one(s, d) for d in docs]

    write_rows(rows)

    from collections import Counter
    c = Counter(r["classification"] for r in rows)
    print(f"\n=== SWEEP COMPLETE: {len(rows)} government responses ===")
    for k, v in c.most_common():
        print(f"  {k}: {v} ({v/len(rows)*100:.1f}%)")
    flushdays = Counter(r["tabled_senate"] for r in rows
                        if r["classification"] == "proforma_closure")
    print("\npro-forma closures by tabling day (top 10):")
    for day, n in flushdays.most_common(10):
        print(f"  {day or '(house only)'}: {n}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
