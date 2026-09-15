# The implementation claims, read in full

*15 September 2026.*

`implementation_evidence.py` finds the answers that say a recommendation has
been implemented, actioned or delivered. There are five. Five is small enough to
read rather than sample, so all five were read in full — the committee's
recommendation, the government's whole answer, and the sentence the rule
matched — and so was the one candidate the rule rejected.

The question asked of each was the one that matters for this site: **is the
sentence about the recommendation the row carries?** Not whether the claim is
true. Nothing here checks whether the thing was done.

| Response | Rec | Tabled | The sentence | Reading |
|---|---|---|---|---|
| OTD 6041 | 3 | 16 May 2024 | "This recommendation has been implemented" | The whole answer. Nothing else in it. |
| OTD 6208 | 3 | 25 Jun 2024 | "The Government has implemented this recommendation." | Followed by the instrument: the trade agreement entered into force 29 December 2022. |
| OTD 9517 | 1 | 27 Feb 2025 | "The Government has actioned this recommendation." | Followed by the Act, the consultation dates and the instrument that entered force 14 May 2024. |
| OTD 9517 | 3 | 27 Feb 2025 | "The Government has actioned this recommendation." | Followed by the Bill the Parliament passed in September 2024. |
| OTD 16205 | 3 | 8 May 2026 | "The government has delivered this recommendation." | Followed by the Act. The extract ends with the page-foot word OFFICIAL, a known apparatus limit. |

Four of the five name the instrument that carried it out. That is what a record
of implementation would look like if there were one.

## The candidate that was rejected

**OTD 8738, recommendation 2, tabled 19 December 2024.** The rule matched:

> Annex A details how the Australian Government has implemented the
> recommendations accepted (in principle or in part) in response to
> *Compassion, Not Commerce*.

The words are the government's and they are about implementation. They are
about a different committee's report from three years earlier, which the
recommendation in front of them asks the government to get on with. Counting it
would have put an implementation claim against a recommendation it was not
about.

This is an **attribution** failure, not a reading one — the distinction the
coverage sample is built on — and it is the failure this site is least willing
to make, because it is the one that inflates a count in the site's favour and is
invisible to a reader who does not open the document.

The cause was small: the pattern for "this recommendation" had no word boundary,
so it matched the first thirteen letters of "recommendations". The boundary is
now there and the sentence is a test in
`scraper/tests/test_implementation_evidence.py`.

## What was not checked

The five sentences were read against the index's own extract of each document,
not against the PDF. The extract is verified word for word against the source by
`verify_recommendations.py`, so the words are the document's; what a fresh
reading of the PDF would add is confirmation that the whole segment was attached
to the right recommendation label in the first place — the general risk the
coverage sample measures, not something specific to these five.

Five PDFs is a small enough ask that this should be done by a person before the
figure is quoted anywhere outside the site.
