# Source test: Robodebt and the Disability Royal Commission

Done 6 September 2026, as `docs/ROYAL_COMMISSIONS.md` asks: two commissions,
end to end, before any pipeline code. Nothing here was added to `scraper/`
and nothing on the site changed.

Every number below was produced by the command printed beside it. The scripts
are in `source-test-scripts/`; they are evidence of how this was reached, not
pipeline steps. Run them from that directory. Documents come from
`sources.tsv` and are fetched by

```
bash fetch.sh /tmp/rc-a
```

which writes each file and a manifest of name, HTTP code, redirects, bytes,
content type, sha256, final URL and the time of the fetch. The seventeen
documents in `sources.tsv` were fetched four times on 6 September 2026, into
four empty directories, at 09:56, 09:58, 10:25 and 10:26 UTC.

Two commands recur:

```
python3 pdftext.py /tmp/rc-a/<file>.pdf /tmp/rc-a/<file>.txt
```

which is the three lines `harvest_report_pdfs.py` uses — pdfplumber, page by
page, joined with a newline — so that what is said about the existing code is
said about the text the existing code would see; and

```
python3 report_recs.py /tmp/rc-a/<file>.txt
python3 positions.py  /tmp/rc-a/<file>.txt
```

which run `extract_report_recommendations.py`, `extract_recommendations.py`
and `coverage.py` unchanged over a file.

---

## Royal Commission into the Robodebt Scheme

### 1. The report

The commission's site is live. `curl` of
<https://robodebt.royalcommission.gov.au/publications/report>, 6 September
2026, returns 200 and links six files: three volume PDFs under a `2023-07`
path, an accessible full report as PDF and DOCX under `2023-09`, and a
corrigendum PDF.

It is also tabled, as one document. Tabled Documents id **2743**, "Royal
Commission into the Robodebt Scheme", document type **Royal commission**,
tabled in the Senate **7 July 2023** and the House **31 July 2023**; one file,
`Report of the Royal Commission into the Robodebt Scheme.pdf`, 1,039 pages.
The corrigendum is id **2915** (Senate 27 July 2023, House 31 July 2023).

```
python3 otd_search.py --type "Royal commission" | grep -i robodebt
2915|2023-07-27|2023-07-31||Royal Commission into the Robodebt Scheme [Corrigendum]
2743|2023-07-07|2023-07-31||Royal Commission into the Robodebt Scheme
```

The text is native. No page needed OCR:

```
python3 pdftext.py robodebt_report_volume_1.pdf robodebt_report_volume_1.txt
robodebt_report_volume_1.pdf: 364 pages, 1197504 characters, 4 pages with no text
robodebt_report_volume_2.pdf: 344 pages, 969143 characters, 4 pages with no text
robodebt_report_volume_3.pdf: 344 pages, 1019158 characters, 3 pages with no text
```

The four and three pages with no text are covers and dividers.

The existing step reads nothing from it:

```
python3 report_recs.py robodebt_report_volume_1.txt
# 0 lines match the step's heading pattern (the label alone on its own line)
# 56 distinct recommendation numbers appear anywhere in the text
# 0 recommendations extracted from robodebt_report_volume_1.txt
```

The reason is one line of layout. `extract_report_recommendations.py` expects
the label alone on its line, because that is how a Senate committee prints it.
This report prints the label and the recommendation's own title together:
"Recommendation 10.1: Design policies and processes with emphasis on the
people they are meant to serve". Reading that shape instead:

```
python3 numbered_recs.py robodebt_report_volume_1.txt
# 56 headings, 56 distinct recommendation numbers in robodebt_report_volume_1.txt
# every one but the last stops at the next heading: shortest 65 characters, median 261, longest 1240
# the last, 23.8, has no heading after it and runs to the end of the file: 1138989 characters
```

So 55 of the 56 end where the report ends them, at the next heading, and none
of them is longer than 1,240 characters. The last, 23.8, has nothing after it:
the List of Recommendations has no terminator, and a rule would have to supply
one.

