"""Which government a recommendation names, and which one answered it.

This site's registers are Commonwealth. The committees are committees of the
Commonwealth Parliament, the responses are Commonwealth government responses,
and the deadlines are the two chambers' own. That is a limit, not a claim about
importance, and it was not stated anywhere a reader would see it until an
external review on 13 September 2026 pointed out that a register presented as
national has to say which body it holds to account.

Saying so in prose is easy. What is worth counting is the gap the limit leaves,
and there are two measurable parts of it.

  names another government   A recommendation can name a state, a territory or
                             a council in its own words. Naming is not the same
                             as being addressed to — a recommendation can ask
                             the Commonwealth to work WITH the states — and
                             nothing here decides who a recommendation is for.
                             The count says how often another government is in
                             the frame at all.

  the answer points          The government's own answer can say the matter
  elsewhere                  belongs to somebody else: "this is a matter for
                             state and territory governments". Those are the
                             rows where the limit bites hardest, because the
                             Commonwealth is the only government this site can
                             read and the Commonwealth has just said it is not
                             the one who would act. Where such a row ALSO
                             carries a stated position, the index shows an
                             acceptance of something the government says is not
                             its to do, and the site should say so rather than
                             leave the reader to notice.

Neither regex decides anything about a recommendation. They match words in the
documents, the matched words are written out beside every row, and the rows are
published so the reading can be checked.

Usage:
    python jurisdiction.py
Writes data/jurisdiction.json (the counts) and data/jurisdiction.csv (the rows
whose answer points elsewhere, with the words that matched).
"""
from __future__ import annotations

import csv
import datetime
import json
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

# The governments this site cannot read. Spelled out rather than inferred: a
# bare "Victoria" is a place and a person's name as often as a government, so
# every state and territory has to be named AS a government to count.
JURISDICTION = (r"(?:New South Wales|Victorian?|Queensland|Western Australian?"
                r"|South Australian?|Tasmanian?|Northern Territory"
                r"|Australian Capital Territory)")
OTHER_GOVERNMENT = re.compile(
    r"\bstates?\s+and\s+territor(?:y|ies)\b"
    r"|\bstate\s+or\s+territory\b"
    r"|\bstate,?\s+territory\b"
    r"|\b" + JURISDICTION + r"\s+(?:Government|Governments|Parliament)\b"
    r"|\bgovernments?\s+of\s+" + JURISDICTION + r"\b"
    r"|\blocal\s+governments?\b", re.I)

# The government saying, in its answer, that the matter is somebody else's.
# Anchored to a phrase of responsibility and to one of those governments, with
# only a short gap between them, so "works with the states" does not match:
# working with somebody is not handing the matter to them.
#
# SHARED is the guard that gap needs, and it is the whole difference between
# this measure and a wrong one. "A responsibility of all Australian governments
# and that states and territories lead delivery", "the responsibility of
# Commonwealth, state and territory governments", "sits with both the
# Australian Government and state and territory authorities" — each is the
# Commonwealth including itself, not excusing itself. Four rows read the other
# way until every one of these words was in the guard.
# "Western Australian Government" and "South Australian Government" are two of
# the governments this measure is about, and both end in the words the guard
# looks for, so the guard has to refuse those two prefixes explicitly.
SHARED = (r"(?:all\s+(?:Australian\s+)?governments|shared|jointly|joint\b|both\b"
          r"|Commonwealth|(?<!Western )(?<!South )Australian\s+Government"
          r"|Federal\s+Government)")
POINTS_ELSEWHERE = re.compile(
    r"\b(?:(?:principally\s+|primarily\s+|largely\s+|solely\s+|a\s+|is\s+a\s+)*"
    r"matters?\s+for"
    r"|(?:the\s+(?:primary\s+)?)?responsibility\s+of"
    r"|(?:falls|fall|lies|rests|sits)\s+(?:with|within)"
    r"|within\s+the\s+(?:sole\s+)?(?:remit|purview|responsibility|jurisdiction)\s+of)"
    r"[^.]{0,40}?"
    r"(?:states?\s+and\s+territor(?:y|ies)|state\s+or\s+territory|state,?\s+territory"
    r"|" + JURISDICTION + r"|local\s+governments?)", re.I)
SHARED_RE = re.compile(SHARED, re.I)


def sentence_around(text: str, start: int, end: int) -> str:
    """The full stop to full stop sentence a match sits in."""
    lo = text.rfind(".", 0, start) + 1
    hi = text.find(".", end)
    return text[lo:hi if hi != -1 else len(text)].strip()


def points_elsewhere(words: str) -> "re.Match[str] | None":
    """A match only where the SENTENCE hands the matter over.

    Reading the whole sentence rather than the gap between two phrases is what
    makes this conservative. "Established pest and weed management is a shared
    responsibility between landholders, community, industry and governments,
    noting it is primarily the responsibility of state and territory
    governments" contains a clean hand-over and is not one: the sentence has
    already called the responsibility shared, and a sentence that does is not
    counted here however it goes on.
    """
    for m in POINTS_ELSEWHERE.finditer(words):
        if not SHARED_RE.search(sentence_around(words, m.start(), m.end())):
            return m
    return None


def flat(s: str) -> str:
    return " ".join((s or "").split())


def read(name: str) -> list[dict]:
    with open(DATA / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> int:
    states = {(r["source"], r["source_id"], r["label"], r["recommended_by"]): r
              for r in read("recommendation_positions.csv")}

    names: Counter = Counter()
    elsewhere: Counter = Counter()
    rows: list[dict] = []
    total = 0
    for r in read("recommendations.csv"):
        s = states.get((r["source"], r["source_id"], r["label"], r.get("recommended_by") or ""))
        if not s:
            continue
        total += 1
        rec, gov = flat(r["recommendation"]), flat(r["government_words"])
        if OTHER_GOVERNMENT.search(rec):
            names["total"] += 1
            names[s["state"]] += 1
        m = points_elsewhere(gov)
        if not m:
            continue
        elsewhere["total"] += 1
        elsewhere[s["state"]] += 1
        rows.append({
            "source_id": r["source_id"], "label": r["label"],
            "state": s["state"], "verdict": s["verdict"],
            "department": r["department"] or r["committee"],
            "the_words_that_point_elsewhere": m.group(0),
            "the_sentence_they_are_in": sentence_around(gov, m.start(), m.end())[:400],
            "recommendation": rec[:300], "government_words": gov[:400],
            "url": r["response_url"] or r["url"],
        })

    out = DATA / "jurisdiction.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "source_id", "label", "state", "verdict", "department",
            "the_words_that_point_elsewhere", "the_sentence_they_are_in",
            "recommendation", "government_words", "url"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["source_id"], r["label"])))

    summary = {
        "measured": datetime.date.today().isoformat(),
        "recommendations": total,
        "names_another_government": names["total"],
        "answer_points_elsewhere": elsewhere["total"],
        # The rows that matter most: the answer says the matter is somebody
        # else's AND the index still shows a Commonwealth position on it.
        "points_elsewhere_with_a_position": elsewhere["position"],
        "points_elsewhere_noted": elsewhere["noted"],
    }
    with open(DATA / "jurisdiction.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    print(f"{total} recommendations in the index")
    print(f"  {names['total']:>5}  name a state, territory or local government in their own words")
    print(f"  {elsewhere['total']:>5}  are answered in words that say the matter is one of theirs")
    print(f"  {elsewhere['position']:>5}  of those carry a stated Commonwealth position anyway")
    print(f"  {elsewhere['noted']:>5}  of those are noted without one")
    print(f"wrote {out} and {DATA / 'jurisdiction.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
