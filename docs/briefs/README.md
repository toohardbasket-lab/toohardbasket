# Briefs, and how they are kept honest

A media brief states dozens of figures and then invites the reader to check
them: *"Run it and diff the result against this document."* Between the brief
going out and somebody reading it, the dataset rebuilds. Figures move. That is
the register working, not an error — but a journalist who takes the invitation
finds a document that does not match, and has no way to tell the two apart.

So a brief lives here in three pieces.

    2026-09-08.txt          the brief's own text, extracted from what was sent
    2026-09-08.claims.csv   each sentence with a figure, and where the figure
                            comes from in brief_figures.py
    (the PDF as sent)       kept wherever it was sent from; not needed here

`scraper/check_brief.py` puts them back together and prints an errata sheet:
which figures have moved, to what, and the sentence each one sits in. Run it
before answering a question about a brief that is already out, and run it again
before sending a new one.

    python scraper/check_brief.py            # the newest brief
    python scraper/check_brief.py --all      # every brief on file

## Writing the claims file

One row per sentence carrying figures. `pattern` is the brief's own words with
`{}` where each figure goes; `keys` is one path per `{}`, in order,
slash-separated into `brief_figures.py --json`. Matching flattens whitespace,
so the line breaks the PDF extraction leaves behind do not matter.

A key may be a plain path (`coverage/position_stated`), a rate the brief prints
as a percentage (`compliance/rate%`), or a difference the brief states that the
dataset only implies (`a/b - c/d`).

Write claims for every figure, not the interesting ones. A claim the checker
cannot find in the brief is reported as unmatched rather than skipped, because
a checker that quietly passes over what it cannot read would call a document
clean without having checked it — and a brief with no claims file beside it is
refused outright for the same reason.

## What this does not do

It checks figures against the dataset. It does not check that a sentence is a
fair reading of its figure, that a date is right, or that an example says what
the document it cites says. Those are read by hand, and the figures moving is
not a substitute for reading them again.
