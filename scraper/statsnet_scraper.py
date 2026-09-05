"""
statsnet_scraper.py — fetch the modern Senate StatsNet government-responses
register (2012 onward) via a headless browser.

Why Playwright rather than requests: the register lives in an ASP.NET
WebForms page (VIEWSTATE postbacks) whose date-range refine control drives
the data. Driving the real page is far more robust than reverse-engineering
postbacks, and matches exactly what a human sees. Verified interactively
23 Aug 2026: the table is a client-side jQuery DataTable (serverSide:false),
so once a range is loaded, `Show: All` puts every row in the DOM.

The register lists responses TABLED OR PRESENTED within the date range.

Usage:
    pip install playwright && playwright install chromium
    python statsnet_scraper.py 2012 2026
"""
from __future__ import annotations
import sys, csv, pathlib
from datetime import date
from playwright.sync_api import sync_playwright
from thb_parser import parse_statsnet_cells, Row

URL = ("https://www.aph.gov.au/Parliamentary_Business/Statistics/"
       "Senate_StatsNet#/government-responses")
RAW = pathlib.Path(__file__).parent / "raw"

# aph.gov.au filters non-browser user agents (it 403s requests, and serves a
# hollow shell to HeadlessChrome) — present as a normal desktop Chrome.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# readiness: the government-responses table is the one whose header row
# includes 'Committee' — anything else (e.g. the calendar widget) is noise
READY_JS = ("() => [...document.querySelectorAll('table')].some(t => "
            "[...t.querySelectorAll('th')].some(h => /Committee/i.test(h.innerText)))")
TABLE_JS = ("[...document.querySelectorAll('table')].find(t => "
            "[...t.querySelectorAll('th')].some(h => /Committee/i.test(h.innerText)))")


def scrape_range(page, from_str: str, to_str: str, source: str) -> list[Row]:
    """Set the refine range (dd/mm/yyyy strings), load all rows, parse.

    Facts established by probing the live page (24 Aug 2026): the page
    serves a hollow shell to the HeadlessChrome user agent (hence UA
    override); ?from/?to URL params are IGNORED (default = current year);
    the data table is #government-responses-table; the two date fields are
    the only input[type=text] elements (empty until used; the DataTables
    search boxes are type=search); the control is button.refine-button.
    'networkidle' never settles (an accessibility widget polls forever)."""
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_function(READY_JS, timeout=45000)
    # The REFINE button is a panel TOGGLE (chevron icon). Opening it reveals
    # two react-datepicker inputs and an Apply button. React ignores raw
    # value injection, so type into the pickers like a user and click Apply.
    page.wait_for_selector("button.refine-button", state="attached", timeout=30000)
    # REFINE toggles the panel, and the page object is reused across years —
    # only click if the pickers aren't already showing (idempotent open)
    dates = page.locator(".react-datepicker__input-container input")
    if not dates.first.is_visible():
        page.evaluate("document.querySelector('button.refine-button').click()")
    dates.first.wait_for(state="visible", timeout=15000)
    for idx, val in ((0, from_str), (1, to_str)):
        dates.nth(idx).click()
        dates.nth(idx).fill(val)
        page.keyboard.press("Escape")  # dismiss the calendar popup
    page.locator('button:has-text("Apply")').first.click()
    # the label beside REFINE updates to the applied range — that's the signal
    page.wait_for_function(
        f"""() => (document.querySelector('button.refine-button')
                   .closest('div').parentElement.innerText || '')
                   .includes('{from_str}')""", timeout=30000)
    page.wait_for_function(READY_JS, timeout=45000)
    page.wait_for_timeout(2000)

    # Show all rows, then read the cells.
    page.evaluate("jQuery('#government-responses-table').DataTable().page.len(-1).draw()")
    rows_data = page.evaluate("""
        [...document.querySelectorAll('#government-responses-table tbody tr')].map(tr =>
            [...tr.querySelectorAll('td')].map(td => td.innerText))
    """)
    out = []
    for cells in rows_data:
        if len(cells) < 4:
            continue  # spacer/empty rows
        out.append(parse_statsnet_cells(cells[0], cells[1], cells[2], cells[3],
                                        source=source))
    # sanity: a FAILED refine returns the default (current-year) data — near
    # 0% rows in the requested year. A small tail outside the year is normal:
    # the register selects on tabled-OR-presented dates, and multi-response
    # inquiries carry their latest response date. Threshold 50% separates
    # the two cleanly (observed: failed ≈ 0%, genuine years ≈ 85–100%).
    year = from_str[-4:]
    inside = sum(1 for r in out if r.response_tabled.startswith(year))
    if out and inside < 0.5 * len(out):
        raise ValueError(f"{source}: only {inside}/{len(out)} rows have a "
                         f"{year} response date — REFINE range not applied?")
    # cache raw cell data for audit
    RAW.mkdir(exist_ok=True)
    with open(RAW / f"statsnet_{from_str[-4:]}_{to_str[-4:]}.csv", "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["inquiry", "committee", "report", "response"])
        w.writerows(rows_data)
    return out


def rows_from_cache(year: int) -> list[Row] | None:
    """Re-parse a year from its cached cells, without a browser.

    The cache holds the table's own cells, written on the run that scraped
    them, and it is committed. A year that has ended cannot change, so
    re-scraping it every week buys nothing and risks everything: this is the
    only step in the weekly job that needs a browser, and it drives a site
    that filters non-browser traffic. It failed on 2 September and took the
    whole build with it, which meant the registers did not refresh either —
    for data that had not moved since 2012.
    """
    path = RAW / f"statsnet_{year}_{year}.csv"
    if not path.exists():
        return None
    out: list[Row] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)   # inquiry, committee, report, response
        for cells in reader:
            if len(cells) < 4:
                continue
            out.append(parse_statsnet_cells(cells[0], cells[1], cells[2], cells[3],
                                            source=f"statsnet/{year}"))
    return out


