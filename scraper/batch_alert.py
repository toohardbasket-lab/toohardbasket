"""batch_alert.py — say when the government closed a batch of reports in one day.

The register's most reportable event is not a number on a page, it is a day: a
sitting Tuesday on which the government tables a stack of responses and most of
them dispose of the committee's report with the passage-of-time sentence. It has
happened fifteen times since 2022 and the largest, 13 August 2024, closed
thirty-nine reports with nothing else in the batch. Those days are visible in the
dataset the moment the job reads them, and were being found weeks later by
looking.

So this runs in the rebuild and writes a note when a day of five or more
form-letter closures appears that it has not already reported. The workflow turns
that note into a GitHub issue, which is an email.

    python batch_alert.py                    # the scheduled run
    python batch_alert.py --threshold 8      # a quieter bar
    python batch_alert.py --dry-run          # print, record nothing

Days already reported are kept in data/alerted_batches.json, committed with the
rest of the dataset, so a day is never reported twice. Every day that already
qualified when this was written is seeded into that file: the point is to hear
about the next one, not to be told fifteen times about the last four years.

This never fails the job. A register that stops being rebuilt because its alarm
broke is worse than an alarm that stays quiet.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from collections import defaultdict

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
RESPONSES = DATA / "response_documents.csv"
STATE = DATA / "alerted_batches.json"
NOTE = pathlib.Path("/tmp/batch_alert.md")

DEFAULT_THRESHOLD = 5


def tabled(row: dict) -> str:
    return (row.get("tabled_senate") or row.get("tabled_house") or "").strip()


def read_state() -> dict:
    if not STATE.exists():
        return {"reported": [], "threshold": DEFAULT_THRESHOLD}
    try:
        s = json.loads(STATE.read_text(encoding="utf-8"))
        s.setdefault("reported", [])
        return s
    except Exception as exc:                       # a corrupt file must not stop the job
        print(f"batch_alert: could not read {STATE.name} ({exc}); reporting nothing new",
              file=sys.stderr)
        return {"reported": ["*"], "threshold": DEFAULT_THRESHOLD}


def note_for(day: str, closures: list[dict], whole_day: list[dict]) -> str:
    """The issue body: what a person needs to decide whether it is a story."""
    depts = sorted({(r.get("department") or r.get("author") or "").strip()
                    for r in whole_day} - {""})
    others = [r for r in whole_day if r not in closures]
    lines = [
        f"On **{day}** the government tabled **{len(whole_day)} responses** to committee "
        f"reports. **{len(closures)}** of them closed the report with the passage-of-time "
        f"sentence, taking a position on nothing.",
        "",
    ]
    if len(depts) == 1:
        lines.append(f"Every one came from **{depts[0]}**.")
    elif depts:
        lines.append(f"From {len(depts)} departments: {', '.join(depts)}.")
    if others:
        lines.append(f"The other {len(others)} did something else. What they were, and whose "
                     f"bills they answered, is usually the other half of the story.")
    lines += ["", "### Closed with the form letter", ""]
    for r in sorted(closures, key=lambda r: r.get("title", "")):
        hits = r.get("template_hits") or "0"
        times = "once" if hits == "1" else f"{hits} times"
        lines.append(f"- [{r.get('title','(no title)')}]({r.get('url','')}) — the sentence {times}")
    if others:
        lines += ["", "### Answered some other way", ""]
        for r in sorted(others, key=lambda r: r.get("title", "")):
            lines.append(f"- [{r.get('title','(no title)')}]({r.get('url','')}) "
                         f"({r.get('classification','')})")
    lines += [
        "",
        "---",
        "",
        "The comparison a reporter asks for first — whether a day this size is unusual — is in "
        "the dataset: group `data/response_documents.csv` by tabling date.",
        "",
        "*Raised by `scraper/batch_alert.py`. Close this issue once the day has been looked at; "
        "it will not be raised again.*",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    threshold = DEFAULT_THRESHOLD
    if "--threshold" in argv:
        threshold = int(argv[argv.index("--threshold") + 1])
    dry = "--dry-run" in argv

    if not RESPONSES.exists():
        print(f"batch_alert: no {RESPONSES.name}; nothing to check")
        return 0

    with RESPONSES.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if tabled(r):
            by_day[tabled(r)].append(r)

    state = read_state()
    already = set(state.get("reported", []))
    if "*" in already:                             # unreadable state file
        return 0

    fresh = []
    for day, whole in sorted(by_day.items()):
        closures = [r for r in whole if r.get("classification") == "proforma_closure"]
        if len(closures) >= threshold and day not in already:
            fresh.append((day, closures, whole))

    if not fresh:
        print(f"batch_alert: no new day with {threshold} or more closures "
              f"({len(already)} already reported)")
        return 0

    body = "\n\n".join(note_for(d, c, w) for d, c, w in fresh)
    title = (f"{len(fresh[0][1])} reports closed with the form letter on {fresh[0][0]}"
             if len(fresh) == 1 else
             f"{len(fresh)} days of batch closures not yet looked at")

    print(f"batch_alert: {len(fresh)} new day(s) at or over {threshold}: "
          f"{', '.join(d for d, _, _ in fresh)}")
    if dry:
        print("\n" + title + "\n\n" + body)
        return 0

    NOTE.write_text(title + "\n---\n" + body, encoding="utf-8")
    state["reported"] = sorted(already | {d for d, _, _ in fresh})
    state["threshold"] = threshold
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    print(f"batch_alert: wrote {NOTE} and recorded the day in {STATE.name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:                       # never fail the rebuild
        print(f"batch_alert: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(0)
