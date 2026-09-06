"""pitch_figures.py — every number the media pack quotes, computed, not typed.

The evidence brief, the covering email and the spreadsheet all quote figures
from this dataset. The spreadsheet is generated. The other two were typed by
hand, and one of the typed figures — "191 responses, 46 form letters" — turned
out never to have been true: from the story date of 3 March 2026 the register
gives 198 and 50, and it gave 198 and 50 in the only commit that has ever
touched response_documents.csv. A figure that cannot be reproduced is worse
than no figure, because it is the one a department will find.

So this computes them all, from the published files, and prints them twice:
once as JSON for the spreadsheet build, once as a block a person can read
against a draft line by line.

    python pitch_figures.py                          # as at today
    python pitch_figures.py --as-at 2026-09-08       # as at an edition
    python pitch_figures.py --story-date 2026-03-03  # the "since" anchor
    python pitch_figures.py --json out.json

TWO THINGS IT IS CAREFUL ABOUT

Day counts are recomputed from --as-at, never read from the ledger's own
days_outstanding column. That column is frozen at the build that wrote it,
while the site recomputes every wait from the current day, so quoting the
column in a document dated later is how a figure goes quietly stale.

Reports awaiting a response are counted as distinct reports. The Senate
register and the House register overlap, so adding the two totals
double-counts everything joint. The email said 38 and 82; a reader adds them
and gets 120; the true number of distinct reports is 96. Both numbers are
reported here, with the overlap named, so the sentence can be written
correctly.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys
from collections import Counter, defaultdict
from datetime import date, datetime

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

DEADLINE_DAYS = 91          # the Senate's three-month rule, in days


def rd(name: str) -> list[dict]:
    p = DATA / name
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def jd(name: str) -> dict:
    p = DATA / name
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        return {}


def d(s) -> date | None:
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def tabled(r: dict) -> str:
    return (r.get("tabled_senate") or r.get("tabled_house") or "").strip()


def words(days: int) -> str:
    y, rest = divmod(days, 365)
    m = rest // 30
    if y and m:
        return f"{y} year{'s' if y != 1 else ''} {m} month{'s' if m != 1 else ''}"
    if y:
        return f"{y} year{'s' if y != 1 else ''}"
    if m:
        return f"{m} month{'s' if m != 1 else ''}"
    return f"{days} day{'s' if days != 1 else ''}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-at", default=date.today().isoformat(),
                    help="the edition date every wait is measured to")
    ap.add_argument("--story-date", default="2026-03-03",
                    help="the date the reporter's story ran; the 'since' anchor")
    ap.add_argument("--batch-day", default="2026-03-19",
                    help="the tabling day the pitch leads with")
    ap.add_argument("--json", default=None, help="also write the figures here")
    a = ap.parse_args(argv)

    as_at, story, batch = d(a.as_at), d(a.story_date), a.batch_day
    if not as_at or not story:
        print("pitch_figures: --as-at and --story-date must be YYYY-MM-DD", file=sys.stderr)
        return 2

    responses = [r for r in rd("response_documents.csv") if tabled(r)]
    reports = {(r.get("response_id") or "").strip(): r for r in rd("response_reports.csv")}
    senate, house = rd("ledger_v2.csv"), rd("house_ledger.csv")
    cross = rd("cross_register.csv")
    since_s, since_h = rd("answered_since_senate.csv"), rd("answered_since_house.csv")
    cov = jd("coverage_summary.json").get("total", {})
    recs = rd("recommendations.csv")

    closure = lambda r: r.get("classification") == "proforma_closure"
    f = {}

    # ---- the corpus -------------------------------------------------------
    f["as_at"] = as_at.isoformat()
    f["edition_tag"] = f"edition-{as_at.isoformat()}"
    f["edition_url"] = f"https://toohardbasket.org.au/as-at/{as_at.isoformat()}/"
    f["responses_on_file"] = len(responses)
    f["form_letters_total"] = sum(1 for r in responses if closure(r))
    f["latest_response_tabled"] = max(tabled(r) for r in responses)
    f["recommendations_indexed"] = len(recs)
    f["recommendations_with_words"] = cov.get("recommendations")
    f["position_stated"] = cov.get("position_stated")
    f["coverage_pct"] = (round(100 * cov["position_stated"] / cov["recommendations"])
                         if cov.get("recommendations") else None)
    f["responses_in_coverage"] = cov.get("responses")
    f["noted_no_position"] = cov.get("noted_no_position")
    f["not_addressed_individually"] = cov.get("not_addressed_individually")

    # ---- since the story --------------------------------------------------
    since = [r for r in responses if tabled(r) >= story.isoformat()]
    f["story_date"] = story.isoformat()
    f["since_story_responses"] = len(since)
    f["since_story_form_letters"] = sum(1 for r in since if closure(r))
    f["days_story_to_batch"] = (d(batch) - story).days if d(batch) else None

    # ---- the batch day ----------------------------------------------------
    day = [r for r in responses if tabled(r) == batch]
    f["batch_day"] = batch
    f["batch_day_responses"] = len(day)
    f["batch_day_form_letters"] = sum(1 for r in day if closure(r))
    f["batch_day_substantive"] = sum(1 for r in day if r.get("classification") == "substantive")
    f["batch_day_departments"] = sorted({(r.get("department") or r.get("author") or "").strip()
                                         for r in day} - {""})

    by_day = defaultdict(list)
    for r in responses:
        by_day[tabled(r)].append(r)
    ranked = sorted(by_day.items(), key=lambda kv: -len(kv[1]))
    f["biggest_tabling_days"] = [
        {"date": k, "responses": len(v),
         "form_letters": sum(1 for r in v if closure(r))}
        for k, v in ranked[:5]]
    f["batch_day_rank"] = next((i + 1 for i, (k, _) in enumerate(ranked) if k == batch), None)

    # ---- the registers, counted as distinct reports -----------------------
    f["senate_awaiting"] = len(senate)
    f["house_awaiting"] = len(house)
    f["on_both_registers"] = len(cross)
    f["awaiting_distinct"] = len(senate) + len(house) - len(cross)
    f["awaiting_naive_sum"] = len(senate) + len(house)

    waits = []
    for row, chamber in [(r, "Senate") for r in senate] + [(r, "House") for r in house]:
        t = d(row.get("report_tabled"))
        if t:
            waits.append(((as_at - t).days, t.isoformat(), (row.get("title") or "").strip(),
                          (row.get("committee") or "").strip(), chamber))
    waits.sort(reverse=True)
    if waits:
        n, t, title, cttee, chamber = waits[0]
        f["longest_wait"] = {"days": n, "in_words": words(n), "report_tabled": t,
                             "title": title, "committee": cttee, "register": chamber}
    # Overdue has the same double-counting trap as the totals above: a joint
    # report overdue on both registers is two rows and one report.
    overdue_rows = sum(1 for w in waits if w[0] > DEADLINE_DAYS)
    yes = lambda v: (v or "").strip().lower() in ("true", "1", "yes")
    both_overdue = sum(1 for r in cross if yes(r.get("senate_overdue"))
                       and yes(r.get("house_overdue")))
    f["overdue_register_rows"] = overdue_rows
    f["overdue_distinct"] = overdue_rows - both_overdue

    # ---- did the backlog fall by answering, or by closing? ----------------
    # Only some removals name the response that caused them; the rest come off
    # because the register itself now says answered. So this can never support
    # a claim about WHY the backlog fell unless the attributed share is large.
    removed = since_s + since_h
    ids = {(r.get("response_id") or "").strip() for r in removed} - {""}
    by_id = {(r.get("id") or "").strip(): r for r in responses}
    known = [by_id[i] for i in ids if i in by_id]
    f["removed_since_schedule"] = len(removed)
    f["removed_with_a_named_response"] = len(known)
    f["removed_by_a_form_letter"] = sum(1 for r in known if closure(r))
    f["removed_by_a_substantive_response"] = sum(
        1 for r in known if r.get("classification") == "substantive")
    f["removal_attribution_is_sufficient"] = bool(removed) and len(known) >= 0.8 * len(removed)

    # ---- named examples the documents lean on -----------------------------
    def find(rows, needle):
        return next((r for r in rows if needle.lower() in (r.get("title") or "").lower()), None)

    fin = find(senate, "financial abuse") or find(house, "financial abuse")
    if fin and d(fin.get("report_tabled")):
        n = (as_at - d(fin["report_tabled"])).days
        f["financial_abuse"] = {"report_tabled": fin["report_tabled"], "days": n,
                                "in_words": words(n),
                                "being_considered": fin.get("being_considered")}

    longest_closure = max((r for r in responses if closure(r)),
                          key=lambda r: int(r.get("template_hits") or 0), default=None)
    if longest_closure:
        f["most_repeated_form_letter"] = {
            "title": longest_closure.get("title"), "tabled": tabled(longest_closure),
            "times": int(longest_closure.get("template_hits") or 0),
            "url": longest_closure.get("url")}

    # ---- print ------------------------------------------------------------
    print(f"THE TOO HARD BASKET — figures as at {f['as_at']}")
    print(f"Edition {f['edition_tag']} · {f['edition_url']}")
    print()
    print("THE CORPUS")
    print(f"  {f['responses_on_file']} responses on file, latest tabled {f['latest_response_tabled']}")
    print(f"  {f['form_letters_total']} of them closed the report with the form letter")
    print(f"  {f['recommendations_indexed']} recommendations in the index")
    print(f"  {f['position_stated']} of {f['recommendations_with_words']} recommendations "
          f"have a stated position ({f['coverage_pct']}%)")
    print()
    print(f"SINCE THE STORY ({f['story_date']})")
    print(f"  {f['since_story_responses']} responses tabled, "
          f"{f['since_story_form_letters']} of them the form letter")
    if f["days_story_to_batch"] is not None:
        print(f"  {f['batch_day']} was {f['days_story_to_batch']} days after the story")
    print()
    print(f"THE BATCH DAY ({f['batch_day']})")
    print(f"  {f['batch_day_responses']} responses, {f['batch_day_form_letters']} form letters, "
          f"{f['batch_day_substantive']} substantive")
    print(f"  department(s): {', '.join(f['batch_day_departments']) or '(none recorded)'}")
    print(f"  ranks {f['batch_day_rank']} of all tabling days since April 2022")
    for b in f["biggest_tabling_days"]:
        print(f"    {b['date']}  {b['responses']:>3} responses, {b['form_letters']:>3} form letters")
    print()
    print("THE REGISTERS")
    print(f"  Senate {f['senate_awaiting']}, House {f['house_awaiting']}, "
          f"{f['on_both_registers']} on both")
    print(f"  => {f['awaiting_distinct']} DISTINCT reports awaiting a response "
          f"(do not write {f['awaiting_naive_sum']})")
    if "longest_wait" in f:
        lw = f["longest_wait"]
        print(f"  longest wait {lw['in_words']} ({lw['days']:,} days), tabled "
              f"{lw['report_tabled']}: {lw['title'][:60]}")
    print(f"  {f['overdue_distinct']} distinct reports are past the three-month rule "
          f"({f['overdue_register_rows']} register rows)")
    print()
    print("HOW THE BACKLOG FELL")
    print(f"  {f['removed_since_schedule']} reports removed since the schedules; "
          f"only {f['removed_with_a_named_response']} name the response that did it")
    print(f"    of those: {f['removed_by_a_form_letter']} a form letter, "
          f"{f['removed_by_a_substantive_response']} substantive")
    if not f["removal_attribution_is_sufficient"]:
        print("    DO NOT write why the backlog fell: most removals are unattributed.")
    if "financial_abuse" in f:
        fa = f["financial_abuse"]
        print()
        print(f"FINANCIAL ABUSE REPORT: tabled {fa['report_tabled']}, "
              f"{fa['days']:,} days ({fa['in_words']}), "
              f"being considered = {fa['being_considered']}")

    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(f, indent=1) + "\n", encoding="utf-8")
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
