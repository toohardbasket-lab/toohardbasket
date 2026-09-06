"""What digest.py must do, and must not do.

The digest exists to be read. Its failure modes are being noisy when nothing
happened, describing the same response twice, estimating a wait it cannot
know, and taking the build down. All four are pinned here.
"""
import csv
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import digest as D  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


RESP_COLS = ["id", "classification", "template_hits", "title", "author",
             "department", "tabled_senate", "tabled_house", "url"]


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})


def setup(responses, reports=(), coverage=(), state=None):
    d = pathlib.Path(tempfile.mkdtemp())
    D.RESPONSES = d / "response_documents.csv"
    D.REPORTS = d / "response_reports.csv"
    D.COVERAGE = d / "coverage.csv"
    D.STATE = d / "digested_responses.json"
    D.NOTE = d / "note.md"
    write_csv(D.RESPONSES, RESP_COLS, responses)
    write_csv(D.REPORTS, ["response_id", "report_id", "report_title",
                          "report_tabled", "report_url", "basis"], reports)
    write_csv(D.COVERAGE, ["response_id", "recommendations", "position_stated",
                           "committee"], coverage)
    if state is not None:
        D.STATE.write_text(json.dumps(state), encoding="utf-8")
    return d


def run(argv=()):
    rc = D.main(["digest.py", *argv])
    note = D.NOTE.read_text(encoding="utf-8") if D.NOTE.exists() else None
    st = json.loads(D.STATE.read_text(encoding="utf-8")) if D.STATE.exists() else None
    return rc, note, st


R1 = {"id": "1", "classification": "proforma_closure", "template_hits": "18",
      "title": "Response to the children overboard inquiry", "department": "PM&C",
      "tabled_senate": "2026-04-01", "url": "https://aph.gov.au/1"}
R2 = {"id": "2", "classification": "substantive", "template_hits": "0",
      "title": "Response to the gambling inquiry", "department": "DSS",
      "tabled_house": "2026-05-12", "url": "https://aph.gov.au/2"}

# --- quiet when it should be quiet -----------------------------------------
setup([R1, R2], state={"seen": ["1", "2"]})
rc, note, st = run()
check("everything already described: silent", rc == 0 and note is None)

setup([])
rc, note, st = run()
check("no responses file rows at all: silent", rc == 0 and note is None)

setup([{**R1, "tabled_senate": "", "tabled_house": ""}], state={"seen": []})
rc, note, st = run()
check("a response with no tabling date is skipped: silent", rc == 0 and note is None)

# --- speaks once, and records what it said ---------------------------------
setup([R1, R2], state={"seen": ["1"]})
rc, note, st = run()
check("one new response: raises", rc == 0 and note is not None)
check("  describes only the new one", note is not None
      and "gambling" in note and "children overboard" not in note)
check("  records it so it is not described again", set(st["seen"]) == {"1", "2"})
check("  keeps the response already recorded", "1" in st["seen"])

D.NOTE.unlink()                       # the workflow only acts on a note this run wrote
rc2, note2, _ = run()
check("running again straight after: silent", rc2 == 0 and note2 is None)

# --- the wait, and refusing to invent one ----------------------------------
setup([R1], reports=[{"response_id": "1", "report_tabled": "2002-10-23",
                      "report_title": "A certain maritime incident"}],
      state={"seen": []})
rc, note, st = run()
check("a paired response reports the wait in words",
      note is not None and "23 years" in note)
check("  and in days", note is not None and "8,561 days" in note)
check("  and past the three-month rule", note is not None
      and "days past the three-month rule" in note)
check("  and names the report answered",
      note is not None and "A certain maritime incident" in note)

setup([R1], reports=[{"response_id": "1", "report_tabled": ""}], state={"seen": []})
rc, note, st = run()
check("an unpaired response says so rather than estimating",
      note is not None and "could not be identified" in note
      and "no wait is shown" in note)
check("  and shows no day count", note is not None and "days past" not in note)

