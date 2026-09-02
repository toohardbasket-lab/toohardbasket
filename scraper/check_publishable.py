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


def main() -> int:
    responses = rows("response_documents.csv")
    if responses:
        every_response_has_been_read(responses)
        the_closure_columns_add_up(responses)
    the_registers_are_not_empty()
    the_removals_are_counted_and_listed_alike()
    the_recommendation_index_is_populated()

    if failures:
        print(f"\n{len(failures)} check(s) failed — not fit to publish", file=sys.stderr)
        return 1
    print("\nfit to publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
