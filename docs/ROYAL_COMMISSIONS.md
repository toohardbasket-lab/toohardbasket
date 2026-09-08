# Adding royal commissions — scoping notes

Not a plan. A list of what has to be settled before any code is written,
written down so a new session starts from the real problem rather than
from the assumption that this is the same job again with a different noun.

Read `CLAUDE.md` first.

## Why it is not a drop-in

The existing register works because it stands on two institutional records
that already exist and are already published: the President of the Senate's
twice-yearly report and the Speaker's schedule. Those documents decide every
row. The site does not judge whether a report is outstanding — a presiding
officer does, and the site follows.

**Royal commissions have no equivalent.** There is no officer of the
Parliament keeping a schedule of which royal commission recommendations the
government has not answered. Whatever this becomes, it cannot inherit the
structure that makes the committee registers defensible. That is the central
design problem and everything else follows from it.

## The four questions to settle first

**1. What is the row?** For committees, a row is a report awaiting a
response. For a royal commission the candidates are different and the choice
changes the whole build: the commission itself (a handful of rows), its
report volumes, or its individual recommendations (hundreds each — the
Disability Royal Commission alone made 222). Recommendation-level is the
honest unit and the one that matches what the site already indexes, but it
is a much larger corpus and the pairing problem is harder.

**2. What counts as an answer, and against what clock?** Committee reports
have a deadline: three months in the Senate since 1973, six in the House
since 2010. **Royal commissions have no such rule.** A government responds
when it decides to. So "overdue" — which is half of what the current site
measures — has no meaning here unless a different standard is adopted, and
adopting one would be the site's own judgement rather than the Parliament's.
That is a real departure from the rule that keeps the register neutral.
Decide deliberately, and say so on the methods page either way.

**3. Where does the data come from?** Committee data comes from the Tabled
Documents register and StatsNet, both machine-readable-ish and both already
scraped. Royal commission material is scattered: commission websites that
get archived when the commission ends, government response documents on
department sites, implementation progress reports of varying formats, and
tabled versions on aph.gov.au. Before designing anything, establish for two
or three commissions whether the reports, the responses **and the
recommendation text** can be got at reliably and repeatedly. If they cannot,
the register cannot be rebuilt weekly, and a register that cannot be rebuilt
is a snapshot pretending to be a register.

**4. Is this one site or two?** The strongest argument for adding royal
commissions is that governments answer their recommendations in the same
vocabulary — accepted, accepted in principle, noted — which the classifier
already reads, and the same "noted without a position" evasion is available.
The strongest argument against is dilution: the site's claim is currently
narrow, mechanical and easy to defend. A second corpus with no deadline, a
patchier source and a different institutional basis makes the claim harder
to state in one sentence. A separate register on the same site, sharing the
recommendation index and the verdict vocabulary but making no deadline
claim, is probably the shape — but that is a decision, not an assumption.

## What has been settled

Written down 6 September 2026, after the source test. The questions above are
left as they were; this says what the answers turned out to be.

**1. The row is a recommendation**, one per row, in the shape of the existing
recommendations index and its verdict vocabulary: accepted, in part or in
principle, not accepted, and "noted" as no position. Both commissions in the
source test number their recommendations and both governments answer them one
by one, so the honest unit is also the available one.

**2. There is no deadline and the register will not invent one.** No statute
requires a government to answer a royal commission, so nothing here is ever
overdue. The site shows elapsed time from the report to the response, or to
today. Where a response commits to a date, the sentence is recorded verbatim
and linked; nothing is computed against it.

**3. The data comes from tabled documents.** Established rather than assumed:
`docs/royal-commissions/source-test-2026-09.md` fetched both commissions'
reports and responses four times from clean directories and got the same bytes
every time, with no redirects and nothing needing a browser or a login. The
departmental copies do not behave that way — one host refuses automated
requests, and the other moved department, changed its URL and published a
different file from the one it tabled. So a stored Tabled Documents id is the
address, not a departmental URL.

**4. One site, and an index rather than a register.** Settled on 8 September,
after writing the page: this site's own admission test requires an obligation, a
claimant with standing to demand an answer, and a date, and a royal commission
has none of the three. A royal commissions *register* could not be admitted
without bending that rule, and the rule is worth more than the word. What is
published is an index of the same shape as the committee recommendations index
— what was recommended, and what the government said about it — over a second
corpus, sharing its verdict vocabulary and its test of a stated position. Methods
is the main heading and `/methods/royal-commissions/` is beneath it, carrying
only what differs.

