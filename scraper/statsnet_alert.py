"""statsnet_alert.py — say when the compliance series has quietly stopped moving.

The register has one step that needs a real browser: the Senate StatsNet page
at aph.gov.au, which is where the compliance series comes from. That page
refuses automated traffic often enough that killing the build over it was
worse than the alternative, so a failed scrape now falls back to the cells
cached from the last successful one.

That is the right behaviour for one week and the wrong one for two months.
The build stays green, the site keeps publishing, and the compliance series
silently stops moving — which looks exactly like a series with nothing to
report. This is the thing that says otherwise.

    python statsnet_alert.py                 # the weekly run
    python statsnet_alert.py --days 21       # a longer rope
    python statsnet_alert.py --dry-run       # print, record nothing

It reads data/statsnet_freshness.json, which statsnet_scraper.py writes on
every run: for each year, the last date the live page actually gave it to us.
If the current year has not been read for STALE_AFTER_DAYS, it writes a note
that the workflow turns into an issue, and records the date so it does not
raise the same complaint every week — once a fortnight is enough to nag and
few enough to be worth reading.

Like batch_alert.py, this never fails the job. A register that stops being
rebuilt because its alarm broke is worse than an alarm that stays quiet.
"""
from __future__ import annotations

import json
import pathlib
import sys
from datetime import date, datetime

HERE = pathlib.Path(__file__).parent
FRESHNESS = HERE / "data" / "statsnet_freshness.json"
NOTE = pathlib.Path("/tmp/statsnet_alert.md")

STALE_AFTER_DAYS = 14


def as_date(s: str | None) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except Exception:
        return None


def note_for(year: int, last: date | None, days: int | None, threshold: int) -> str:
    if last is None:
        said = (f"The live register has **never** been read successfully for {year} "
                f"on a run that recorded it.")
    else:
        said = (f"The live register was last read successfully for {year} on "
                f"**{last.isoformat()}**, {days} days ago.")
    return "\n".join([
        said,
        "",
        f"Every rebuild since then has used the cells cached from that day. The site "
        f"is up, the registers are current, and new responses are still arriving — they "
        f"reach the site through the Tabled Documents API, not through this page. What "
        f"has stopped moving is the compliance series: the by-year figures that come "
        f"from the Senate's own StatsNet register.",
        "",
        "### What to do",
        "",
        "1. Open https://www.aph.gov.au/Parliamentary_Business/Statistics/Senate_StatsNet#/government-responses "
        "in a browser and check the page still exists and still has a Committee column.",
        "2. If it does, dispatch **Update dataset** by hand and read the `Build dataset` step: "
        "the scrape prints why each attempt failed.",
        "3. If the page has been redesigned, the selectors in `scraper/statsnet_scraper.py` "
        "are what need changing — they are documented in `scrape_range`'s docstring, "
        "with the date each was verified against the live page.",
        "",
        "---",
        "",
        f"*Raised by `scraper/statsnet_alert.py`, which speaks when the current year has "
        f"not been read live for {threshold} days. It will not raise this again for "
        f"another {threshold} days. Close the issue once the scrape is working.*",
    ])


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv

    if not FRESHNESS.exists():
        print(f"statsnet_alert: no {FRESHNESS.name} yet; nothing to compare")
        return 0

    try:
        state = json.loads(FRESHNESS.read_text(encoding="utf-8"))
    except Exception as exc:                       # a corrupt file must not stop the job
        print(f"statsnet_alert: could not read {FRESHNESS.name} ({exc}); staying quiet",
              file=sys.stderr)
        return 0

    # the file carries the rope, the command line can override it
    threshold = int(state.get("stale_after_days", STALE_AFTER_DAYS))
    if "--days" in argv:
        threshold = int(argv[argv.index("--days") + 1])

    year = date.today().year
    live = state.get("last_live_scrape", {})

    if not live:
        # The file exists but nothing has ever been recorded. That is the state
        # on the first run after this landed, not a fault worth an issue.
        print("statsnet_alert: nothing recorded yet; staying quiet")
        return 0

    last = as_date(live.get(str(year)))
    days = (date.today() - last).days if last else None

    if last is not None and days is not None and days < threshold:
        print(f"statsnet_alert: {year} read live {days} day(s) ago — fine")
        return 0

    said_before = as_date((state.get("alerted") or {}).get(str(year)))
    if said_before and (date.today() - said_before).days < threshold:
        print(f"statsnet_alert: {year} is stale but was already raised on "
              f"{said_before.isoformat()}; not raising it again yet")
        return 0

    title = (f"The Senate register has not been read for {days} days"
             if days is not None else
             f"The Senate register has never been read successfully for {year}")
    body = note_for(year, last, days, threshold)

    print(f"statsnet_alert: {year} is stale "
          f"({'never read' if days is None else f'{days} days'})")
    if dry:
        print("\n" + title + "\n\n" + body)
        return 0

    NOTE.write_text(title + "\n---\n" + body, encoding="utf-8")
    state.setdefault("alerted", {})[str(year)] = date.today().isoformat()
    FRESHNESS.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
    print(f"statsnet_alert: wrote {NOTE} and recorded the complaint in {FRESHNESS.name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:                       # never fail the weekly rebuild
        print(f"statsnet_alert: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(0)
