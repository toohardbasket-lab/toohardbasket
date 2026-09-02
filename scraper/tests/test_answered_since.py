"""Tests for the step that takes a report off a public register.

This is the one piece of code in the project that removes a row from a
register, so the cost of it being wrong is asymmetric: a report wrongly kept is
a stale row, and a report wrongly removed is a report the government has not
answered disappearing from a site whose whole purpose is to list it.

The cases below are the three ways it was shown to be able to go wrong, each
written as a test so it cannot come back.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import answered_since as A


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f"  got {got!r}, want {want!r}"))
    return ok


def numbered_reports_need_matching_numbers() -> bool:
    """"Report 505" and "Report 506" differ by one character.

    Tokens of three characters or fewer are dropped before matching, so the two
    titles reduce to the same words. Without the number rule a response to one
    removes the other.
    """
    ok = True
    ok &= check("505 != 506", A._numbers("Report 505—Inquiry into program design")
                == A._numbers("Report 506—Inquiry into program design"), False)
    ok &= check("505 == 505", A._numbers("Report 505—Inquiry into program design")
                == A._numbers("Government response to Report 505"), True)
    ok &= check("no number in either", A._numbers("Wage theft") == A._numbers("Wage theft"), True)
    ok &= check("'Report No. 4' reads as 4", A._numbers("Report No. 4 of 2026"), {"4"})
    return bool(ok)


def a_chamber_only_answers_its_own_register() -> bool:
    """A response tabled in one chamber does not discharge the other's claim.

    The President reports on responses tabled in the Senate. Taking the later
    of the two tabling dates would remove a joint report from his register on
    the strength of a House tabling he has not recorded.
    """
    as_at = dt.date(2026, 6, 30)
    senate = {r["response_id"] for r in A.responses_since(as_at, "senate")}
    house = {r["response_id"] for r in A.responses_since(as_at, "house")}
    either = {r["response_id"] for r in A.responses_since(as_at)}
    ok = check("neither chamber sees more than both", senate <= either and house <= either, True)
    # 17526, the Thriving Kids response, was tabled in the House only.
    ok &= check("a House-only response is not on the Senate's list",
                "17526" in house and "17526" not in senate, True)
    return bool(ok)


def the_register_is_current_to_a_date_it_can_state() -> bool:
    to = A.checked_to()
    return check("checked_to is a date", bool(to) and len(to) == 10 and to[4] == "-", True)


def the_published_list_accounts_for_every_removal() -> bool:
    """The page's count and the page's list must come from the same set.

    Two things take a report off the Senate register: the Senate's own record
    of responses, applied by the builder, and the Tabled Documents register,
    applied by the removal step. The page reported the sum and listed only the
    second, so it said sixteen and showed two. A departmental officer counting
    the difference has nowhere to look for the other fourteen.
    """
    import csv
    import tempfile
    saved = A.DATA
    A.DATA = pathlib.Path(tempfile.mkdtemp())
    try:
        by_document = [{"report_tabled": "2026-01-29", "committee": "Defence",
                        "title": "Annual report 2023-24", "report_otd_id": "14745",
                        "response_id": "17516", "response_tabled": "2026-08-13",
                        "response_title": "Government response", "removal_basis": "OTD link"}]
        by_register = [{"report_tabled": "2023-07-12", "committee": "Economics",
                        "title": "Corporate Insolvency in Australia", "report_otd_id": "",
                        "response_id": "", "response_tabled": "2026-08-11",
                        "response_title": "", "removal_basis": "Senate response register"},
                       # the same report the document link already accounts for,
                       # spelled the way the other source spells it
                       {"report_tabled": "2026-01-29", "committee": "Defence",
                        "title": "annual report 2023-24 ", "report_otd_id": "",
                        "response_id": "", "response_tabled": "2026-08-13",
                        "response_title": "", "removal_basis": "Senate response register"}]
        A.report(by_document, "senate", by_register)
        rows = list(csv.DictReader(open(A.DATA / "answered_since_senate.csv", encoding="utf-8")))
        ok = check("both sources are published", len(rows), 2)
        ok &= check("a report counted twice is listed once",
                    sorted(r["title"] for r in rows),
                    ["Annual report 2023-24", "Corporate Insolvency in Australia"])
        ok &= check("each row says what settled it",
                    sorted(r["removal_basis"] for r in rows),
                    ["OTD link", "Senate response register"])

        # A row with no Tabled Documents id must still be publishable.
        A.report([], "senate", by_register)
        rows = list(csv.DictReader(open(A.DATA / "answered_since_senate.csv", encoding="utf-8")))
        ok &= check("register-only removals publish on their own", len(rows), 2)
        return bool(ok)
    finally:
        A.DATA = saved


def main() -> int:
    results = [numbered_reports_need_matching_numbers(),
               the_published_list_accounts_for_every_removal(),
               a_chamber_only_answers_its_own_register(),
               the_register_is_current_to_a_date_it_can_state()]
    if all(results):
        print("all tests passed")
        return 0
    print("FAILURES", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
