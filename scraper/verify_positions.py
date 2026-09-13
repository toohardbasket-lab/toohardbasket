"""What can be checked by code about the join between a recommendation and
the government's answer to it — and what cannot.

verify_recommendations.py proves one half: every published recommendation was
found, verbatim, under the number it claims. The other half is the join
coverage.py makes afterwards — that a passage of the response belongs to THAT
recommendation and not the one above it. That is the join the one known false
positive broke, on 8 September 2026: a real verdict word, correctly read,
attached to the wrong row.

A first version of this file tested whether the recommendation's own words sit
just above the government's words in the document. Every row passed, and the
test was worthless: extract_recommendations.py cuts one segment at the
recommendation's heading and splits it at the handover, so the recommendation
is above the answer BY CONSTRUCTION. A test that cannot fail is not evidence,
and publishing its 100% would have been the same overclaiming this file exists
to retire. It was dropped.

What is left are three things that can fail, and one that cannot but is worth
stating because it says what the construction actually guarantees:

  begins at a handover      every position row's words start at an explicit
  (cannot fail)             handover in the document — "Australian Government
                            response", "Response:", or a bare verdict. Where
                            the extractor finds no handover it records no
                            government words at all, so a row with a stated
                            position always has a marked answer under it.

  verdict near the head     how far into those words the verdict sits. A
  (can fail)                verdict in the first sentence is the answer to
                            this recommendation. One three hundred characters
                            down is the kind that turned out, in September, to
                            be about something else.

  runs on                   whether the words attributed to one row contain
  (can fail, with limits)   another recommendation's opening words from the
                            same document — the signature of a segment that
                            swallowed the recommendation below it. The limit:
                            a run-on happens because a label was missed, and a
                            missed label usually means there is no row to
                            compare against. This catches only the cases where
                            the label was found somewhere else in the document.

  other numbers named       whether the words name a different recommendation
  (can fail)                number. Sometimes legitimate ("as with our answer
                            to recommendation 4"), so this is reported, not
                            failed — a list to read, not a verdict.

None of this measures an error rate. Only people reading response documents
can do that; qa_positions.py builds the sheet for it.

Usage:
    python verify_positions.py
Writes data/position_checks.csv (every row flagged) and data/position_checks.json
(the counts, which the methods page reads so they cannot go stale).
"""
from __future__ import annotations

import csv
import datetime
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from coverage import find

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

# A verdict this far into the government's words is not the answer's opening
# sentence. It may still be the right answer; it is the kind that needs eyes.
FAR = 200
# The slice of a recommendation used to recognise it inside another row's
# answer. Long enough not to match boilerplate openings.
OPENING = 60
OTHER_NUMBER = re.compile(r"\brecommendations?\s+(?:no\.?\s*)?(\d{1,3})\b", re.I)


def flat(s: str) -> str:
    return " ".join((s or "").split())


def read(name: str) -> list[dict]:
    with open(DATA / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> int:
    states = {(r["source"], r["source_id"], r["label"], r["recommended_by"]): r
              for r in read("recommendation_positions.csv")}
    rows = read("recommendations.csv")

    siblings: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["source"] == "response":
            siblings[r["source_id"]].append(r)

    counts: Counter = Counter()
    flagged: list[dict] = []
    for r in rows:
        s = states.get((r["source"], r["source_id"], r["label"], r.get("recommended_by") or ""))
        if not s or s["state"] != "position":
            continue
        counts["rows with a stated position"] += 1
        said = flat(r["government_words"])
        label = str(r["label"]).strip()

        m = find(said, r["label"])
        distance = m.start() if m else -1
        if distance < 0:
            counts["no verdict found on a second reading"] += 1
        elif distance >= FAR:
            counts[f"verdict {FAR}+ characters into the answer"] += 1

        ran_on = ""
        for other in siblings[r["source_id"]]:
            if other is r:
                continue
            a = flat(other["recommendation"])
            if len(a) >= OPENING and a[:OPENING] in said:
                ran_on = other["label"]
                break
        if ran_on:
            counts["runs on into another recommendation"] += 1

        others = sorted({n for n in OTHER_NUMBER.findall(said) if n != label})
        if others:
            counts["names another recommendation number"] += 1

        why = "; ".join(x for x in (
            "no verdict found on a second reading" if distance < 0 else "",
            f"verdict {distance} characters in" if distance >= FAR else "",
            f"runs on into recommendation {ran_on}" if ran_on else "",
            f"names recommendation {', '.join(others)}" if others else "") if x)
        if why:
            flagged.append({
                "source_id": r["source_id"], "label": label, "verdict": s["verdict"],
                "why": why, "department": r["department"] or r["committee"],
                "recommendation": flat(r["recommendation"])[:300],
                "government_words": said[:400],
                "url": r["response_url"] or r["url"]})

    out = DATA / "position_checks.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source_id", "label", "verdict", "why", "department",
                                          "recommendation", "government_words", "url"])
        w.writeheader()
        w.writerows(sorted(flagged, key=lambda r: (r["source_id"], r["label"])))

    total = counts["rows with a stated position"]
    summary = {
        "checked": datetime.date.today().isoformat(),
        "far_threshold": FAR,
        "rows": total,
        # Not a test: a row whose extraction found no handover records no
        # government words, so it cannot reach this count in the first place.
        "begins_at_a_handover": total,
        "no_verdict_on_a_second_reading": counts["no verdict found on a second reading"],
        "verdict_far_into_the_answer": counts[f"verdict {FAR}+ characters into the answer"],
        "runs_on_into_another_recommendation": counts["runs on into another recommendation"],
        "names_another_recommendation_number": counts["names another recommendation number"],
        "flagged_for_reading": len(flagged),
    }
    with open(DATA / "position_checks.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    print(f"{total} rows with a stated position")
    print(f"  {total:>5}  begin at an explicit handover in the document "
          f"(by construction — a row without one records no words)")
    for k in ("no verdict found on a second reading",
              f"verdict {FAR}+ characters into the answer",
              "runs on into another recommendation",
              "names another recommendation number"):
        print(f"  {counts[k]:>5}  {k}")
    print(f"wrote {out} — {len(flagged)} rows flagged for reading")
    print(f"wrote {DATA / 'position_checks.json'}")
    print("None of this is an error rate. qa_positions.py builds the sheet that measures one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
