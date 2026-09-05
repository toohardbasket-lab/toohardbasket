"""brief_figures.py — every figure in the media brief, computed from the dataset.

Run from the repository root or from scraper/:

    python brief_figures.py            # prints the figures
    python brief_figures.py --json     # machine-readable, for pasting into a brief

Nothing here is typed in. Each figure is derived from the CSVs in scraper/data/
the same way the site derives it, so the brief and the site cannot disagree.
Where the brief states a fact that is not in the dataset (for example that one
of the eighteen entries in the children-overboard response is from the minority
report), that is said in the brief itself and is not a figure this script owns.
"""
from __future__ import annotations

import csv
import json
import pathlib
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date

HERE = pathlib.Path(__file__).resolve().parent
CANDIDATES = [HERE / "data", HERE / "scraper" / "data", HERE.parent / "scraper" / "data",
              HERE.parent / "data"]
DATA = next((p for p in CANDIDATES if (p / "responses.csv").exists()), None)
if DATA is None:
    sys.exit("cannot find scraper/data — run from the repository root or from scraper/")


def read(name: str) -> list[dict]:
    with open(DATA / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_json(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def iso(s: str) -> date:
    return date.fromisoformat(s[:10])


def deadline_days(tabled: str) -> int:
    """Three calendar months from tabling, read as the Senate reads it."""
    d = iso(tabled)
    m = d.month + 3
    y = d.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    # roll 30 November + 3 months back to the last day of February, etc.
    import calendar
    day = min(d.day, calendar.monthrange(y, m)[1])
    return (date(y, m, day) - d).days


GOVERNMENTS = [
    ("Howard", "1996-03-11", "2007-12-03"),
    ("Rudd / Gillard", "2007-12-03", "2013-09-18"),
    ("Abbott / Turnbull / Morrison", "2013-09-18", "2022-05-23"),
    ("Albanese", "2022-05-23", "2099-01-01"),
]


def main(as_json: bool = False) -> int:
    out: dict = {}

    # ---------------------------------------------------------------- corpus
    excluded = {r["id"] for r in read("scope_exclusions.csv")}
    docs = [r for r in read("response_documents.csv") if r["id"] not in excluded]
    closures = [r for r in docs if r["classification"] == "proforma_closure"]
    partial = [r for r in docs if r["classification"] == "partial_proforma"]
    substantive = [r for r in docs if r["classification"] == "substantive"]
    unclassified = [r for r in docs if r["classification"] not in
                    ("proforma_closure", "partial_proforma", "substantive")]
    tabled = lambda r: (r["tabled_senate"] or r["tabled_house"])[:10]
    out["corpus"] = {
        "documents_read": len(docs),
        "excluded_by_scope": len(excluded),
        "form_letter_closures": len(closures),
        "closure_share": round(len(closures) / len(docs), 4),
        "partial_template": len(partial),
        "substantive": len(substantive),
        "unclassified_WARN_if_nonzero": len(unclassified),
        "read_from": min(tabled(r) for r in docs),
        "read_to": max(tabled(r) for r in docs),
        # The passage-of-time sentence, as the classifier fingerprints it
        # ("given the passage of time ... no longer appropriate"), counted
        # across the closures. This is template_hits, NOT the count of
        # "notes this recommendation" — the two differ and the site must use
        # the same one as the brief.
        "template_sentence_occurrences": sum(int(r["template_hits"] or 0) for r in closures),
        "closures_using_sentence_once": sum(1 for r in closures if r["template_hits"] == "1"),
        "closures_noting_no_recommendation": sum(1 for r in closures
                                                 if (r["notes_recommendation"] or "0") == "0"),
    }

    # --------------------------------------------------------------- by year
    by_year: dict[str, dict] = defaultdict(lambda: {"documents_read": 0, "form_letter_closures": 0,
                                                    "partial_template": 0, "substantive": 0})
    for r in docs:
        y = tabled(r)[:4]
        by_year[y]["documents_read"] += 1
        key = {"proforma_closure": "form_letter_closures", "partial_proforma": "partial_template",
               "substantive": "substantive"}.get(r["classification"])
        if key:
            by_year[y][key] += 1
    for y in by_year:
        d = by_year[y]
        d["closure_share"] = round(d["form_letter_closures"] / d["documents_read"], 4)
    out["by_year"] = dict(sorted(by_year.items()))

    # ------------------------------------------------------- the busiest day
    per_day = Counter(tabled(r) for r in closures)
    day, n = per_day.most_common(1)[0]
    out["busiest_day"] = {"date": day, "form_letter_closures_tabled": n,
                          "all_responses_tabled_that_day": sum(1 for r in docs if tabled(r) == day),
                          "template_sentences_that_day": sum(int(r["template_hits"] or 0)
                                                             for r in closures if tabled(r) == day)}

    # ------------------------------------------------ reports on bills, aside
    # Identified by title. The Senate does not require a separate response to
    # a report on a bill, so the press-office reply is anticipated by setting
    # every one of them aside and recounting.
    import re
    is_bill = lambda r: bool(re.search(r"\bBill\b|\[Provisions\]", r["title"]))
    non_bill_docs = [r for r in docs if not is_bill(r)]
    non_bill_closures = [r for r in closures if not is_bill(r)]
    out["reports_on_bills_aside"] = {
        "closures_on_bill_reports": len(closures) - len(non_bill_closures),
        "closures_remaining": len(non_bill_closures),
        "responses_remaining": len(non_bill_docs),
        "closure_share_without_bills": round(len(non_bill_closures) / len(non_bill_docs), 4),
    }

    # ----------------------------------------------------- named examples
    # Documents the brief cites by name: the count of template sentences in
    # each is the response's own count of the recommendations it disposed of.
    by_id = {r["id"]: r for r in docs}
    def ex(*ids):
        return {"documents": list(ids), "tabled": tabled(by_id[ids[0]]),
                "template_sentences": sum(int(by_id[i]["template_hits"]) for i in ids),
                "title": by_id[ids[0]]["title"]}
    out["examples"] = {
        "corporate_tax_avoidance_parts_1_to_3": ex("6660", "6659", "6653"),
        "superbad_wage_theft": ex("6656"),
        "life_insurance_industry": ex("6668"),
        "bushfire_lessons_2019_20": ex("5814"),
        "national_disgrace_temporary_visas": ex("5812"),
        "out_of_pocket_costs": ex("7572"),
        "for_profit_aged_care": ex("7565"),
    }

    # --------------------------------------------------- recommendation floor
    counts = read("recommendation_counts.csv")
    counted = [r for r in counts if r["counted"] == "yes"]
    reasons = Counter()
    for r in counts:
        if r["counted"] != "yes":
            why = r["excluded_because"]
            reasons["labels and sentences disagree" if "against" in why else why] += 1
    out["recommendation_floor"] = {
        "closures_examined": len(counts),
        "closures_that_prove_their_own_count": len(counted),
        "recommendations_floor": sum(int(r["recommendations_counted"]) for r in counted),
        "closures_excluded": len(counts) - len(counted),
        "excluded_reasons": dict(reasons),
    }

    # --------------------------------------------------- the slowest response
    resp = read("responses.csv")
    def register_days(pattern):
        hits = [r for r in resp if re.search(pattern, r["inquiry"], re.I) and r["days_to_respond"]]
        hit = max(hits, key=lambda r: r["response_tabled"]) if hits else None
        return {"report_tabled": hit["report_last_tabled"], "response_tabled": hit["response_tabled"],
                "days": int(hit["days_to_respond"])} if hit else None
    out["examples"]["bushfire_lessons_2019_20"]["register"] = register_days(r"bushfire season 2019")
    out["examples"]["national_disgrace_temporary_visas"]["register"] = register_days(r"temporary work visa")
    out["examples"]["out_of_pocket_costs"]["register"] = register_days(r"^Out-of-pocket costs")
    out["examples"]["for_profit_aged_care"]["register"] = register_days(r"for-profit aged care")
    out["examples"]["corporate_tax_avoidance_parts_1_to_3"]["register_first_report"] = min(
        r["report_first_tabled"] for r in resp if re.search(r"^Corporate tax avoidance", r["inquiry"], re.I))
    out["examples"]["corporate_tax_avoidance_parts_1_to_3"]["register_last_report"] = max(
        r["report_last_tabled"] for r in resp if re.search(r"^Corporate tax avoidance", r["inquiry"], re.I))
    day_rows = [r for r in resp if r["response_tabled"] == day and r["report_last_tabled"]]
    out["busiest_day"]["reports_tabled_between"] = [min(r["report_last_tabled"] for r in day_rows),
                                                    max(r["report_last_tabled"] for r in day_rows)]
    timed = [r for r in resp if r["days_to_respond"] and r["report_last_tabled"]]
    slowest = max(timed, key=lambda r: int(r["days_to_respond"]))
    cmi = next((r for r in docs if r["id"] == "15895"), None)
    out["slowest_response"] = {
        "inquiry": slowest["inquiry"], "committee": slowest["committee"],
        "report_tabled": slowest["report_last_tabled"], "response_tabled": slowest["response_tabled"],
        "days": int(slowest["days_to_respond"]),
        "years_months": f"{int(slowest['days_to_respond']) // 365} years, "
                        f"{round((int(slowest['days_to_respond']) % 365) / 30.44)} months",
        "otd_document": cmi["id"] if cmi else None,
        "author": cmi["author"] if cmi else None,
        "template_sentence_count_in_document": int(cmi["template_hits"]) if cmi else None,
        "classification": cmi["classification"] if cmi else None,
    }

    # ---------------------------------------------------------- the registers
    sm, hm = read_json("ledger_meta.json"), read_json("house_ledger_meta.json")
    senate_rows = read("ledger_v2.csv")
    house_rows = read("house_ledger.csv")
    oldest = max(senate_rows, key=lambda r: int(r["days_outstanding"]))
    runs = read("being_considered_runs.csv")
    out["registers"] = {
        "as_at_schedules": sm["as_at"],
        "rebuilt": sm["rebuilt"],
        "responses_checked_to": sm["responses_checked_to"],
        "senate": {
            "presidents_report_tabled": sm["tabled"],
            "listed": sm["listed"], "answered_at_schedule": sm["answered_at_schedule"],
            "outstanding_at_schedule": sm["outstanding_at_schedule"],
            "answered_since_schedule": sm["answered_since_schedule"],
            "outstanding_now": len(senate_rows),
            "overdue": sum(1 for r in senate_rows if r["overdue"] == "True"),
            "being_considered": sum(1 for r in senate_rows if r["being_considered"] == "True"),
            "being_considered_status_report_as_at": sm["being_considered_as_at"],
            "editions_read_since": sm["editions_from"], "editions_read": sm["editions_read"],
            "being_considered_in_every_edition": sum(1 for r in runs
                                                     if int(r["editions_in_a_row"]) == sm["editions_read"]),
            "longest_wait_days": int(oldest["days_outstanding"]),
            "longest_wait_report": oldest["title"], "longest_wait_tabled": oldest["report_tabled"],
        },
        "house": {
            "speakers_schedule_presented": hm["tabled"],
            "listed": hm["listed"],
            "schedule_own_tally_awaiting": hm["schedule_says_outstanding"],
            "schedule_own_tally_received": hm["schedule_says_answered"],
            "rows_with_response_dated_before_period": hm["response_out_of_period"],
            "outstanding_at_schedule_as_read": hm["outstanding_at_schedule"],
            "answered_since_schedule": hm["answered_since_schedule"],
            "outstanding_now": len(house_rows),
            "overdue": sum(1 for r in house_rows if r["overdue"] == "True"),
            "being_considered": hm["being_considered"],
            "speakers_on_time": f"{hm['answered_on_time']} of {hm['answered_with_a_verdict']}",
            "speakers_on_time_rate": round(hm["on_time_rate"], 3),
        },
        "on_both_registers": sm["on_both_registers"],
    }

    # ------------------------------------------------------------ compliance
    rows = []
    for r in resp:
        if r["days_to_respond"] and r["report_last_tabled"]:
            rows.append({"days": int(r["days_to_respond"]),
                         "deadline": deadline_days(r["report_last_tabled"]),
                         "response": r["response_tabled"], "report": r["report_last_tabled"]})
    n = len(rows)
    on_time = sum(1 for r in rows if r["days"] <= r["deadline"])
    over_year = sum(1 for r in rows if r["days"] > 365)
    over_2x = sum(1 for r in rows if r["days"] > 180)
    govs = {}
    for name, a, b in GOVERNMENTS:
        by_resp = [r for r in rows if a <= r["response"] < b]
        by_rep = [r for r in rows if a <= r["report"] < b]
        govs[name] = {
            "responses_tabled": len(by_resp),
            "met_rule_by_response": round(sum(1 for r in by_resp if r["days"] <= r["deadline"]) / len(by_resp), 4) if by_resp else None,
            "reports_tabled": len(by_rep),
            "met_rule_by_report": round(sum(1 for r in by_rep if r["days"] <= r["deadline"]) / len(by_rep), 4) if by_rep else None,
        }
    out["compliance"] = {
        "measurable_responses_2000_on": n,
        "excluded_no_report_date": len(resp) - n,
        "within_three_months": on_time, "rate": round(on_time / n, 4),
        "median_days": round(statistics.median(r["days"] for r in rows)),
        "over_a_year": over_year, "over_a_year_share": round(over_year / n, 4),
        "over_six_months_share": round(over_2x / n, 4),
        "by_government": govs,
        "highest_rate_any_government_either_reading": max(
            v for g in govs.values() for v in (g["met_rule_by_response"], g["met_rule_by_report"]) if v),
    }

    # ----------------------------------------------------- responses per year
    per = Counter(r["response_tabled"][:4] for r in resp if r["response_tabled"])
    base = [per[str(y)] for y in range(2000, 2024)]
    out["responses_per_year_senate_register"] = {
        "mean_2000_2023": round(sum(base) / len(base), 1),
        "max_2000_2023": max(base),
        "2024": per["2024"], "2025": per["2025"], "2026_to_date": per["2026"],
        "latest_response_in_register": max(r["response_tabled"] for r in resp if r["response_tabled"]),
        "total_2000_on": len(resp),
    }

    # --------------------------------------------------- recommendations index
    try:
        recs = read("recommendations.csv")
        out["recommendations_index"] = {
            "rows": len(recs),
            "documents": len({(r["source"], r["source_id"]) for r in recs}),
            "awaiting_a_response": sum(1 for r in recs if r["response_classification"] == "awaiting a response"),
            "with_government_words": sum(1 for r in recs if r["government_words"]),
            "flagged_other_author_NOTE_undercount_until_finding_2_fixed":
                sum(1 for r in recs if r["recommended_by"]),
            "dropped_by_verification": len(read("recommendations_dropped.csv"))
                if (DATA / "recommendations_dropped.csv").exists() else 0,
        }
    except FileNotFoundError:
        pass

    # ------------------------------------------------------------ coverage
    # For each recommendation the index holds, whether the response stated a
    # position on it. Produced by coverage.py; read back here so the brief
    # quotes the same file the site does.
    cov_file = DATA / "coverage_summary.json"
    if cov_file.exists():
        cov = read_json("coverage_summary.json")
        t = cov["total"]
        out["coverage"] = {
            "definition": cov["definition"],
            "responses_with_recommendations_indexed": t["responses"],
            "responses_with_nothing_indexed": cov["responses_with_nothing_indexed"],
            "recommendations_assessed": t["recommendations"],
            "position_stated": t["position_stated"],
            "position_stated_share": t["coverage"],
            "accepted": t["accepted"],
            "in_part_or_in_principle": t["in_part_or_in_principle"],
            "not_accepted": t["not_accepted"],
            "noted_no_position": t["noted_no_position"],
            "form_letter": t["form_letter"],
            "not_addressed_individually": t["not_addressed_individually"],
            "unreadable_excluded": t["unreadable"],
            "responses_with_no_position_on_any_recommendation": t["responses_with_no_position_at_all"],
            "responses_with_a_position_on_every_recommendation": t["responses_fully_covered"],
            "by_year": {y: {"recommendations": v["recommendations"], "position_stated": v["position_stated"],
                            "share": v["coverage"]} for y, v in cov["by_year"].items()},
        }

    out["generated"] = date.today().isoformat()

    if as_json:
        print(json.dumps(out, indent=2))
        return 0

    def show(d, indent=0):
        for k, v in d.items():
            if isinstance(v, dict):
                print(" " * indent + f"{k}:")
                show(v, indent + 2)
            else:
                print(" " * indent + f"{k}: {v}")
    show(out)
    if out["corpus"]["unclassified_WARN_if_nonzero"]:
        print("\nWARNING: the corpus holds unclassified documents; the closure rate is understated.")
    return 0


if __name__ == "__main__":
    sys.exit(main("--json" in sys.argv))
