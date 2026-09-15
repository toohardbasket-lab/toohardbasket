"""The two ledger_meta files are shared records, and no step owns all of them.

Five steps of the weekly job write into ledger_meta.json and
house_ledger_meta.json: the register build, the removal step, the
cross-register pass, the status-history pass, and the edition snapshot. They
run at different points, and one of the readers — brief_figures.py, called
from tests/test_awaiting.py — runs in the MIDDLE of that sequence, after the
register build and before the removal step.

So a build step that writes the file from an empty dict destroys every key it
does not itself compute, and the run fails in between on a KeyError that names
none of this. It happened on 15 September 2026: a new President's report
triggered the first full rebuild since those keys were added, build_ledger.py
wrote a fresh dict, and the job stopped at "Owed-an-answer tests" with
KeyError: 'responses_checked_to'. Nothing was published, which is the gate
working, but the message pointed at a file three steps away from the cause.

These tests are the rule that prevents it: a step owns the keys it computes and
leaves the rest alone.
"""
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import build_ledger  # noqa: E402
import build_house_ledger  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


# The keys other steps add, and which step adds each. Named here so that
# deleting one from its writer without thinking breaks this file.
ADDED_BY_OTHERS = {
    "responses_checked_to": "prune_answered.py",
    "covers_responses_to": "prune_answered.py",
    "pruned": "prune_answered.py",
    "on_both_registers": "cross_register.py",
    "editions_read": "build_status_history.py",
}

for name, merge in [("build_ledger", build_ledger.merge_meta),
                    ("build_house_ledger", build_house_ledger.merge_meta)]:
    d = pathlib.Path(tempfile.mkdtemp()) / "meta.json"
    before = {k: f"set by {who}" for k, who in ADDED_BY_OTHERS.items()}
    before["listed"] = 1
    d.write_text(json.dumps(before), encoding="utf-8")

    merge(d, {"listed": 285, "rebuilt": "2026-09-15"})
    after = json.loads(d.read_text(encoding="utf-8"))

    check(f"{name}: keeps what other steps wrote",
          all(after.get(k) == before[k] for k in ADDED_BY_OTHERS),
          f"lost {[k for k in ADDED_BY_OTHERS if after.get(k) != before[k]]}")
    check(f"{name}: writes what it computed", after["listed"] == 285)
    check(f"{name}: adds its new keys", after.get("rebuilt") == "2026-09-15")

    # A first run has no file at all, and must not need one.
    fresh = pathlib.Path(tempfile.mkdtemp()) / "meta.json"
    merge(fresh, {"listed": 1})
    check(f"{name}: works with no file there yet",
          json.loads(fresh.read_text(encoding="utf-8")) == {"listed": 1})

# The reader stays strict on purpose. brief_figures.py asks for the key
# outright rather than shrugging with .get(), because a missing key means a
# step destroyed it and that is worth stopping for. Softening the reader would
# have turned this into a silently wrong figure in a media brief instead of a
# failed build.
src = (pathlib.Path(__file__).resolve().parent.parent / "brief_figures.py").read_text(
    encoding="utf-8")
check("brief_figures still demands the key rather than defaulting it",
      'sm["responses_checked_to"]' in src)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
