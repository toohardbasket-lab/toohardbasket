# Pairing a response to the report it answers — where this stands

Not a plan. What the pairing can and cannot do today, with the numbers, so a
session picking this up starts from the real shape of the problem.

Read `CLAUDE.md` first.

## Why it matters twice

The pairing has two consumers, and they carry different risk.

**The register removal.** `answered_since.py` takes a report off a public
register when a response answers it. A wrong pairing removes a report the
government has not answered; a missing one leaves an answered report published
as outstanding. That module already treats the pairing as evidence and grades
it — OTD's own link, then a hand-checked entry, then a strict title match — and
its tests exist because loose matching once removed 71 reports against 16 real
responses.

**The reader.** The search page offers "the report it answers" beside a claim
about what the government did with it. A reader who cannot reach the report
cannot check the claim, and checkability is the whole product.

## The numbers, as at 9 September 2026

Of 624 responses in the corpus, 245 carry a link to a report — 39 per cent.

```
  284  not found                 searched, nothing scored 0.8 or better
  199  otd link                  Parliament's own documentLinks
   93  no title in response      nothing in the response's title to search on
   44  title search              matched at 0.8 or better
    2  by hand                   response_report_links_manual.csv
```

It is much worse on the subset the search page exposes most plainly — the 151
responses that set out no recommendations at all:

```
  102  not found
   44  no title in response
    4  otd link
```

Four of 151. A response that answers a report in prose, or closes it with the
form letter, is often two pages with a thin title, so the subset hardest to
pair is exactly the subset where the page has least else to show.

## What has already been fixed, and should not be re-litigated

- **A response is not a report.** Every route into the file could pair a
  response with another response. OTD linked response 10128 to document 11618,
  the same answer tabled a second time; the title search paired response 9463
  with itself at 0.83, because a response quotes the title of the report it
  answers and so scores against its own text. `not_a_report()` in
  `link_responses_to_reports.py` refuses all three shapes, sweeps rows already
  in the file, and `tests/test_pairing.py` gates both workflows.
- **A report older than the Tabled Documents register can be named by hand.**
  The register starts in April 2022, so 29 of the 118 rows on the two registers
  carry no OTD id and cannot be named by one. `response_report_links_manual.csv`
  now accepts an exact title plus an exact tabling date instead. See
  `answered_since.py`.

## What the hand-check found, 9 September 2026

The plan was to hand-check 50 of the 284 unpaired rows to find the ceiling.
The sample said the ceiling was low, so all 284 were re-searched instead and
the answer is measured rather than extrapolated. The working file is
`scraper/data/pairing_sample_2026-09-09.csv`, one row per response with the
best candidate the search returns and a verdict.

**Under the rules as they stand, none of the 284 pair.** Two narrow changes
recover 12, and every one of the 12 is an exact title match with exactly one
candidate, the right committee, and the report tabled before the response.
Each was checked by hand.

```
  222  nothing close — the report is not in the Tabled Documents register
   37  the search returns no committee document at all
   12  recovered by the two changes below, hand-checked
   11  a candidate exists but below the bar for a reason other than a date
    2  correct, checked by hand, and not safely automatable
```

**Change one: ignore a trailing bracketed date when scoring.** The register
titles a report "Project known as the Iron Boomerang [August 2023]" while the
response calls it "Project known as the Iron Boomerang". `overlap()` takes the
lesser of the two directions, so the extra words cost the match. Strip a
trailing `[Month Year]` or `(Year)` from both titles for the score only, and
leave `agree()` reading the raw titles so the year test is untouched. Ten of
the twelve.

**Change two: the short-title guard fires before the score.** `best()` returns
nothing when the query has fewer than three distinctive words, to stop
"Interim Report" matching everything. But it also discards
"Corporate insolvency in Australia" — two distinctive words — which matches its
report exactly, uniquely, from the right committee. The guard belongs on weak
matches, not on exact ones: require a short title to score 1.0 rather than
refusing to look. Two of the twelve.

**What the year and stage test is worth.** Two more rows have a candidate at
0.8 that `agree()` refuses, and it is right to refuse both automatically. One
is the response to the *final* report on the conduct of the 2022 federal
election, where the register titles the final report by date and only the
interim carries a stage word; the other says "Interim Report" against a
committee title with no stage word at all. Both are correct pairings, and both
are judgements rather than matches — the manual file is where they belong. Do
not relax `agree()` to catch them: the interim report of that same inquiry is
sitting in the same result set.

## Why the rest cannot be paired

259 of the 284 have nothing to pair with, and the reason is not the matcher.

Of the 284, **201 are form-letter closures** — the one-sentence letters that
close an inquiry years later — against 1 of the 199 responses OTD links itself.
Every report that has ever paired was tabled in 2022 or later, bar one. The
Tabled Documents register begins in April 2022, and a closure by definition
answers something old. The document being searched for is not in the corpus
being searched.

So a better matcher is not the work. If these are to be linked at all, the site
needs a pre-2022 report corpus, which means the committee report pages on
aph.gov.au — the source `reports_manual.csv` already covers by hand for 26
reports. That is a scraper, and a different job from this one.

## One thing to fix regardless

**A row that fails once is never tried again.** `link_responses_to_reports.py`
keeps any row already in the file unless `--refetch` is given, and no workflow
gives it: all 284 unfound rows carry `checked_on` of 2026-09-04, the day of the
bulk run. OTD publishes a response record and its report record at different
times, so a response harvested before its report reaches the register is
recorded as unpairable permanently. Re-searching the unfound rows costs about
five minutes of API calls; doing it weekly, or monthly, would cost little and
would catch the cases this file cannot predict.

## How to start on the pre-2022 corpus

Pick ten of the 201 closures, find their reports on the committee pages by
hand, and record what it took. That says whether the committee pages can be
scraped repeatably or whether this stays a hand-checked file forever. Report
what could not be found, and do not build the scraper first.
