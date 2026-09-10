"""Tests for the link between a government response and the report it answers.

The site puts that link in front of readers: on the search page a response
that sets out no recommendations offers "the report it answers", and the claim
attached to it is that the government closed or answered that report. A link
pointing at the wrong document makes a checkable claim uncheckable, which is
worse than making no claim at all.

Two pairings in the file did exactly that. OTD's own documentLinks tied
response 10128 to document 11618, which is the same government answer tabled a
second time. The title search tied response 9463 to itself, scoring 0.83,
because a response quotes the title of the report it answers and so scores
against its own text. Neither is exotic: every route into the file can pair a
response with a response, because nothing was checking what the target was.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import link_responses_to_reports as L

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def rd(name: str) -> list[dict]:
    with (DATA / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


responses = rd("response_documents.csv")
ids = {r["id"] for r in responses}
pairs = rd("response_reports.csv")

# --- the rule itself ---------------------------------------------------------
check("a response cannot answer itself",
      bool(L.not_a_report({"response_id": "42", "report_id": "42", "report_title": "A report"}, ids)))
check("a response cannot answer another response, by id",
      bool(L.not_a_report({"response_id": "42", "report_id": next(iter(ids)),
                           "report_title": "A report"}, ids)))
check("a response cannot answer a document titled as a government response",
      bool(L.not_a_report({"response_id": "42", "report_id": "999999",
                           "report_title": "Australian Government response to the X Committee"}, ids)))
check("an ordinary report is allowed",
      not L.not_a_report({"response_id": "42", "report_id": "999999",
                          "report_title": "Inquiry into the Department of Defence Annual Report"}, ids))
check("no pairing at all is allowed",
      not L.not_a_report({"response_id": "42", "report_id": "", "report_title": ""}, ids))

# --- and the file obeys it ---------------------------------------------------
self_paired = [r for r in pairs if r["report_id"] and r["report_id"] == r["response_id"]]
check("no response in the file is paired with itself", not self_paired,
      ", ".join(r["response_id"] for r in self_paired[:5]))

to_a_response = [r for r in pairs if r["report_id"] and r["report_id"] in ids]
check("no response in the file is paired with another response", not to_a_response,
      ", ".join(f"{r['response_id']}->{r['report_id']}" for r in to_a_response[:5]))

refused = [r for r in pairs if r["report_id"] and L.not_a_report(r, ids)]
check("every pairing that carries a link survives the check", not refused,
      ", ".join(f"{r['response_id']}->{r['report_id']}" for r in refused[:5]))

# --- a link the site shows must go somewhere -------------------------------
linked = [r for r in pairs if (r["report_url"] or "").strip()]
check("every linked pairing names a report id", all(r["report_id"] for r in linked))
check("every linked pairing points at aph.gov.au",
      all(r["report_url"].startswith("https://www.aph.gov.au/") for r in linked))
check("a pairing with no report carries no url",
      all(not (r["report_url"] or "").strip() for r in pairs if not r["report_id"]))

# --- the accept test, against real search results ----------------------------
# Twelve responses the pairing could not settle, and two it should still refuse.
# The results are what otd.aph.gov.au actually returned on 9 September 2026,
# kept in tests/fixtures so this runs offline and cannot quietly change when the
# API's ranking does. Each of the twelve was checked by hand against the
# committee's own record: one candidate, exact title, right committee, report
# tabled before the response.
FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "pairing_cases_2026-09-09.json"
cases = json.loads(FIX.read_text(encoding="utf-8"))["cases"]
wanted = [c for c in cases if c["expect_report_id"]]
refused = [c for c in cases if not c["expect_report_id"]]

check("the fixture still holds every case", len(wanted) == 12 and len(refused) == 2,
      f"{len(wanted)} wanted, {len(refused)} refused")

for c in wanted:
    hit, score = L.best(c["results"], c["query"], c["before"])
    got = str(hit["id"]) if hit else ""
    check(f"response {c['response_id']} pairs with report {c['expect_report_id']}",
          got == c["expect_report_id"] and score >= 0.8, f"got {got or 'nothing'} at {score:.2f}")

# Refused means "not accepted at the bar the pipeline uses" — best() reports its
# top candidate and its score, and the caller takes it only at 0.8 or better.
for c in refused:
    hit, score = L.best(c["results"], c["query"], c["before"])
    check(f"response {c['response_id']} is still refused — {c['why'][:60]}",
          hit is None or score < 0.8,
          f"paired with {hit['id'] if hit else ''} at {score:.2f}")

# --- what the trailing-date rule may and may not touch ------------------------
check("a trailing month and year is ignored",
      L.strip_qualifier("Project known as the Iron Boomerang [August 2023]")
      == "Project known as the Iron Boomerang")
check("a trailing year alone is ignored",
      L.strip_qualifier("Eighty Seventh Annual Report (2023)") == "Eighty Seventh Annual Report")
check("[Provisions] is part of the title and stays",
      L.strip_qualifier("Fair Work Legislation Amendment Bill 2023 [Provisions]")
      == "Fair Work Legislation Amendment Bill 2023 [Provisions]")
check("a year inside the title stays",
      L.strip_qualifier("Conduct of the 2022 federal election")
      == "Conduct of the 2022 federal election")

# The year test reads the raw titles, so stripping the qualifier for the score
# cannot let one year's report answer another year's.
check("the year test is unaffected by the stripping",
      not L.agree("Annual report 2021-22", "Annual report 2022-23 [October 2023]"))
check("an interim report does not answer a final one",
      not L.agree("Inquiry into X — Final Report", "Inquiry into X [Interim report]"))

# --- a short title has to be unique, not merely exact -------------------------
def doc(i, title, tabled="2023-01-01"):
    return {"id": i, "title": title, "author": "A Committee", "department": "A Committee",
            "tabledSenate": tabled, "tabledHouse": ""}

two = [doc(1, "Corporate insolvency in Australia"), doc(2, "Corporate insolvency in Australia")]
hit, _ = L.best(two, "Corporate insolvency in Australia", "2026-01-01")
check("a two-word title with two exact candidates pairs with neither", hit is None,
      f"paired with {(hit or {}).get('id')}")

one = [doc(1, "Corporate insolvency in Australia"), doc(2, "Corporate plans of Commonwealth entities")]
hit, score = L.best(one, "Corporate insolvency in Australia", "2026-01-01")
check("a two-word title with one exact candidate pairs with it",
      (hit or {}).get("id") == 1, f"got {(hit or {}).get('id')} at {score:.2f}")

near = [doc(1, "Corporate insolvency in Australia and New Zealand")]
hit, score = L.best(near, "Corporate insolvency in Australia", "2026-01-01")
check("a two-word title that is only nearly exact pairs with nothing", hit is None,
      f"paired at {score:.2f}")

# --- the hand-checked file has two shapes, and this step can only use one -----
# An entry may name the report by its OTD id, or, for a report older than the
# Tabled Documents register, by its exact title and tabling date. Only the first
# is usable here. Taking the second anyway built a link ending in nothing —
# ".../Tabled_Documents/" — on a row with no report id, and the invariants above
# caught it in the watcher before it reached the site.
manual = list(csv.DictReader(
    open(DATA / "response_report_links_manual.csv", encoding="utf-8-sig")))
usable = L.manual_links()

by_title = [r for r in manual if not (r.get("report_id") or "").strip()]
check("the hand-checked file holds an entry with no report id",
      bool(by_title),
      "every entry names an id, so this suite cannot detect the fault it exists for")
check("an entry with no report id is not used to build a link",
      all(r["response_id"] not in usable for r in by_title),
      ", ".join(r["response_id"] for r in by_title if r["response_id"] in usable))
check("every entry that names an id is used",
      all(r["response_id"] in usable
          for r in manual if (r.get("report_id") or "").strip()))
check("no usable entry carries an empty id", all(v for v in usable.values()))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for x in FAIL:
        print("  FAILED:", x)
    sys.exit(1)
print("all tests passed")