# --- the comparison is against the whole file, not the new rows ------------
older = [{"id": str(100 + i), "classification": "substantive", "template_hits": "0",
          "title": f"Old {i}", "tabled_senate": "2024-01-01",
          "url": f"https://aph.gov.au/{100+i}"} for i in range(4)]
reports = [{"response_id": str(100 + i), "report_tabled": "2023-12-01"}
           for i in range(4)]
reports.append({"response_id": "1", "report_tabled": "2002-10-23"})
setup([R1] + older, reports=reports, state={"seen": [str(100 + i) for i in range(4)]})
rc, note, st = run()
check("the percentile counts every paired response on file, not just the new one",
      note is not None and "of the 5 responses on file" in note)
check("  a 23-year wait beats the four short ones",
      note is not None and "longer than 80%" in note)

# --- what else was tabled that day -----------------------------------------
same_day = [{"id": str(200 + i), "classification": "proforma_closure",
             "template_hits": "1", "title": f"Batch {i}",
             "tabled_senate": "2026-03-19", "url": "u"} for i in range(3)]
setup(same_day, state={"seen": ["201", "202"]})
rc, note, st = run()
check("a response tabled alongside others says how many",
      note is not None and "One of 3 responses tabled that day" in note)
check("  and how many of them were closures", note is not None and "3 of them closures" in note)

setup([R2], state={"seen": []})
rc, note, st = run()
check("a lone response says it was alone",
      note is not None and "only response tabled that day" in note)

# --- coverage detail --------------------------------------------------------
setup([R1], coverage=[{"response_id": "1", "recommendations": "18",
                       "position_stated": "0", "committee": "Select Committee"}],
      state={"seen": []})
rc, note, st = run()
check("recommendations and stated positions are reported",
      note is not None and "18 recommendations indexed" in note
      and "position on 0 of them (0%)" in note)
check("  and the committee named", note is not None and "Select Committee" in note)

# --- the message itself -----------------------------------------------------
setup([R1, R2], state={"seen": []})
rc, note, st = run()
check("the note is title, ---, body", note is not None and "\n---\n" in note)
check("  the title counts the responses",
      note is not None and note.splitlines()[0].startswith("2 responses tabled"))
check("  the body says how many were closures", note is not None and "1 of them closing" in note)
check("  it disclaims judging newsworthiness",
      note is not None and "is a judgement about whether something is newsworthy" in note)

# --- a batch day is capped, and points at the right tool -------------------
big = [{"id": str(300 + i), "classification": "proforma_closure", "template_hits": "1",
        "title": f"Big {i}", "tabled_senate": "2026-03-19", "url": "u"}
       for i in range(D.MAX_LISTED + 5)]
setup(big, state={"seen": []})
rc, note, st = run()
check("a day larger than the cap lists only the cap",
      note is not None and note.count("### ") == D.MAX_LISTED)
check("  and defers the rest to batch_alert",
      note is not None and "5 further response(s) not listed" in note
      and "batch_alert.py" in note)
check("  but records every one of them", len(st["seen"]) == D.MAX_LISTED + 5)

# --- flags -------------------------------------------------------------------
setup([R1, R2], state={"seen": []})
rc, note, st = run(["--dry-run"])
check("--dry-run writes no note", rc == 0 and note is None)
check("  and records nothing", st == {"seen": []})

setup([R1, R2], state={"seen": ["1", "2"]})
rc, note, st = run(["--all"])
check("--all describes everything regardless of the record",
      rc == 0 and note is not None and "children overboard" in note)

# --- never fails the job -----------------------------------------------------
d = setup([R1], state={"seen": []})
D.STATE.write_text("{not json", encoding="utf-8")
check("a corrupt record: silent, exit 0",
      D.main(["digest.py"]) == 0 and not D.NOTE.exists())

d = setup([R1], state={"seen": []})
D.RESPONSES.write_text("id,classification\n", encoding="utf-8")
check("a responses file with no rows: silent, exit 0",
      D.main(["digest.py"]) == 0 and not D.NOTE.exists())

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
