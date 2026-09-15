"""Every file the site reads is either written by the weekly job or declared by hand.

Twice on 15 September a published figure was wrong for the same structural
reason, and neither time did anything say so.

    jurisdiction.py and verify_positions.py were not in the weekly job at all.
    Both write JSON the methods page reads. Both were last run by hand on 14
    September. So the page told readers the index holds 5,463 recommendations
    while the index held 5,539 — a checkable figure, sitting beside the figure
    it disagreed with, quietly describing a different dataset.

Fixing the two instances leaves the class open: the next script added to the
repo and wired into a page, but not into the job, fails the same way and is
found the same way, by somebody noticing. So this file closes the class instead.

It reads which data files the site actually opens, out of the site's own source,
and requires each one to be in exactly one of two lists below: written by a step
the weekly workflow runs, or hand-maintained with a reason. Adding a read of a
new data file to the site breaks this test until the file is declared. That is
the point of it — the declaration is cheap and the silent wrong figure is not.

On its first run it found two files a careful hand search had missed —
house_ledger.csv and ledger_v2.csv, both read by the site through a helper the
search did not match on. Both are written weekly, so neither was a fault; the
point is that the list a person builds by grepping is not the list.

What this does NOT do: confirm that the named step really writes the file. It
checks that the step runs weekly and that its source at least names the file,
which catches a renamed script and a typo, not a lie. The honest limit of a
cheap test, stated rather than glossed.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SITE = ROOT / "site" / "src"
SCRAPER = ROOT / "scraper"
WORKFLOW = ROOT / ".github" / "workflows" / "update-dataset.yml"

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


# The step of the weekly job that writes each file. Where several steps touch a
# file, this names the one that creates it.
BY_A_WEEKLY_STEP = {
    "responses.csv": "build_dataset.py",
    "response_documents.csv": "harvest_responses.py",
    "response_reports.csv": "link_responses_to_reports.py",
    "reports_manual.csv": "harvest_manual_reports.py",
    "recommendations.csv": "extract_recommendations.py",
    "recommendations_dropped.csv": "verify_recommendations.py",
    "labels_refused.json": "extract_recommendations.py",
    "layout_suspect.json": "layout_check.py",
    "recommendation_counts.csv": "count_recommendations.py",
    "recommendation_positions.csv": "coverage.py",
    "coverage_summary.json": "coverage.py",
    "jurisdiction.json": "jurisdiction.py",
    "position_checks.json": "verify_positions.py",
    "implementation_claims.csv": "implementation_evidence.py",
    "implementation_evidence.json": "implementation_evidence.py",
    "backlog_history.csv": "build_history.py",
    "schedule_snapshots.csv": "build_status_history.py",
    "ledger_v2.csv": "build_ledger_v2.py",
    "house_ledger.csv": "build_house_ledger.py",
    "ledger_meta.json": "build_ledger.py",
    "house_ledger_meta.json": "build_house_ledger.py",
    "royal_commissions.csv": "harvest_royal_commissions.py",
    "rc_documents.csv": "harvest_royal_commissions.py",
    "rc_sweep.json": "harvest_royal_commissions.py",
    "rc_recommendations.csv": "extract_rc_recommendations.py",
    "rc_recommendation_counts.csv": "extract_rc_recommendations.py",
    "rc_positions.csv": "extract_rc_positions.py",
    "rc_position_counts.csv": "extract_rc_positions.py",
}

# Files a person writes. Each needs a reason, because "no script writes it" is
# the same observation as the bug this file exists to catch — the difference is
# entirely whether somebody meant it.
HAND_MAINTAINED = {
    "corrections.csv":
        "A correction is a person saying the site was wrong. Nothing can generate one, "
        "and a generated corrections log would be the site marking its own homework.",
    "scope_exclusions.csv":
        "Why a tabled document is not in the corpus. A person reads the document and "
        "writes the reason; the count of exclusions is then checked against it.",
    "rc_not_held.csv":
        "Which royal commissions the index does not hold, and why. Hand-written, and "
        "harvest_royal_commissions.py verifies every claim in it against the register "
        "it has just read and refuses the run on a bad one.",
    "rc_not_ours.csv":
        "Every register record considered and rejected, with the reason a person gave. "
        "Same verification as rc_not_held.csv.",
}


def data_files_the_site_reads() -> set[str]:
    """What the site opens out of scraper/data, read from the site's own source."""
    found: set[str] = set()
    for p in SITE.rglob("*"):
        if p.suffix not in {".ts", ".astro", ".js", ".tsx"} or not p.is_file():
            continue
        s = p.read_text(encoding="utf-8", errors="ignore")
        found |= set(re.findall(r'"([a-z_0-9]+\.(?:csv|json))"', s))
    # editions/ is a directory of per-edition snapshots, not a file.
    return {f for f in found if not f.startswith("editions")}


def weekly_steps() -> set[str]:
    s = WORKFLOW.read_text(encoding="utf-8")
    return set(re.findall(r"python ([a-z_0-9]+\.py)", s))


reads = data_files_the_site_reads()
steps = weekly_steps()

check("the site reads some data files at all", len(reads) > 10, f"found {len(reads)}")
check("the weekly job runs some steps at all", len(steps) > 10, f"found {len(steps)}")

undeclared = sorted(f for f in reads
                    if f not in BY_A_WEEKLY_STEP and f not in HAND_MAINTAINED)
check("every file the site reads is declared",
      not undeclared,
      "undeclared: " + ", ".join(undeclared) +
      " — add each to BY_A_WEEKLY_STEP (naming the weekly step that writes it) or to "
      "HAND_MAINTAINED (with the reason a person writes it)")

both = sorted(set(BY_A_WEEKLY_STEP) & set(HAND_MAINTAINED))
check("no file is declared twice", not both, ", ".join(both))

missing_step = sorted(f for f, step in BY_A_WEEKLY_STEP.items()
                      if f in reads and step not in steps)
check("every step named here is a step the weekly job actually runs",
      not missing_step,
      "; ".join(f"{f} names {BY_A_WEEKLY_STEP[f]}, which the job does not run"
                for f in missing_step))

wrong_name = sorted(f for f, step in BY_A_WEEKLY_STEP.items()
                    if f in reads and (SCRAPER / step).exists()
                    and f not in (SCRAPER / step).read_text(encoding="utf-8", errors="ignore"))
check("every step named here at least mentions the file it is said to write",
      not wrong_name,
      "; ".join(f"{BY_A_WEEKLY_STEP[f]} never mentions {f}" for f in wrong_name))

gone = sorted(f for f, step in BY_A_WEEKLY_STEP.items() if not (SCRAPER / step).exists())
check("every step named here exists", not gone,
      "; ".join(f"{f} names {BY_A_WEEKLY_STEP[f]}, which is not in scraper/" for f in gone))

# A list that outlives what it describes stops being read. If the site no longer
# reads a file, its declaration should go with it.
stale = sorted(f for f in set(BY_A_WEEKLY_STEP) | set(HAND_MAINTAINED) if f not in reads)
check("no declaration is left behind for a file the site no longer reads",
      not stale, "stale: " + ", ".join(stale))

check("every hand-maintained file says why a person writes it",
      all(len(why.strip()) > 40 for why in HAND_MAINTAINED.values()))

print(f"\nNOTE  {len(reads)} data files read by the site: "
      f"{len([f for f in reads if f in BY_A_WEEKLY_STEP])} written weekly, "
      f"{len([f for f in reads if f in HAND_MAINTAINED])} by hand.")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
