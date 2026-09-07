"""harvest_royal_commissions.py — which documents belong to which royal commission.

The committee registers stand on two documents that already exist: the
President's report and the Speaker's schedule. Royal commissions have no such
document, and the Tabled Documents register — which does hold the reports and
the responses — has no reliable field saying which commission a document
belongs to. Three facts from the source test of 6 September 2026 make that
concrete, and each of them is the reason a rule alone will not do:

  * Twelve of the thirteen records that make up the Disability Royal
    Commission's final report are titled by their volume ("Voices of people
    with disability [Final report - volume 1]"), so no title rule reaches them.
  * Three of the five government responses on file are typed "Other" rather
    than "Government response", so no type filter reaches them either.
  * The author field names the commission for fourteen of the twenty records
    typed "Royal commission", is empty for five of them — including both
    Robodebt records — and names a department for the twentieth.

So the mapping is data, not a guess. data/royal_commissions.csv names the
commissions and data/rc_seed.csv says which register ids belong to each and in
what role. This step does three things with that:

  1. Reads the register once and writes what it says about every seeded id —
     title, type, tabling dates, department, files — to data/rc_documents.csv.
     It extracts nothing from any document. No PDF is downloaded.
  2. Writes to data/rc_candidates.csv every register record that is typed
     "Royal commission" or whose title names one of the commissions, and which
     neither the seed nor data/rc_not_ours.csv already holds. That is how a new
     commission, a new volume or a new response arrives: as a row for a person
     to accept into the seed, never as a silent inclusion and never as a silent
     miss. A record a person has looked at and rejected goes in rc_not_ours.csv
     with the reason, so the candidate list empties and the next arrival is
     visible in it. A list that never empties is an alarm nobody reads.
  3. Refuses, loudly, rather than writing a table that is quietly wrong.

    python3 harvest_royal_commissions.py            # read the register, write both files
    python3 harvest_royal_commissions.py --check    # read and report, write nothing

Nothing here is wired into the weekly job yet. It is run by hand until there is
a step that consumes what it writes.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
COMMISSIONS = DATA / "royal_commissions.csv"
SEED = DATA / "rc_seed.csv"
DOCUMENTS = DATA / "rc_documents.csv"
CANDIDATES = DATA / "rc_candidates.csv"
NOT_OURS = DATA / "rc_not_ours.csv"

SEARCH = "https://otd.aph.gov.au/public-api/api/search"
PAGE = "https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{id}"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json",
           "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
           "Origin": "https://www.aph.gov.au", "Referer": "https://www.aph.gov.au/"}

# The roles a seeded document may carry. A role is what the document is to the
# commission, which the register does not record: its own type says "Royal
# commission" for a report and, three times in five, "Other" for a response.
ROLES = {"report", "corrigendum", "response", "statement", "other"}

ROYAL = "Royal commission"
# The register held twenty documents of that type on 6 September 2026, and every
# one of them is a report of one of the four seeded commissions. A sweep that
# suddenly returns far fewer has not found a quiet week; it has failed.
FEWEST_ROYAL_COMMISSION_RECORDS = 15


def register_records() -> list[dict]:
    """Every record in the Tabled Documents register.

    The search endpoint's searchTerm was tested on 6 September 2026 and did not
    filter: passing a term returned the same records as passing none. So nothing
    here relies on it — the whole register is read and matched locally. It is
    about 175 requests and takes a minute and a half. Each record carries its
    own file list, so no second call per document is needed.

    The page loop is driven by the register's own pageCount and checked against
    its own rowCount, and does not stop at the first short page. Stopping at a
    short page is how an earlier version of this sweep read 17,380 records where
    the register held 17,486, without any error: a hundred documents missing and
    nothing to show for it.
    """
    out, page, pages, expected = [], 1, None, None
    while True:
        payload = {"searchTerm": "", "documentCategories": [], "documentTypes": [],
                   "departments": [], "parliamentNumbers": [], "isDisallowable": [],
                   "sortBy": 1, "sortDirection": 1, "pageSize": 100, "currentPage": page,
                   "tableHouse": True, "tableSenate": True}
        req = urllib.request.Request(SEARCH, data=json.dumps(payload).encode(), headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        # A 200 whose shape has changed must not read as an empty register. The
        # responses harvest learned this; the same trap is here.
        if not isinstance(data, dict) or "results" not in data:
            raise SystemExit(
                f"The Tabled Documents search returned a {type(data).__name__} with keys "
                f"{sorted(data)[:8] if isinstance(data, dict) else '—'}; expected an object "
                "with 'results'. The API has changed shape. Stopping rather than reporting "
                "an empty register.")
        results = data.get("results") or []
        if results and not all(isinstance(d, dict) and "id" in d for d in results):
            raise SystemExit("The search returned results without an 'id'. The API has "
                             "changed shape. Stopping.")
        # The field that says what a document is has two names in this API:
        # search results call it "type", a document's own record calls it
        # "typeDescription". Reading the wrong one returns an empty string for
        # every record, which looked exactly like a register holding no royal
        # commission reports at all.
        if results and not any("type" in d for d in results):
            raise SystemExit("The search returned results with no 'type'. The API has "
                             "changed shape. Stopping.")
        if pages is None:
            pages, expected = data.get("pageCount"), data.get("rowCount")
            if not isinstance(pages, int) or not isinstance(expected, int) or pages < 1:
                raise SystemExit(
                    f"The search returned pageCount={pages!r} and rowCount={expected!r}; "
                    "both must be whole numbers or the sweep cannot know when it has read "
                    "the whole register. Stopping.")
        out += results
        if page >= pages:
            break
        page += 1
    seen = {str(d.get("id")) for d in out}
    if len(seen) != expected:
        raise SystemExit(
            f"The register said it holds {expected} records and the sweep read {len(seen)} "
            "distinct ones. Stopping rather than reporting a register with documents "
            "missing from it.")
    return out


def read(path: pathlib.Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def iso(value) -> str:
    return (value or "")[:10]


def tabled(record: dict) -> str:
    return max(iso(record.get("tabled_senate", record.get("tabledSenate"))),
               iso(record.get("tabled_house", record.get("tabledHouse"))))


def title_of(record: dict) -> str:
    return " ".join(str(record.get("title") or "").split())


def write(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def phrases(commissions: list[dict]) -> list[tuple[str, str]]:
    """(commission_id, phrase) for every name a commission is known by."""
    out = []
    for c in commissions:
        for phrase in [c["name"], *(c.get("short_names") or "").split("|")]:
            if phrase.strip():
                out.append((c["commission_id"], phrase.strip()))
    return out


DOCUMENT_FIELDS = ["commission_id", "role", "carries_recommendations", "id", "type",
                   "additional_type", "category", "title", "author", "department",
                   "tabled_senate", "tabled_house", "parliament", "files", "url", "note"]
CANDIDATE_FIELDS = ["id", "type", "title", "tabled_senate", "tabled_house", "reason", "url"]


def row_for(seed_row: dict, d: dict) -> dict:
    return {
        "commission_id": seed_row["commission_id"], "role": seed_row["role"],
        # Which report document sets the recommendations out under their own
        # numbers. The Disability Royal Commission's final report is thirteen
        # documents and puts all 222 in one of them; Robodebt's is one document.
        # It is a fact about the report, checked by the extraction step against
        # the number the report itself states, not a shortcut taken on trust.
        "carries_recommendations": seed_row.get("carries_recommendations") or "",
        "id": str(d.get("id", "")), "type": d.get("type") or "",
        "additional_type": d.get("additionalType") or "",
        "category": d.get("category") or "", "title": title_of(d),
        "author": d.get("author") or "", "department": d.get("department") or "",
        "tabled_senate": iso(d.get("tabledSenate")), "tabled_house": iso(d.get("tabledHouse")),
        "parliament": d.get("parliamentNumber") or "",
        "files": "; ".join(f"{f.get('fileId')}|{f.get('name')}" for f in (d.get("files") or [])),
        "url": PAGE.format(id=seed_row["otd_id"]), "note": seed_row.get("note") or "",
    }


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    commissions = read(COMMISSIONS)
    seed = read(SEED)
    known = {c["commission_id"] for c in commissions}

    bad = [r for r in seed if r["commission_id"] not in known or r["role"] not in ROLES]
    for r in bad:
        print(f"rc_seed.csv: {r['otd_id']} names commission {r['commission_id']!r} "
              f"and role {r['role']!r}", file=sys.stderr)
    if bad:
        print("REFUSING: the seed names a commission or a role that does not exist",
              file=sys.stderr)
        return 1
    ids = [r["otd_id"] for r in seed]
    if len(set(ids)) != len(ids):
        print("REFUSING: rc_seed.csv holds the same document twice", file=sys.stderr)
        return 1

    records = register_records()
    by_id = {str(d.get("id", "")): d for d in records}
    royal = [d for d in records if (d.get("type") or "") == ROYAL]
    if len(royal) < FEWEST_ROYAL_COMMISSION_RECORDS:
        print(f"REFUSING: the register returned {len(royal)} documents typed {ROYAL!r}; "
              f"fewer than {FEWEST_ROYAL_COMMISSION_RECORDS} means the sweep failed, not "
              "that reports have been withdrawn", file=sys.stderr)
        return 1

    rows, wrong = [], []
    for r in seed:
        d = by_id.get(r["otd_id"])
        if d is None:
            wrong.append((r["otd_id"], "the register no longer holds it"))
            continue
        if not (d.get("files") or []):
            wrong.append((r["otd_id"], "the register lists no file for it"))
            continue
        rows.append(row_for(r, d))

    # A seeded document that cannot be read is not a warning. The table would be
    # missing a report or a response and would say nothing about it.
    for otd_id, why in wrong:
        print(f"  OTD {otd_id}: {why}", file=sys.stderr)
    if wrong:
        print(f"REFUSING: {len(wrong)} seeded documents could not be read from the register",
              file=sys.stderr)
        return 1

    rejected = {r["otd_id"]: r.get("reason", "") for r in
                (read(NOT_OURS) if NOT_OURS.exists() else [])}
    both = sorted(set(ids) & set(rejected))
    if both:
        print(f"REFUSING: {', '.join(both)} are in rc_seed.csv and rc_not_ours.csv at once",
              file=sys.stderr)
        return 1
    held = set(ids) | set(rejected)
    named = phrases(commissions)
    candidates = []
    for d in records:
        otd_id = str(d.get("id", ""))
        if otd_id in held:
            continue
        title = title_of(d)
        reason = ""
        if (d.get("type") or "") == ROYAL:
            reason = f"typed {ROYAL} and not in the seed"
        else:
            for commission_id, phrase in named:
                if re.search(re.escape(phrase), title, re.I):
                    reason = f"title names {commission_id}: {phrase!r}"
                    break
        if not reason:
            continue
        candidates.append({
            "id": otd_id, "type": d.get("type") or "", "title": title,
            "tabled_senate": iso(d.get("tabledSenate")),
            "tabled_house": iso(d.get("tabledHouse")),
            "reason": reason, "url": PAGE.format(id=otd_id),
        })
    candidates.sort(key=tabled, reverse=True)

    for c in commissions:
        mine = [r for r in rows if r["commission_id"] == c["commission_id"]]
        counts = [(role, sum(1 for r in mine if r["role"] == role)) for role in sorted(ROLES)]
        print(f"{c['commission_id']}: "
              + ", ".join(f"{n} {role}" for role, n in counts if n))
    unseeded = [c for c in candidates if c["reason"].startswith("typed")]
    print(f"{len(rows)} documents across {len(commissions)} commissions; "
          f"{len(records)} records in the register, {len(royal)} typed {ROYAL}, "
          f"{len(unseeded)} of those not in the seed")
    print(f"{len(candidates)} candidates for a person to accept or reject; "
          f"{len(rejected)} records already rejected in {NOT_OURS.name}")
    for c in candidates[:10]:
        print(f"  {tabled(c)}  OTD {c['id']}  {c['reason']}  {c['title'][:70]}")
    if len(candidates) > 10:
        print(f"  … and {len(candidates) - 10} more in {CANDIDATES.name}")

    if check_only:
        print("--check: nothing written")
        return 0
    write(DOCUMENTS, DOCUMENT_FIELDS, rows)
    write(CANDIDATES, CANDIDATE_FIELDS, candidates)
    print(f"wrote {DOCUMENTS.name} and {CANDIDATES.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