ATTEMPTS = 3


def scrape_with_retry(page, year: int, attempts: int = ATTEMPTS) -> list[Row]:
    """Scrape one year, trying more than once before giving up on the live page.

    Nearly every failure of this step has been the same thing: aph.gov.au
    taking longer than the wait allows, on a page that loads fine a minute
    later. The scheduled run of 1 September and the manual run of 2 September
    both died that way, and both succeeded on a retry by hand. Doing the retry
    here means the fallback below is reserved for the page genuinely refusing
    us, rather than being reached on a slow morning — which matters, because
    falling back to cache is silent in the sense that the build stays green
    and the compliance series quietly stops moving.

    Each attempt re-navigates (scrape_range begins with page.goto), so a
    part-loaded page from a failed attempt cannot poison the next one.
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            rows = scrape_range(page, f"01/01/{year}", f"31/12/{year}",
                                source=f"statsnet/{year}")
            if attempt > 1:
                print(f"{year}: {len(rows)} responses (scraped on attempt {attempt})")
            else:
                print(f"{year}: {len(rows)} responses (scraped)")
            return rows
        except Exception as e:                       # noqa: BLE001 - reported below
            last = e
            if attempt < attempts:
                print(f".. {year}: attempt {attempt} of {attempts} failed "
                      f"({type(e).__name__}: {str(e).splitlines()[0][:100]}); "
                      f"waiting {attempt * 10}s and trying again.")
                page.wait_for_timeout(attempt * 10_000)
    raise last                                       # type: ignore[misc]


def scrape(year_from: int, year_to: int, refresh: set[int] | None = None) -> list[Row]:
    """Build the modern register, scraping only the years that can still change.

    By default that is the current year and any year with no cache. Pass
    refresh={...} to force particular years, or the full range for a rebuild.
    """
    if refresh is None:
        refresh = {date.today().year}
    all_rows: list[Row] = []
    todo: list[int] = []
    stale: list[int] = []
    for year in range(year_from, year_to + 1):
        cached = None if year in refresh else rows_from_cache(year)
        if cached is None:
            todo.append(year)
        else:
            print(f"{year}: {len(cached)} responses (from cache)")
            all_rows.extend(cached)

    if todo:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=UA,
                                    viewport={"width": 1600, "height": 1000})
            try:
                for year in todo:
                    try:
                        rows = scrape_with_retry(page, year)
                    except Exception as e:
                        # aph.gov.au filters automated traffic and the run may
                        # be refused on any given day. Falling back to the
                        # cached cells keeps the registers refreshing — new
                        # responses reach them through harvest_responses.py and
                        # the Tabled Documents API, not through this page — but
                        # it must never be quiet about it.
                        rows = rows_from_cache(year)
                        if rows is None:
                            raise
                        print(f"!! {year}: the live scrape failed ({type(e).__name__}: "
                              f"{str(e).splitlines()[0][:120]}).")
                        print(f"!! {year}: using {len(rows)} cached responses instead. "
                              "The compliance series is as at the last successful scrape.")
                        stale.append(year)
                    all_rows.extend(rows)
            finally:
                browser.close()
    if stale:
        print(f"\nWARNING: {len(stale)} year(s) came from cache after a failed "
              f"scrape: {', '.join(map(str, stale))}")
    return all_rows


def probe(year: int = 2012):
    """Diagnostic: load the register with ?from/to URL params and report what
    the page actually contains, so selector fixes are grounded in fact."""
    base = URL.split("#")[0]
    probe_url = f"{base}?from={year}-01-01&to={year}-12-31#/government-responses"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA)
        page.goto(probe_url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_function(READY_JS, timeout=45000)
            page.evaluate(f"jQuery({TABLE_JS}).DataTable().page.len(-1).draw()")
        except Exception as e:
            print("responses table never appeared:", str(e)[:120])
        info = page.evaluate("""() => {
            const tables = [...document.querySelectorAll('table')].map((t, i) => {
                const rows = [...t.querySelectorAll('tbody tr')];
                const first = rows.length ?
                    [...rows[0].querySelectorAll('td')].map(td =>
                        td.innerText.replace(/\\s+/g, ' ').slice(0, 90)) : [];
                const heads = [...t.querySelectorAll('th')].map(th =>
                    th.innerText.slice(0, 30)).slice(0, 6);
                return {i, id: t.id || '', cls: (t.className || '').slice(0, 40),
                        rows: rows.length, heads, first};
            });
            const refine = [...document.querySelectorAll('*')]
                .filter(e => /refine/i.test(e.value || '') ||
                             /^\\s*refine\\s*$/i.test(e.textContent || ''))
                .map(e => e.tagName + '#' + (e.id || '') + '.' +
                          (typeof e.className === 'string' ? e.className.slice(0, 30) : ''))
                .slice(0, 8);
            const label = [...document.querySelectorAll('span,div,p,label')]
                .map(e => e.textContent || '')
                .find(t => /\\d{2}\\/\\d{2}\\/\\d{4}\\s*-\\s*\\d{2}\\/\\d{2}\\/\\d{4}/.test(t));
            return {tables, refine,
                    rangeLabel: label ? label.replace(/\\s+/g,' ').slice(0, 120) : null};
        }""")
        browser.close()
    import json
    print(json.dumps(info, indent=1)[:4000])


def probe2(year: int = 2012):
    """Interaction probe: what is the refine widget, and what does clicking
    REFINE actually do?"""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA, viewport={"width": 1600, "height": 1000})
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function(READY_JS, timeout=45000)
        page.wait_for_selector("button.refine-button", state="attached", timeout=30000)
        before = page.evaluate("""() => ({
            href: location.href,
            inputs: [...document.querySelectorAll('input[type=text]')].map(i => ({
                id: i.id, name: i.name, cls: i.className,
                placeholder: i.placeholder, value: i.value,
                attrs: [...i.attributes].map(a => a.name + '=' + a.value.slice(0,40)).join(' ')
            })),
            button: document.querySelector('button.refine-button').outerHTML.slice(0, 400),
            frameworks: {angular: !!window.angular, ko: !!window.ko,
                         vue: !!window.Vue, react: !!document.querySelector('[data-reactroot]')},
            rangeText: (document.querySelector('button.refine-button').closest('div')?.parentElement?.innerText || '').slice(0, 200)
        })""")
        import json
        print("BEFORE:", json.dumps(before, indent=1))
        # now set dates, click, and see what happens
        f, t = f"01/01/{year}", f"31/12/{year}"
        page.evaluate("""([f, t]) => {
            const ins = [...document.querySelectorAll('input[type=text]')];
            ins[0].value = f; ins[1].value = t;
            for (const i of ins.slice(0, 2)) {
                i.dispatchEvent(new Event('input', {bubbles: true}));
                i.dispatchEvent(new Event('change', {bubbles: true}));
                i.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
                i.blur(); i.dispatchEvent(new Event('blur', {bubbles: true}));
            }
        }""", [f, t])
        page.evaluate("document.querySelector('button.refine-button').click()")
        page.wait_for_timeout(6000)
        after = page.evaluate("""() => ({
            href: location.href,
            rows: document.querySelectorAll('#government-responses-table tbody tr').length,
            firstResp: (document.querySelector('#government-responses-table tbody tr td:last-child') || {}).innerText || ''
        })""")
        print("AFTER:", json.dumps(after, indent=1))
        browser.close()


def probe3():
    """Open the refine panel and inventory its controls."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=UA, viewport={"width": 1600, "height": 1000})
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function(READY_JS, timeout=45000)
        page.wait_for_selector("button.refine-button", state="attached", timeout=30000)
        page.evaluate("document.querySelector('button.refine-button').click()")
        page.wait_for_timeout(2500)
        info = page.evaluate("""() => {
            const inputs = [...document.querySelectorAll('input')]
                .filter(i => i.type !== 'hidden' && !/GenericSearch/.test(i.id))
                .map(i => ({id: i.id, type: i.type, cls: (i.className||'').slice(0,40),
                            value: i.value, ph: i.placeholder||''}));
            const btns = [...document.querySelectorAll('button, a.button, input[type=button], input[type=submit]')]
                .map(b => ({tag: b.tagName, cls: (b.className||'').slice(0,50),
                            txt: (b.value || b.textContent || '').trim().slice(0,30)}))
                .filter(b => b.txt || /apply|update|refine|go|ok/i.test(b.cls));
            const selects = [...document.querySelectorAll('select')]
                .map(s => ({id: s.id, cls: (s.className||'').slice(0,40),
                            opts: [...s.options].slice(0,4).map(o=>o.text)}));
            const panels = [...document.querySelectorAll('[class*=calendar],[class*=range],[class*=picker],[class*=refine]')]
                .map(e => e.tagName + '.' + (typeof e.className==='string'?e.className.slice(0,50):''))
                .slice(0, 15);
            return {inputs, btns, selects, panels};
        }""")
        import json
        print(json.dumps(info, indent=1)[:3800])
        browser.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--probe3":
        probe3()
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--probe2":
        probe2(int(sys.argv[2]) if len(sys.argv) > 2 else 2012)
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "--probe":
        probe(int(sys.argv[2]) if len(sys.argv) > 2 else 2012)
        sys.exit(0)
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2012
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    rows = scrape(y0, y1)
    print(f"total: {len(rows)} rows")
