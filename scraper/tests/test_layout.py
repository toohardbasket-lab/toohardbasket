"""Which quotations were written by nobody.

A government response printed in two columns comes out of the PDF read across
the columns rather than down them, and the government's answer ends up spliced
into the committee's sentence:

    The committee recommends that the The Government is committed to deterring
    Australian Government establish a small wage theft, and ensuring that where
    it does claims tribunal…

Every word of that is in the document. verify_recommendations.py therefore
passes it — the row it checks really does appear in the text it names — and so
does every other check here, because they all ask whether the words are the
document's, and these words are. This is the only step that can see it.

The tests below are mostly sentences that must NOT be called spliced, because
the first three versions of this check each called something innocent broken:

  - "the Australian Government support efforts to collect the data" is the
    subjunctive, which is what a recommendation sounds like;
  - "That SO 4(h) and SO 4(i) be amended as follows: (h) The Prime Minister
    shall inform the House" introduces a sentence with a sub-clause marker;
  - "Wage-setting practices The Australian Government should actively monitor…"
    is the report's own heading run into the sentence below it by the layout.

The last of those is the reason the test is not about position. A heading sits
before the committee starts speaking; a column break lands after.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import layout_check as L  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


# --- spliced, and must be caught ---------------------------------------------
for text in [
    "The committee recommends that the The Government is committed to deterring Australian "
    "Government establish a small wage theft, and ensuring that where it does claims tribunal",
    "The committee recommends that the Australian Government review whether The Government "
    "appreciates concerns employee representatives that hold 'right raised by witnesses",
    "The Committee recommends that Australian The Australian Government agrees that "
    "Government agencies continue to engage with engagement with the community is important",
]:
    check(f"spliced: …{text[38:88]}…", bool(L.suspect(text)))

# --- not spliced, and must be left alone --------------------------------------
for text, why in [
    ("The Committee recommends that the Australian Government support efforts to collect "
     "gender-disaggregated data on the prevalence of child and forced marriage.",
     "the subjunctive is what a recommendation sounds like"),
    ("Wage-setting practices The Australian Government should actively monitor wage-setting "
     "practices, especially in enterprise agreements, to ensure that modern award outcomes "
     "lead to sustainable wage growth.",
     "the report's own heading, run into the sentence by the layout"),
    ("Compassion, Not Commerce The Sub-Committee recommends that the Australian Government "
     "includes information on trafficking in human organs on relevant government websites.",
     "a heading again, before the committee starts speaking"),
    ("That SO 4(h) and SO 4(i) be amended as follows: (h) The Prime Minister or another "
     "Minister shall inform the House of the time when the Governor-General will receive "
     "the Members.",
     "a sub-clause marker introduces a sentence"),
    ("The Committee recommends that, as soon as practicable after the Australian Government "
     "is informed of a proposed amendment to a species listed in the CITES Appendices, it "
     "publish the advice.",
     "a subordinate clause about the government, inside the recommendation"),
    ("The Committee recommends that the Australian Government fund research into the "
     "prevalence and impact of family violence on children, including: • during the first "
     "1,000 days. The Government supports this recommendation.",
     "a full stop introduces the sentence, so it is a boundary and not a splice"),
]:
    check(f"left alone ({why})", not L.suspect(text), L.suspect(text))


# --- the document-level rule --------------------------------------------------
# A share on its own is useless: a response with one recommendation is at 100 per
# cent the moment that row is flagged. A count on its own is useless too: a long
# response can carry three odd rows and be soundly laid out.
check("the rule needs both a count and a share", L.LEAST_ROWS >= 3 and L.LEAST_SHARE >= 0.5,
      f"{L.LEAST_ROWS} rows, {L.LEAST_SHARE} share")

# --- and it must still say something about the live dataset -------------------
import json  # noqa: E402

out = pathlib.Path(L.DATA) / "layout_suspect.json"
if out.exists():
    d = json.loads(out.read_text(encoding="utf-8"))
    check("the file names how many documents and how many rows",
          {"documents", "rows_in_those_documents", "rows_flagged_elsewhere"} <= set(d))
    check("rows flagged outside those documents are reported rather than acted on",
          isinstance(d.get("rows_flagged_elsewhere"), int))
    print(f"\\nNOTE  {d['documents']} document(s) the extraction could not follow, "
          f"{d['rows_in_those_documents']} rows. {d['rows_flagged_elsewhere']} odd rows "
          f"elsewhere are counted and left alone, because one strange sentence is not "
          f"evidence that a response was laid out in two columns.")

print(f"\\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
