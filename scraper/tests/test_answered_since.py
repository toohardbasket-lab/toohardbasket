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



def a_hand_checked_entry_names_one_row_and_no_other() -> bool:
    """The hand-checked file may name a report that has no OTD id.

    The Tabled Documents register starts in April 2022, so an older report
    carries no id and an id-keyed entry cannot reach it. Such an entry names
    the report by its title and its tabling date together, and both have to
    match: a title alone would reach a re-tabled report of the same name, and
    a date alone would reach every report tabled that day.
    """
    import csv

    ok = True
    manual = list(csv.DictReader(
        open(A.DATA / "response_report_links_manual.csv", encoding="utf-8-sig")))

    ok &= check("every entry names a report, by id or by title and date",
                all(r.get("report_id") or (r.get("report_title") and r.get("report_tabled"))
                    for r in manual), True)
    ok &= check("every entry says why, and when it was checked",
                all(len(r.get("basis") or "") > 40 and len(r.get("verified_on") or "") == 10
                    for r in manual), True)

    # Each title-keyed entry must name exactly one row of one register. A typo
    # in a copied title is the way this file goes wrong, and it fails silently:
    # the report simply stays on the register.
    rows = []
    for f in ("ledger_v2.csv", "house_ledger.csv"):
        rows += list(csv.DictReader(open(A.DATA / f, encoding="utf-8-sig")))
    for r in manual:
        if not r.get("report_title"):
            continue
        key = (A._norm(r["report_title"]), r["report_tabled"][:10])
        hits = [x for x in rows
                if (A._norm(x.get("title", "")), (x.get("report_tabled") or "")[:10]) == key]
        ok &= check(f"entry for response {r['response_id']} names exactly one register row",
                    len(hits), 1)

    # Both halves of the key are load-bearing.
    by_title = A._by_title()
    for r in manual:
        if not r.get("report_title"):
            continue
        title, tabled = A._norm(r["report_title"]), r["report_tabled"][:10]
        ok &= check("the entry is found by title and date together",
                    r["response_id"] in by_title.get((title, tabled), []), True)
        ok &= check("the same title on another date is not the same report",
                    (title, "1999-01-01") in by_title, False)
        ok &= check("another title on the same date is not the same report",
                    ("a report of some other name", tabled) in by_title, False)
    return bool(ok)


def a_hand_checked_entry_removes_nothing_until_the_response_is_on_file() -> bool:
    """An entry is evidence, not an instruction.

    It names a response by id. Until that response is in the dataset with a
    tabling date, the row it points at stays on the register, because what
    removes a report is a tabled government document and not a line in a file.
    """
    import csv

    find = A.finder(dt.date(2000, 1, 1))
    on_file = {r["response_id"] for r in A.responses_since(dt.date(2000, 1, 1))}
    manual = list(csv.DictReader(
        open(A.DATA / "response_report_links_manual.csv", encoding="utf-8-sig")))

    ok = True
    for r in manual:
        if not r.get("report_title") or r["response_id"] in on_file:
            continue
        rows = []
        for f in ("ledger_v2.csv", "house_ledger.csv"):
            rows += list(csv.DictReader(open(A.DATA / f, encoding="utf-8-sig")))
        key = (A._norm(r["report_title"]), r["report_tabled"][:10])
        for x in rows:
            if (A._norm(x.get("title", "")), (x.get("report_tabled") or "")[:10]) == key:
                ok &= check(f"response {r['response_id']} is not on file, so the row stays",
                            find(x), None)
    return bool(ok)



def the_entry_removes_the_row_once_the_response_is_tabled() -> bool:
    """And when the response is on file, the row does leave.

    The negative test above passes whether the lookup works or was never
    written, so this one puts the named response on file and requires the
    removal, on the stated basis.
    """
    import csv

    manual = [r for r in csv.DictReader(
        open(A.DATA / "response_report_links_manual.csv", encoding="utf-8-sig"))
        if r.get("report_title")]
    if not manual:
        return check("no title-keyed entries to exercise", True, True)

    rows = []
    for f in ("ledger_v2.csv", "house_ledger.csv"):
        rows += list(csv.DictReader(open(A.DATA / f, encoding="utf-8-sig")))

    ok = True
    saved = A.responses_since
    try:
        for r in manual:
            key = (A._norm(r["report_title"]), r["report_tabled"][:10])
            row = next(x for x in rows
                       if (A._norm(x.get("title", "")), (x.get("report_tabled") or "")[:10]) == key)
            stub = {"response_id": r["response_id"], "title": "a title that matches nothing",
                    "tabled": "2026-09-08"}
            A.responses_since = lambda as_at, chamber="", _s=stub: [dict(_s)]
            hit = A.finder(dt.date(2026, 1, 1))(row)
            ok &= check(f"response {r['response_id']} on file removes the row it names",
                        bool(hit), True)
            ok &= check("and says the basis was a hand check",
                        (hit or {}).get("basis"), "checked by hand")
            # the same response must not carry off a different row
            others = [x for x in rows if x is not row and A.finder(dt.date(2026, 1, 1))(x)]
            ok &= check("and removes nothing else", len(others), 0)
    finally:
        A.responses_since = saved
    return bool(ok)


def main() -> int:
    results = [numbered_reports_need_matching_numbers(),
               the_published_list_accounts_for_every_removal(),
               a_chamber_only_answers_its_own_register(),
               the_register_is_current_to_a_date_it_can_state(),
               a_hand_checked_entry_names_one_row_and_no_other(),
               a_hand_checked_entry_removes_nothing_until_the_response_is_on_file(),
               the_entry_removes_the_row_once_the_response_is_tabled()]
    if all(results):
        print("all tests passed")
        return 0
    print("FAILURES", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