### 2. The report's own count

The report says 57. Volume 1, line 449 of the extracted text, under "List of
Recommendations":

> The following is a list of 57 recommendations of this Commission.
> Recommendations have been grouped and numbered according to the chapter in
> which they appear.

```
grep -n "list of 57 recommendations" robodebt_report_volume_1.txt
449:The following is a list of 57 recommendations of this Commission. ...
```

The extraction finds 56, and finds 56 in two different renditions of the
report read by two different extractors — pdfplumber over the three volumes,
and `pdftotext -layout` over the accessible full report:

```
pdftotext -layout robodebt_accessible_full_report.pdf robodebt_accessible_full_report.txt
grep -oEi 'Recommendation[ \t]+[0-9]{1,3}\.[0-9]{1,3}' robodebt_accessible_full_report.txt \
  | sed -E 's/.*[ \t]//' | sort -u -V | wc -l
56
```

The numbers are 10.1; 11.1–11.4; 12.1–12.4; 13.1–13.4; 15.1–15.6; 16.1–16.2;
17.1–17.2; 18.1–18.2; 19.1–19.13; 20.1–20.5; 21.1–21.5; 23.1–23.8. There is
no gap inside a chapter. Chapters 14 and 22 carry none.

The difference of one is not resolved here. The sealed chapter is not the
explanation on the evidence available: the version of it since tabled (see 5
below) contains no numbered recommendation.

```
grep -oEi 'Recommendation[ \t]+[0-9]{1,3}(\.[0-9]{1,3})?' otd_15488_robodebt_closed_chapter.txt | wc -l
0
```

### 3. The government response

Tabled. Id **4163**, "Government Response | Royal Commission Into The Robodebt
Scheme November 2023 [November 2023]", tabled in the **House 13 November
2023** and the **Senate 14 November 2023**; one file, 39 pages.

Its document type in the register is **Other**, not Government response.

```
python3 -c "import json,urllib.request;d=json.load(urllib.request.urlopen('https://otd.aph.gov.au/public-api/api/documents/4163'))['document'];print(d['typeDescription'],'|',d['tabledSenate'][:10],'|',d['tabledHouse'][:10])"
Other | 2023-11-14 | 2023-11-13
```

That matters more than it looks. `harvest_responses.py` asks the register for
`documentTypes: ["Government response"]`, so this document has never reached
the dataset:

```
grep -c '^4163,' ../../../scraper/data/response_documents.csv
0
grep -c '^6874,' ../../../scraper/data/response_documents.csv
1
```

The Disability response is in the file and set aside by
`scope_exclusions.csv`; the Robodebt response was never seen at all. A royal
commissions harvest cannot inherit the type filter.

There is a departmental copy, at PM&C, and it could not be fetched. See "What
could not be got".

The response quotes all 56 recommendations and states a position on each. The
existing split reads 49 of them:

```
python3 positions.py otd_4163_robodebt_response.txt
# 49 recommendations split out of otd_4163_robodebt_response.txt
# states:   {'position': 49}
# verdicts: {'accepted': 43, 'in part or in principle': 6}
```

The seven it does not read fail on the recommendation, not on the government's
words:

```
python3 why_dropped.py otd_4163_robodebt_response.txt
15.5  does not use a word the recommendation test looks for
15.6  does not use a word the recommendation test looks for
18.2  read as a broken extraction (two or more stray single letters)
20.5  does not use a word the recommendation test looks for
21.1  does not use a word the recommendation test looks for
21.4  does not use a word the recommendation test looks for
21.5  read as a broken extraction (two or more stray single letters)
# 56 recommendation numbers in the document, 49 read, 7 not read
```

Five are written in the subjunctive — "That in developing compliance Budget
measures…", "A statutory duty be imposed…", "The Ombudsman maintain a log…" —
and use none of the words `SAYS_RECOMMEND` looks for. Two cite sections of an
Act, "s 1234B" and "S 10A and s 11", which the broken-extraction test counts
as stray single letters. Both are properties of the test, not of the document.

