# The Too Hard Basket

A public register of the committee reports the Australian Government has
not answered. Independent and non-partisan, published by the **Australian
Public Interest Alliance** (APIA — apia.org.au).

Site: **[toohardbasket.org.au](https://toohardbasket.org.au)** — live.

## What this is

When a parliamentary committee reports, the government is expected to say
what it will do about the recommendations. The Senate has asked for that
within three months since 1973 and the House within six months since 2010.
Often it does not come, or comes years later, and there is no single public
record of which reports are still waiting.

Two registers are published, one per chamber, each following its presiding
officer:

- **Senate** — the President of the Senate's twice-yearly report to the
  Senate on the status of government responses. His status column decides
  every row; reports he records as answered are not published as
  outstanding, and reports he lists are not filtered out here.
- **House of Representatives** — the Speaker's equivalent schedule, on the
  same rule.

Most of what is on both registers is joint committee reports, which are
presented to both houses and listed by both officers, so the same report can
appear on each. **The two counts are never added together**: it would count
those reports twice, and the two chambers ask for different things.

A report leaves a register when a response to it is tabled, whatever that
response says. Alongside the registers, the site measures how long responses
take (from the Senate's own register of responses, 2000 to date) and how
many of them dispose of every recommendation with the same template
sentence.

Next: a Western Australian equivalent, then other obligations of the same
shape — a stated commitment, a claimant with standing, and a date.

## Repository layout

```
scraper/            Python pipeline — see scraper/README.md for full detail
  thb_parser.py          parsing core, unit-tested against real fixtures
  classic_scraper.py     Senate StatsNet Classic, 2000-2011
  statsnet_scraper.py    Senate StatsNet, 2012-now (Playwright)
  otd_sweep.py           government-response pro-forma classifier (OTD API)
  build_dataset.py       orchestrates parse -> validate -> data/responses.csv
  build_ledger.py        reads the President's schedule PDF -> data/ledger.csv
  build_ledger_v2.py     the published Senate register
  build_house_ledger.py  reads the Speaker's schedule PDF -> the House register
  harvest_links.py       OTD's own report-to-response links
  link_reports.py        links each register row to its report on aph.gov.au
  prune_answered.py      removes reports answered since the schedules were printed
  cross_register.py      marks joint reports and the overlap between registers
  build_history.py       the backlog history behind the chart
  validate.py            refuse-to-publish gate
  data/                  versioned CSV outputs (CC BY 4.0 — see DATA_LICENSE.md)
  ledger/                source PDFs: the two schedules and the government's
                         status report, as they stood on the day
  raw/                   fetch cache / audit trail (partial — see .gitignore)
site/                Astro site; builds to static HTML, deployed on push to main
.github/workflows/   scheduled Action: weekly rebuild of both registers
```

The pipeline runs in this order, and the order matters — the removal step
needs the report links, and the links need the registers:

```
build_dataset.py --all
build_ledger.py && build_ledger_v2.py     # Senate
build_house_ledger.py                     # House
harvest_links.py && link_reports.py
prune_answered.py                         # answered since the schedules
cross_register.py                         # joint reports, and the overlap
build_history.py
```

## Methodology, in brief

- **Senate rule:** a response within three months of tabling, in force since
  14 March 1973. **House rule:** six months, since 29 September 2010. Three
  months means three calendar months, which is how the President reads it —
  not ninety days.
- Every register row names the document it came from and links to it. Where
  the Tabled Documents index has the report itself, the title links to it;
  that index begins in 2022, so older reports are listed without a link
  rather than with a guessed one.
- Response classification (substantive / pro-forma / partial) is regex-based
  on document text and spot-checked by hand before publication. Full rules
  and known gaps (2000-01 registers lack report dates; some older PDFs are
  scanned images pending OCR) are in `scraper/README.md`.
- Everything the method cannot see is set out on the site's
  [methods page](https://toohardbasket.org.au/methods), and everything it
  has had to fix is in the
  [corrections log](https://toohardbasket.org.au/corrections/).

## Licensing

- **Code** (this repo, excluding `scraper/data/`): MIT — see `LICENSE`.
- **Data** (everything in `scraper/data/`): CC BY 4.0, attribution required
  — see `DATA_LICENSE.md`. Please credit **toohardbasket.org.au** in any
  reuse; that credit is how we track the project's impact.

## Status

Live. Both registers are published and rebuilt weekly by a scheduled
Action, which commits only if every step succeeds. The repository is public
from day one, partly as solo-maintainer continuity insurance: if something
here is wrong, it is wrong in a way you can demonstrate.

Found something wrong? corrections@toohardbasket.org.au.
