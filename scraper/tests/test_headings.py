"""Which "Recommendation 3" is a heading, and which is a mention of one.

extract_recommendations.py finds a recommendation by its label and then reads
forward. So the first question it asks of every label is whether the label is
the heading of a recommendation being quoted, or a mention of one inside a
sentence. Get that wrong in the strict direction and a real recommendation is
dropped without trace; get it wrong in the loose direction and a cross-
reference becomes a row.

It was wrong in the strict direction for a year. Once the PDF's line breaks are
thrown away, a section heading looks exactly like the middle of a sentence:

    …addresses the recommendations contained in the Report and in the
    additional comments. Committee's Recommendations Recommendation 1 The
    committee recommends that the minimum consultation period…

The character before "Recommendation 1" is the "s" of "Recommendations", so the
label read as mid-sentence and the document's first recommendation was never
extracted. 241 documents were missing recommendations for that reason, 218 of
them their Recommendation 1.

So these tests are mostly pairs: the same label, once under a heading and once
inside a sentence.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import extract_recommendations as E  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def heading(before: str) -> bool:
    """Is a label a heading, given the words before it?"""
    body = before + "Recommendation 1 The committee recommends that something be done."
    return E.is_heading(body, len(before))


# --- a heading, even though it ends in a lower-case letter -------------------
for before in [
    "…in the additional comments. Committee's Recommendations ",
    "Response to the Committee's recommendations ",
    "…after referral by the Senate on 4 February 2021. Recommendations ",
    "…resilience against foreign interference Recommendations ",
    "Government Response to the Senate Economics Legislation Committee Report ",
    "…in the Committee's Final Report ",
    "Senator Scarr's Additional Recommendations ",
    "Australian Greens Senator's Dissenting Report ",
    "…the Australian Labor Party in Additional Comments ",
]:
    check(f"heading: …{before.strip()[-42:]}", heading(before))

# --- not a heading: a label inside a running sentence -----------------------
for before in [
    "The Government has already acted on the matters raised in ",
    "…implementing recommendation 7 from the Tax dispute inquiry report and ",
    "…the Committee's view about the previous Government response in relation to ",
    "…which repeats the substance of ",
    "…as set out in the answer to ",
]:
    check(f"not a heading: …{before.strip()[-42:]}", not heading(before))

# --- the boundaries the rule always had, and must keep ----------------------
check("the start of the document is a heading", heading(""))
check("after a full stop is a heading", heading("…and nothing further. "))
check("after a bullet is a heading", heading("…and nothing further • "))
# A title that does NOT end in one of the heading words is still mid-sentence
# to this rule. That is a known limit, not an oversight: widening it to "any
# capitalised run" would readmit the cross-references the rule exists to keep
# out. Where such a document has a second, cleaner occurrence of the label, the
# extractor finds it there instead.
check("a title ending in an ordinary word is still not a heading",
      not heading("AUDIT REPORT 492: Governance in the Stewardship of Public Resources "))

# The heading word has to be the last thing before the label. A sentence that
# merely contains "report" further back is still a sentence.
check("a heading word further back does not rescue a sentence",
      not heading("…the report says that the Government should consider "))

# --- the rule admits a label; it does not publish one ------------------------
# Everything that made a row trustworthy before is still downstream of this.
body = ("Committee's Recommendations Recommendation 1 The committee recommends that the "
        "minimum consultation period for the Code is extended to at least 60 days. "
        "The Government agrees to this recommendation. It was amended accordingly. "
        "Recommendation 2 The committee recommends that the Department publish an annual "
        "statement setting out what it has done about each of these matters. "
        "The Government notes this recommendation.")
found = E.recommendations_in(body)
check("the recommendation under the heading is now found", "1" in found)
check("and the one after it still is", "2" in found)
check("the committee's words stop where the government's start",
      found["1"][0].endswith("at least 60 days"))
check("the government's words start where they start",
      found["1"][1].startswith("The Government agrees"))


# --- the verdict printed above the recommendation ---------------------------
# Some documents put the verdict first: "Recommendation 20 Noted. First
# Nations-led innovations … should be prioritised". The handover then matches at
# the head of the segment, everything the committee wrote reads as the
# government's words, and nothing is left to quote. 120 labels are laid out that
# way. It is a parsing fault, not an admission rule — it widens nothing — but it
# published the government's own words as the committee's four times before the
# guards below were added, which is the worst thing this file can do.

def one(body: str, label: str = "1"):
    got = E.recommendations_in(body)
    return got.get(label)


r = one("Recommendation 1 Supported The Committee recommends that the Australian Government "
        "fund research into the prevalence of family violence.")
check("verdict first: the committee's words are recovered",
      bool(r) and r[0].startswith("The Committee recommends that the Australian Government fund"))
check("verdict first: the verdict is the government's words", bool(r) and r[1] == "Supported")

r = one("Recommendation 1 Noted. First Nations-led innovations in governance of Country should "
        "be prioritised, supported, resourced and encouraged.")
check("verdict first: a recommendation that never says \"recommends\"",
      bool(r) and r[0].startswith("First Nations-led innovations"))

# A verdict with a subject is not a verdict label, it is the government talking,
# and what follows it is the rest of its sentence.
r = one("Recommendation 1 The Australian Government notes this recommendation. However, given "
        "the passage of time since this report was tabled, a substantive response is no "
        "longer appropriate.")
check("a clause with a subject is not a verdict printed above a quotation",
      r is None or not r[0].startswith("this recommendation"))

# Two columns read across each other. Every word is in the document and the
# sentence was written by nobody.
r = one("Recommendation 1 Accepted. The committee recommends that the The Government has "
        "committed to Australian Government prioritise criminalising wage theft in its "
        "Secure amendments to the Fair Work Act 2009.")
check("a spliced two-column sentence is refused", r is None)

r = one("Recommendation 1 Noted. The committee recommends that in developing the Accreditation "
        "The Attorney-General's Department is currently preparing an impact analysis for the "
        "new Rules for Children's Contact Services.")
check("a sentence that restarts mid-sentence is refused", r is None)

# The same recommendation printed twice: once in a summary table under its
# verdict, once in the body with the government's reasons. The table's entry is
# shorter and would win on length, and the answer would shrink to one word.
both = ("Recommendation 1 Supported The Committee recommends that the Australian Government "
        "fund research into the prevalence of family violence. "
        "Recommendation 1 The Committee recommends that the Australian Government fund "
        "research into the prevalence of family violence. The Government supports this "
        "recommendation. Funding has been allocated to the Institute to lead the work.")
r = one(both)
check("the body's answer beats the table's verdict",
      bool(r) and len(r[1]) > len("Supported"), )
check("and the recommendation is still the committee's words",
      bool(r) and r[0].startswith("The Committee recommends"))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
