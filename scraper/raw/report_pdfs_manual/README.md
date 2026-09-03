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
3. Save it here under the filename the list gives, exactly.
4. Open `../../data/reports_manual.csv` and put the page you took it from in
   `pdf_source_url` for that row. This is what the site links to, so a reader
   can check a quotation against the same document.

Then:

    python harvest_manual_reports.py

reads every PDF present into `raw/report_text/`, and marks the row collected.
A PDF that yields almost no text is a scan; it is refused and named rather than
half-read, and needs OCR.

Finally, the ordinary chain:

    python extract_recommendations.py && python extract_report_recommendations.py
    python verify_recommendations.py

The reports collected here go through the same parser, the same verification
and the same drop rules as every other report. The only difference is
provenance, and each row records it.

## Why the PDFs are not committed

The text extracted from each report is committed, under `raw/report_text/`,
because it is the evidence behind a published quotation. The PDFs themselves
are the Parliament's to distribute and are linked, not mirrored.