**5. Nothing is published that has not been found in its own document.**
Settled 8 September. `scraper/verify_rc_index.py` is the same job
`verify_recommendations.py` does for the committee side and for the same
reason: the failure that matters is not a garbled quotation, which a reader
can see, but the right words under the wrong number, which nothing on the page
would show. Every published recommendation is looked for in the report it
names — a distinctive slice of its text, with the row's own heading above it
and the row's own label above that — and every government quotation is looked
for under the heading the response itself puts over it, with the government's
label stated there as the whole of what the document states and not the
opening of it. A row that cannot be found that way is removed and counted, not
flagged. The step refuses outright if nothing verifies, or if less than nine
tenths of the index does, because this index is built from two documents by
rules written against them and anything short of nearly all of it is a broken
rule rather than a difficult document.

`--control` answers the objection that a check written from the same documents
as the extraction will pass whatever the extraction did. It gives every row a
neighbour's number, heading and words and counts what survives: at 8 September,
276 of 276 pairs refuse a neighbour's number, 276 of 276 refuse a neighbour's
heading, 173 of 176 refuse the words of the row after them and 153 of 154
refuse the words of the row 37 further on. The handful that pass are rows a
response answers in the same words on purpose; the control names them rather
than claiming a clean sweep.

Neither of those reaches the cached text itself, so twenty rows were read off
the tabled PDFs by eye —
`docs/royal-commissions/hand-check-2026-09.md`. All twenty carry the label,
heading and text their report prints and the position their response states.
The hand check found four faults in the published quotations that the
automatic check could not, because in every one the published words really
were the document's: the running head printed inside the quotation (120 of 228
answers), the next block's heading and verdict lines at the front of it (6),
one answer cut to eleven words at the government's own cross-reference, and 29
quotations stopping in the middle of a word at the character cap. All four are
fixed in `extract_rc_positions.py`, and a fifth — a recommendation answered
part by part, quoting only the first part with nothing to say the rest existed
— is now marked by `government_words_more`.

**6. A row is a report's recommendation, not a commission's.** Settled 8
September, adding the Royal Commission into Defence and Veteran Suicide. That
commission made 13 recommendations in an interim report the government answered
in 2022 and 122 more in its final report, answered in 2024, and both sets are
numbered from one. So the pair — a report that sets recommendations out under
their own numbers, and the response to it — is the unit, and a row is
identified by its commission, its report and its number. Which report a
response answers is data: `answers` in `rc_seed.csv`, and a response that does
not say is refused rather than read against everything the commission ever
recommended.

Three things about that commission's documents broke rules written from the
first two, which is what a third corpus is for:

  * **Numbering.** It numbers straight through — "Recommendation 61" — where
    the first two number by chapter. The pattern now counts all three shapes it
    has seen (by chapter, straight through, straight through with no titles at
    all) and takes whichever heads more of the report's recommendations. It is
    never close, and the minority is exactly what the rule keeps out: a bare
    number in the first two reports is a citation of another commission, and
    the Defence interim report cites the Productivity Commission's numbering
    three times.
  * **Where a heading stops.** A line beginning with a number is not a heading
    when it is the tail of a sentence the page broke — "as part of the process
    set out in / Recommendation 74.", "(see / Recommendation 11) as part of the
    check". Reading those as headings ended two answers before they began and
    truncated a recommendation. The rule is that a title never begins in lower
    case or with the punctuation that closes a clause. It also fixed a
    recommendation in the *published* Disability index, 7.30, which had been
    stopped at 537 characters by "Recommendation 7.30 until ADEs are phased
    out" and now runs to its real end at 1,629.
  * **Where a verdict is read from.** The response to recommendation 42 opens
    "The Government notes this recommendation" and later says related
    recommendations "will be implemented with regard to the recommendations of
    the Twenty-Year Review". Read whole, that was published as *accepted* — an
    acceptance the government did not state. A prose response is now read from
    its opening sentence where that sentence is about the recommendation, and
    from the whole answer otherwise. It is the only row of the 191 answered in
    prose that the two readings disagree about, and coverage.py is untouched,
    so nothing on the committee register moves.

