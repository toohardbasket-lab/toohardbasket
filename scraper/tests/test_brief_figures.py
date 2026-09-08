"""The figures the media pack quotes must come from the corpus, not from the raw file.

One number in a draft email was wrong for six days because the block that
computes the pack's figures re-read response_documents.csv directly instead of
using the corpus the rest of the script had already built. The raw file holds
35 responses that answer somebody other than a parliamentary committee; two of
them fell inside the window, so "responses since the story" came out as 199
where the answer is 197. Nothing failed, nothing looked wrong, and the figure
went into a document written to be checked.

These tests run against the real dataset, because that is where the mistake
lives. They pin the discipline rather than the values, so they keep passing as
the register moves and start failing the moment the scope is dropped again.
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCRAPER = HERE.parent
DATA = SCRAPER / "data"

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def rd(name):
    with (DATA / name).open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


out = subprocess.run([sys.executable, str(SCRAPER / "brief_figures.py"), "--json"],
                     capture_output=True, text=True, cwd=SCRAPER)
if out.returncode != 0:
    print(out.stderr[-2000:])
    sys.exit("brief_figures.py --json did not run")
f = json.loads(out.stdout)
p, corpus, reg = f["the_pitch"], f["corpus"], f["registers"]

# --- the corpus, computed here the way the script should be computing it ----
excluded = {r["id"] for r in rd("scope_exclusions.csv")}
rows = rd("response_documents.csv")
dated = [r for r in rows if (r.get("tabled_senate") or r.get("tabled_house") or "").strip()]
in_scope = [r for r in dated if r["id"] not in excluded]
tabled = lambda r: (r.get("tabled_senate") or r.get("tabled_house") or "").strip()

check("scope_exclusions.csv is not empty", len(excluded) > 0, f"{len(excluded)}")
check("some excluded documents carry a tabling date",
      len(dated) > len(in_scope),
      "nothing is excluded, so this suite cannot detect the fault it exists for")

# --- the fault itself --------------------------------------------------------
check("the pack's figures never count more than the corpus",
      p["since_story_responses"] <= corpus["documents_read"])

since_scoped = [r for r in in_scope if tabled(r) >= p["story_date"]]
since_raw = [r for r in dated if tabled(r) >= p["story_date"]]
check("since-story count matches the scoped corpus",
      p["since_story_responses"] == len(since_scoped),
      f"script {p['since_story_responses']}, scoped {len(since_scoped)}")
if len(since_raw) != len(since_scoped):
    check("since-story count is NOT the unscoped count",
          p["since_story_responses"] != len(since_raw),
          f"script {p['since_story_responses']} equals the raw file's {len(since_raw)}")

fl = sum(1 for r in since_scoped if r["classification"] == "proforma_closure")
check("since-story form letters match the scoped corpus",
      p["since_story_form_letters"] == fl,
      f"script {p['since_story_form_letters']}, scoped {fl}")

day = [r for r in in_scope if tabled(r) == p["batch_day"]]
check("the batch day is counted in scope too",
      p["batch_day_responses"] == len(day),
      f"script {p['batch_day_responses']}, scoped {len(day)}")

# --- the two arithmetic traps the block exists to stop -----------------------
check("distinct reports awaiting = senate + house - both",
      p["awaiting_distinct_reports"]
      == reg["senate"]["outstanding_now"] + reg["house"]["outstanding_now"]
      - reg["on_both_registers"])
check("the naive sum is reported separately, and is larger",
      p["awaiting_if_wrongly_added_DO_NOT_USE"] > p["awaiting_distinct_reports"])
check("overdue is reported distinct as well as by register row",
      p["overdue_distinct_reports"] <= p["overdue_register_rows"])

# --- it must not license a claim it cannot evidence --------------------------
attributed = p["removed_with_a_named_response"]
total = p["removed_since_schedules"]
check("the backlog claim is allowed only when most removals are attributed",
      p["may_say_why_the_backlog_fell"] == (bool(total) and attributed >= 0.8 * total),
      f"{attributed} of {total} attributed, flag={p['may_say_why_the_backlog_fell']}")
check("attributed removals never exceed the total", attributed <= total)

# --- the day counts must follow --as-at, not a frozen column -----------------
check("as_at is carried into the output", bool(p.get("as_at")))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for x in FAIL:
        print("  FAILED:", x)
    sys.exit(1)
print("all tests passed")
