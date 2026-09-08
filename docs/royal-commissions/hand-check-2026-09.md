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

---

# Fourteen Defence and Veteran Suicide rows, read the same way

8 September 2026, after adding the third commission.

The rules that read this commission were changed the same day: a new numbering
shape, a new test of where a heading stops, and a new rule about which sentence
a verdict is read from. None of its 135 rows had been looked at. Fourteen were
read off the tabled PDFs — three of the interim report's thirteen and eleven of
the final report's hundred and twenty-two — chosen to cover every rule that had
just changed plus the rows the automated checks had already argued about.

## What it found

Twelve of the fourteen are right in every particular: the label, the heading,
the recommendation's own words, the government's words, and the position.

Two were not, and neither could have been caught by `verify_rc_index.py`,
because in both the published words are the document's words. Both are fixed.

### Recommendation 90 — a refusal published as no position

The response to recommendation 90 reads, with the verdict in bold exactly where
every other answer in the document puts it:

> The Government **does not support** the removal of the service differential as
> it relates to permanent impairment compensation.

and three paragraphs later:

> The Government agrees-in-principle to further expanding non-liability health
> care for mental health conditions to all reserve personnel.

Part (a) is refused and part (b) is agreed in principle. The index records the
row as answered without a stated position.

The cause is an asymmetry in `coverage.py`, which both indexes share. Its test
for a verdict at the opening of an answer recognises "The Government agrees…"
but not "The Government does not support…", because the negation is not part of
the verdict vocabulary it looks for at that position; and its other test wants
the verb's object to be the recommendation, where here the object is "the
removal of the service differential". So a positive verdict about a part of a
recommendation is read as a position and a negative one about a part is not.

This matters more than one row. The index page states, from the figure, that no
response in it refuses a recommendation outright. On this reading that sentence
is true; on the document's own reading it is false.

Allowing a negation in front of the verdict at the opening of an answer was
measured against the committee register before being proposed: of its 3,172
answers, **four** would move, all of them from "answered without a stated
position" to "not accepted", and all four say plainly that the government does
not agree —

> The Government does not agree with the assertions contained in this
> recommendation.

So it is a correction on both indexes rather than a reinterpretation, and it
was made: `coverage.py` now reads a negation written in front of the verb as
well as into it. Recommendation 90 reads "not accepted", and the index page
says one recommendation was refused outright instead of none.

Two of those four committee rows are inside coverage.py's own scope and move
its published figures: 1,030 recommendations with a stated position becomes
1,032, and 81 not accepted becomes 83. Both are on responses that plainly
refuse — the advisory report on the Voice referendum bill and the supermarket
prices report — and both were read before the change was kept. The entry is in
`data/corrections.csv`, so the site says what moved and why on its own
corrections page rather than leaving the figures to change quietly.

What this did not touch is the rule that a verdict's object has to be the
recommendation. That rule governs a verdict found anywhere in an answer; this
one governs the answer's opening sentence, where a government is answering the
recommendation it has just been asked about. Reading recommendation 90's first
sentence any other way requires believing the government set "does not
support" in bold about something else.

### Recommendation 60 and ten others — the report's own furniture

The Defence and Veteran Suicide final report prints, inside each recommendation
box and at the end of it, where the recommendation is discussed:

> (Chapter 13: Oversight of Defence workplace health and safety)

and where the page broke after that, the running footer came with it —
"Recommendations 129", the word and the page number. Eleven recommendations
carried the locator and ten of those carried the footer as well. The other 111
had been cut before it by the next section heading, so the same locator was
published on some rows and not others. A recommendation now ends at the locator.
Fixed, and the eleven rows are the report's words again.

## The rows

Report and response page numbers are the pages' own.

### Interim report, tabled 11 August 2022; response 26 September 2022

