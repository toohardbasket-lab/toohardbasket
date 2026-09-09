"""Tests for who a recommendation belongs to when it is read out of a report.

A report's recommendations are the committee's. Its additional comments and
dissents are somebody's, and the site has to be able to tell them apart,
because publishing one member's demand as a committee's finding is the worst
mistake this file can make — and it made it.

The Education Committee's report of 29 June 2026 carries the committee's
Recommendation 1 and, in the additional comments, a recommendation of the
Independent Member for Curtin, numbered 1 again. The author test looked for a
party name in the opening words or a dissent heading above; an independent
member writing "I recommend" and signing underneath matched neither. With no
author found, the two candidates counted as the same authorship, the shorter
text won the number, and the site published hers as the committee's — with her
signature block still attached to it, because a signature was only recognised
as a signature when the word "Chair" followed the name.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import extract_report_recommendations as E

PASS, FAIL = [], []


def check(name: str, cond, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


CHANEY = (
    "I recommend that the Australian Government, as part of its ongoing reform of higher "
    "education funding, prioritise review and remediation of the student contribution "
    "increases imposed on humanities, arts, and social sciences degrees under the "
    "Job-Ready Graduates Package\nMs Kate Chaney MP\nIndependent Member for Curtin\n")
CHAIR = ("The committee recommends that the Australian Government act on this matter "
         "without further delay and report back within six months.\nSenator Jane Smith\nChair\n")

# --- the signature is not part of what was recommended -----------------------
tidied = E.tidy(CHANEY)
check("a member's sign-off is stripped from the recommendation",
      "Kate Chaney" not in tidied and "Independent Member" not in tidied, tidied[-60:])
check("and the recommendation itself survives intact",
      tidied.endswith("Job-Ready Graduates Package"), tidied[-60:])
check("a chair's sign-off is still stripped",
      "Jane Smith" not in E.tidy(CHAIR) and E.tidy(CHAIR).endswith("within six months"))
check("a chair's sign-off with a trailing clause is still stripped",
      "Jane Smith" not in E.tidy(CHAIR.replace("Chair\n", "Chair, Standing Committee on Things\n")))

# --- who said it -------------------------------------------------------------
check("a first-person recommendation is attributed to the member who signed it",
      E.signed_in_the_first_person(CHANEY, tidied) == "Ms Kate Chaney",
      E.signed_in_the_first_person(CHANEY, tidied))
check("a committee recommendation signed by its chair is not the chair's",
      E.signed_in_the_first_person(CHAIR, E.tidy(CHAIR)) == "",
      E.signed_in_the_first_person(CHAIR, E.tidy(CHAIR)))
check("a signature without the first person is not an attribution",
      E.signed_in_the_first_person(
          "The committee recommends that X be done promptly.\nMs Kate Chaney MP\n"
          "Independent Member for Curtin\n",
          "The committee recommends that X be done promptly.") == "")
check("first person without a signature is not an attribution",
      E.signed_in_the_first_person("", "I recommend that the Government act.") == "")

# --- "Member" is also an ordinary word ---------------------------------------
ordinary = ("The committee recommends that each Member of the scheme be told in writing what "
            "the change means for them before it takes effect.\n")
check("a recommendation using the word Member is not cut short at it",
      E.tidy(ordinary).endswith("before it takes effect"), E.tidy(ordinary)[-50:])

# --- and the committee keeps its own number ----------------------------------
REPORT = ("Recommendation 1\n"
          "The Committee recommends that the Australian Government develop a ten-year national "
          "strategy, and report on it annually to the Parliament.\n"
          "Additional comments from Ms Kate Chaney MP\n"
          "Recommendation 1\n" + CHANEY)
got = {r["label"]: r for r in E.recommendations_in(REPORT)}
check("the committee's recommendation wins the number it shares with a member's",
      got.get("1", {}).get("recommendation", "").startswith("The Committee recommends"),
      got.get("1", {}).get("recommendation", "")[:70])
check("and the member's own words are not published under it",
      "Job-Ready Graduates" not in got.get("1", {}).get("recommendation", ""),
      got.get("1", {}).get("recommendation", "")[:80])

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for x in FAIL:
        print("  FAILED:", x)
    sys.exit(1)
print("all tests passed")