The verifier caught the last of those and two more: a label published as "The
Australian Government agrees" where the document says "agrees-in-principle",
and one where the document's own slip, "The Australian agrees", is now
published as written. Its label check on a prose response is now the same test
it applies to a block one — the label has to end where the row says it ends.

**8. A recommendation that is not public is a row, and says so.** Settled 8
September, adding the Royal Commission on Antisemitism and Social Cohesion.
Five of the fourteen recommendations in its interim report are in a
confidential report. Where the recommendation would be, the public report
prints its number and one sentence saying so, and the response prints the same.

They are rows. A gap in the numbering with no explanation tells a reader less
than the truth does, and that five of fourteen recommendations of a royal
commission into antisemitism are not public is a fact of the record, not an
inconvenience to hide. Their rows carry the number and the sentence the report
printed, and say the response names the recommendation and states no position
on it — which is what "noted" means here, and is not "not addressed", which on
this index means the response does not mention it at all. Of these five it
plainly does, and saying otherwise would be false.

No words are published as the government's. Under every other heading in that
response the recommendation is reprinted before the answer, so the single
sentence under these could be either the commission's or the government's, and
the index does not decide that by guessing. `verify_rc_index.py` checks such a
row on the claim it actually makes — that the response names the recommendation
— and still refuses a row that claims a stated position with nothing behind it.

Reading that report also found the last of the furniture problems, and the
biggest. A footnote is not part of a recommendation and neither is a page's
running footer, but flattened to characters they are indistinguishable from it:
where a page breaks inside a recommendation, the whole apparatus at the foot of
that page lands in the middle of the sentence. The report says which is which
in the only way print can, and the same way this pipeline already tells a
heading from the text under it — by the type. The body is whatever size most of
the document is set in; anything smaller is apparatus. That fixed four of the
Antisemitism report's recommendations, one cut mid-clause, and **thirty of the
Disability report's**, which had been carrying "Executive Summary, Our vision
for an inclusive Australia and Recommendations 193" and the like in the middle
of the commission's words since the index was built. A line is taken out by its
words rather than by where it is, so a line that is apparatus in one place and
the report's own text in another is left alone: "mental health" is a footnote
somewhere in the Defence final report and the wrapped tail of its
recommendation 117.

**7. It is rebuilt weekly, and it alarms rather than gates while it is a
draft.** Settled 8 September. The five steps — harvest, read, recommendations,
positions, verify — are in `update-dataset.yml` behind the four test files,
between the link-preview card and `check_publishable.py`, so what they write is
committed with the rest of the dataset. Every one of them refuses rather than
write something it cannot stand behind, and unheard a refusal is decoration, so
`rc_alert.py` turns one into an issue. It does the same for a record in the
Tabled Documents register that looks like a royal commission document the seed
does not hold: that list is empty today, nothing was watching the file, and the
week a further response is tabled it will not be.

The block carries `continue-on-error: true`. No page the site publishes reads
any of these files, and a draft index that cannot be built is a reason to tell
somebody rather than a reason to leave the live registers a week stale. **When
the index goes live, delete that one line.** Every refusal in the block then
stops the run the way the committee side's gates do, which is what this site's
own rule requires of anything it publishes. Nothing else needs to change: the
alarm is worth keeping either way, because a candidate waiting is not a failure
and still needs a person.

A partial read cannot become a quiet undercount. `harvest_rc_text.py` writes
the cached text only when it reaches the last page, so a run that hits its
budget leaves no file and the extraction refuses by name — "OTD 7262: no cached
text" — rather than extracting from half a report whose own total it has no way
to check.

The first step built from all that is `scraper/harvest_royal_commissions.py`,
which decides which tabled documents belong to which commission and extracts
nothing.

**9. Where a report's own total disagrees with its numbering, the report is
read again rather than argued with.** Settled 8 September, on Robodebt's 57
against 56.

The report says "The following is a list of 57 recommendations of this
Commission" and prints 56 numbers. Until now the index showed both figures,
adopted neither, and said the shortfall was not a recommendation it was hiding
and that the report's sentence was not evidence a further one existed. The
first half of that was true. The second was not, and it had never been checked.

