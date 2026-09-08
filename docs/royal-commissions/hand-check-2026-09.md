# Twenty rows, checked against the tabled PDFs by eye

8 September 2026

`verify_rc_index.py` checks every published row back against the cached text of
the document it names. It cannot check the cache. If a page of the report never
made it into `raw/rc_text/`, or made it in garbled, the verifier compares the
index against the same garble and passes it. `--control` answers the question of
whether the check has teeth; it does not answer the question of whether the
cached text is the document.

So this is twenty rows read off the PDFs as a person would read them: the page
image rendered from the file the Tabled Documents register serves, and the
published row beside it. Five of the fifty-six robodebt rows and fifteen of the
two hundred and twenty-two disability rows, chosen to include every awkward case
the extraction rules were written for, plus a spread of ordinary ones.

## What it found

Every one of the twenty carries the label, the heading and the recommendation
text its report prints, and the position and the label its response states.

The government's **words** were a different matter, and the value of doing this
by eye is that four defects showed up in the first five minutes of reading the
rows, none of which the verifier could have caught. The verifier asks whether
the published words are in the document. All four were: they were the document's
words with the document's furniture attached, or with the government's sentence
cut in half.

| What was wrong | Rows affected | Fixed by |
| --- | --- | --- |
| The page's running head printed inside the quotation — "…in some jurisdictions. Australian Government Response – Volume 4 51 The Australian Government will further consider…" | 120 of the 228 answers | `furniture()` in `extract_rc_positions.py` |
| The quotation opening with the *next* block's heading and verdict lines — "Response to Recommendation 7.20 Responsibility: Australian Government Joint Response: Accept in principle The Australian Government and state…" | 6 | `said_from()`, which now runs to the next heading rather than taking twelve lines of the page |
| Robodebt 20.5 cut to eleven words at the government's own cross-reference — "The Government accepts this recommendation. As noted in the response to" | 1 | `prose_end()`, which stops at a heading and not at a mention |
| The quotation stopping in the middle of a word at the 900-character cap | 29 | `cut()`, which stops at the end of a sentence and sets `government_words_more` so the row says the answer goes on |

A fifth of the same kind turned up when the Royal Commission into Defence and
Veteran Suicide was added on 8 September, and was found the same way — by
scanning the new rows for the defects the earlier reading had named. Its
response is filed in the register as "Government Response to the Final report
of the Royal Commission Inquiry into Defence and Veteran Suicide" and heads its
pages "**Australian** Government Response to the Royal Commission into Defence
and Veteran Suicide", so the rule that finds a running head by the document's
own title missed it by one word and three answers were published with the head,
a page number and the next volume's title inside them. A head may now carry a
word in front of the title's own opening, and only there.

A fifth, found while checking disability 6.31: where a response answers a
recommendation part by part — "Recommendation 6.31 (a)" and "(b)", with a
different verdict for each — the row quoted part (a) and said nothing to
suggest part (b) existed. It now says the answer continues.

None of these changed a single verdict, a single label or a single count. What
they changed is whether a reader who quotes this index quotes the government or
quotes the typesetting.

## The rows

Page numbers are the PDF's own printed page, with the file's page in brackets
where they differ. "Report" is the page the recommendation is printed on;
"response" the page the government's answer is printed on.

### Royal Commission into the Robodebt Scheme

| Row | Report | Response | Checked |
| --- | --- | --- | --- |
| 10.1 Design policies and processes with emphasis on the people they are meant to serve | 342 (385) | 9 | Heading, four bullets and closing words exact. "The Government **accepts** this recommendation." → accepted. Quotation runs to the end of the third paragraph and says the answer goes on, which it does. |
| 17.2 Establishment of a body to monitor and audit automated decision-making | 488 (531) | 22 | Exact, including the report's own "audit automate decision-making processes", which is left as printed. |
| 20.5 Administrative Review Council | 566 (609) | 32 | The report heads it "Recommendation - Administrative Review Council", with no number; the number comes from the report's own numbered list and the response confirms it. This is the row that was cut to eleven words. |
| 21.1 Statutory duty to assist | 582 (625) | 33 | Exact. |
| 23.8 Documenting decisions and discussions | 646 (689) | 39 | Exact. |

