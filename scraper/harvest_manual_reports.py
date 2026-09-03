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
       and put the page it came from in that folder's SOURCES.txt, one per line
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


# The columns this step maintains. Anything else already in the file is carried
# through untouched — a rewrite that silently drops a column another step
# depends on is a bug that only shows up as work having to be done twice.
FIELDS = ["key", "chamber", "also_on", "report_tabled", "days_outstanding",
          "committee", "title", "report_page_url", "pdf_source_url",
          "collected", "notes"]


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
        # Carry anything another step has added that this one knows nothing
        # about, rather than dropping it on the next rewrite.
        for k, v in prior.items():
            out[-1].setdefault(k, v)
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
    extra = [k for k in rows[0] if k not in FIELDS]
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS + extra, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


SOURCES = PDFS / "SOURCES.txt"


def read_sources(rows: list[dict]) -> int:
    """Fold URLs recorded in a plain text file into the manifest.

    The manifest is a CSV with em-dashes in the committee names, and a
    spreadsheet opened and saved without thinking about the encoding will
    quietly replace them. Nobody should have to think about that to record
    twenty-six URLs, so they can be written one per line here instead:

        1  https://www.aph.gov.au/...
        2  https://www.aph.gov.au/...

    as a number from the list or a key, then any whitespace, then the URL.
    Lines starting with # are ignored. The CSV stays the record; this is just a
    safer way to write to it.
    """
    if not SOURCES.exists():
        return 0
    by_key = {r["key"]: r for r in rows}
    by_num = {str(i): r for i, r in enumerate(rows, 1)}
    n, unknown, attached = 0, [], []
    for line in SOURCES.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or not parts[1].lower().startswith("http"):
            unknown.append(line[:70])
            continue
        which, url = parts[0].strip(), parts[1].strip()
        row = by_num.get(which) or by_key.get(which)
        if not row:
            unknown.append(line[:70])
            continue
        if row.get("pdf_source_url") != url:
            row["pdf_source_url"] = url
            attached.append((which, row["title"]))
            n += 1
    # Printed one per line, because a number is a position in this list and a
    # position can move: if a report is answered and leaves the registers, every
    # number after it shifts, and a URL written against the old numbering would
    # silently attach to the wrong report. Seeing what each one landed on is
    # the check. Writing the key instead of the number cannot go wrong at all.
    for which, title in attached:
        print(f"    {which} -> {title[:64]}")
    if unknown:
        print(f"\n  {len(unknown)} line(s) in {SOURCES.name} were not understood "
              "(expected: a number or key, then a URL):")
        for u in unknown[:6]:
            print(f"    {u}")
    return n


STOP = {"the", "and", "for", "into", "based", "report", "reports", "inquiry",
        "australia", "australian", "government", "committee", "final", "second",
        "first", "third", "interim", "provisions", "bill", "amendment", "act"}


def title_terms(title: str) -> set[str]:
    """The words in a title that actually distinguish it from another title."""
    return {w for w in _norm(title).split() if len(w) > 3 and w not in STOP}


def report_number(title: str) -> str | None:
    m = re.search(r"report\s*(?:no\.?\s*)?(\d{2,4})", _norm(title))
    return m.group(1) if m else None


def identify(text: str, candidates: list[dict]) -> tuple[dict | None, str]:
    """Work out which report a PDF is, by reading it.

    Requiring an exact filename put the whole burden on transcription, and the
    failure it invites is the worst one available here: a PDF filed against the
    wrong report publishes that committee's recommendations under another
    committee's name. Reading the first pages and matching them against the
    titles we are looking for costs nothing and catches it.

    A match has to be clear. Where two reports score alike — the numbered
    Auditor-General series are near-identical in wording — nothing is claimed
    and the file is left for the number to decide.
    """
    head = _norm(text[:6000])
    scored = []
    for r in candidates:
        terms = title_terms(r["title"])
        hit = sum(1 for t in terms if t in head)
        score = hit / len(terms) if terms else 0.0
        num = report_number(r["title"])
        if num:
            # "Report 460" in the document is worth more than any wording.
            score += 0.75 if re.search(rf"report\s*{num}\b", head) else -0.25
        year = (r.get("report_tabled") or "")[:4]
        if year and year in head:
            score += 0.15
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    if not scored or scored[0][0] < 0.55:
        return None, "nothing in the first pages matches a report on the list"
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.25:
        return None, (f"could be {scored[0][1]['title'][:44]!r} or "
                      f"{scored[1][1]['title'][:44]!r} — too close to call")
    return scored[0][1], ""


def claim_by_content(rows: list[dict], pdfplumber) -> list[str]:
    """Adopt any PDF in the folder, whatever it is called, if it can be read."""
    taken = {f"{r['key']}.pdf" for r in rows}
    loose = [p for p in sorted(PDFS.glob("*.pdf"))
             if p.name not in taken and not re.fullmatch(r"\d+\.pdf", p.name)]
    if not loose:
        return []
    wanted = [r for r in rows if not (PDFS / f"{r['key']}.pdf").exists()]
    out = []
    for pdf in loose:
        try:
            with pdfplumber.open(pdf) as doc:
                head = "\n".join((pg.extract_text() or "") for pg in doc.pages[:3])
        except Exception as exc:
            out.append(f"{pdf.name}: could not be opened — {str(exc).splitlines()[0][:60]}")
            continue
        match, why = identify(head, wanted)
        if not match:
            out.append(f"{pdf.name}: {why}")
            continue
        pdf.rename(PDFS / f"{match['key']}.pdf")
        wanted = [r for r in wanted if r["key"] != match["key"]]
        out.append(f"{pdf.name}\n      is {match['title'][:60]} — filed")
    return out


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
    try:
        import pdfplumber
    except ImportError:
        sys.exit("pdfplumber is needed to read the PDFs: pip install -r requirements.txt")

    write_manifest(rows)          # keep the list current with the registers
    noted = read_sources(rows)
    if noted:
        print(f"  {noted} source URL(s) recorded from {SOURCES.name}")
        write_manifest(rows)
    renamed = claim_numbered(rows)
    for line in renamed:
        print(f"  renamed {line}")
    for line in claim_by_content(rows, pdfplumber):
        print(f"  {line}")
    if "--list" in argv:
        return show(rows)

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
