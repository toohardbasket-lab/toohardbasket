"""
build_dataset.py — assemble data/responses.csv from whatever sources are
available, then validate before writing.

Modes:
    python build_dataset.py --fixtures      # offline: parse fixtures/ only
    python build_dataset.py --classic       # + live Classic scrape (2000-2011)
    python build_dataset.py --statsnet      # + live StatsNet scrape (2012-now)
    python build_dataset.py --all           # everything

The CSV schema (one row per government response recorded in a register):
    era, committee, inquiry, report_first_tabled, report_last_tabled,
    response_tabled, days_to_respond, days_from_first_report,
    deadline_days, days_overdue, interim_only, source, notes
"""
from __future__ import annotations
import csv, sys, pathlib
from thb_parser import (parse_classic_text, parse_statsnet_text,
                        rows_to_dicts, Row)
import validate as validation

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
FIXTURES = HERE / "fixtures"

FIELDS = ["era", "committee", "inquiry", "report_first_tabled",
          "report_last_tabled", "response_tabled", "days_to_respond",
          "days_from_first_report", "deadline_days", "days_overdue",
          "interim_only", "source", "notes"]


def from_fixtures(include_classic: bool = True,
                  include_statsnet: bool = True) -> list[Row]:
    rows: list[Row] = []
    if include_classic:
        for f in sorted(FIXTURES.glob("classic_*.txt")):
            year = f.stem.split("_")[1]
            rows += parse_classic_text(f.read_text(encoding="utf-8"),
                                       source=f"fixtures/classic/{year}")
    if include_statsnet:
        for f in sorted(FIXTURES.glob("statsnet_*.txt")):
            year = f.stem.split("_")[1]
            rows += parse_statsnet_text(f.read_text(encoding="utf-8"),
                                        source=f"fixtures/statsnet/{year}")
    return rows


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "--fixtures"
    rows: list[Row] = []

    if mode == "--fixtures":
        rows += from_fixtures()
    if mode in ("--classic", "--all"):
        from classic_scraper import scrape as scrape_classic
        rows += scrape_classic()
        # live scrape supersedes the classic fixtures, but the statsnet
        # fixture (2026 register) still carries the modern-era data until
        # the Playwright scraper has been run
        rows += from_fixtures(include_classic=False)
    if mode in ("--statsnet", "--all"):
        from statsnet_scraper import scrape as scrape_statsnet
        rows += scrape_statsnet(2012, 2026)

    # de-duplicate (fixtures overlap live scrapes for the same years)
    seen, unique = set(), []
    for r in rows:
        key = (r.committee, r.inquiry, r.report_last_tabled, r.response_tabled)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    rc = validation.main(unique)
    if rc != 0:
        return rc

    DATA.mkdir(exist_ok=True)
    out = DATA / "responses.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for d in rows_to_dicts(unique):
            w.writerow(d)
    print(f"wrote {out} ({len(unique)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
