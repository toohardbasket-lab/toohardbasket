"""check_publishable.py — the last gate before the weekly job commits.

Every other gate in the job tests a step. This one tests the dataset the site
is about to be built from, because the failures that matter most here are the
ones that do not raise: a figure that quietly stops moving, a column that stops
adding up, a file that is written but never filled in. A job that fails loudly
is a good week; a job that succeeds while publishing a frozen number is the
thing this project cannot afford.

Each check is a published claim. If a check fails, the run stops before the
commit and the failure step opens an issue.

Usage: python check_publishable.py
"""
from __future__ import annotations

import csv
import pathlib
import sys
from collections import Counter

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

failures: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)
    print(f"FAIL  {msg}")


def ok(msg: str) -> None:
    print(f"ok    {msg}")


def rows(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        fail(f"{name} does not exist")
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def every_response_has_been_read(responses: list[dict]) -> None:
    """A row with no classification is a document seen but not read.

    harvest_responses.py writes those deliberately, so the removal step can
    take an answered report off a register the same week. otd_sweep --refresh
    fills them in. If any survive to here, the classifier did not run on them,
    and the closure counts on the home page are computed over a corpus smaller
    than the one the site says it holds.
    """
    unread = [r["id"] for r in responses if not (r.get("classification") or "").strip()]
    if unread:
        fail(f"{len(unread)} response document(s) carry no classification "
             f"({', '.join(unread[:8])}). The closure figures exclude them "
             "while the corpus count includes them.")
    else:
        ok(f"all {len(responses)} response documents are classified")


def the_closure_columns_add_up(responses: list[dict]) -> None:
    """The home page prints a total and a breakdown. They must be the same set.

    They stopped being the same set when a third closure class was added:
    the breakdown summed proforma and partial closures while the headline
    counted only the first, so the column totalled 265 against a published 260.
    """
    c = Counter((r.get("classification") or "").strip() for r in responses)
    closure = {k: v for k, v in c.items() if "closure" in k}
    print(f"      classifications: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
    if not closure:
        fail("no closure classifications found at all")
        return
    ok("closure classes: " + ", ".join(f"{k}={v}" for k, v in sorted(closure.items()))
       + f"  (total {sum(closure.values())})")


def the_registers_are_not_empty() -> None:
    for name in ("ledger_v2.csv", "house_ledger.csv"):
        r = rows(name)
        if not r:
            continue
        if len(r) < 10:
            fail(f"{name} has only {len(r)} rows — that is not a register")
        else:
            ok(f"{name}: {len(r)} reports")


def the_recommendation_index_is_populated() -> None:
    recs = rows("recommendations.csv")
    if not recs:
        return
    if len(recs) < 2000:
        fail(f"recommendations.csv has {len(recs)} rows; the index has not been "
             "below 2,000 since it was built. Something dropped a source.")
        return
    docs = len({r.get("source_id") or r.get("document_id") or "" for r in recs})
    ok(f"recommendations.csv: {len(recs)} recommendations from {docs} documents")


def the_coverage_file_agrees_with_the_index() -> None:
    """coverage.csv and recommendation_positions.csv are derived from
    recommendations.csv by coverage.py. If the index was rebuilt and coverage
    was not, the search page would label rows from one build with states from
    another, and the responses page would publish a rate for a corpus that no
    longer exists."""
    recs = rows("recommendations.csv")
    if not recs:
        return
    pos = rows("recommendation_positions.csv")
    if not pos:
        fail("recommendation_positions.csv is missing or empty — run coverage.py after the index")
        return
    if len(pos) != len(recs):
        fail(f"recommendation_positions.csv has {len(pos)} rows; recommendations.csv has "
             f"{len(recs)} — coverage.py has not been run on this index")
        return
    cov = rows("coverage.csv")
    stated = sum(int(r["position_stated"] or 0) for r in cov)
    counted = sum(1 for r in pos if r["state"] == "position")
    if stated != counted:
        fail(f"coverage.csv counts {stated} stated positions; recommendation_positions.csv "
             f"has {counted}")
        return
    ok(f"coverage: {len(cov)} responses, {counted} recommendations with a stated position, "
       f"one state per index row")


def the_removals_are_counted_and_listed_alike() -> None:
    """Each register states how many reports it removed and lists them.

    They came from different places — the count from the register meta, the
    list from the removals file — and for a while they disagreed: the Senate
    page said sixteen removals and showed two, because only one of the two
    sources that remove a report wrote to the file the page reads. A reader
    counting the difference is exactly the reader this site is built for.
    """
    import json
    for reg, meta_name in (("senate", "ledger_meta.json"),
                           ("house", "house_ledger_meta.json")):
        meta_path = DATA / meta_name
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        claimed = int(meta.get("answered_since_schedule") or 0)
        listed = len([r for r in rows(f"answered_since_{reg}.csv") if r.get("response_tabled")])
        if claimed != listed:
            fail(f"{reg}: the page will say {claimed} report(s) were answered since the "
                 f"schedule and list {listed}. Both come from this dataset; they must "
                 "be the same set.")
        else:
            ok(f"{reg}: {claimed} removal(s) counted, {listed} listed")


def nothing_has_gone_backwards() -> None:
    """Compare this build against the one in the repository.

    The parser tests run on fixtures and the validator checks two historical
    totals. Neither would notice a StatsNet or Tabled Documents layout change
    that degraded the read rather than breaking it — half the rows parsed, a
    date column landing empty — because the result is a smaller, perfectly
    well-formed dataset. What that looks like from outside is the backlog
    falling. The previous commit is the only baseline that is always to hand,
    and it is free.
    """
    import io
    import subprocess
    for name, key in (("response_documents.csv", "id"),
                      ("responses.csv", None),
                      ("recommendations.csv", None)):
        try:
            old_text = subprocess.run(
                ["git", "show", f"HEAD:scraper/data/{name}"],
                cwd=HERE.parent, capture_output=True, text=True, check=True).stdout
        except Exception:
            continue                      # first commit, or not a checkout
        if not old_text.strip():
            continue
        before = list(csv.DictReader(io.StringIO(old_text)))
        after = rows(name)
        if len(after) < len(before):
            fail(f"{name}: {len(before)} rows in the repository, {len(after)} in this "
                 "build. A dataset that shrinks is a read that went wrong, not a record "
                 "that got smaller.")
        else:
            ok(f"{name}: {len(before)} → {len(after)} rows")

    # The newest response on file must never move backwards either: that is the
    # date both registers publish as how current they are.
    after = rows("response_documents.csv")
    if after:
        newest = max(max(r.get("tabled_senate") or "", r.get("tabled_house") or "")
                     for r in after)
        ok(f"newest response on file: {newest or 'none'}")


def every_report_link_is_the_committees_own() -> None:
    """A register row linked to the Tabled Documents index must be linked to a
    document of its own committee. Three rows once linked to Public Works
    Committee reports tabled the same day as the report they named, and the
    index then published Public Works recommendations under two select
    committees' names. The matcher no longer does that; this makes sure nothing
    else does either, before the rows are published."""
    from link_reports import committees_agree
    index = {r["id"]: r for r in rows("committee_reports.csv")}
    wrong = []
    for name in ("ledger_v2.csv", "house_ledger.csv"):
        for r in rows(name):
            doc = index.get(r.get("report_otd_id") or "")
            if doc and not committees_agree(r.get("committee") or "", doc.get("committee") or ""):
                wrong.append(f"{name}: {r['title'][:50]!r} ({r['committee']}) -> OTD {doc['id']} "
                             f"by {doc['committee']}")
    if wrong:
        for w in wrong:
            fail(f"report link names another committee's document — {w}")
    else:
        ok("every register row's report link is a document of its own committee")


def main() -> int:
    responses = rows("response_documents.csv")
    if responses:
        every_response_has_been_read(responses)
        the_closure_columns_add_up(responses)
    the_registers_are_not_empty()
    every_report_link_is_the_committees_own()
    the_removals_are_counted_and_listed_alike()
    the_recommendation_index_is_populated()
    the_coverage_file_agrees_with_the_index()
    nothing_has_gone_backwards()

    if failures:
        print(f"\n{len(failures)} check(s) failed — not fit to publish", file=sys.stderr)
        return 1
    print("\nfit to publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
