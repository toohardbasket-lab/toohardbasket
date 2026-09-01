"""cross_register.py — the reports that are on both registers at once.

A joint committee's report is presented to both houses, so it can sit on the
President's list and the Speaker's list at the same time. That has three
consequences the site has to state rather than leave a reader to discover:

  1. "82 Senate committee reports" and "38 House committee reports" are the
     wrong labels. Most of both lists are joint committee reports — the
     President's own title is "Senate AND JOINT committee reports" — and only a
     handful of the House rows are House committee reports.

  2. The two counts must never be added, and the reason is not the one the site
     was giving. It is not only that three months and six months are different
     obligations; it is that adding them would count the same report twice.

  3. The same report can be overdue on one register and within time on the
     other, because the Senate counts three months from Senate tabling and the
     House six months from House presentation. That looks like a contradiction
     on one site unless the site says why.

Matching is by Tabled Documents id where both rows have one — that is exact.
Where one does not, a report is matched on title and tabling date: four fifths
of the words in common and no more than three weeks apart, which catches the
same report written up differently by the two officers ("Report 485—Cyber
Resilience" against "Report 485: Cyber Resilience").

Runs after prune_answered.py. Adds `joint_committee` and `also_on_other_register`
to both register CSVs, writes data/cross_register.csv listing every pair, and
records the counts in both meta files.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

REGISTERS = [
    {"name": "senate", "ledger": "ledger_v2.csv", "meta": "ledger_meta.json"},
    {"name": "house", "ledger": "house_ledger.csv", "meta": "house_ledger_meta.json"},
]

# How each officer writes a joint committee: the Speaker parenthesises it,
# the President appends it after an em dash, and the standing joint committees
# carry "Parliamentary Joint Committee" or "PJC" in their own names.
JOINT = re.compile(r"\bjoint\b|\bPJC\b", re.I)

# Same report, presented to the two houses on days that need not match.
SAME_WEEKS = 21
SAME_TITLE = 0.8


def words(s: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9]+", " ", s.lower()).split() if len(w) > 2}


def load(name: str) -> list[dict]:
    with (DATA / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def pair(senate: list[dict], house: list[dict]) -> list[tuple[dict, dict, str]]:
    out: list[tuple[dict, dict, str]] = []
    taken_h: set[int] = set()

    by_id = {}
    for i, h in enumerate(house):
        if h["report_otd_id"]:
            by_id[h["report_otd_id"]] = i
    for s in senate:
        i = by_id.get(s["report_otd_id"]) if s["report_otd_id"] else None
        if i is not None:
            out.append((s, house[i], "same report id"))
            taken_h.add(i)

    matched_s = {id(s) for s, _, _ in out}
    for s in senate:
        if id(s) in matched_s:
            continue
        st, sd = words(s["title"]), dt.date.fromisoformat(s["report_tabled"])
        for i, h in enumerate(house):
            if i in taken_h:
                continue
            hd = dt.date.fromisoformat(h["report_tabled"])
            if abs((hd - sd).days) > SAME_WEEKS:
                continue
            ht = words(h["title"])
            if not ht or not st:
                continue
            if len(st & ht) / min(len(st), len(ht)) >= SAME_TITLE:
                out.append((s, h, "title and tabling date"))
                taken_h.add(i)
                break
    return out


def write(name: str, rows: list[dict]) -> None:
    path = DATA / name
    fields = list(rows[0].keys())
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def main() -> int:
    senate, house = load("ledger_v2.csv"), load("house_ledger.csv")
    pairs = pair(senate, house)
    on_both = {id(r) for p in pairs for r in p[:2]}

    for rows in (senate, house):
        for r in rows:
            r["joint_committee"] = str(bool(JOINT.search(r["committee"])))
            r["also_on_other_register"] = str(id(r) in on_both)
    write("ledger_v2.csv", senate)
    write("house_ledger.csv", house)

    with (DATA / "cross_register.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["senate_tabled", "house_tabled", "committee", "title",
                    "report_otd_id", "senate_overdue", "house_overdue", "matched_on"])
        for s, h, how in sorted(pairs, key=lambda p: p[0]["report_tabled"]):
            w.writerow([s["report_tabled"], h["report_tabled"], s["committee"],
                        s["title"], s["report_otd_id"] or h["report_otd_id"],
                        s["overdue"], h["overdue"], how])

    differ = sum(1 for s, h, _ in pairs if s["overdue"] != h["overdue"])
    for reg, rows in ((REGISTERS[0], senate), (REGISTERS[1], house)):
        path = DATA / reg["meta"]
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta.update({
            "joint_committee": sum(1 for r in rows if r["joint_committee"] == "True"),
            "own_chamber": sum(1 for r in rows if r["joint_committee"] == "False"),
            "on_both_registers": len(pairs),
            "deadline_differs_across_registers": differ,
        })
        path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    exact = sum(1 for _, _, how in pairs if how == "same report id")
    print(f"{len(pairs)} reports are on both registers "
          f"({exact} matched on report id, {len(pairs) - exact} on title and date)")
    print(f"  Senate: {sum(1 for r in senate if r['joint_committee'] == 'True')} of "
          f"{len(senate)} rows are joint committee reports")
    print(f"  House:  {sum(1 for r in house if r['joint_committee'] == 'True')} of "
          f"{len(house)} rows are joint committee reports")
    if differ:
        print(f"  {differ} of them are past the deadline on one register and not "
              "on the other — different rules, different tabling dates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