It is checked now, by the same rule that tells a heading from the text under
it. In the report's own List of Recommendations there are 57 headings set in
Calibri-Bold 11 with the recommendation set underneath in Calibri 11. Fifty-six
of them begin "Recommendation" and a number. The fifty-seventh is the last item
in the list, under the section heading "Closing observations": "Section 34 of
the Cth FOI Act should be repealed", with the Cabinet Handbook amendment
underneath it. The report counts it. It gives it no number.

The government read it the same way. Its response opens its answers with "The
Royal Commission into the Robodebt Scheme made 56 recommendations and one
closing observation", answers the closing observation on its own — "For these
reasons, the Government does not consider that section 34 of the FOI Act should
be repealed" — and then says it "accepts or accepts in principle all 56
recommendations". Both documents count 56 numbered recommendations and one
further item that is not one of them.

It is not a row. Both the report and the response call it a closing observation
rather than a recommendation, and this is an index of recommendations. Beyond
that, every row here is keyed by the number the report prints;
`verify_rc_index.py` checks a position by looking for that number in the
government's response; and a row with no number would be a row no check could
reach. Publishing it as "recommendation 57" would be inventing a number the
commission did not print, which is the one thing this index must never do.

So it is explained instead, and the explanation is produced by code, not typed
into a CSV: `unnumbered_in_list()` reads the sidecar, finds the headings inside
the list that carry no label, and writes them to
`rc_recommendation_counts.csv`. The page prints the words the report printed and
says why they are not a row. Where the arithmetic reconciles — found plus
unnumbered equals stated — the page says so; where it does not, it says only
that the difference has not been accounted for, which is what it said before.

Only the list is read, never the whole report. Bold at body size is a lead-in,
a table's column head and a chart's label everywhere else: 101 of those in
Robodebt against the one in the list. The list is bounded by the report itself,
running from the line that says "List of Recommendations", set larger again, to
the next line set that way. The Disability report, which agrees with itself at
222, yields nothing, and so do the three reports that state no total.

**10. A response that names a recommendation and does not answer it has not
been silent, and is not shown as though it were.** Settled 8 September, in the
hand check of the Robodebt and Disability rows.

Fifty of the Disability report's 222 recommendations were published as "not
addressed", which this index defines as the response not mentioning the
recommendation at all. The response mentions every one of them. Its reader's
guide says: "This document includes responses to the 172 recommendations within
the Australian Government's primary or shared responsibility. It does not
include responses to the 50 recommendations within state and territory
governments' primary responsibility." Appendix B then lists all fifty by number
and title under "The table below includes the 50 Disability Royal Commission
recommendations within the sole responsibility of state and territory
governments."

The sorting was right — the index found 172 answered and 50 not, which is
exactly the split the response states — and the words on it were wrong. A
government that says which recommendations it is not answering, and why, is not
a government that ignored them, and 50 rows of 427 said otherwise. The verifier
could not have caught it: it checks the words a row carries against the
document, and these rows carried none.

So there is a fourth state, `named, not answered`. The row says "The response
names it and does not answer it" and carries the list's own caption as its
quotation, so the reason given is the government's. `not addressed` stays in the
vocabulary and no row is one today; a response that never mentions a
recommendation is a thing that can happen, and when it does it will not be
confused with this.

The rule is the shape of the thing rather than that document: a run of at least
five lines each opening with a recommendation's number, where none of those
recommendations is answered anywhere in the response — below five, a number
opening a line is a cross-reference or a row of a table. The words are the
sentence that ends nearest above the list, rebuilt across a line the page broke,
and because the row now has words the verifier checks them like any other
quotation. Fifty rows moved from unverifiable to verified.

## What transfers, and what does not

Transfers: the recommendation index and its schema; the verdict vocabulary
and the position-stated test; the "nothing is inferred" discipline; the
frozen-edition and corrections machinery; the alarm pattern.

Does not transfer: the presiding officers' schedules and everything derived
from them; the deadline and every overdue figure; the form-letter test,
which is specific to a template sentence used on committee reports and
should not be assumed to appear here; the compliance series.

## How to start

Do the source investigation before writing a line of pipeline code. Pick two
commissions with different characteristics — one recent and well documented,
one old enough that its website has been archived — and establish end to end
whether their reports, recommendations and government responses can be
fetched, parsed and re-fetched. Report what you find, including what could
not be got. Then design.

Resist building the register first and looking for the data afterwards. The
committee register worked because the data existed and was authoritative.