Asking only whether the verdict word is in the document at all:

```
python3 verdict_by_segment.py otd_4163_robodebt_response.txt
# 56 distinct recommendation numbers in otd_4163_robodebt_response.txt
#     49  accepted
#      7  in part or in principle
```

The government's own label is a sentence of the form "The Government accepts
this recommendation." or "The Government accepts in principle this
recommendation." Both are inside `coverage.py`'s existing test. Nothing in
this document is answered "not accepted".

From the report's tabling to the response's:

```
python3 elapsed.py 2026-09-06
  129 days  Robodebt: report tabled in the Senate [2743] to response tabled in the House [4163]
 1157 days  Robodebt: report tabled in the Senate [2743] to today
```

### 4. Addressees

No recommendation names another government:

```
python3 names_a_state.py robodebt_report_volume_1.txt
# 56 distinct recommendations in robodebt_report_volume_1.txt
# 0 name a state or territory in their own text
```

They are addressed to Services Australia, the Department of Social Services,
the Commonwealth, the Ombudsman and the AAT. The question does not arise for
this commission, and no rule is needed.

### 5. Later documents

One later document, and it is tabled. Id **15488**, "Royal Commission into the Robodebt
Scheme—Referrals", file `Closed Chapter -  Recommendations and Referrals -
Final.pdf`, tabled in the **House 12 March 2026** — 979 days after the report
(`python3 elapsed.py 2026-09-06`). 56 pages, native text, no numbered
recommendations; its contents are referrals to the National Anti-Corruption
Commission, the Australian Federal Police, the ACT Law Society and agency
heads.

No implementation or progress report was found. Two searches were run: the
register itself, `python3 otd_search.py --title 'robodebt'`, which returns
eleven records and no progress report among them; and web searches for a
Commonwealth implementation report, which return ministerial media releases on
`ministers.pmc.gov.au` and `ministers.dss.gov.au` and an APSC page. None of
those is tabled.

Two other tabled records mention the commission and are documents presented by
a Member rather than government documents: 12653 (pages of volume 1) and 12654
(a Hansard speech).

### 6. Re-fetching

```
bash fetch.sh /tmp/rc-a
bash fetch.sh /tmp/rc-b
diff <(cut -f1,6 /tmp/rc-a/manifest.tsv) <(cut -f1,6 /tmp/rc-b/manifest.tsv)
```

Every Robodebt document came back byte for byte identical on all four passes,
from both `robodebt.royalcommission.gov.au` and `otd.aph.gov.au`, with no
redirects and no request refused. Sixteen of the seventeen documents match
across every pass. The one that does not is `robodebt_response_pmc.pdf`, which
is not the document: it is PM&C's refusal page, and it carries a different
reference number each time.

### 7. Dates stated in the response

```
python3 dated_sentences.py otd_4163_robodebt_response.pdf
# 6 sentences with a future-tense verb and a date in otd_4163_robodebt_response.pdf
```

One is a commitment, and it reports an announcement rather than making one. It
appears twice, both on PDF page 32, under recommendations 20.4 and 20.5:

> On 29 September 2023, the Government announced that by the end of the year it
> will introduce legislation to abolish the Administrative Appeals Tribunal
> (AAT) and replace it with a new body, the Administrative Review Tribunal
> (ART).

The rest are dates in the past or references to other documents.

---

## Royal Commission into Violence, Abuse, Neglect and Exploitation of People with Disability

### 1. The report

The commission's site is live. `curl` of
<https://disability.royalcommission.gov.au/publications/final-report>,
6 September 2026, returns 200. It is an index, not a document: one page per
volume, and the files are on those pages. Each volume page offers the same
four formats — PDF, DOCX, Easy Read PDF and Easy Read text-only DOCX.

The recommendations are collected in one volume, "Executive Summary, Our
vision for an inclusive Australia and Recommendations".

It is tabled as thirteen separate records: the executive summary and volumes 1
to 12, all tabled in the Senate **29 September 2023** and the House **18
October 2023**, with a corrigendum (id 4072) on 2 and 16 November 2023.

```
python3 otd_search.py --type "Royal commission"
3444|2023-09-29|2023-10-18||Executive Summary, Our vision for an inclusive Australia and Recommendations [Final report]
3446|2023-09-29|2023-10-18||Voices of people with disability [Final report - volume 1]
   (ten more volumes, all 2023-09-29 and 2023-10-18)
