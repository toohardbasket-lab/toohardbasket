"""What statsnet_alert.py must do, and must not do.

The alarm's whole value is that it stays quiet until it should not, and then
says something once rather than every week. Both halves are tested here.
"""
import json
import pathlib
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import statsnet_alert as A  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def run(state, argv=()):
    """Run main() against a freshness file holding `state`; return (rc, file, note)."""
    d = pathlib.Path(tempfile.mkdtemp())
    A.FRESHNESS = d / "statsnet_freshness.json"
    A.NOTE = d / "note.md"
    if state is not None:
        A.FRESHNESS.write_text(json.dumps(state), encoding="utf-8")
    rc = A.main(["statsnet_alert.py", *argv])
    after = json.loads(A.FRESHNESS.read_text(encoding="utf-8")) if A.FRESHNESS.exists() else None
    note = A.NOTE.read_text(encoding="utf-8") if A.NOTE.exists() else None
    return rc, after, note


def ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


Y = str(date.today().year)

# --- quiet when it should be quiet -----------------------------------------
rc, after, note = run(None)
check("no freshness file at all: silent", rc == 0 and note is None)

rc, after, note = run({})
check("file exists but nothing recorded yet: silent", rc == 0 and note is None)

rc, after, note = run({"last_live_scrape": {Y: ago(0)}})
check("read live today: silent", rc == 0 and note is None)

rc, after, note = run({"last_live_scrape": {Y: ago(13)}})
check("13 days, under the 14-day rope: silent", rc == 0 and note is None)

rc, after, note = run({"last_live_scrape": {Y: ago(30)},
                       "alerted": {Y: ago(3)}})
check("stale but raised 3 days ago: silent", rc == 0 and note is None)

# a year that is not this year going stale is not this alarm's business
rc, after, note = run({"last_live_scrape": {"2013": ago(400), Y: ago(1)}})
check("an old year untouched for a year: silent", rc == 0 and note is None)

# --- speaks when it should speak -------------------------------------------
rc, after, note = run({"last_live_scrape": {Y: ago(14)}})
check("exactly 14 days: raises", rc == 0 and note is not None)
check("  the note names the day count", note is not None and "14 days ago" in note)
check("  the title leads with the day count",
      note is not None and note.splitlines()[0].startswith(
          "The Senate register has not been read for 14 days"))
check("  the note is title, ---, body", note is not None and "\n---\n" in note)
check("  the complaint is recorded", after.get("alerted", {}).get(Y) == date.today().isoformat())
check("  recording the complaint does not erase the freshness",
      after.get("last_live_scrape", {}).get(Y) == ago(14))

rc, after, note = run({"last_live_scrape": {"2013": ago(400)}})
check("this year never read live at all: raises", rc == 0 and note is not None)
check("  and says never rather than a day count",
      note is not None and "never" in note.splitlines()[0].lower())

rc, after, note = run({"last_live_scrape": {Y: ago(30)}, "alerted": {Y: ago(20)}})
check("stale, last raised 20 days ago: raises again", rc == 0 and note is not None)

# --- the rope is adjustable, and the file wins over the default ------------
rc, after, note = run({"last_live_scrape": {Y: ago(20)}, "stale_after_days": 30})
check("file sets a 30-day rope, 20 days old: silent", rc == 0 and note is None)

rc, after, note = run({"last_live_scrape": {Y: ago(20)}, "stale_after_days": 30},
                      argv=["--days", "7"])
check("--days overrides the file's rope: raises", rc == 0 and note is not None)

rc, after, note = run({"last_live_scrape": {Y: ago(30)}}, argv=["--dry-run"])
check("--dry-run writes no note", rc == 0 and note is None)
check("  and records no complaint", "alerted" not in (after or {}))

# --- never fails the job ---------------------------------------------------
d = pathlib.Path(tempfile.mkdtemp())
A.FRESHNESS = d / "statsnet_freshness.json"
A.NOTE = d / "note.md"
A.FRESHNESS.write_text("{not json at all", encoding="utf-8")
check("a corrupt freshness file: silent, exit 0",
      A.main(["statsnet_alert.py"]) == 0 and not A.NOTE.exists())

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
