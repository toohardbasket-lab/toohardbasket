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

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for x in FAIL:
        print("  FAILED:", x)
    sys.exit(1)
print("all tests passed")
