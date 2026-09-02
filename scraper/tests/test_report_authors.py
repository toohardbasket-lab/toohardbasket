"""Tests for whose recommendation gets published under a number.

A dissenting report restarts its numbering at 1, so one report can hold two
"Recommendation 1" — the committee's and a party's. Publishing a party's demand
as a committee's is the worst mistake this project can make: it is the exact
charge a press office would use to call the whole register activist
misinformation, and it would be true.

It happened. Before 2 September, report 16917's recommendations 1 and 2 were
published as the committee's and were the Coalition's, because the reports side
detected dissent only by section heading while the responses side also read the
wording, and because the shortest text won a number regardless of who wrote it.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import extract_report_recommendations as R


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f"  got {got!r}, want {want!r}"))
    return ok


def the_committee_wins_a_contested_number() -> bool:
    """Both claim Recommendation 1. The committee's is the one published."""
    body = "\n".join([
        "Recommendation 1", "",
        "The committee recommends that the Australian Government establish a national "
        "framework for the regulation of the industry, in consultation with the states.",
        "", "Dissenting Report", "", "Recommendation 1", "",
        "Coalition Senators recommend that the bill not be passed.",
    ])
    out = {r["label"]: r for r in R.recommendations_in(body)}
    ok = check("one row for Recommendation 1", len(out), 1)
    ok &= check("it is the committee's", "national framework" in out["1"]["recommendation"], True)
    ok &= check("and it is not attributed to a party", out["1"]["recommended_by"], "")
    return bool(ok)


def a_party_that_owns_its_number_keeps_it_and_is_named() -> bool:
    body = "\n".join([
        "Recommendation 1", "",
        "The committee recommends that the bill be passed with the amendments set out above.",
        "", "Dissenting Report", "", "Recommendation 2", "",
        "Coalition Senators recommend that the bill not be passed in its current form, "
        "and that an exposure draft be released for public consultation.",
    ])
    out = {r["label"]: r for r in R.recommendations_in(body)}
    ok = check("both are published", sorted(out), ["1", "2"])
    ok &= check("the committee's is unattributed", out["1"]["recommended_by"], "")
    ok &= check("the party's names its author", out["2"]["recommended_by"], "Coalition Senators")
    return bool(ok)


def an_author_named_late_is_not_a_dissent() -> bool:
    """A committee recommendation may mention a senator without being theirs."""
    body = "\n".join([
        "Recommendation 3", "",
        "The committee recommends that the Australian Government respond to the matters "
        "raised in evidence by Senator Smith regarding the operation of the scheme, and "
        "report back within six months of the tabling of this report.",
    ])
    out = R.recommendations_in(body)
    return check("mentioning a senator does not make it theirs",
                 out[0]["recommended_by"], "")


def the_signature_block_is_not_part_of_a_recommendation() -> bool:
    body = "\n".join([
        "Recommendation 5", "",
        "The committee recommends that the Senate pass the bill.",
        "Senator Lisa Darmanin Chair Labor Senator for Victoria",
    ])
    out = R.recommendations_in(body)
    text = out[0]["recommendation"] if out else ""
    ok = check("the recommendation is kept", "pass the bill" in text, True)
    ok &= check("the sign-off is not", "Darmanin" in text, False)
    return bool(ok)


def main() -> int:
    results = [the_committee_wins_a_contested_number(),
               a_party_that_owns_its_number_keeps_it_and_is_named(),
               an_author_named_late_is_not_a_dissent(),
               the_signature_block_is_not_part_of_a_recommendation()]
    if all(results):
        print("all tests passed")
        return 0
    print("FAILURES", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
