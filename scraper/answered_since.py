"""answered_since.py — the reports answered since a schedule was printed.

Both registers publish a presiding officer's schedule, and both schedules are
months old by the time anyone reads them. Between the schedule's as-at date and
today the government keeps tabling responses, and every one of those is a report
the register would otherwise publish as unanswered. That is the worst error this
site can make: a departmental officer who finds one answered report on the list
has a reason to dismiss the whole thing, and is right to.

The Senate register had a removal step from the start. The House register did
not, so on 1 September 2026 it was publishing six reports the government had
already answered. This module is the one removal step, used by both, so the two
registers cannot drift apart again.

Three ways a response is tied to the report it answers, in order of strength:

  1. OTD's own `documentLinks`, harvested by harvest_links.py. This is the
     Parliament's statement of which response answers which report. It is right
     by definition, and it covers about 30% of responses.

  2. data/response_report_links_manual.csv — a link checked by hand, with the
     reasoning written down in the file and the date it was checked. Used only
     where OTD has no link and the titles do not carry the match. Every entry
     is a judgement the site has to be able to defend, so it is kept in the
     repository next to the data rather than in code.

  3. The response document's title, which nearly always quotes the report's.
     Strict: four fifths of the report title's distinctive words have to appear
     in the response's title, and the committee has to overlap. Loose matching
     is how an earlier build removed 71 reports against 16 real responses.

Nothing here ever adds a row or changes a status. It removes rows, and only when
a named, dated, citable government document says the report has been answered.
"""
from __future__ import annotations

import csv
import pathlib
import re
from datetime import date

DATA = pathlib.Path(__file__).parent / "data"

# Words that appear in half the titles on the register and so cannot carry a
# match: the scaffolding of committee and bill names.
NOISE = set("""report reports inquiry inquiries into the of and for on a an australian
australia government response responses committee committees joint standing select
legislation references final first second interim provisions bill bills act review
parliamentary house senate""".split())


def _toks(s: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if len(w) > 3}


def _key(s: str) -> set[str]:
    return _toks(s) - NOISE


def responses_since(as_at: date, chamber: str = "") -> list[dict]:
    """Government responses tabled after `as_at`, in the chamber that counts.

    A response tabled in one chamber does not discharge the obligation in the
    other. The President reports on responses "tabled in the Senate"; the
    Speaker on responses presented to the House. Taking the later of the two
    dates — which this did — could remove a joint report from the Senate
    register on the strength of a House tabling the President had not recorded,
    in the government's favour and disclosed nowhere.

    chamber is "senate", "house", or "" for either (which is only right when
    the caller has no register to answer to).
    """
    path = DATA / "response_documents.csv"
    if not path.exists():
        return []
    field = {"senate": ("tabled_senate",), "house": ("tabled_house",)}.get(
        chamber, ("tabled_senate", "tabled_house"))
    cut = as_at.isoformat()
    out = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            tabled = max(r[k] for k in field)
            if tabled > cut:
                out.append({"response_id": r["id"], "title": r["title"],
                            "tabled": tabled[:10]})
    return out


def checked_to() -> str:
    """The latest tabling date on the response list — how current a build is.

    A register is only as current as the responses it has seen. Publishing the
    schedule's date alone implies the register is current to today, which it is
    not: it is current to the last response anyone harvested.
    """
    path = DATA / "response_documents.csv"
    if not path.exists():
        return ""
    with open(path, newline="", encoding="utf-8-sig") as f:
        dates = [max(r["tabled_senate"], r["tabled_house"]) for r in csv.DictReader(f)]
    return max((d[:10] for d in dates if d), default="")


def _links() -> dict[str, list[str]]:
    """report id -> response ids, from OTD's links and the hand-checked file."""
    out: dict[str, list[str]] = {}
    for name in ("response_report_links.csv", "response_report_links_manual.csv"):
        path = DATA / name
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["report_id"]:
                    out.setdefault(r["report_id"], []).append(r["response_id"])
    return out


REPORT_NO = re.compile(r"\breport\s+(?:no\.?\s*)?(\d{1,4})\b", re.I)


def _numbers(text: str) -> set[str]:
    """The report numbers a title carries, if any.

    "Report 505" and "Report 506" differ by one character, and the word test
    cannot see it: tokens of three characters or fewer are dropped, so both
    reduce to the same handful of words. A numbered report may only be matched
    to a response naming the same number.
    """
    return set(REPORT_NO.findall(text))


def finder(as_at: date, chamber: str = ""):
    """Returns find(row) -> the response that answers it, or None.

    `row` needs `title`, `committee`, and `report_otd_id` where one is known.
    """
    responses = responses_since(as_at, chamber)
    by_id = {r["response_id"]: r for r in responses}
    links = _links()

    def find(row: dict) -> dict | None:
        report_id = (row.get("report_otd_id") or "").strip()
        for rid in links.get(report_id, []):
            if rid in by_id:
                return dict(by_id[rid], basis="OTD link")

        t = _key(row.get("title", ""))
        c = _key(row.get("committee", ""))
        n = _numbers(row.get("title", ""))
        if not t:
            return None
        for r in responses:
            rt = _toks(r["title"])
            if len(t & rt) / len(t) < 0.8 or (c and not (c & rt)):
                continue
            # A numbered report is only answered by a response naming that
            # number, and a response that names a number is not answering a
            # report that does not.
            rn = _numbers(r["title"])
            if (n or rn) and n != rn:
                continue
            return dict(r, basis="title match")
        return None

    return find


def apply(rows: list[dict], as_at: date, chamber: str = "") -> tuple[list[dict], list[dict]]:
    """Split rows into those still outstanding and those answered since `as_at`."""
    find = finder(as_at, chamber)
    kept, removed = [], []
    for row in rows:
        hit = find(row)
        if hit:
            removed.append(dict(row, response_id=hit["response_id"],
                                response_tabled=hit["tabled"],
                                response_title=hit["title"],
                                removal_basis=hit["basis"]))
        else:
            kept.append(row)
    return kept, removed


def report(removed: list[dict], register: str) -> None:
    """Print what was removed, and write it where the site can publish it."""
    if not removed:
        print(f"{register}: no report on the register has been answered since "
              "the schedule was printed")
        return
    print(f"{register}: {len(removed)} report(s) answered since the schedule "
          "was printed, removed from the register:")
    for r in sorted(removed, key=lambda x: x["response_tabled"]):
        print(f"  {r['response_tabled']}  OTD {r['response_id']}  "
              f"[{r['removal_basis']}]  {r['title'][:60]}")
    out = DATA / f"answered_since_{register}.csv"
    fields = ["report_tabled", "committee", "title", "report_otd_id",
              "response_id", "response_tabled", "response_title", "removal_basis"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(removed, key=lambda x: x["response_tabled"]))
    print(f"  written to {out.name}")