| Row | Report | Response | Checked |
| --- | --- | --- | --- |
| 1 Improve the capacity of future royal commissions | 226 | 6 | Exact. |
| 4 The Department of Veterans' Affairs to provide advice on its funding needs | 275 | 9 | The response really does open "**Government** agrees to this recommendation", without the "The". Published as written, which is why the verifier's label test on a prose response looks for the label as it stands. |
| 13 Co-design education on information access mechanisms | 319 | 14 | Exact. |

### Final report, tabled 9 September 2024; response 2 December 2024

| Row | Report | Response | Checked |
| --- | --- | --- | --- |
| 1 Improve the capacity of future royal commissions | 102 | 161 | Exact. |
| 12 Consider emotional intelligence and performance against wellbeing targets | 109 | 36 | Its own text contains "(see / Recommendation 11) as part of the check", broken across lines. Read as a heading that ended the row before its answer; now it does not. |
| 42 Ensure that future Inspectors-General will not have served in the ADF | 127 | 66 | "The Government **notes** this recommendation." Published as accepted until today, on the strength of a later sentence about a Twenty-Year Review. Now noted, which is what the page says. |
| 60 Improve strategies for harm prevention by sharing quality data | 136 | 84 | The answer is two sentences and ends at the second. Until today it also carried the running head, a page number and the next volume's title. The recommendation carried the chapter locator and the footer. Both fixed. |
| 61 Establish a brain injury program | 137 | 85 | Exact; "agrees-in-principle" sorted as in part or in principle. |
| 68 Strike the right balance between confidentiality and disclosure | 143 | 92 | Its own text ends "as part of the process set out in / Recommendation 74." Read as a heading, that put the answer outside every window; now it does not. |
| 72 Expand and strengthen healthcare services for veterans | 146 | 96 | "The Government notes this recommendation for further consideration by the Taskforce" — no position, correctly. This is also the row whose heading was taken from a sentence broken before its number, and is now the report's. |
| 78 Consider moral injury in the Australian military population | 150 | 102 | Running head removed; the answer ends at its own last sentence. |
| 90 Remove the service differential | 157 | 114 | **Was wrong.** Refused in bold, published as no position stated. Fixed; see above. |
| 96 Ongoing funding for Provisional Access to Medical Treatment | 159 | 120 | "The Australian Government **agrees-in-principle**", and the label now says so; until today it said "agrees". |
| 122 Establish a new statutory entity to oversee system reform | 175 | 147 | Exact, after the running head and "Annex A" were taken off the end of it. |

## What this does not establish

Fourteen rows of 135. Every rule that changed today is covered by at least one
of them, and the two defects found were both in the class the automated check
cannot see. Nothing here says anything about the other 121.

## Robodebt's 57 against 56, read off both documents — 8 September 2026

The index showed "56 · the report says 57" and said, on the methods page, that
"the report's own sentence is not evidence that a further recommendation
exists". That was an assertion nobody had checked. Here is the check.

**The report's own list.** In the typography sidecar for OTD 2743, the List of
Recommendations runs from the line "List of Recommendations" (Calibri-Bold 27)
to "Overview of Robodebt" (Calibri-Bold 27). Inside it, 61 lines are set in
Calibri-Bold 11 — the face and size every recommendation heading in that list
is set in, with the recommendation underneath in Calibri 11. Four of the 61 are
the wrapped second lines of headings ("to serve", "compliance activity",
"including consultation with advocacy bodies", "reporting"), leaving 57
headings. Fifty-six begin "Recommendation" and a number. One does not:

> Closing observations
> **Section 34 of the Cth FOI Act should be repealed**
> The Commonwealth Cabinet Handbook should be amended so that the description
> of a document as a Cabinet document is no longer itself justification for
> maintaining the confidentiality of the document…

The list's own opening sentence is "The following is a list of 57
recommendations of this Commission." 56 numbered plus this one is 57.

