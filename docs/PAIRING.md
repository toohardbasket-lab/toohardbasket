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

## What a real fix would have to settle

**1. Is 39 per cent a problem, or is it the honest ceiling?** OTD publishes a
link for about a third of responses and that is not going to change. The
question is whether the remaining pairings can be established to a standard the
site can defend, or whether the answer is to say "not identified" well — which
is what the pages now do. Decide that before writing a matcher.

**2. What evidence exists besides the title?** The current search uses the
response title alone. Unused: the committee named in the response, the tabling
dates (a response follows its report, usually by months), the department, and
the text of the response itself, which very often names the report in its first
paragraph. A rule combining committee plus a date window plus a weaker title
score may be both tighter and broader than one strong title test — but "may" is
the word, and it has to be measured against a hand-checked sample, not asserted.

**3. What is the acceptable error rate, and in which direction?** For the reader
a wrong link is worse than none. For the register a wrong removal is far worse
than a stale row. These are the same evidence with different thresholds, and the
code currently uses one bar (0.8) for both. Consider separating them: a pairing
good enough to show a reader may not be good enough to remove a row.

**4. How is it checked?** Any new matcher needs a hand-labelled set to measure
against. Build that first — a few hundred rows, checked on aph.gov.au, kept in
the repository — or there is no way to tell an improvement from a regression.

## How to start

Take a random sample of 50 of the 284 "not found" rows and establish by hand
what the right answer is for each. That tells you the ceiling — how many are
even findable — and gives you the beginning of the labelled set. Report what you
find, including the ones that cannot be settled at all.

Do not tune the threshold against the whole corpus and look at the totals. The
totals cannot tell you whether the new matches are right.
