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
