"""digest.py — one message listing the responses tabled since the last one.

batch_alert.py catches the day the government closes a stack of reports at
once. It cannot catch the other shape: a single report, answered or closed on
an ordinary Tuesday, that waited eleven years to get there. Nothing was
watching for that, and by the time anyone looked it was weeks old.

So this reports what is new — once per run, in one message, and only when
there is something to report. Not one message per response: on 19 March 2026
that would have been twenty-nine of them about a single event that
batch_alert.py already describes better in one.

    python digest.py                  # the scheduled run
    python digest.py --dry-run        # print, record nothing
    python digest.py --all            # ignore the record, describe everything

WHAT THIS DELIBERATELY DOES NOT DO

It does not say whether something is newsworthy. That is a judgement, it
cannot be reproduced, and the register's whole authority rests on every
figure it publishes being mechanical and checkable. Instead this computes the
comparisons a person needs in order to judge for themselves — how long the
wait was against every other wait on file, how many recommendations the
response disposed of, whether it stood alone that day — and orders the list
by the longest wait first. Every number in the message comes from the
published dataset and can be checked against it. The ordering is an ordering
of facts, not a ranking of importance.

WHAT IT OFTEN CANNOT SAY

A response can only be matched to the report it answers where Parliament's
own document link, a check by hand, or the response's own title produce a
match. That is about two in five. Where it fails, the wait is unknown and
this says so rather than estimating it. On 19 March 2026, twenty-two of the
twenty-nine responses were in that state.

Responses already described are recorded in data/digested_responses.json,
which is committed, so nothing is described twice. Everything on file when
this was written is seeded into that record: the point is to hear about the
next one.

Like batch_alert.py, this never fails the job. A register that stops being
rebuilt because its alarm broke is worse than an alarm that stays quiet.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from collections import defaultdict
from datetime import date, datetime

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
RESPONSES = DATA / "response_documents.csv"
REPORTS = DATA / "response_reports.csv"
COVERAGE = DATA / "coverage.csv"
STATE = DATA / "digested_responses.json"
NOTE = pathlib.Path("/tmp/digest.md")

# The Senate has required a response within three months since its resolution
# of 14 March 1973. Ninety-one days is that rule in days, and is only ever
# used to say how far past it a response landed.
DEADLINE_DAYS = 91

MAX_LISTED = 40          # a batch day is described by batch_alert, not here


def read(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def tabled(row: dict) -> str:
    return (row.get("tabled_senate") or row.get("tabled_house") or "").strip()


def as_date(s: str | None):
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def as_int(s, default=None):
    try:
        return int(str(s).strip())
    except Exception:
        return default


def in_words(days: int) -> str:
    """A wait, said the way a person says it."""
    years, rest = divmod(days, 365)
    months = rest // 30
    if years and months:
        return f"{years} year{'s' if years != 1 else ''} {months} month{'s' if months != 1 else ''}"
    if years:
        return f"{years} year{'s' if years != 1 else ''}"
    if months:
        return f"{months} month{'s' if months != 1 else ''}"
    return f"{days} day{'s' if days != 1 else ''}"


def read_state() -> dict:
    if not STATE.exists():
        return {"seen": []}
    try:
        s = json.loads(STATE.read_text(encoding="utf-8"))
        s.setdefault("seen", [])
        return s
    except Exception as exc:                       # a corrupt file must not stop the job
        print(f"digest: could not read {STATE.name} ({exc}); describing nothing new",
              file=sys.stderr)
        return {"seen": ["*"]}


CLASSES = {
    "proforma_closure": "Closed the report with the passage-of-time sentence, "
                        "taking a position on nothing",
    "partial_proforma": "Closed part of the report with the passage-of-time sentence",
    "substantive": "Answered substantively",
}


def describe(r: dict, ctx: dict) -> str:
    """One response, as the facts that let a person judge it."""
    rid = (r.get("id") or "").strip()
    day = tabled(r)
    dept = (r.get("department") or r.get("author") or "").strip()
    title = (r.get("title") or "(no title)").strip()
    url = (r.get("url") or "").strip()

    head = f"### [{title}]({url})" if url else f"### {title}"
    lines = [head, ""]
    lines.append(f"Tabled **{day}**" + (f" by {dept}." if dept else "."))
    lines.append("")
    lines.append(f"- {CLASSES.get(r.get('classification',''), 'Classification unknown')}.")

    hits = as_int(r.get("template_hits"), 0) or 0
    if hits:
        times = "once" if hits == 1 else f"{hits} times"
        lines.append(f"- The passage-of-time sentence appears {times}.")

    link = ctx["reports"].get(rid, {})
    rep_tabled = as_date(link.get("report_tabled"))
    resp_tabled = as_date(day)
    if rep_tabled and resp_tabled:
        wait = (resp_tabled - rep_tabled).days
        pct = ctx["percentile"](wait)
        lines.append(
            f"- Waited **{in_words(wait)}** ({wait:,} days) from the report tabled "
            f"{rep_tabled.isoformat()} — longer than {pct}% of the "
            f"{ctx['n_waits']} responses on file whose report can be identified.")
        over = wait - DEADLINE_DAYS
        if over > 0:
            lines.append(f"- That is {over:,} days past the three-month rule.")
        if link.get("report_title"):
            lines.append(f"- Answers: *{link['report_title']}*.")
    else:
        lines.append("- The report this answers could not be identified, so no wait "
                     "is shown and none is estimated.")

    cov = ctx["coverage"].get(rid)
    if cov:
        recs = as_int(cov.get("recommendations"), 0) or 0
        pos = as_int(cov.get("position_stated"), 0) or 0
        if recs:
            share = f"{round(100 * pos / recs)}%"
            lines.append(f"- {recs} recommendations indexed; the government stated a "
                         f"position on {pos} of them ({share}).")
        if cov.get("committee"):
            lines.append(f"- Committee: {cov['committee']}.")

    same = ctx["by_day"].get(day, 0)
    if same <= 1:
        lines.append("- The only response tabled that day.")
    else:
        closures = ctx["closures_by_day"].get(day, 0)
        lines.append(f"- One of {same} responses tabled that day"
                     + (f", {closures} of them closures." if closures else "."))
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    everything = "--all" in argv

    rows = read(RESPONSES)
    if not rows:
        print(f"digest: no {RESPONSES.name}; nothing to describe")
        return 0

    state = read_state()
    seen = set(state.get("seen", []))
    if "*" in seen:                                # unreadable state file
        return 0

    fresh = [r for r in rows
             if everything or (r.get("id") or "").strip() not in seen]
    fresh = [r for r in fresh if tabled(r)]
    if not fresh:
        print(f"digest: nothing new ({len(seen)} responses already described)")
        return 0

    # --- context every entry is measured against ---------------------------
    reports = {(r.get("response_id") or "").strip(): r for r in read(REPORTS)}
    coverage = {(r.get("response_id") or "").strip(): r for r in read(COVERAGE)}

    waits = []
    for r in rows:
        link = reports.get((r.get("id") or "").strip(), {})
        a, b = as_date(link.get("report_tabled")), as_date(tabled(r))
        if a and b:
            waits.append((b - a).days)
    waits.sort()

    def percentile(w: int) -> int:
        if not waits:
            return 0
        below = sum(1 for x in waits if x < w)
        return round(100 * below / len(waits))

    by_day, closures_by_day = defaultdict(int), defaultdict(int)
    for r in rows:
        d = tabled(r)
        if d:
            by_day[d] += 1
            if r.get("classification") == "proforma_closure":
                closures_by_day[d] += 1

    ctx = {"reports": reports, "coverage": coverage, "percentile": percentile,
           "n_waits": len(waits), "by_day": by_day, "closures_by_day": closures_by_day}

    # --- order: the longest wait first, then the most recommendations -------
    def order_key(r: dict):
        link = reports.get((r.get("id") or "").strip(), {})
        a, b = as_date(link.get("report_tabled")), as_date(tabled(r))
        wait = (b - a).days if a and b else -1
        cov = coverage.get((r.get("id") or "").strip(), {})
        return (wait, as_int(cov.get("recommendations"), 0) or 0,
                as_int(r.get("template_hits"), 0) or 0)

    fresh.sort(key=order_key, reverse=True)
    shown, hidden = fresh[:MAX_LISTED], fresh[MAX_LISTED:]

    n = len(fresh)
    closures = sum(1 for r in fresh if r.get("classification") == "proforma_closure")
    longest = order_key(fresh[0])[0]
    title = (f"{n} response{'s' if n != 1 else ''} tabled"
             + (f" — the longest waited {in_words(longest)}" if longest > 0 else ""))

    body = [
        f"**{n}** response{'s' if n != 1 else ''} to committee reports "
        f"{'have' if n != 1 else 'has'} been tabled since the last digest"
        + (f", {closures} of them closing the report with the passage-of-time "
           f"sentence." if closures else "."),
        "",
        "Ordered by the longest wait first. Nothing below is a judgement about "
        "whether something is newsworthy — every figure comes from the published "
        "dataset and can be checked against it.",
        "",
    ]
    body += [describe(r, ctx) + "\n" for r in shown]
    if hidden:
        body.append(f"*{len(hidden)} further response(s) not listed. A day this size "
                    f"is described in full by `batch_alert.py`.*")
    body += [
        "---",
        "",
        "*Raised by `scraper/digest.py` on the run that first saw these responses. "
        "Close this issue once you have read it; these will not be described again.*",
    ]

    print(f"digest: {n} new response(s); longest wait "
          f"{longest if longest > 0 else 'unknown'}")
    if dry:
        print("\n" + title + "\n\n" + "\n".join(body))
        return 0

    NOTE.write_text(title + "\n---\n" + "\n".join(body), encoding="utf-8")
    state["seen"] = sorted(seen | {(r.get("id") or "").strip() for r in fresh})
    STATE.write_text(json.dumps(state, indent=1) + "\n", encoding="utf-8")
    print(f"digest: wrote {NOTE} and recorded {len(fresh)} response(s) in {STATE.name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as exc:                       # never fail the rebuild
        print(f"digest: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(0)
