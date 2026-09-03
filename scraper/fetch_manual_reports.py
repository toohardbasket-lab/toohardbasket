"""fetch_manual_reports.py — download the reports the Tabled Documents register cannot supply.

These reports are on the registers, have waited longest, and are missing from
the recommendation index because the Tabled Documents API does not go back far
enough. They are all published on their committees' own pages.

It was said, in this repository and to the person doing the work, that
aph.gov.au refuses automated requests and so they had to be collected by hand.
That was wrong, and it cost someone an afternoon before it was checked: the site
refuses a bare request, and answers normally to one that identifies itself as a
browser. Twenty-six documents were about to be fetched by a person because
nobody tried the second thing.

What this does, for each report whose page URL is recorded in the manifest:

    fetch the committee's report page
    find the whole-report PDF on it, not a chapter and not a submission
    download it
    check by reading it that it is the report we asked for
    record where it came from

The check matters more than the download. A page can offer six PDFs, and filing
the wrong one publishes a committee's recommendations under another committee's
name. Anything that cannot be identified confidently is left alone and named.

    python fetch_manual_reports.py            # everything still missing
    python fetch_manual_reports.py --only 3   # one entry, by its number

Then: python harvest_manual_reports.py, which reads them into the text cache.
"""
from __future__ import annotations

import csv
import html
import pathlib
import re
import sys
import tempfile
import time
import urllib.parse

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
PDFS = HERE / "raw" / "report_pdfs_manual"
MANIFEST = DATA / "reports_manual.csv"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA,
           "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
           "Accept-Language": "en-AU,en;q=0.9"}

# One request every second and a half. Nothing here is urgent, and a public
# register that hammers a parliamentary website to build itself would deserve
# everything it got.
PAUSE = 1.5

# A chapter is a PDF too. The whole report is the one worth having, and these
# are the names committees give it.
WHOLE = re.compile(r"(complete|whole|entire|full)[\s_-]*report|(^|/)report\.pdf$"
                   r"|final[\s_-]*report", re.I)
CHAPTER = re.compile(r"/(c|a|b|d|e|f)\d{2}\.pdf$|chapter|appendix|submission"
                     r"|dissent|minority|terms[\s_-]*of[\s_-]*reference", re.I)


def rows() -> list[dict]:
    with MANIFEST.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save(data: list[dict]) -> None:
    with MANIFEST.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader()
        w.writerows(data)


def get(session, url: str, **kw):
    time.sleep(PAUSE)
    return session.get(url, headers=HEADERS, timeout=60, allow_redirects=True, **kw)


def pdf_links(page_url: str, page_html: str) -> list[str]:
    """Every PDF on the page, best candidate for the whole report first."""
    found = []
    for m in re.finditer(r'href="([^"]+)"', page_html):
        # Full unescaping, not just &amp;. One report's URL carries an
        # apostrophe written as &#39;, and half-unescaping it produced a link
        # that fetched nothing and reported the page as having no PDF at all.
        href = html.unescape(m.group(1))
        if ".pdf" not in href.lower():
            continue
        # aph writes site-root media links as "~/media/...". Stripping the
        # tilde gives /media/..., which 404s; the site serves them at /-/media/.
        if href.startswith("~/"):
            href = "/-/" + href[2:]
        url = urllib.parse.urljoin(page_url, href)
        # ParlInfo hands back a PDF either way, but says so only when asked.
        if "parlinfo.aph.gov.au" in url and "fileType=" not in url:
            url += ";fileType=application%2Fpdf"
        if url not in found:
            found.append(url)

    def rank(u: str) -> tuple[int, int]:
        return (0 if WHOLE.search(u) else (2 if CHAPTER.search(u) else 1), len(u))

    return sorted(found, key=rank)