3458|2023-09-29|2023-10-18||Beyond the Royal Commission [Final report - volume 12]
   (then the corrigendum, and the six records of the three other commissions)
# 20 of 20 register records match type 'Royal commission'
```

None of the thirteen titles names the commission. Two of them contain the
words "Royal Commission" without saying which one. The corrigendum, tabled
five weeks later, is the only one of the report's own records whose title
carries the commission's name. A register that matches documents to
commissions by title will find none of the report.

The text is native:

```
python3 pdftext.py otd_3444_drc_execsummary_recs.pdf otd_3444_drc_execsummary_recs.txt
otd_3444_drc_execsummary_recs.pdf: 356 pages, 805817 characters, 3 pages with no text
```

The existing step reads nothing from it, for the same reason as Robodebt —
the label and the recommendation's title share a line, here without a colon:

```
python3 report_recs.py otd_3444_drc_execsummary_recs.txt
# 0 lines match the step's heading pattern (the label alone on its own line)
# 224 distinct recommendation numbers appear anywhere in the text
# 0 recommendations extracted from otd_3444_drc_execsummary_recs.txt
```

224 rather than 222 because that count also matches a bare integer, and the
two extra are citations to another commission: "recommendation 20" and
"Recommendation 28 of the Mental Health Royal Commission's Final Report". A
label pattern that does not require the chapter number will import other
commissions' numbering.

Reading the shape the report uses:

```
python3 numbered_recs.py otd_3444_drc_execsummary_recs.txt
# 223 headings, 222 distinct recommendation numbers in otd_3444_drc_execsummary_recs.txt
# every one but the last stops at the next heading: shortest 137 characters, median 843, longest 3683
# the last, 12.8, has no heading after it and runs to the end of the file: 36338 characters
```

The same shape and the same single defect: 221 of the 222 end at the next
heading, and the last has nothing after it. These recommendations are longer
than Robodebt's — a median of 843 characters against 261, and up to 3,683 —
because many are set out in lettered parts, so a maximum length written for
committee recommendations would cut them. One number is printed twice
(223 headings, 222 numbers); taking the shorter of the two, which is what the
existing report step does for committee reports, resolves it.

The tabled copy and the commission's own copy are not the same file:

```
sha256sum otd_3444_drc_execsummary_recs.pdf drc_site_execsummary.pdf
9dfac2e393a5796510d460892e1910a0bd7c4b4f7ee30167e69b1fe0b6ec05bb  otd_3444_drc_execsummary_recs.pdf
9ae9c826217fef7a0686f85bf91a20584ab077eee0dbc77e95b1c4d8fd570d13  drc_site_execsummary.pdf
```

Both are 356 pages and both carry 222 numbered recommendations. The tabled one
was created 31 August 2023 and the site's on 20 October 2023
(`pdfinfo <file> | grep CreationDate`).

### 2. The report's own count

The report says 222, and 222 is what is there.

```
grep -n "total of 222 recommendations" otd_3444_drc_execsummary_recs.txt
232:The Final report contains a total of 222 recommendations. ...
```

```
grep -oEi 'Recommendation[ \t]+[0-9]{1,3}\.[0-9]{1,3}' otd_3444_drc_execsummary_recs.txt \
  | sed -E 's/.*[ \t]//' | sort -u -V | wc -l
