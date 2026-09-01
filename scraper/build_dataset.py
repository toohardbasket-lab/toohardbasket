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
import csv, re, sys, pathlib
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

    # De-duplicate. Fixtures overlap live scrapes for the same years, and the
    # two parsers do not always split a wrapped register line at the same
    # point: the 2026 fixture read "Access to" as the inquiry and "Australian
    # Parliament House by lobbyists Finance and Public Administration
    # References Committee" as the committee, where the live scrape read them
    # the right way round. Both rows describe one response, and a key made of
    # the two fields separately cannot see it — 28 responses were counted
    # twice, which moved the compliance rate, the median and every year count.
    #
    # So the second pass keys on the words rather than the fields: same report
    # date, same response date, and the same set of words across committee and
    # inquiry together, however they were divided between the two. Where a
    # fixture row and a live row collide, the live row wins, because it is the
    # one whose split is right.
    def words(r) -> frozenset:
        text = f"{r.committee} {r.inquiry}".lower()
        return frozenset(w for w in re.sub(r"[^a-z0-9]+", " ", text).split() if len(w) > 3)

    def loose(r) -> tuple:
        return (r.report_last_tabled, r.response_tabled, words(r))

    # Where a fixture row and a live row are the same response, drop the
    # fixture one — the live scrape is the one whose split is right. Done as a
    # pre-pass rather than by sorting, so the order of everything else, and so
    # the weekly diff, stays readable.
    live = {loose(r) for r in rows
            if r.report_last_tabled and r.response_tabled
            and not r.source.startswith("fixtures")}

    seen, unique = set(), []
    for r in rows:
        dated = bool(r.report_last_tabled and r.response_tabled)
        if dated and r.source.startswith("fixtures") and loose(r) in live:
            continue
        exact = (r.committee, r.inquiry, r.report_last_tabled, r.response_tabled)
        if exact in seen or (dated and loose(r) in seen):
            continue
        seen.add(exact)
        if dated:
            seen.add(loose(r))
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
