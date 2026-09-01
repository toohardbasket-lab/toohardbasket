"""
validate.py — the pipeline's refuse-to-publish gate.

The Too Hard Basket's premise is holding government to account for its
record-keeping; a silently wrong number would be fatal to credibility.
So the pipeline REFUSES to publish (non-zero exit) rather than publish
data that fails these checks. A layout change at aph.gov.au should stop
the build loudly, never degrade it quietly.
"""
from __future__ import annotations
import re
import sys
from datetime import date
from thb_parser import Row

# The Senate's own stated counts, where a register page states one.
# Extend this as years are scraped: {"classic/2011": 70, ...}
EXPECTED_COUNTS = {
    "classic/2005": 40,
    "classic/2011": 70,   # 67 tabled/presented in 2011 + 3 presented 2010
}

FLOOR_DATE = date(1970, 1, 1)


def validate(rows: list[Row], today: date | None = None) -> list[str]:
    today = today or date.today()
    errors: list[str] = []

    if not rows:
        errors.append("zero rows parsed — refusing to publish")
        return errors

    # 1. Per-source counts match the register's own stated totals.
    by_source: dict[str, int] = {}
    for r in rows:
        key = "/".join(r.source.rsplit("/", 2)[-2:]) if r.source else "unknown"
        by_source[key] = by_source.get(key, 0) + 1
    for key, expected in EXPECTED_COUNTS.items():
        got = sum(v for k, v in by_source.items() if k.endswith(key.split("/")[-1])
                  and key.split("/")[0] in k)
        if got and got != expected:
            errors.append(f"{key}: parsed {got} rows, register states {expected}")

    # 2. Date sanity.
    for r in rows:
        if r.report_last_tabled and r.response_tabled:
            rep = date.fromisoformat(r.report_last_tabled)
            resp = date.fromisoformat(r.response_tabled)
            if resp < rep:
                errors.append(f"response before report: {r.inquiry[:60]!r} "
                              f"({r.report_last_tabled} -> {r.response_tabled})")
            for d, label in ((rep, "report"), (resp, "response")):
                if not (FLOOR_DATE <= d <= today):
                    errors.append(f"{label} date out of range {d}: {r.inquiry[:60]!r}")

    # 3. Missing-data budget: unparsed rows must stay rare AND explained.
    #    A missing report date is EXPECTED for 2000/2001 (the register never
    #    recorded them) — those rows carry the 'not recorded' note and are
    #    exempt from the budget; they still lack a days_to_respond by design.
    missing = [r for r in rows if not (r.report_last_tabled and r.response_tabled)]
    unexplained = [r for r in missing if not r.notes]
    if unexplained:
        errors.append(f"{len(unexplained)} rows missing dates with no explanatory note")
    budget = [r for r in missing
              if not r.response_tabled or "not recorded" not in r.notes]
    if len(budget) > 0.03 * len(rows):
        errors.append(f"{len(budget)}/{len(rows)} rows with unexpected missing dates — above 3% budget")

    # 4. Duplicates. Two keys, because one is not enough: the exact fields,
    #    and the same words across committee and inquiry however they were
    #    split between them. The second key is the one that matters — two
    #    parsers reading the same register line can divide it differently, and
    #    28 responses were counted twice before this check could see them.
    seen: set[tuple] = set()
    for r in rows:
        text = f"{r.committee} {r.inquiry}".lower()
        words = frozenset(w for w in re.sub(r"[^a-z0-9]+", " ", text).split() if len(w) > 3)
        exact = (r.committee, r.inquiry, r.report_last_tabled, r.response_tabled)
        loose = (r.report_last_tabled, r.response_tabled, words)
        if exact in seen and any(exact):
            errors.append(f"duplicate row: {r.inquiry[:60]!r} {r.response_tabled}")
        elif r.report_last_tabled and r.response_tabled and loose in seen:
            errors.append(f"duplicate response, split differently: "
                          f"{r.committee[:40]!r} / {r.inquiry[:40]!r} {r.response_tabled}")
        seen.add(exact)
        seen.add(loose)

    return errors


def main(rows: list[Row]) -> int:
    errors = validate(rows)
    if errors:
        print("VALIDATION FAILED — NOT publishing:")
        for e in errors:
            print("  •", e)
        return 1
    print(f"validation passed: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    print("run via build_dataset.py")
    sys.exit(0)