222
```

They agree.

### 3. The government response

Tabled. Id **6874**, "Australian Government Response to the Disability Royal
Commission", document type **Government response**, author Department of
Social Services, tabled in the **Senate 31 July 2024** and the **House 12
August 2024**; two files, the response and an Easy Read summary. A ministerial
statement on it is separately tabled as id **6982**, both houses 12 August
2024. It is already in `scope_exclusions.csv` as a royal commission response.

There is a departmental copy, and it is a different document. The DSS URL now
redirects:

```
curl -sS -o /dev/null -L -w "%{http_code} %{url_effective}\n" \
  https://www.dss.gov.au/responding-disability-royal-commission/resource/australian-government-response-disability-royal-commission
200 https://www.health.gov.au/resources/publications/australian-government-response-to-the-disability-royal-commission
```

The file it offers has a different checksum from the tabled one, a different
size (4,719,715 against 5,041,972 bytes) and a later creation date (5 August
2024 against 29 July 2024). Both are 312 pages. Their text differs in two
places:

```
diff otd_6874_drc_response.txt drc_response_health.txt
< and the review of the Disability Standards for Education 2005 Review
< undertaken in 2020.
---
> and the review of the Disability Standards for Education 2005 undertaken
> in 2020.
< payments for properties with 610 residents.
---
> payments for properties with 6–10 residents.
```

The first is a correction to the words. The second is a dash the tabled PDF
renders in a way pdfplumber reads as digits. No corrigendum accompanies
either.

The existing split and position test do not read this document:

```
python3 positions.py otd_6874_drc_response.txt
# 110 recommendations split out of otd_6874_drc_response.txt
# states:   {'noted': 2, 'unreadable': 108}
# verdicts: {}
# dropped by the split: {"the government's words begin mid-sentence": 62}
```

```
python3 verdict_by_segment.py otd_6874_drc_response.txt
# 176 distinct recommendation numbers in otd_6874_drc_response.txt
#    161  (no verdict word)
#      8  accepted
#      7  in part or in principle
```

This is not a broken document. It answers in a different grammar. Where a
committee response writes "The Government accepts this recommendation", this
one writes a labelled block:

```
Response to Recommendation 6.41
Responsibility: Australian, state and territory governments
ACT and WA: Accept in principle
Commonwealth, NSW, QLD, NT, SA, TAS, VIC: Subject to
further consideration
```

`coverage.py` looks for a verdict word used of the recommendation in a
sentence, or as a label at the very start of the government's words. Here the
verdict is a label on its own line, after a line naming who is answering, and
the recommendation's text is above it rather than beside it. Read as blocks:

```
python3 drc_blocks.py otd_6874_drc_response.txt otd_3444_drc_execsummary_recs.txt
# 118 response blocks, naming 172 recommendations between them
# 17 blocks answer more than one recommendation at once
# 172 recommendations get a verdict for the Commonwealth's part under the rule above
# responsibility lines:
#     64  Australian, state and territory governments
#     50  Australian Government
#      3  Australian Government and non-government
#      1  Australian government
# (the list of who each verdict is attributed to is omitted here)
# verdict words, exactly as the response writes them:
#     88  Accept in principle
#     19  Subject to further consideration
#     16  Accept
#      5  Note
#      1  Subject to
# the report makes 222 numbered recommendations
# 50 of them are not named by any response block
```

Four things follow. A block can answer a range — "Response to Recommendations
4.1–4.21" — so seventeen blocks carry more than one recommendation and a rule
has to expand the range. A recommendation can be answered in more than one
block, a lettered part at a time: 6.41 has five. The verdict vocabulary is
four labels, of which "Accept" is the site's *accepted*, "Accept in principle"
its *in part or in principle*, and "Note" its no position; "Subject to further
consideration" has no equivalent in the existing vocabulary and is not a
position. And the single "Subject to" is the same label broken across a line
by the page layout, which any rule has to rejoin.

Fifty of the report's 222 recommendations are named by no block at all.
Eighteen of those fifty name a state or territory in their own text
(`names_a_state.py`, intersected with the list `drc_blocks.py` prints); what
the other thirty-two are addressed to is not established here. The register
would show all fifty as carrying no Commonwealth position, which is what the
document supports.

From tabling to tabling:

```
python3 elapsed.py 2026-09-06
  306 days  Disability: report tabled in the Senate [3444] to response tabled in the Senate [6874]
 1073 days  Disability: report tabled in the Senate [3444] to today
