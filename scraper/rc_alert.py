"""rc_alert.py — say what the royal commissions steps found, without stopping the run.

The royal commissions index is a second corpus and is not published yet. While
that is true its steps do not gate the weekly rebuild: the pages that ARE
published do not read any of its files, and a draft index that cannot be built
is a reason to tell somebody, not a reason to leave the live registers a week
stale. That decision is written into the workflow as `continue-on-error` on the
royal commissions block, and this is the other half of it — the part that makes
sure a step failing quietly is not the same as a step passing.

    python rc_alert.py --failed        # the block above did not finish
    python rc_alert.py                 # it did; is there anything else to say?
    python rc_alert.py --dry-run       # print, record nothing

Two things are worth an issue.

A step that refused. Every step in that block refuses rather than writes when
what it found does not add up: the register sweep when its own record count
disagrees, the extraction when a report it is told to read has no cached text,
the verifier when less than nine tenths of the index can be found in the
documents it names. Those refusals are the design. Unheard, they are decoration.

A candidate waiting. harvest_royal_commissions.py writes out every record in
the Tabled Documents register that is typed "Royal commission", or whose title
names one of the commissions, and that the seed does not hold — for a person to
accept or reject. The list is empty today. The week a further response or a
corrigendum is tabled it will not be, and nobody is watching the file.

Like batch_alert.py and statsnet_alert.py this never fails the job, and it does
not raise the same candidate twice: the ids it has spoken about are recorded in
data/rc_alerted.json.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from datetime import date

HERE = pathlib.Path(__file__).parent
CANDIDATES = HERE / "data" / "rc_candidates.csv"
STATE = HERE / "data" / "rc_alerted.json"
NOTE = pathlib.Path("/tmp/rc_alert.md")


def read(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def note_for(failed: bool, fresh: list[dict]) -> tuple[str, str]:
    parts: list[str] = []
    if failed:
        parts += [
            "One of the royal commissions steps refused to write.",
            "",
            "Every step in that block refuses rather than publish something it cannot "
            "stand behind: the register sweep when its own record count disagrees with "
            "what it read, the extraction when a report it is told to read has no cached "
            "text or when the report's own stated total is not what was found, and "
            "`verify_rc_index.py` when less than nine tenths of the index can be found "
            "in the documents it names. The run carried on because the index is a draft "
            "and the published registers do not read any of its files.",
            "",
            "The step's own output says which one and why — open the run and read "
            "**Royal commissions (draft — alarms, does not gate)**.",
        ]
    if fresh:
        if parts:
            parts += ["", "---", ""]
        one = len(fresh) == 1
        parts += [
            f"{'A record' if one else f'{len(fresh)} records'} in the Tabled Documents "
            f"register {'looks' if one else 'look'} like {'a document' if one else 'documents'} "
            "of a royal commission, and the seed does not hold "
            f"{'it' if one else 'them'}.",
            "",
            "| OTD | Type | Tabled | Title |",
            "| --- | --- | --- | --- |",
        ]
        for c in fresh[:20]:
            tabled = c.get("tabled_senate") or c.get("tabled_house") or ""
            title = (c.get("title") or "").replace("|", "\\|")[:110]
            parts.append(f"| [{c['id']}]({c.get('url', '')}) | {c.get('type', '')} "
                         f"| {tabled} | {title} |")
        if len(fresh) > 20:
            parts.append(f"| … | | | and {len(fresh) - 20} more in `rc_candidates.csv` |")
        parts += [
            "",
            "### What to do",
            "",
            "Decide, one at a time, whether each belongs to a commission this index "
            "holds. A document that does belongs in `scraper/data/rc_seed.csv` with its "
            "role — report, corrigendum, response, ministerial statement — and, if it is "
            "a response, the report it answers. One that does not belongs in "
            "`rc_not_ours.csv` with the reason, so the candidate list empties and the "
            "next thing to arrive is visible in it.",
        ]
    title = ("A royal commissions step refused" if failed and not fresh else
             "A royal commissions step refused, and a candidate is waiting" if failed else
             "A royal commission document nobody has ruled on" if len(fresh) == 1 else
             f"{len(fresh)} royal commission documents nobody has ruled on")
    parts += [
        "",
        "---",
        "",
        "*Raised by `scraper/rc_alert.py`. The royal commissions index is not published "
        "yet, so its steps alarm rather than stop the weekly rebuild. Candidates already "
        "raised are recorded in `data/rc_alerted.json` and are not raised twice.*",
    ]
    return title, "\n".join(parts)


def main(argv: list[str]) -> int:
    failed, dry = "--failed" in argv, "--dry-run" in argv

    try:
        state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    except Exception as exc:                        # a corrupt file must not stop the job
        print(f"rc_alert: could not read {STATE.name} ({exc}); starting fresh",
              file=sys.stderr)
        state = {}
    said = set(state.get("candidates") or [])

    candidates = read(CANDIDATES)
    fresh = [c for c in candidates if c.get("id") and c["id"] not in said]

    if not failed and not fresh:
        print(f"rc_alert: the block finished and {len(candidates)} candidate(s) are on "
              f"file, none of them new — nothing to say")
        return 0

    title, body = note_for(failed, fresh)
    print(f"rc_alert: {title.lower()}")
    if dry:
        print("\n" + title + "\n\n" + body)
        return 0

    NOTE.write_text(title + "\n---\n" + body, encoding="utf-8")
    if fresh:
        state["candidates"] = sorted(said | {c["id"] for c in fresh})
        state["last_raised"] = date.today().isoformat()
        STATE.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
    print(f"rc_alert: wrote {NOTE}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:                        # never fail the weekly rebuild
        print(f"rc_alert: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(0)
