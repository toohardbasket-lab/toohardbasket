"""What harvest_royal_commissions.py must refuse to do.

The step writes a table of which tabled documents belong to which royal
commission. Everything that could go wrong with it is silent: a page of the
register that comes back short, a seeded report the register no longer holds,
a field that changed its name. None of those raise anything on their own, and
each one produces a table that looks complete and is not. These tests are
about the refusals, and about the one thing the table must never do — miss a
new commission without saying so.
"""
import csv
import io
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import harvest_royal_commissions as H  # noqa: E402

REAL_WALK = H.register_records          # bed() replaces it; the walk tests want it back
PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def record(otd_id, type_="Royal commission", title="A report", files=1, **kw):
    d = {"id": otd_id, "type": type_, "title": title, "category": "Government Document",
         "additionalType": None, "author": "", "department": "", "parliamentNumber": "47",
         "tabledSenate": "2024-01-01T10:00:00+11:00", "tabledHouse": "2024-01-02T00:00:00+11:00",
         "files": [{"fileId": 1, "name": "report.pdf", "size": 1}] * files}
    d.update(kw)
    return d


def bed(commissions, seed, records, rejected=None):
    """A temporary directory holding the seed files, and the register to read."""
    d = pathlib.Path(tempfile.mkdtemp())
    with (d / "royal_commissions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "name", "short_names", "notes"])
        w.writeheader(); w.writerows(commissions)
    with (d / "rc_seed.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "otd_id", "role",
                                          "carries_recommendations", "note"])
        w.writeheader(); w.writerows(seed)
    H.COMMISSIONS, H.SEED = d / "royal_commissions.csv", d / "rc_seed.csv"
    H.DOCUMENTS, H.CANDIDATES = d / "rc_documents.csv", d / "rc_candidates.csv"
    H.NOT_OURS = d / "rc_not_ours.csv"
    if rejected is not None:
        with H.NOT_OURS.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["otd_id", "reason"])
            w.writeheader(); w.writerows(rejected)
    H.register_records = lambda: records
    return d