**Cross-check on the list itself.** The 56 numbered entries in the list are the
same 56 the index publishes — in the list and not in the index: none; in the
index and not in the list: none — and there are no gaps within any chapter.
Chapters 14 and 22 make no recommendations at all.

**The government's response.** OTD 4163 opens its answers: "The Royal
Commission into the Robodebt Scheme made 56 recommendations and one closing
observation." It answers the closing observation separately — "For these
reasons, the Government does not consider that section 34 of the FOI Act should
be repealed" — and then says it "accepts or accepts in principle all 56
recommendations".

**What was done.** Both documents count 56 recommendations and one further item
that neither calls a recommendation. It is not published as a row: it has no
number, this is an index of recommendations, and every check in the pipeline
reaches a row by the number the report printed. `unnumbered_in_list()` now finds
it by the same typographic rule the pipeline already uses to tell a heading from
the text under it, bounded by the list because bold at body size is a lead-in, a
column head and a chart label everywhere else in that report — 101 of those
outside the list against the one inside it. The words go to
`rc_recommendation_counts.csv` and both pages print them. The false sentence on
the methods page is gone.

Nothing published in the index changed. No row was added, removed or altered,
and the 427 remain 427.

## Robodebt and Disability, read off the tabled PDFs — 8 September 2026

Fourteen rows across the two biggest sets in the index — 56 and 222 of the 427
— read page by page against the printed reports and responses.

### The Robodebt list, pages xiii to xxi of the report

| Row | Report page | Checked |
| --- | --- | --- |
| 10.1 Design policies and processes with emphasis on the people they are meant to serve | xiii | Exact, including the report's own "the particular difficulties rural and remote living". Heading split correctly across the line the page broke. |
| 11.1 Clear documentation of exclusion criteria | xiii | Exact. |
| 11.2 Identification of circumstances affecting the capacity to engage with compliance activity | xiii | Exact; two-line heading. |
| 13.3 "Face-to-face" support | xv | Exact, curly quotes and all. Response page 15: "The Government **accepts in principle** this recommendation", quoted to the end of a sentence with the rest marked as continuing. |
| 13.4 Increased number of social workers | xv | Exact. |
| 15.2 Include legal advices with New Policy Proposals | xv | Exact. |
| 23.8 Documenting decisions and discussions | xxi | Exact, and it stops where it should: what follows on the page is "Closing observations", which is a section heading in print. Response page 39 quoted exactly. |

### The Disability report and the Australian Government's response

| Row | Report page | Checked |
| --- | --- | --- |
| 8.21 Diversion of people with cognitive disability from criminal proceedings | 277–278 | Exact across the page break: both lists, all six bullets, no running footer, and it stops before "Raising the age of criminal responsibility". This is the class the apparatus rule fixed. |
| 8.22 Age of criminal responsibility | 278 | Exact. |
| 5.3, 8.21, 8.22, 11.17 and the other 46 marked "not addressed" | — | **Was wrong.** See below. |

### What was wrong

The index published 50 Disability rows as "not addressed", which it defines as
the response not mentioning the recommendation at all. Searching the response
for each of the fifty numbers found every one of them — once each, in Appendix
B, "State and territory recommendations", under the sentence "The table below
includes the 50 Disability Royal Commission recommendations within the sole
responsibility of state and territory governments." The reader's guide at the
front says the same the other way round: 172 answered, 50 not, because they are
the states' responsibility. The index's own split is 172 and 50.

Fixed the same day: a fourth state, "named, not answered", with the list's own
caption as the row's words. Written up as decision 10 in `ROYAL_COMMISSIONS.md`.

### One thing checked and left alone

Every quotation on this site ends without its full stop, on this index and on
the live recommendations index alike — `tidy()` strips it. It is consistent
across both corpora and it is the only difference between a row and the
document it came from, so it stays; it is now said on the methods page instead
of left for a reader to find.

## What this does not establish

Fourteen rows of 278. The defect found was in the class no automated check
could see, which is now three hand checks in a row.
