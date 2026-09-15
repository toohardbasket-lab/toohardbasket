"""What the documents say about whether anything was done.

A register of what the government *said* invites the obvious next question:
did it happen? An external review put it plainly — accepted is not done — and
suggested recording implementation evidence as dated attributed statements,
without judging success. That is the right shape for this site. The question
this file answers is the one that comes first: is there anything to record?

The answer is almost nothing, and the number is the point. A government
response is a statement of intention. It is written weeks or months after the
report, before the thing it promises has happened, and it is the last document
the government is obliged to produce. Nothing in the process requires it to
come back and say what it did. So the register stops where the government
stopped, and this file measures that rather than asserting it.

Three counts, named separately because they are three different claims:

  stated_done
      A sentence whose subject is the government and whose object is this
      recommendation, saying it has been implemented, actioned or delivered.
      This is the only class that is an implementation claim about the
      recommendation in front of you. It is small enough to have been read in
      full by hand rather than sampled — see docs/implementation-check.md.

  documents_with_an_implementation_section
      Documents whose own text carries a heading like "Implementation status".
      The document is declaring the type of what follows, which is a structural
      fact and not a reading. Counted at the document level because that is
      where the heading lives.

  completed_action_vocabulary
      Answers that use a completed-action verb anywhere — "has established",
      "was completed", "has commenced". This is a count of words, NOT a count
      of implementation, and it is published under that name for one reason: it
      is much larger than the first count, and a reader who saw only the first
      might think the corpus had been searched narrowly. It has not. The gap
      between the two numbers is the size of the judgment this site refuses to
      make, because deciding whether "the Government has established a new
      partnership" means the committee's recommendation was carried out is a
      reading of prose, and no language model reads a document here.

Run:  python implementation_evidence.py
Out:  data/implementation_evidence.json, data/implementation_claims.csv
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "otd_text"
OUT_JSON = DATA / "implementation_evidence.json"
OUT_CSV = DATA / "implementation_claims.csv"

# The actor has to be the government, not the committee and not a state. "The
# Scheme" and "the Department" are the government speaking as the body that
# would act; a committee never says it has implemented its own recommendation.
ACTOR = r"(?:the\s+)?(?:Australian\s+)?Government|Commonwealth|the\s+Scheme|the\s+Department"

# The object has to be THIS recommendation, in the singular. An earlier draft
# allowed "the recommendations" and immediately picked up a response describing
# what it had done about a different committee's report three years earlier:
#
#   Annex A details how the Australian Government has implemented the
#   recommendations accepted … in response to Compassion, Not Commerce.
#
# The words are the government's and they are about implementation, and they
# are still not an answer to the recommendation the row carries. That is an
# attribution failure, which is the failure this site is most careful about,
# and it is why the plural is not admitted. The word boundary after
# "recommendation" is what does it: without it the singular pattern matches the
# first thirteen letters of the plural and admits exactly this sentence.
THIS = (r"this\s+recommendation\b|the\s+recommendation\b"
        r"|recommendation\s+\d+(?:\.\d+)?\b")

DONE = r"implemented|actioned|delivered|completed"

ACTIVE = re.compile(rf"(?:{ACTOR})\s+(?:has|have)\s+(?:already\s+|now\s+)?(?:{DONE})\s+(?:{THIS})",
                    re.I)
PASSIVE = re.compile(rf"(?:{THIS})\s+(?:has|have)\s+(?:already\s+|now\s+)?been\s+(?:{DONE})", re.I)

# A heading the document writes itself. Not a reading: the document is saying
# what kind of thing the next paragraph is.
SECTION = re.compile(r"implementation\s+(?:status|update|progress)\b", re.I)

# Words that describe a finished action, anywhere in the answer. Deliberately
# broad, because this count exists to show how much is NOT being claimed.
COMPLETED_VERB = re.compile(
    r"\b(?:has|have|was|were|is|are)\s+(?:now\s+|already\s+|since\s+)?(?:been\s+)?"
    r"(?:implemented|completed|delivered|established|enacted|introduced|commenced"
    r"|finalised|finalized)\b", re.I)


def sentence_around(text: str, start: int, end: int) -> str:
    """The sentence the match sits in, so the claim is published with its words."""
    lo = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start))
    lo = 0 if lo < 0 else lo + 1
    hi = text.find(". ", end)
    hi = len(text) if hi < 0 else hi + 1
    return " ".join(text[lo:hi].split())


def rows_with_answers() -> list[dict]:
    p = DATA / "recommendations.csv"
    with p.open(newline="", encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if (r.get("government_words") or "").strip()]


def stated_done(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        g = r["government_words"]
        m = ACTIVE.search(g) or PASSIVE.search(g)
        if not m:
            continue
        out.append({
            "response_id": r["source_id"],
            "label": r["label"],
            "response_tabled": r.get("response_tabled", ""),
            "committee": r.get("committee", ""),
            "document_title": r.get("document_title", ""),
            "response_url": r.get("response_url", ""),
            "recommendation": " ".join(r["recommendation"].split()),
            "the_claim": sentence_around(g, m.start(), m.end()),
        })
    out.sort(key=lambda d: (d["response_tabled"], d["response_id"], d["label"]))
    return out


def documents_with_a_section() -> list[str]:
    seen = set()
    if TEXT.exists():
        for p in sorted(TEXT.glob("*.txt")):
            if SECTION.search(p.read_text(encoding="utf-8", errors="ignore")):
                seen.add(p.name.split("_")[0])
    return sorted(seen, key=lambda s: (len(s), s))


def royal_commission_progress_reports() -> list[dict]:
    """Progress reports on the register, and which commission each belongs to.

    Read from the file that records why a commission is not in the index, so
    that this cannot drift from what the royal commissions page says.
    """
    p = DATA / "rc_not_held.csv"
    if not p.exists():
        return []
    out = []
    with p.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if "progress report" in (r.get("why") or "").lower():
                out.append({"commission": r["name"], "short_name": r.get("short_name", ""),
                            "fails": r.get("fails", ""), "why": r.get("why", "")})
    return out


def main() -> int:
    rows = rows_with_answers()
    claims = stated_done(rows)
    sections = documents_with_a_section()
    vocabulary = [r for r in rows if COMPLETED_VERB.search(r["government_words"])]

    summary = {
        "answers_with_government_words": len(rows),
        "stated_done": len(claims),
        "stated_done_responses": sorted({c["response_id"] for c in claims}),
        "documents_with_an_implementation_section": len(sections),
        "documents_with_an_implementation_section_ids": sections,
        "completed_action_vocabulary": len(vocabulary),
        "royal_commission_progress_reports": royal_commission_progress_reports(),
    }

    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(claims[0].keys()) if claims else
                           ["response_id", "label", "response_tabled", "committee",
                            "document_title", "response_url", "recommendation", "the_claim"])
        w.writeheader()
        w.writerows(claims)

    print(f"{len(rows)} answers whose government words could be read")
    print(f"{len(claims)} say this recommendation has been implemented, actioned or delivered")
    for c in claims:
        print(f"    {c['response_tabled']}  OTD {c['response_id']} rec {c['label']}  "
              f"{c['the_claim'][:90]}")
    print(f"{len(sections)} documents carry an implementation heading: {', '.join(sections)}")
    print(f"{len(vocabulary)} answers use a completed-action verb somewhere "
          f"(a count of words, not of implementation)")
    for rc in summary["royal_commission_progress_reports"]:
        print(f"    progress report on the register: {rc['short_name']} — {rc['fails']}")
    print(f"written to {OUT_JSON.name} and {OUT_CSV.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
