"""Tests for the weekly refresh of the response corpus.

The home page quotes the closure figures. Until this step existed they were
frozen on whatever day the full sweep was last run by hand, and nothing on the
site said so. Now the weekly job classifies whatever is new — which means a
mistake here changes a published figure without anyone typing anything.

These tests use a fake search and a fake harvester, so they run without the
network and without downloading anything. What they pin is the part that can
quietly do damage: the guards, and the merge.
"""
from __future__ import annotations

import csv
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import otd_sweep as S

COLUMNS = ["id", "classification", "template_hits", "notes_recommendation",
           "accept_support_agree", "text_length", "title", "author",
           "department", "tabled_senate", "tabled_house", "parliament",
           "file", "url"]


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'} {name}" + ("" if ok else f"  got {got!r}, want {want!r}"))
    return ok


def write_csv(path: pathlib.Path, ids: list[int], unread: set[int] = frozenset()) -> None:
    """ids in `unread` get a row with an empty classification — what
    harvest_responses.py writes when it sees a response it has not read."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for i in ids:
            row = {c: "" for c in COLUMNS}
            if i in unread:
                row.update(id=i, title=f"Response {i}", tabled_senate="2026-08-01")
                w.writerow(row)
                continue
            row.update(id=i, classification="substantive", template_hits=0,
                       notes_recommendation=0, accept_support_agree=0,
                       text_length=900, title=f"Response {i}",
                       tabled_senate="2026-01-01")
            w.writerow(row)


class Harness:
    """Runs refresh() against a temp CSV, a fixed search result and a fake
    harvester, restoring the module afterwards."""

    def __init__(self, on_file: list[int], listed: list[int],
                 unread: set[int] = frozenset()):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.out = self.dir / "response_documents.csv"
        write_csv(self.out, on_file, unread)
        self.listed = listed
        self.harvested: list[int] = []

    def __enter__(self):
        self._saved = (S.OUT, S.search_all, S.harvest_one)
        S.OUT = self.out
        S.search_all = lambda session, limit: [{"id": i} for i in self.listed]
        def fake(session, doc):
            self.harvested.append(doc["id"])
            row = {c: "" for c in COLUMNS}
            row.update(id=doc["id"], classification="proforma_closure",
                       template_hits=4, notes_recommendation=4,
                       accept_support_agree=0, text_length=500,
                       title=f"Response {doc['id']}", tabled_senate="2026-08-01")
            return row
        S.harvest_one = fake
        return self

    def __exit__(self, *a):
        S.OUT, S.search_all, S.harvest_one = self._saved

    def rows(self) -> list[dict]:
        return list(csv.DictReader(open(self.out, encoding="utf-8")))


def only_new_documents_are_downloaded() -> bool:
    """The expensive part must not re-run on documents already classified.

    A refresh that re-harvested all 658 every week would take twenty minutes,
    re-download a quarter of a gigabyte, and — worse — silently overwrite rows
    whose classification was corrected by hand.
    """
    with Harness(on_file=[1, 2, 3], listed=[1, 2, 3, 4, 5]) as h:
        rc = S.refresh()
        ok = check("refresh succeeded", rc, 0)
        ok &= check("only the unseen ids are harvested", sorted(h.harvested), [4, 5])
        ok &= check("every row is kept", [r["id"] for r in h.rows()],
                    ["1", "2", "3", "4", "5"])
        ok &= check("existing rows are not reclassified",
                    [r["classification"] for r in h.rows()][:3],
                    ["substantive"] * 3)
    return bool(ok)


def a_short_read_is_not_a_shrinking_record() -> bool:
    """If the API returns a fraction of its catalogue, that is a bad read.

    The failure this prevents: OTD answers one page instead of seven, the job
    treats the missing documents as withdrawn, and a corpus of 658 becomes a
    corpus of 90 — with every published rate computed on the remainder.
    """
    with Harness(on_file=list(range(1, 101)), listed=[1, 2, 3]) as h:
        rc = S.refresh()
        ok = check("a short enumeration is refused", rc, 1)
        ok &= check("nothing was harvested", h.harvested, [])
        ok &= check("the file is untouched", len(h.rows()), 100)
    return bool(ok)


def documents_are_never_deleted_by_a_refresh() -> bool:
    """A document OTD stops listing stays on file.

    Removing it would rewrite history: the row is evidence that a response was
    tabled and classified, and a published figure computed from it should not
    change because a database was tidied.
    """
    with Harness(on_file=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                 listed=[1, 2, 3, 4, 5, 6, 7, 8, 9, 11]) as h:
        rc = S.refresh()
        ok = check("refresh succeeded", rc, 0)
        ok &= check("the unlisted document is still on file",
                    "10" in [r["id"] for r in h.rows()], True)
        ok &= check("the new one was added", "11" in [r["id"] for r in h.rows()], True)
    return bool(ok)


def an_implausible_number_of_new_documents_stops_the_run() -> bool:
    """The largest real day on the record is 39 responses.

    A week that adds more than the cap means the search changed shape, not that
    Parliament had a remarkable Tuesday. The run stops for a person to look.
    """
    listed = list(range(1, S.REFRESH_CAP + 52))
    with Harness(on_file=list(range(1, 51)), listed=listed) as h:
        ok = check("over the cap is refused", S.refresh(), 1)
        ok &= check("nothing was harvested", h.harvested, [])
        ok &= check("--force overrides it", S.refresh(force=True), 0)
        ok &= check("and then everything new is harvested",
                    len(h.harvested), len(listed) - 50)
    return bool(ok)


def a_seen_but_unread_document_is_classified() -> bool:
    """harvest_responses.py writes a row the week a response is tabled, with
    an empty classification, so the removal step can act on it at once. This
    step is what fills that in.

    The failure this prevents is silent and permanent: build the known set from
    every id on file, and the first harvested row is treated as already done.
    The classifier then never runs on anything again, the closure figures the
    home page leads with freeze, and nothing errors.
    """
    with Harness(on_file=[1, 2, 3, 4], listed=[1, 2, 3, 4], unread={3, 4}) as h:
        rc = S.refresh()
        ok = check("refresh succeeded", rc, 0)
        ok &= check("the unread rows are the ones downloaded", sorted(h.harvested), [3, 4])
        ok &= check("they are replaced, not duplicated", [r["id"] for r in h.rows()],
                    ["1", "2", "3", "4"])
        ok &= check("and they now carry a classification",
                    [r["classification"] for r in h.rows()],
                    ["substantive", "substantive", "proforma_closure", "proforma_closure"])
    return bool(ok)


def a_new_document_and_an_unread_one_are_both_handled() -> bool:
    """The ordinary week: one response harvested on Tuesday and not yet read,
    one that appeared between the harvest and the sweep."""
    with Harness(on_file=[1, 2, 3], listed=[1, 2, 3, 4], unread={3}) as h:
        ok = check("refresh succeeded", S.refresh(), 0)
        ok &= check("both are downloaded", sorted(h.harvested), [3, 4])
        ok &= check("four rows, no duplicate", [r["id"] for r in h.rows()],
                    ["1", "2", "3", "4"])
    return bool(ok)


def main() -> int:
    results = [only_new_documents_are_downloaded(),
               a_seen_but_unread_document_is_classified(),
               a_new_document_and_an_unread_one_are_both_handled(),
               a_short_read_is_not_a_shrinking_record(),
               documents_are_never_deleted_by_a_refresh(),
               an_implausible_number_of_new_documents_stops_the_run()]
    if all(results):
        print("all tests passed")
        return 0
    print("FAILURES", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