def looks_like(text: str, title: str, tabled: str) -> float:
    """How much of the wanted title turns up in the document's first pages."""
    import unicodedata
    def norm(s):
        s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
        return re.sub(r"[^a-z0-9]+", " ", s)
    head, want = norm(text[:6000]), norm(title)
    stop = {"the", "and", "for", "into", "based", "report", "inquiry", "australia",
            "australian", "government", "committee", "final", "provisions", "bill"}
    terms = {w for w in want.split() if len(w) > 3 and w not in stop}
    score = sum(1 for t in terms if t in head) / len(terms) if terms else 0.0
    m = re.search(r"report\s*(?:no\.?\s*)?(\d{2,4})", want)
    if m:
        score += 0.75 if re.search(rf"report\s*{m.group(1)}\b", head) else -0.25
    if tabled[:4] and tabled[:4] in head:
        score += 0.15
    return score


def main(argv: list[str]) -> int:
    try:
        import requests
        import pdfplumber
    except ImportError:
        sys.exit("needs requests and pdfplumber: pip install -r requirements.txt")

    data = rows()
    only = None
    if "--only" in argv:
        only = int(argv[argv.index("--only") + 1])

    PDFS.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    got, failed = 0, []

    for i, r in enumerate(data, 1):
        if only and i != only:
            continue
        target = PDFS / f"{r['key']}.pdf"
        if target.exists():
            continue
        page = (r.get("report_page_url") or "").strip()
        # A few committee pages answer a browser and 404 a script, and one
        # answers neither reliably. Where the PDF's own address is known, it is
        # recorded and used directly; the check below still has to pass, so a
        # wrong address is caught the same way a wrong link would be.
        direct = (r.get("pdf_direct_url") or "").strip()
        if not page and not direct:
            failed.append((i, r["title"], "no report_page_url in the manifest"))
            continue

        print(f"\n{i:>2}. {r['title'][:66]}")
        if direct:
            candidates = [direct]
        else:
            try:
                resp = get(session, page)
                resp.raise_for_status()
            except Exception as exc:
                failed.append((i, r["title"], f"page: {str(exc)[:70]}"))
                continue
            candidates = pdf_links(page, resp.text)
            if not candidates:
                failed.append((i, r["title"], "no PDF linked from that page"))
                continue

        best, chosen = None, None
        for url in candidates[:4]:
            try:
                pr = get(session, url)
                # What it IS, not what it says it is. ParlInfo serves these
                # with no content-type at all unless the URL carries a
                # fileType parameter, and the header check silently skipped
                # every report published through it.
                if pr.status_code != 200 or not pr.content.startswith(b"%PDF"):
                    continue
                # Scratch goes to a temp directory, never into the folder the
                # collected reports live in: a half-downloaded candidate sitting
                # beside them is one careless glob away from being published,
                # and the folder is the user's, not ours to litter.
                tmp = pathlib.Path(tempfile.gettempdir()) / "thb_candidate.pdf"
                tmp.write_bytes(pr.content)
                with pdfplumber.open(tmp) as doc:
                    head = "\n".join((p.extract_text() or "") for p in doc.pages[:3])
                    pages = len(doc.pages)
                score = looks_like(head, r["title"], r.get("report_tabled", ""))
                print(f"      {score:4.2f}  {pages:>3}pp  {url.split('/')[-1][:44]}")
                if best is None or score > best:
                    best, chosen = score, (url, pr.content, pages)
            except Exception as exc:
                print(f"      --    {url.split('/')[-1][:44]}  ({str(exc)[:40]})")

        if not chosen or best < 0.55:
            failed.append((i, r["title"],
                           f"nothing on the page reads like this report (best {best or 0:.2f})"))
            continue

        url, content, pages = chosen
        target.write_bytes(content)
        r["pdf_source_url"] = page or url
        r["notes"] = (f"downloaded from {url.split('/')[-1]}, {pages} pages, "
                      f"title match {best:.2f}").strip()
        got += 1
        print(f"      kept  {len(content) // 1024} KB, {pages} pages")

    save(data)
    print(f"\n{got} downloaded. {len(failed)} still to do.")
    for i, title, why in failed:
        print(f"  {i:>2}. {title[:58]}\n      {why}")
    if got:
        print("\nNow run: python harvest_manual_reports.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
