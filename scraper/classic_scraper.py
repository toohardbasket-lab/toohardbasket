"""
classic_scraper.py — fetch the Senate StatsNet Classic government-responses
registers (2000–2011) and parse them into rows.

The Classic archive is static server-rendered HTML: div.box containing
h2.head3 (committee) followed by ul.no-bullet.stats > li (entries).
aph.gov.au serves 403 to non-browser user agents, so we send browser-like
headers. Be polite: one request per year, cached to raw/.

Usage:
    python classic_scraper.py            # all years 2000-2011
    python classic_scraper.py 2007 2011  # a range
"""
from __future__ import annotations
import sys, time, pathlib
import requests
from bs4 import BeautifulSoup
from thb_parser import parse_classic_text, Row

BASE = ("https://www.aph.gov.au/Parliamentary_Business/Statistics/"
        "Senate_StatsNet_Classic/documents/governmentresponses/{year}")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

RAW = pathlib.Path(__file__).parent / "raw"
CLASSIC_YEARS = range(2000, 2012)  # the archive holds data to 31 Dec 2011


def fetch_year(year: int, session: requests.Session) -> str:
    """Return the register text for one year (cached in raw/)."""
    cache = RAW / f"classic_{year}.html"
    if cache.exists():
        html = cache.read_text(encoding="utf-8")
    else:
        resp = session.get(BASE.format(year=year), headers=HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text
        RAW.mkdir(exist_ok=True)
        cache.write_text(html, encoding="utf-8")
        time.sleep(2)  # politeness delay between live fetches
    return html


def html_to_register_text(html: str) -> tuple[str, int | None]:
    """Reduce the page to marker-tagged text for the parser, and extract the
    register's own stated total. Markup varies by era (verified against the
    live cache, 23 Aug 2026):
      2000-01: h2.head3 + ul/li, entries have NO report date (title + response)
      2002-03: h2.head3 + <p> entries inside indented divs
      2004:    plain h2 ('40th Parliament' sections) + plain h3 committees + li
      2005-11: h2.head3 + ul/li with full report/response lines
    Committee headings are emitted as '## <name>' so the parser never has to
    guess heading vs title. Returns (text, stated_total or None)."""
    soup = BeautifulSoup(html, "html.parser")
    box = None
    for div in soup.select("div.box"):
        if div.find(["h2", "h3"]):
            box = div
            break
    if box is None:
        raise ValueError("register container (div.box with headings) not found — "
                         "page layout may have changed; refusing to guess")

    # stated total from the header table: a 'Total' row wins, else sum rows
    stated = None
    table = box.find("table")
    if table:
        vals, total = [], None
        for tr in table.find_all("tr"):
            td = tr.find("td")
            if td:
                digits = "".join(c for c in td.get_text() if c.isdigit())
                if digits:
                    v = int(digits)
                    if "total" in tr.get_text().lower():
                        total = v
                    else:
                        vals.append(v)
        stated = total if total is not None else (sum(vals) if vals else None)

    lines = []
    for el in box.find_all(["h2", "h3", "li", "p"]):
        if el.name in ("h2", "h3"):
            # collapse ALL whitespace — source HTML wraps headings mid-name
            t = " ".join(el.get_text(" ", strip=True).split())
            if t:
                lines.append("## " + t)
        else:
            if el.find(["li", "p"]):
                continue  # container holding real entries; skip wrapper
            # split ONLY on real <br> tags — get_text("\n") would also split
            # at inline tags like <em>, shredding titles into phantom entries
            for br in el.find_all("br"):
                br.replace_with("\x00")
            for t in el.get_text(" ", strip=True).split("\x00"):
                t = " ".join(t.split())
                if t:
                    lines.append(t)
    return "\n".join(lines), stated


def scrape(years=CLASSIC_YEARS) -> list[Row]:
    rows: list[Row] = []
    mismatches: list[str] = []
    with requests.Session() as s:
        for year in years:
            html = fetch_year(year, s)
            text, stated = html_to_register_text(html)
            year_rows = parse_classic_text(text, source=BASE.format(year=year))
            note = f" (register states {stated})" if stated is not None else ""
            print(f"{year}: {len(year_rows)} responses{note}")
            if stated is not None and len(year_rows) != stated:
                mismatches.append(f"{year}: parsed {len(year_rows)} vs stated {stated}")
            rows.extend(year_rows)
    if mismatches:
        raise ValueError("parsed counts disagree with the register's own totals — "
                         "refusing to continue: " + "; ".join(mismatches))
    return rows


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]]
    years = range(args[0], args[1] + 1) if len(args) == 2 else CLASSIC_YEARS
    all_rows = scrape(years)
    print(f"total: {len(all_rows)} rows")