```

### 4. Addressees

The recommendations themselves say who they are for, but not reliably:

```
python3 names_a_state.py otd_3444_drc_execsummary_recs.txt
# 222 distinct recommendations in otd_3444_drc_execsummary_recs.txt
# 88 name a state or territory in their own text
```

The response is the better source, because it says so on a line of its own:
64 blocks "Australian, state and territory governments", 50 "Australian
Government", 3 "Australian Government and non-government", 1 the same words in
lower case.

A rule can decide the Commonwealth's part without judgement, from the
left-hand side of the verdict label. "Response:" and "Joint response:" and
"Australian Government Response:" speak for the Commonwealth; a left-hand side
that lists states without naming the Commonwealth does not. Under that rule
every block yields a position for the Commonwealth — 172 of the 222
recommendations — and the states-only lines are recorded but are not the
Commonwealth's position. The rule is in `drc_blocks.py` and is four lines of
regular expression.

The lower-case "Australian government" is a reminder that the responsibility
line is prose and has to be matched case-insensitively.

### 5. Later documents

One progress report, on a department site, not tabled.

*Disability Royal Commission Progress Report 2025*,
<https://www.health.gov.au/resources/publications/disability-royal-commission-progress-report-2025>,
publication date 27 November 2025, fetched 6 September 2026. It is HTML with a
page per recommendation, for example
`.../disability-royal-commission-progress-report-2025/volume-12-beyond-the-royal-commission/recommendation-122-implementation-of-the-final-report-recommendations`,
which returns 200. There is also a standing page, "Implementing the
recommendations of the Disability Royal Commission", at
<https://www.health.gov.au/our-work/disability-royal-commission-response/implementing-recommendations>.

Neither is tabled. A title search of the register returns four records — the
corrigendum, volume 3, the response and the ministerial statement — and no
progress report; the thirteen report volumes are found only by document type,
because their titles do not carry the commission's name.

```
python3 otd_search.py --title 'disability royal commission|violence, abuse, neglect'
4072|2023-11-02|2023-11-16||Royal Commission into Violence, Abuse, Neglect and Exploitation of People with Disability [Final report - Corrigendum]
3448|2023-09-29|2023-10-18||Nature and extent of violence, abuse, neglect and exploitation [Final report - volume 3]
6982|2024-08-12|2024-08-12||Ministerial Statement on the Australian Government Response to the Final Report ...
6874|2024-07-31|2024-08-12||Australian Government Response to the Disability Royal Commission
# 4 of 17380 register records match title /disability royal commission|violence, abuse, neglect/
```

Nothing was extracted from the progress report.

The states and territories have published their own responses. They are out of
scope by decision and were not looked at.

### 6. Re-fetching

Every Disability document — the tabled executive summary, the corrigendum, the
response, its Easy Read summary, the ministerial statement, the commission's
own copy of the executive summary, and the departmental copy at
health.gov.au — came back byte for byte identical on all four passes, with no
redirects, by the same commands as above.

The one moving part is the departmental address. The `dss.gov.au` URL is a
redirect to `health.gov.au` following a change of department, and the file it
points at sits under a `2025-07` path although the document is from July 2024.
A stored departmental URL will rot; a stored Tabled Documents id will not.

### 7. Dates stated in the response

```
python3 dated_sentences.py otd_6874_drc_response.pdf
# 54 sentences with a future-tense verb and a date in otd_6874_drc_response.pdf
```

Three are commitments to a date. Verbatim, with the PDF page:

> p80: Scoping and development will commence in 2024.

> p148: Initiatives listed in the Plan will be reported on to the Disability
> Reform Ministerial Council every 12 months, and the Plan will be updated in
> mid-late 2024 to reflect actions being taken in response to the Disability
> Royal Commission and the NDIS Review.

> p268: On 5 March 2024, the Australian Government and state and territory
> governments, except Tasmania due to being in caretaker, released a joint
> statement committing to responding to joint Disability Royal Commission
> recommendations by mid-2024.

The rest are dates in the past, or dates attached to other documents. Recorded
here for the record; nothing is computed against them.

---

## What could not be got

**The Robodebt response as PM&C publishes it.** `www.pmc.gov.au` refuses
automated requests. Both the PDF and its resource page return 403 with a bot
interstitial, on every one of the four fetches, with a plain user agent and
with a browser one:

```
curl -sS -o /dev/null -L -w "%{http_code} %{content_type} %{size_download}\n" \
  https://www.pmc.gov.au/sites/default/files/resource/download/gov-response-royal-commission-robodebt-scheme.pdf
