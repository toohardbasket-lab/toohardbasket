# The Too Hard Basket

An Our World in Data–style public scoreboard of Australian government
outcomes: what government promised to do, dated. Independent and
non-partisan, published by the **Australian Public Interest Alliance**
(APIA — apia.org.au).

Site: **toohardbasket.org.au** (registered; site build is Phase 2)

## What this is

The first dataset tracks government responses to Senate committee
reports against the Senate's 90-day response rule: every response
tabled 2000–present, whether it met the deadline, and — where it
missed — whether the eventual response was substantive or a pro-forma
closure ("passage of time" template detection).

Roadmap: House of Representatives and WA Parliament equivalents next,
then a shortlist of further "government ignoring its own obligations"
datasets (Questions on Notice, watchdog recommendations, statutory
deadlines, service backlogs, budget underspends).

## Repository layout

```
scraper/            Python pipeline — see scraper/README.md for full detail
  thb_parser.py         parsing core, unit-tested against real fixtures
  classic_scraper.py    Senate StatsNet Classic, 2000-2011
  statsnet_scraper.py   Senate StatsNet, 2012-now (Playwright)
  otd_sweep.py           Government-response pro-forma classifier (OTD API)
  build_dataset.py       orchestrates parse -> validate -> data/responses.csv
  build_ledger.py        outstanding-responses ledger (President's schedule PDF)
  validate.py            refuse-to-publish gate
  data/                  versioned CSV outputs (CC BY 4.0 — see DATA_LICENSE.md)
  raw/                   fetch cache / audit trail (partial — see .gitignore)
ledger/              Source PDFs: the President's twice-yearly schedules
media/               Write-ups and evidence briefs
.github/workflows/   Scheduled Actions (weekly dataset refresh)
```

Site source (Astro, Phase 2) will land in `site/` once that phase starts.

## Methodology, in brief

- **Senate rule:** responses due within 3 months, in force since 14 Mar
  1973. **House rule:** 6 months, since 29 Sept 2010.
- Every row links to its source document on aph.gov.au.
- Response classification (substantive / pro-forma / partial) is
  regex-based on document text and is spot-checked by hand before
  publication. Full rules and known gaps (e.g. 2000-01 registers lack
  report dates; some older PDFs are scanned images pending OCR) are in
  `scraper/README.md`.

## Licensing

- **Code** (this repo, excluding `scraper/data/`): MIT — see `LICENSE`.
- **Data** (everything in `scraper/data/`): CC BY 4.0, attribution
  required — see `DATA_LICENSE.md`. Please credit
  **toohardbasket.org.au** in any reuse; that credit is how we track
  the project's impact.

## Status

Pre-launch. Build-first: the pipeline and dataset are being validated
before any public launch decision — see the project's rollout plan for
phase details. Public from day one, partly as solo-maintainer
continuity insurance.
