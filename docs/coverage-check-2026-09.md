# Checking the coverage measure, September 2026

## Why

An external review on 13 September made two points about the same claim.
Methods said the coverage method "cannot inflate" the number of
recommendations with a stated position. Conservative and *cannot overcount*
are different claims, and only the first was supported: no hand check of this
index's own rows existed. The word was retired the same day, and the page now
carries a commitment to publish a sample instead.

This is that sample's design and where it stands.

## What is being tested

Two steps can fail independently, and they fail differently:

| step | failure | what it does to the count |
| --- | --- | --- |
| attribution | the words shown are not this recommendation's answer | can inflate it |
| reading | the words are right, the verdict read from them is wrong | either way |

The one known false positive, found by eye in the royal commissions index on
8 September, was an attribution failure. That is why the sheet records a wrong
call as one of two things rather than simply "wrong".

## The sample

`scraper/qa_positions.py`, seed 1, 13 September 2026. 106 rows:

| stratum | n | population | what it answers |
| --- | --- | --- | --- |
| position | 60 | 1,032 | can the number be inflated, and how often |
| noted | 25 | 565 | how many verdicts the method misses |
| not individual | 10 | 480 | is it true no response answers these one by one |
| unreadable | 5 | 305 | does the document really say nothing |
| position, verdict far from the head | 6 | 6 | the fragile rows, all of them |

Sixty position rows with no error found put the error rate under about 5% at
95% confidence. That is the size the stratum was chosen for; it is not a
promise about what will be found.

`form letter` (1,427) is left out — the pro-forma classification has its own
sheet, `qa/review_2026-08-29.html`, at document level. `awaiting` (1,062) has
no response to read. `dissent` (388) is excluded from the coverage measure.

Each card shows the recommendation, the words attributed to it with the
verdict marked, and the passage of the response those words came from with
400 characters before them, so attribution can be judged without opening the
PDF. The PDF is linked and settles anything the cached text leaves in doubt.

The sheet is published as an artifact so answers survive a closed laptop and
so a second reader's answers are kept in their own document, unseen by the
first. Two readings of the same sample, disagreements read out, is the
strongest form this check takes.

## What code could say first

`scraper/verify_positions.py`, run 13 September over all 1,032 rows with a
stated position:

    1032  begin at an explicit handover in the document
       0  no verdict found on a second reading
       6  verdict 200+ characters into the answer
       0  runs on into another recommendation
      14  names another recommendation number

19 rows are flagged for reading in `data/position_checks.csv`. None of this is
an error rate.

The first line cannot fail and is reported as what the construction
guarantees, not as a test: a row where the extractor finds no handover records
no government words at all and never reaches this count.

## The check that was thrown away

A fourth test was written the same day and deleted. It asked whether each
recommendation's own words sit just above the government's in the document.
All 1,032 rows passed — because `extract_recommendations.py` cuts one segment
at the recommendation's heading and splits it at the handover, so the question
is above the answer by construction. A test that cannot fail is not evidence.
Its hundred per cent is not published anywhere, and Methods says why.

The lesson is worth keeping: when a verification passes at 100% on the first
run, the first question is whether it shares a mechanism with the thing it is
verifying.

## Standing

- [x] sheet built and published
- [x] whole-population checks that can fail, run and published
- [ ] first reading
- [ ] second, independent reading
- [ ] counts published on `/methods/#one-way`, with every error listed

Until the last two are done, Methods says the figures are *built* to undercount
and not that they are proven to.