403 text/html 879
curl -sS -o /dev/null -L -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..." -w "%{http_code}\n" \
  https://www.pmc.gov.au/resources/government-response-royal-commission-robodebt-scheme
403
```

So the tabled and departmental copies of that response could not be compared,
as they were for the Disability response. Whether a browser driven by hand
gets through was not tested; it would need a site approval, and the register
would not be allowed to depend on it either way. `ministers.pmc.gov.au`
answers normally, so this is the one host, not the department.

**The 57th Robodebt recommendation.** The report says 57 and prints 56. The
closed chapter, now tabled, contains referrals and no numbered recommendation,
so it is not the missing one. Nothing here decides between the two figures and
neither is adopted.

**The sealed chapter as it stood when the report was made.** What exists is
the version tabled on 12 March 2026, 979 days later. Its own contents pages
describe referrals to five bodies. No public document says whether it is the
whole of what was sealed.

**Nothing needed a login.** No document in `sources.tsv` is behind
authentication, a paywall or a CAPTCHA, and none needed a browser.

**Not looked at, by decision:** state and territory commissions, the state and
territory responses to the Disability Royal Commission, and the Wikipedia
census in `discovery/`.

---

## Go or no-go

Go, for a Commonwealth register built on tabled documents, with one condition
that has to be met first. Both commissions' reports and both governments'
responses are in the Tabled Documents register, are native-text PDFs needing
no OCR, and come back byte for byte identical on four fetches into empty
directories, with no redirects and nothing that needed a browser or a login —
which
is the property a weekly rebuild actually depends on, and the departmental
copies do not have it: one host refuses automated requests outright and the
other has moved department, changed its URL and published a quietly different
file from the one it tabled. The condition is that neither the recommendation
side nor the response side of the existing pipeline reads these documents
today, and the reasons are specific rather than general: the report step
expects the recommendation number alone on its line and both reports put the
number and the recommendation's title together, so it extracts nothing from
either; the response step reads Robodebt's 49 of 56 and loses seven to two
tests that were written for committee prose; and `coverage.py` cannot see the
Disability response at all, because that response answers with a label on a
line — "Joint response: Accept in principle" — rather than a sentence, and
answers ranges of recommendations in one block, and gives one verdict for the
Commonwealth and another for the states. Each of those is a rule a person can
write down and a test can pin, and none requires anything to be inferred; but
a register that shipped before they were written would publish the Disability
Royal Commission's 222 recommendations as carrying no stated position, when
the response states one for 172 of them.

The first pipeline step is therefore not a scraper. It is a harvest that finds
the documents at all: a sweep of the Tabled Documents register by document
type `Royal commission` — twenty records today, covering four commissions —
plus the government responses to them, which cannot be found by type, because
Robodebt's is typed `Other` and the Disability one is typed
`Government response`. That step produces a table of commission, report
documents, response documents and tabling dates, from the register only, with
no extraction. Everything else waits until that table exists and can be
rebuilt on a Tuesday without changing.
