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

**The Royal Commission on Antisemitism and Social Cohesion is not read.** Five
of the fourteen recommendations in its interim report are in a confidential
report; the public report and the response both say only "This recommendation
is contained in the confidential Interim Report". The index has no way to carry
that: "not addressed" would be false, because the response does name them, and
there is nothing to quote. The documents are in the table with the reason
written beside them, and the next piece of design is what a row says when the
recommendation itself is not public.

The first step built from all that is `scraper/harvest_royal_commissions.py`,
which decides which tabled documents belong to which commission and extracts
nothing. It is run by hand and is not in the weekly job, because nothing
consumes what it writes yet.

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
