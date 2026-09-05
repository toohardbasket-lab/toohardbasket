# The Too Hard Basket — inquiry-response scraper

Builds the dataset of Australian Government responses to Senate and joint
committee reports: every response recorded in the Senate's own registers,
with days-to-respond computed against the Senate’s three-calendar-month rule
(order of 14 March 1973; the House allows six months).

## Layout

    thb_parser.py        parsing core (shared, unit-tested against real fixtures)
    classic_scraper.py   Senate StatsNet Classic, 2000–2011 (requests + BeautifulSoup)
    statsnet_scraper.py  Senate StatsNet, 2012–now (Playwright headless browser)
    validate.py          refuse-to-publish gate — build fails loudly on bad data
    build_dataset.py     orchestrates: parse → de-dupe → validate → data/responses.csv
    fixtures/            real register text captured 23 Aug 2026 (2005, 2011, 2026)
    tests/               parser tests; run: python tests/test_parser.py
    raw/                 fetch cache (never committed clean — it is the audit trail)

## Quick start

    pip install requests beautifulsoup4
    python tests/test_parser.py           # verify the parser (offline)
    python build_dataset.py --fixtures    # build from fixtures (offline, ~290 rows)
    python build_dataset.py --classic     # + live scrape 2000–2011

    # for 2012+ (WebForms page, needs a real browser):
    pip install playwright && playwright install chromium
    python build_dataset.py --all

## Design decisions

**Clock start.** Days-to-respond runs from the report's *tabled* date (not
presented), and for multi-report inquiries from the *last* report tabled —
the conservative choice. The first-tabled date is also recorded
(`days_from_first_report`) so nobody can accuse the site of inflating.

**Refuse-to-publish.** `validate.py` fails the build on: parsed counts that
disagree with the register's own stated totals, responses dated before
their reports, dates outside sane bounds, more than 3% of rows missing
dates, unexplained missing dates, duplicates. A layout change at
aph.gov.au must stop the pipeline loudly, never degrade it silently.

**Two eras, one tested core.** Both scrapers reduce their pages to text
shapes covered by `thb_parser` tests, which run against fixtures captured
from the live site. If APH changes markup, the reduction step throws
rather than guessing.

**Politeness.** One request per year-page, 2s delay, cached to `raw/`.
The whole Classic era is 12 requests, once ever.

## Verified facts the pipeline rests on (checked 23 Aug 2026)

- Classic archive holds registers for 2000–2011 ("data to 31 December
  2011"); year pages are server-rendered HTML and fetch fine with
  browser-like headers (403 otherwise — user-agent filtering, not a block).
- The 2012+ register is a client-side DataTable inside a WebForms page;
  the date-range REFINE control selects responses tabled/presented in the
  range; "Show All" puts every row in the DOM. There is also a
  "Download results as CSV" button — a manual fallback.
- The register is read afresh every Tuesday; the current figures are on the
  site, not here. (For the record, an early read on 20 August 2026 found 181
  responses in the 2026 register and a maximum of 8,561 days: *A certain
  maritime incident*, 2002 report, response tabled 1 April 2026.)

## What runs each week

Everything below is implemented and runs in `.github/workflows/update-dataset.yml`
every Tuesday at 06:00 Perth time, in this order: the Senate response
registers; the President's report and the Speaker's schedule (the two
registers of what is still waiting); the government's own status reports;
every response document from the Tabled Documents system, read and
classified; the recommendations index, verified against its sources;
coverage (whether each response stated a position); removal of reports
answered since the schedules; the backlog history; the link-preview card;
the publish gate; the site build; an edition snapshot; commit and tag.
A failed step commits nothing and opens an issue.

To run the tests and the gate by hand, from `scraper/`:

    for t in tests/test_*.py; do python "$t" || exit 1; done
    python check_publishable.py
