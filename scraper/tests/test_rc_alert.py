"""What rc_alert.py must say, and must not say twice.

The royal commissions steps do not gate the weekly rebuild while the index is
a draft. That is only safe if a step refusing is heard, so every test here is
a way of the alarm going quiet when it should not — or of it nagging every
week about a candidate somebody has already been told about, which is how an
alarm gets ignored.
"""
import csv
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import rc_alert as A  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def bed(candidates=(), said=None):
    d = pathlib.Path(tempfile.mkdtemp())
    A.CANDIDATES, A.STATE = d / "rc_candidates.csv", d / "rc_alerted.json"
    A.NOTE = d / "rc_alert.md"
    fields = ["id", "type", "title", "tabled_senate", "tabled_house", "reason", "url"]
    with A.CANDIDATES.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows({"id": c, "type": "Royal commission", "title": f"A document {c}",
                     "tabled_senate": "2026-09-08", "url": f"https://example.invalid/{c}"}
                    for c in candidates)
    if said is not None:
        A.STATE.write_text(json.dumps({"candidates": list(said)}), encoding="utf-8")
    return d


bed()
A.main(["rc_alert.py"])
check("a clean run with nothing waiting says nothing", not A.NOTE.exists())

bed()
A.main(["rc_alert.py", "--failed"])
check("a step that refused is always worth an issue, even with no candidates",
      A.NOTE.exists() and "refused" in A.NOTE.read_text(encoding="utf-8"))

bed(["9001"])
A.main(["rc_alert.py"])
note = A.NOTE.read_text(encoding="utf-8") if A.NOTE.exists() else ""
check("a candidate nobody has ruled on is worth an issue", "9001" in note)
check("and the issue links the record rather than naming a file to go and open",
      "https://example.invalid/9001" in note)
check("and it says what to do with it",
      "rc_seed.csv" in note and "rc_not_ours.csv" in note)
check("and it is recorded, so it is not raised again",
      "9001" in json.loads(A.STATE.read_text(encoding="utf-8"))["candidates"])

bed(["9001"], said=["9001"])
A.main(["rc_alert.py"])
check("the same candidate a week later is not raised twice", not A.NOTE.exists())

bed(["9001", "9002"], said=["9001"])
A.main(["rc_alert.py"])
note = A.NOTE.read_text(encoding="utf-8") if A.NOTE.exists() else ""
check("a new candidate beside an old one is raised, and only the new one",
      "9002" in note and "9001" not in note)

bed(["9001"], said=["9001"])
A.main(["rc_alert.py", "--failed"])
check("a step that refused is raised even when every candidate is old news",
      A.NOTE.exists() and "refused" in A.NOTE.read_text(encoding="utf-8"))

# The alarm exists so a failure is heard. An alarm that fails is worse than no
# alarm, because the run stays green either way.
bed(["9001"])
A.STATE.write_text("{ this is not json", encoding="utf-8")
check("a corrupt record of what was said does not stop it speaking",
      A.main(["rc_alert.py"]) == 0 and A.NOTE.exists())

A.CANDIDATES = pathlib.Path(tempfile.mkdtemp()) / "missing.csv"
check("no candidates file at all is a quiet run, not a crash",
      A.main(["rc_alert.py"]) == 0)

d = bed(["9001"])
A.main(["rc_alert.py", "--dry-run"])
check("a dry run writes neither the note nor the record",
      not A.NOTE.exists() and not A.STATE.exists())

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
