"""harvest_manual_reports.py — read the reports the Tabled Documents index cannot supply.

The recommendation index has a hole, and it is exactly where the site's
strongest material is. Both halves of the index come from the Tabled Documents
register: the government responses, and the PDFs of the reports still waiting.
That register holds nothing before 2022. So the eighteen longest-waiting reports
on the two registers — including the freedom-of-information report tabled on
25 November 2014 that the home page leads with, 4,299 days and counting — have
no document there to read, and not one of their recommendations is searchable.

A journalist reads "the longest has been waiting 11 years, 9 months", searches
for what that committee actually asked for, and finds nothing.

Those reports do exist; they are on the committees' own pages on aph.gov.au,
which refuses automated requests. So they are collected by hand, once, into
raw/report_pdfs_manual/, and this step reads them into the same text cache the
automatic harvest writes to. From there the ordinary extractor treats them like
any other report: same parser, same verification, same drop rules.

The one thing that differs is provenance, and the index says so on every row:
these were fetched by a person from a named URL, not by a script from an API.
data/reports_manual.csv records where each came from, so the claim is checkable.

    1. python harvest_manual_reports.py --list     what is still needed
    2. save each PDF in raw/report_pdfs_manual/ as its number — 1.pdf, 2.pdf —
       and fill pdf_source_url in the CSV
    3. python harvest_manual_reports.py            renames and reads them
    4. python extract_recommendations.py
       python extract_report_recommendations.py
       python verify_recommendations.py

Nothing here downloads anything.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys
import unicodedata

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
PDFS = HERE / "raw" / "report_pdfs_manual"
TEXT = HERE / "raw" / "report_text"
MANIFEST = DATA / "reports_manual.csv"

# A report PDF that reads as almost nothing is a scan, or a failed extraction.
# Publishing recommendations cut out of 200 characters of noise would be worse
# than publishing none, so it is refused and named.
MIN_CHARS = 3000


FIELDS = ["key", "chamber", "also_on", "report_tabled", "days_outstanding",
          "committee", "title", "pdf_source_url", "collected", "notes"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _dedupe_key(title: str) -> str:
    """A joint report is listed by both presiding officers under near-identical
    titles, and is one document. Numbered reports match on their number; the
    rest on their normalised title."""
    m = re.match(r"report\s*(\d+)", _norm(title))
    return f"report-{m.group(1)}" if m else _norm(title)[:60]


def _slug(s: str, n: int = 40) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()[:n].strip("-")


def rebuild(existing: list[dict]) -> list[dict]:
    """Re-derive the list of reports needing collection from the registers.

    The manifest cannot be a file written once. Reports leave the registers when
    they are answered, and a row that has left should stop being asked for; the
    site also publishes how many are still missing, and that number has to come
    from the same place as the work. Anything already recorded — the URL a PDF
    came from, whether it has been read, any note — is carried across untouched.
    """
    keep = {r["key"]: r for r in existing}
    groups: dict[str, dict] = {}
    for name, chamber in (("ledger_v2.csv", "senate"), ("house_ledger.csv", "house")):
        path = DATA / name
        if not path.exists():
            continue
        for r in csv.DictReader(open(path, encoding="utf-8-sig")):
            if (r.get("report_otd_id") or "").strip():
                continue
            g = groups.setdefault(_dedupe_key(r.get("title", "")),
                                  {"rows": [], "chambers": []})
            g["rows"].append(r)
            g["chambers"].append(chamber)

    out = []
    for g in groups.values():
        first = min(g["rows"], key=lambda r: r.get("report_tabled") or "")
        tabled = first.get("report_tabled") or ""
        key = f"m-{tabled}-{_slug(first.get('title', ''))}"
        prior = keep.get(key, {})
        out.append({
            "key": key,
            "chamber": g["chambers"][0],
            "also_on": ";".join(sorted(set(g["chambers"]))) if len(set(g["chambers"])) > 1 else "",
            "report_tabled": tabled,
            "days_outstanding": first.get("days_outstanding", ""),
            "committee": first.get("committee", ""),
            "title": first.get("title", ""),
            "pdf_source_url": prior.get("pdf_source_url", ""),
            "collected": prior.get("collected", ""),
            "notes": prior.get("notes", ""),
        })
    out.sort(key=lambda r: r["report_tabled"])
    return out


def manifest() -> list[dict]:
    existing: list[dict] = []
    if MANIFEST.exists():
        with MANIFEST.open(newline="", encoding="utf-8-sig") as f:
            existing = list(csv.DictReader(f))
    rows = rebuild(existing)
    if not rows:
        print("Every report on both registers has a Tabled Documents id — nothing to collect.")
    return rows


def write_manifest(rows: list[dict]) -> None:
    if not rows:
        return
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def claim_numbered(rows: list[dict]) -> list[str]:
    """Let a PDF be saved as 1.pdf and renamed into place.

    The keys are fifty characters long, and twenty-six of them have to be typed
    exactly or the file is silently ignored. The number beside each entry in
    --list is the position in this list, so a PDF saved under that number is
    renamed to its key here. The number is not an identifier and is not stored
    anywhere: it is only good until the list changes, which is why the rename
    happens at once rather than the number being used as a key.
    """
    renamed = []
    for i, r in enumerate(rows, 1):
        n = PDFS / f"{i}.pdf"
        if not n.exists():
            continue
        proper = PDFS / f"{r['key']}.pdf"
        if proper.exists():
            print(f"  {i}.pdf ignored — {r['key']}.pdf is already here")
            continue
        n.rename(proper)
        renamed.append(f"{i}.pdf -> {r['title'][:56]}")
    return renamed


def show(rows: list[dict]) -> int:
    have = [r for r in rows if (PDFS / f"{r['key']}.pdf").exists()]
    print(f"{len(rows)} reports on the registers have no Tabled Documents id.")
    print(f"{len(have)} collected, {len(rows) - len(have)} still needed.\n")
    print(f"Save each PDF in {PDFS.relative_to(HERE.parent)}/ as its NUMBER below — 1.pdf,")
    print("2.pdf and so on — and this step renames it. Put the page you took it from in")
    print(f"pdf_source_url in {MANIFEST.name}, which is what the site links to.\n")
    for i, r in enumerate(rows, 1):
        done = " [collected]" if (PDFS / f"{r['key']}.pdf").exists() else ""
        print(f"  {str(i).rjust(2)}. {r['report_tabled']}  "
              f"{str(r['days_outstanding']).rjust(5)} days waiting{done}")
        print(f"      {r['committee']}")
        print(f"      {r['title']}")
        print(f"      save as: {i}.pdf      (becomes {r['key']}.pdf)\n")
    return 0


def main(argv: list[str]) -> int:
    rows = manifest()
    PDFS.mkdir(parents=True, exist_ok=True)
    TEXT.mkdir(parents=True, exist_ok=True)

    write_manifest(rows)          # keep the list current with the registers
    renamed = claim_numbered(rows)
    for line in renamed:
        print(f"  renamed {line}")
    if "--list" in argv:
        return show(rows)

    try:
        import pdfplumber
    except ImportError:
        sys.exit("pdfplumber is needed to read the PDFs: pip install -r requirements.txt")

    read, skipped, thin, bad = 0, 0, [], []
    for r in rows:
        pdf = PDFS / f"{r['key']}.pdf"
        if not pdf.exists():
            skipped += 1
            continue
        out = TEXT / f"{r['key']}.txt"
        # A saved web page, a truncated download or a login wall saved as .pdf
        # are all likely in a job done by hand twenty-six times. Name the file
        # and carry on rather than ending the run with a stack trace.
        try:
            with pdfplumber.open(pdf) as doc:
                text = "\n".join((p.extract_text() or "") for p in doc.pages)
        except Exception as exc:
            bad.append((pdf.name, str(exc).split("\n")[0][:80]))
            continue
        if len(text.strip()) < MIN_CHARS:
            thin.append((r["key"], len(text.strip())))
            r["collected"] = ""
            r["notes"] = ((r.get("notes") or "") +
                          " read as too little text to be a report; probably a scan").strip()
            continue
        out.write_text(text, encoding="utf-8")
        r["collected"] = "yes"
        read += 1
        print(f"  {r['report_tabled']}  {len(text):>7,} chars  {r['title'][:56]}")

    write_manifest(rows)
    print(f"\n{read} report(s) read into {TEXT.relative_to(HERE.parent)}/, {skipped} still to collect")
    if thin:
        print("\nThese produced almost no text and were not written — a scanned PDF needs OCR:")
        for k, n in thin:
            print(f"  {k}  ({n} characters)")
    if bad:
        print("\nThese could not be opened as PDFs at all — check what was actually saved:")
        for k, why in bad:
            print(f"  {k}\n    {why}")
    if read:
        print("\nNow run: python extract_report_recommendations.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