### Royal Commission into Violence, Abuse, Neglect and Exploitation of People with Disability

| Row | Report | Response | Checked |
| --- | --- | --- | --- |
| 4.1 Establish a Disability Rights Act | 193 (213) | 50 (56) | Answered inside "Response to Recommendations 4.1–4.21". Label "Subject to further consideration", so the row states no position and is not a refusal. The running head sits between two paragraphs of this answer on the page — the case that broke 120 rows. |
| 4.29 Offensive behaviour | 206 (226) | 59 (65) | Answered inside "Response to Recommendations 4.23–4.34"; the range is expanded from the heading, and 4.29 falls inside it. |
| 5.3 Review and update of disability strategies and plans | 210 (230) | — | The response goes from 5.2 to 5.4. Recorded as not addressed, not as a refusal. Directed at state and territory governments only. |
| 6.4 Terms and definitions in guardianship and administration legislation | 216 (236) | — | Not addressed, same reason. |
| 6.31 Embed the right to equitable access to health services in key policy instruments | 230 (250) | 98 (104) | "Joint Response to 6.31 (a): **Accept**", "Joint Response to 6.31 (b): **Accept in principle**". Both labels kept; sorted as in part or in principle because the parts differ. |
| 6.41 Legislative prohibition of non-therapeutic sterilisation | 237 (257) | 108 (114) | "ACT and WA: Accept in principle" is kept beside the row; the Commonwealth's own label, "Commonwealth, NSW, QLD, NT, SA, TAS, VIC: **Subject to further consideration**", is wrapped across two lines on the page and is rejoined. States no position. |
| 7.18 Establish specific and disaggregated targets for disability employment in the public sector | 252 (272) | 131 (137) | Two headings printed back to back — 7.18/7.19/7.21/7.22/7.23, then 7.20 — with one body underneath. Six recommendations, one answer. |
| 7.20 Clarify the application of the merit principle in public sector recruitment | 253 (273) | 131 (137) | The same body, and correctly *without* the "answered with the states and territories together" note, because 7.20's own responsibility line names the Australian Government alone. |
| 7.26 Amend the Disability Discrimination Act 1992 (Cth) | 255 (275) | 135 (141) | The answer is one paragraph containing "The Government will consider / Recommendation 7.26 as part of its review" — a sentence the page broke before a number. Read as a heading, that truncated the answer. |
| 7.40 Address homelessness for people with disability in the National Housing and Homelessness Plan | 265 (285) | 155 (161) | Subject to further consideration; states no position. |
| 9.12 Disability-inclusive cultural safety standards | 284 (304) | 196 (202) | The whole answer, 423 characters, and the row correctly does not claim there is more. |
| 10.31 Continuous monitoring of criminal charges | 300 (320) | 242 (248) | Answered inside "Response to Recommendations 10.31–10.33"; en-dash range expanded. |
| 10.32 Operational framework to guide worker screening | 300 (320) | 242 (248) | The same block, the same answer. |
| 11.14 Establishing disability death review schemes | 306 (326) | — | The last block in the chapter is 11.12–11.13. Not addressed. |
| 12.2 Implementation of the Final report recommendations | 310 (330) | 264 (270) | "Joint response: Accept in principle" — lower-case "response", which the rule reads the same way. |

## What this does not establish

Twenty rows out of two hundred and seventy-eight. The check is on the cached
text, not on the extraction rules, and a defect in a rule that happens not to
bite on these twenty pages is not ruled out by them. Two of the twenty were
chosen because a rule had already failed on them once.

The pages were rendered with `pdftoppm -r 100 -gray -png` from the files cached
under `scraper/raw/otd/`, which are the bytes the Tabled Documents register
serves; the source test of 6 September established those are stable across
fetches.
