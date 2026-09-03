# Reports collected by hand

The recommendation index reads report PDFs from the Parliament's Tabled
Documents register. That register holds nothing before 2022, so the reports on
the two registers that were tabled before then — which are the longest waits on
the site — have no document there to read, and none of their recommendations
can be searched.

aph.gov.au refuses automated requests, so they cannot be fetched by the weekly
job. They are collected here by hand, once.

## What to do

    python harvest_manual_reports.py --list

prints what is still needed: the date, the committee, the report's title, and
the exact filename to use.

For each one:

1. Find the report on its committee's page on aph.gov.au. The committee name
   and the tabling date in the list are enough to search for.
2. Download the PDF of the report itself — not the submissions, not a chapter,
   not the government response.
3. Save it here. **The name does not matter** — the next step opens each PDF,
   reads the first pages, works out which report it is and files it. Saving it
   as its number from the list (`1.pdf`, `2.pdf`) also works and skips the
   guessing.

   Where two reports are too alike to tell apart from their first pages — the
   numbered Auditor-General series are nearly identical in wording — nothing is
   filed and it says so; use the number for those.
4. Put the page you took it from in `SOURCES.txt`, in this folder, as

       1   https://www.aph.gov.au/...

   one per line. The next step folds those into `../../data/reports_manual.csv`,
   which is what the site links to, so a reader can check a quotation against
   the same document. You can edit that CSV directly instead if you prefer, but
   it holds em-dashes in the committee names and a spreadsheet will quietly
   mangle them on save; `SOURCES.txt` avoids the question.

The numbers are positions in the current list and nothing more — they are good
until the list changes, which is why the rename happens immediately. Do a few at
a time and re-run `--list` rather than numbering all twenty-six in advance.

Then:

    python harvest_manual_reports.py

reads every PDF present into `raw/report_text/`, and marks the row collected.
A PDF that yields almost no text is a scan; it is refused and named rather than
half-read, and needs OCR. A file that will not open as a PDF at all — a saved
web page, a truncated download — is named too, and the run carries on.

Finally, the ordinary chain:

    python extract_recommendations.py && python extract_report_recommendations.py
    python verify_recommendations.py

The reports collected here go through the same parser, the same verification
and the same drop rules as every other report. The only difference is
provenance, and each row records it.

## What to collect

The report the committee tabled. Not the submissions, not a single chapter, not
the government's response.

Some of these are inquiries into a **bill** rather than into a subject. Those
are still committee reports, the Senate's three-month rule still applies to
them, and that is why the presiding officer has them on the schedule of
responses still owed — so they belong here. Expect few recommendations: a bill
inquiry often makes one.

## Why the PDFs are not committed

The text extracted from each report is committed, under `raw/report_text/`,
because it is the evidence behind a published quotation. The PDFs themselves
are the Parliament's to distribute and are linked, not mirrored.