def rows(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


ONE = [{"commission_id": "robodebt", "name": "Royal Commission into the Robodebt Scheme",
        "short_names": "Robodebt Royal Commission", "notes": ""}]
SEEDED = [{"commission_id": "robodebt", "otd_id": "2743", "role": "report",
           "carries_recommendations": "yes", "note": ""},
          {"commission_id": "robodebt", "otd_id": "4163", "role": "response",
           "carries_recommendations": "", "note": ""}]
# Twenty of these, because the sweep refuses a register holding almost none.
FILLER = [record(9000 + i) for i in range(H.FEWEST_ROYAL_COMMISSION_RECORDS + 1)]
LIVE = [record("2743", title="Royal Commission into the Robodebt Scheme"),
        record("4163", type_="Other", title="Government Response | Royal Commission Into "
               "The Robodebt Scheme November 2023")] + FILLER

# --- the table it writes ----------------------------------------------------
d = bed(ONE, SEEDED, LIVE)
rc = H.main(["harvest_royal_commissions.py"])
got = rows(H.DOCUMENTS)
check("writes a row for each seeded document", rc == 0 and len(got) == 2)
check("keeps the role from the seed, not from the register's type",
      {r["id"]: r["role"] for r in got} == {"2743": "report", "4163": "response"})
check("records the register's own type beside it",
      {r["id"]: r["type"] for r in got} == {"2743": "Royal commission", "4163": "Other"})
check("carries the file list, so nothing has to ask the register twice",
      all(r["files"] == "1|report.pdf" for r in got))
check("carries the flag saying which report document holds the recommendations",
      {r["id"]: r["carries_recommendations"] for r in got} == {"2743": "yes", "4163": ""})
check("a seeded document is never also a candidate",
      not any(c["id"] in {"2743", "4163"} for c in rows(H.CANDIDATES)))

# --- how a new commission arrives -------------------------------------------
d = bed(ONE, SEEDED, LIVE + [record("5555", title="Interim Report of the Royal Commission "
                                    "on Something Else")])
H.main(["harvest_royal_commissions.py"])
new = [c for c in rows(H.CANDIDATES) if c["id"] == "5555"]
check("a new report typed Royal commission becomes a candidate",
      len(new) == 1 and new[0]["reason"].startswith("typed Royal commission"))
check("the candidate is not written into the table",
      "5555" not in {r["id"] for r in rows(H.DOCUMENTS)})

d = bed(ONE, SEEDED, LIVE + [record("5556", type_="Other",
                                    title="Government Response to the Robodebt Royal "
                                          "Commission, second instalment")])
H.main(["harvest_royal_commissions.py"])
new = [c for c in rows(H.CANDIDATES) if c["id"] == "5556"]
check("a document whose title names a commission becomes a candidate, with the phrase",
      len(new) == 1 and "Robodebt Royal Commission" in new[0]["reason"])

d = bed(ONE, SEEDED, LIVE + [record("5557", type_="Other", title="Something else entirely")])
H.main(["harvest_royal_commissions.py"])
check("a document that names no commission is not a candidate",
      "5557" not in {c["id"] for c in rows(H.CANDIDATES)})

# A commission this index has never heard of. The type is no help — the Aged
# Care commission's final report is on the register typed "Other", as volumes
# presented by a Member — so the title has to be enough, or a fifth commission
# could only ever be found because somebody thought to look for it.
d = bed(ONE, SEEDED, LIVE + [record("5559", type_="Other", title="Final report of the Royal "
        "Commission into Something Nobody Here Has Heard Of")])
H.main(["harvest_royal_commissions.py"])
unheld = [c for c in rows(H.CANDIDATES) if c["id"] == "5559"]
check("a commission the index does not hold still reaches the candidate list",
      len(unheld) == 1 and "does not hold" in unheld[0]["reason"])

# --- what a person has already rejected -------------------------------------
NOISE = record("5558", type_="Other", title="Return to an order about the Robodebt Royal "
               "Commission")
d = bed(ONE, SEEDED, LIVE + [NOISE])
H.main(["harvest_royal_commissions.py"])
check("without a rejection file, a title match is a candidate",
      "5558" in {c["id"] for c in rows(H.CANDIDATES)})

before = len(rows(H.CANDIDATES))
d = bed(ONE, SEEDED, LIVE + [NOISE], rejected=[{"otd_id": "5558", "reason": "an order, not "
                                                "a document of the commission"}])
H.main(["harvest_royal_commissions.py"])
after = rows(H.CANDIDATES)
check("a rejected record stops being a candidate, so the list can empty",
      "5558" not in {c["id"] for c in after} and len(after) == before - 1)

d = bed(ONE, SEEDED, LIVE, rejected=[{"otd_id": "2743", "reason": "no"}])
check("a document both seeded and rejected: refuses rather than picking one",
      H.main(["harvest_royal_commissions.py"]) == 1)

# --- the refusals -----------------------------------------------------------
d = bed(ONE, SEEDED + [{"commission_id": "nobody", "otd_id": "1", "role": "report", "note": ""}],
        LIVE)
check("a seed naming a commission that does not exist: refuses, writes nothing",
      H.main(["harvest_royal_commissions.py"]) == 1 and not H.DOCUMENTS.exists())

d = bed(ONE, SEEDED + [{"commission_id": "robodebt", "otd_id": "1", "role": "verdict",
                        "note": ""}], LIVE)
check("a seed naming a role that does not exist: refuses",
      H.main(["harvest_royal_commissions.py"]) == 1 and not H.DOCUMENTS.exists())

d = bed(ONE, SEEDED + [{"commission_id": "robodebt", "otd_id": "2743", "role": "other",
                        "note": ""}], LIVE)
check("the same document seeded twice: refuses",
      H.main(["harvest_royal_commissions.py"]) == 1 and not H.DOCUMENTS.exists())

d = bed(ONE, SEEDED, [r for r in LIVE if str(r["id"]) != "2743"])
check("a seeded report the register no longer holds: refuses rather than dropping it",
      H.main(["harvest_royal_commissions.py"]) == 1 and not H.DOCUMENTS.exists())

d = bed(ONE, SEEDED, [record("2743", files=0), LIVE[1]] + FILLER)
check("a seeded document with no file listed: refuses",
      H.main(["harvest_royal_commissions.py"]) == 1 and not H.DOCUMENTS.exists())

d = bed(ONE, SEEDED, [LIVE[0], LIVE[1]])
check("a register holding almost no royal commission reports: refuses, because that is a "
      "failed sweep and not a withdrawn report",
      H.main(["harvest_royal_commissions.py"]) == 1 and not H.DOCUMENTS.exists())

# The bug that started this: search results call the field "type" and a
# document's own record calls it "typeDescription". Reading the wrong one gave
# every record an empty type, which read as a register with no reports in it.
d = bed(ONE, SEEDED, [dict(r, typeDescription=r.pop("type")) for r in
                      [record("2743"), record("4163")] + [record(9000 + i) for i in range(20)]])
check("results carrying only the old field name: refuses rather than seeing no reports",
      H.main(["harvest_royal_commissions.py"]) == 1)

# --- the walk itself --------------------------------------------------------
def fake_register(pages, row_count, shape=None):
    """Serve `pages` pages to register_records() without a network."""
    H.register_records = REAL_WALK
    calls = {"n": 0}

    def urlopen(req, timeout=None):                      # noqa: ARG001
        page = json.loads(req.data)["currentPage"]
        calls["n"] += 1
        body = shape if shape is not None else {
            "results": pages[page - 1], "pageCount": len(pages), "rowCount": row_count}
        return io.BytesIO(json.dumps(body).encode())
    H.urllib.request.urlopen = urlopen
    return calls


full = [record(1000 + i) for i in range(100)]
short = [record(2000 + i) for i in range(40)]
last = [record(3000 + i) for i in range(60)]
calls = fake_register([full, short, last], 200)
try:
    got = H.register_records()
    ok = len(got) == 200 and calls["n"] == 3
except SystemExit:
    ok = False
check("a short page in the middle does not end the walk", ok)

calls = fake_register([full, short], 200)
try:
    H.register_records(); ok = False
except SystemExit:
    ok = True
check("reading fewer records than the register says it holds: refuses", ok)

# A live register moves under a reader: a document tabled while the sweep is
# running re-sorts the pages and a record is read twice or not at all. That is
# an ordinary sitting Tuesday, and an alarm that fires on it is one somebody
# learns to close without reading.
nearly = [record(4000 + i) for i in range(100)], [record(5000 + i) for i in range(98)]
calls = fake_register(list(nearly), 200)
try:
    got = H.register_records()
    ok = len(got) == 198
except SystemExit:
    ok = False
check("a document tabled while the sweep runs is reported, not refused", ok)

wide = [record(6000 + i) for i in range(100)], [record(7000 + i) for i in range(94)]
calls = fake_register(list(wide), 200)
try:
    H.register_records(); ok = False
except SystemExit:
    ok = True
check("and a gap wider than that is still a gap", ok)

fake_register([[]], 0, shape={"documents": []})
try:
    H.register_records(); ok = False
except SystemExit:
    ok = True
check("a 200 with no 'results' at all: refuses rather than reading an empty register", ok)

fake_register([[]], 1, shape={"results": [{"title": "no id here"}], "pageCount": 1, "rowCount": 1})
try:
    H.register_records(); ok = False
except SystemExit:
    ok = True
check("results without an id: refuses", ok)

fake_register([[]], 1, shape={"results": [full[0]], "pageCount": None, "rowCount": None})
try:
    H.register_records(); ok = False
except SystemExit:
    ok = True
check("no page count to walk by: refuses rather than guessing when to stop", ok)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
