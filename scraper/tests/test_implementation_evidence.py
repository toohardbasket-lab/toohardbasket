"""Which sentences are a claim that this recommendation was carried out.

Five answers in the whole corpus say it. That number is only worth publishing
if the rule that produced it refuses the sentences that look like it and are
not, so most of these tests are sentences that must NOT count.

The one that matters most is the sixth candidate, which the rule admitted until
a word boundary was added:

    Annex A details how the Australian Government has implemented the
    recommendations accepted (in principle or in part) in response to
    Compassion, Not Commerce.

The words are the government's, they are about implementation, and they are
about a different committee's report from three years earlier. Admitting it
would have put an implementation claim against a recommendation it was not
about — an attribution failure, which is the failure this site is least willing
to make. The singular pattern matched the first thirteen letters of
"recommendations".
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import implementation_evidence as I  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def counts(text: str) -> bool:
    return bool(I.ACTIVE.search(text) or I.PASSIVE.search(text))


# --- the five the corpus actually holds -------------------------------------
for said in [
    "This recommendation has been implemented",
    "The Government has implemented this recommendation. The Australia-India Economic "
    "Cooperation and Trade Agreement entered into force on 29 December 2022",
    "The Government has actioned this recommendation. Following the passage of the "
    "Treasury Laws Amendment (2023 Measures No.3) Act 2023 by the Parliament in 2023…",
    "The government has delivered this recommendation. The passage of the "
    "Communications Legislation Amendment Act 2025 ensures Australians have access…",
    "The Australian Government has completed recommendation 4.",
]:
    check(f"counts: {said[:58]}…", counts(said))


# --- the sentence that must not count ---------------------------------------
check("the plural is not this recommendation",
      not counts("Annex A details how the Australian Government has implemented the "
                 "recommendations accepted (in principle or in part) in response to "
                 "Compassion, Not Commerce."))

# --- and the rest of the near misses ----------------------------------------
for said, why in [
    ("States and territories are already implementing a broad suite of measures to "
     "reduce the likelihood of human-shark interaction.",
     "somebody else's action, and not about this recommendation"),
    ("The term 'good oil field practice' is already defined in Section 7 of the OPGGS "
     "Act.", "a reason for refusing, not a claim of having acted"),
    ("The Government supports this recommendation and will implement it in 2027.",
     "a promise, which is what a response is made of"),
    ("The Government has established a whole-of-government taskforce to develop a "
     "detailed implementation plan for Defence Reforms.",
     "an action, but not a claim that the recommendation was carried out"),
    ("The Committee recommends the Government implement this recommendation.",
     "the committee's words, not the government's"),
    ("The Government notes this recommendation. Work is ongoing.",
     "ongoing is the opposite of the claim"),
    ("Implementation of this recommendation has commenced.",
     "commenced is not completed, and the site does not round it up"),
    ("This recommendation will have been implemented by June 2027.",
     "a future perfect is still a promise"),
]:
    check(f"does not count ({why}): {said[:46]}…", not counts(said))


# --- the heading rule is structural, not a reading ---------------------------
for heading in ["Implementation Status (September 2024)", "IMPLEMENTATION UPDATE",
                "Implementation progress"]:
    check(f"a document heading is found: {heading}", bool(I.SECTION.search(heading)))
check("a sentence about implementing something is not a heading",
      not I.SECTION.search("The Government will report on implementation annually."))


# --- the vocabulary count is deliberately broad, and must stay so ------------
# Its whole purpose is to be larger than the claim count. If it ever narrowed to
# match, the site would be quietly asserting that the gap had closed.
check("the broad count catches what the narrow one refuses",
      bool(I.COMPLETED_VERB.search("The Government has established a new First Nations "
                                   "Economic Partnership with the Coalition of Peaks.")))
check("and catches a completed action with no recommendation in sight",
      bool(I.COMPLETED_VERB.search("A review of Redress Support Services was completed in "
                                   "June 2022.")))


# --- the sentence published beside a claim is the claim's own sentence -------
body = ("The Australian Government agrees to this recommendation. The Government has "
        "actioned this recommendation. The Instrument entered into force on 14 May 2024. "
        "Further work continues.")
m = I.ACTIVE.search(body)
got = I.sentence_around(body, m.start(), m.end())
check("the claim is quoted with its own sentence and no more",
      got == "The Government has actioned this recommendation.", got)


# --- the live figures, so a rewrite that changes them has to say so ----------
rows = I.rows_with_answers()
claims = I.stated_done(rows)
check("every claim names the response it came from and the words it is made of",
      all(c["response_id"] and c["the_claim"] for c in claims))
check("no claim is counted twice for one recommendation",
      len({(c["response_id"], c["label"]) for c in claims}) == len(claims))
print(f"NOTE  {len(claims)} claims in the corpus today, from "
      f"{len({c['response_id'] for c in claims})} responses. Each has been read in full; "
      f"see docs/implementation-check.md.")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
