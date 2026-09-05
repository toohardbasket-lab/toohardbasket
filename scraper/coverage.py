"""coverage.py — for each recommendation the index holds, did the government's
response state a position on it?

Run from the repository root or from scraper/:

    python coverage.py

Reads  data/recommendations.csv, data/response_documents.csv, data/scope_exclusions.csv
Writes data/coverage.csv                  one row per response document
       data/coverage_summary.json         totals, by year and by government
       data/recommendation_positions.csv  one row per recommendation: its state

Definition. A recommendation has a *stated position* when the government's own
words about it say that the recommendation is supported, agreed, accepted,
endorsed, rejected, declined, not supported, not agreed, not accepted, or
implemented — in full, in part or in principle. The test is mechanical: a
verdict word of that family used of the recommendation, either as a label at
the start ("Supported in principle") or as a verb whose object is the
recommendation ("The Government does not agree to this recommendation"). It
is not a judgement about whether the position was a good one, or whether
"supports in principle" means much; "supports the intent" counts, because it
is a position, and the words are on the search page for anyone to weigh.

Every other recommendation is in one of four states, each a fact about the
document rather than an opinion about it:

  noted           the government's words are there, but no verdict word is used
                  of the recommendation — typically "The Government notes this
                  recommendation" followed by a description of existing policy
  form letter     the passage-of-time template, which takes no position
  not individual  the response does not set this recommendation out at all;
                  the recommendation was read from the committee's report
  unreadable      the response quotes the recommendation but its words about it
                  could not be separated from the recommendation's own text

The coverage rate is stated positions over recommendations in the first three
states. Unreadable rows are excluded from both sides and counted separately,
because nothing can be said about them either way. Recommendations that name
another author (a dissenting or minority report) are excluded throughout: a
government owes the committee a response, not the minority.

Each stated position is also given the government's own verdict word, and
nothing more: "accepted" when the word is supported, agreed, accepted,
endorsed or implemented with no qualifier; "in part or in principle" when the
same sentence qualifies it (in principle, in part, partially, partly, broadly,
generally); "not accepted" when the word is negated (does not support, not
agreed, cannot accept) or is reject, decline or disagree. The verdict is read
from the sentence the verdict word is in, not the whole response, so a later
"does not" about something else cannot flip it.

Why this is a floor on positions and a ceiling on their absence: a response
that commits to action without using a verdict word ("The Government will
legislate this in 2027") is counted as noted, not as a position, because the
test cannot see it. The mechanical test errs that way on purpose, so the
figure published as "no position stated" can be too high but the figure
published as "position stated" cannot be inflated by the method.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).resolve().parent
CANDIDATES = [HERE / "data", HERE / "scraper" / "data", HERE.parent / "scraper" / "data"]
DATA = next((p for p in CANDIDATES if (p / "recommendations.csv").exists()), None)
if DATA is None:
    sys.exit("cannot find scraper/data — run from the repository root or from scraper/")

GOVERNMENTS = [
    ("Howard", "1996-03-11", "2007-12-03"),
    ("Rudd / Gillard", "2007-12-03", "2013-09-18"),
    ("Abbott / Turnbull / Morrison", "2013-09-18", "2022-05-23"),
    ("Albanese", "2022-05-23", "2099-01-01"),
]

VERDICT = (r"(?:support|supported|supports|agree|agreed|agrees|accept|accepted|accepts|"
           r"endorse|endorsed|endorses|reject|rejected|rejects|decline|declined|declines|"
           r"disagree|disagreed|disagrees|not\s+supported|not\s+agreed|not\s+accepted|"
           r"partially\s+(?:supported|agreed|accepted)|implemented)")
QUAL = r"(?:\s+(?:in[-\s]principle|in[-\s]part|partially|in\s+full))?"

# A verdict label at the very start of the government's words: "Supported",
# "Agreed in part.", "Not supported", "Supported in principle The Government…"
LABEL = re.compile(r"^\W*(?:the\s+)?(?:australian\s+)?(?:government\s+)?" + VERDICT + QUAL + r"\b", re.I)

# A verdict verb whose object is the recommendation, within a short span:
# "supports this recommendation", "does not agree to the recommendation",
# "accepts the Committee's recommendations in principle", "agrees with Recommendation 4".
VERB = re.compile(
    r"\b(?:does\s+not\s+|do\s+not\s+|did\s+not\s+|cannot\s+|can\s+not\s+|will\s+not\s+|is\s+unable\s+to\s+|"
    r"partially\s+|broadly\s+|generally\s+)?"
    + VERDICT + r"(?:\s+(?:to|with))?" + QUAL +
    r"(?:\s+(?:with|to))?\s+(?:[\w’'-]+\s+){0,4}?recommendations?\b", re.I)

# "The recommendation has been implemented" / "This recommendation is implemented".
IMPLEMENTED = re.compile(r"\brecommendations?\b[^.]{0,60}\b(?:has|have|had|is|are|was|were)\s+"
                         r"(?:been\s+|already\s+|now\s+|since\s+been\s+|partially\s+|fully\s+)*implemented\b", re.I)

TEMPLATE = re.compile(r"passage\s+of\s+time", re.I)


def position(words: str) -> bool:
    w = words.strip()
    if not w:
        return False
    return bool(LABEL.match(w) or VERB.search(w) or IMPLEMENTED.search(w))


NEGATED = re.compile(r"(?:does\s+not|do\s+not|did\s+not|cannot|can\s+not|will\s+not|is\s+unable\s+to|"
                     r"not\s+supported|not\s+agreed|not\s+accepted|reject|declin|disagree)", re.I)
QUALIFIED = re.compile(r"\b(?:in[-\s]principle|in[-\s]part|partially|partly|broadly|generally)\b", re.I)


def verdict(words: str) -> str:
    """The government's own verdict word, sorted three ways, for a row that
    has a stated position: 'accepted', 'in part or in principle', or
    'not accepted'. '' for a row with no position."""
    w = words.strip()
    if not w:
        return ""
    m = LABEL.match(w) or VERB.search(w) or IMPLEMENTED.search(w)
    if not m:
        return ""
    if NEGATED.search(m.group(0)):
        return "not accepted"
    # The sentence the verdict word is in: from the start of the words (a
    # label has nothing before it) to the first full stop after the match.
    end = w.find(".", m.end())
    sentence = w[: end if end != -1 else min(len(w), m.end() + 160)]
    if QUALIFIED.search(sentence):
        return "in part or in principle"
    return "accepted"


def state(row: dict) -> str:
    words = (row.get("government_words") or "").strip()
    if row["source"] == "report":
        return "not individual"
    if not words:
        return "unreadable"
    if position(words):
        return "position"
    if TEMPLATE.search(words):
        return "form letter"
    return "noted"


def key(r: dict) -> dict:
    """The columns that identify one row of recommendations.csv."""
    return {"source": r["source"], "source_id": r["source_id"], "label": r["label"],
            "recommended_by": r.get("recommended_by") or ""}


def read(name: str) -> list[dict]:
    with open(DATA / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def government_for(tabled: str) -> str:
    for name, start, end in GOVERNMENTS:
        if start <= tabled < end:
            return name
    return "unknown"


def main() -> int:
    excluded = {r["id"] for r in read("scope_exclusions.csv")}
    docs = {r["id"]: r for r in read("response_documents.csv") if r["id"] not in excluded}
    recs = read("recommendations.csv")

    per_doc: dict[str, Counter] = defaultdict(Counter)
    meta: dict[str, dict] = {}
    positions: list[dict] = []
    dissent = 0
    awaiting = 0
    for r in recs:
        if r.get("response_classification") == "awaiting a response" or not r.get("response_id"):
            awaiting += 1
            positions.append({**key(r), "state": "awaiting", "verdict": ""})
            continue
        if (r.get("recommended_by") or "").strip():
            dissent += 1
            positions.append({**key(r), "state": "dissent", "verdict": ""})
            continue
        rid = r["response_id"]
        if rid not in docs:
            positions.append({**key(r), "state": "out of scope", "verdict": ""})
            continue
        s = state(r)
        v = verdict(r.get("government_words") or "") if s == "position" else ""
        positions.append({**key(r), "state": s, "verdict": v})
        per_doc[rid][s] += 1
        if v:
            per_doc[rid][v] += 1
        meta.setdefault(rid, {
            "response_id": rid,
            "response_tabled": r.get("response_tabled") or "",
            "classification": r.get("response_classification") or docs[rid].get("classification", ""),
            "committee": r.get("committee") or "",
            "report_title": r.get("report_title") or r.get("document_title") or "",
            "response_url": r.get("response_url") or docs[rid].get("url", ""),
        })

    out_rows = []
    for rid, c in per_doc.items():
        assessable = c["position"] + c["noted"] + c["form letter"] + c["not individual"]
        m = meta[rid]
        tabled = m["response_tabled"] or (docs[rid].get("tabled_senate") or docs[rid].get("tabled_house") or "")[:10]
        out_rows.append({
            "response_id": rid,
            "response_tabled": tabled,
            "government": government_for(tabled),
            "classification": m["classification"],
            "committee": m["committee"],
            "report_title": m["report_title"],
            "recommendations": assessable,
            "position_stated": c["position"],
            "accepted": c["accepted"],
            "in_part_or_in_principle": c["in part or in principle"],
            "not_accepted": c["not accepted"],
            "noted_no_position": c["noted"],
            "form_letter": c["form letter"],
            "not_addressed_individually": c["not individual"],
            "unreadable": c["unreadable"],
            "coverage": (round(c["position"] / assessable, 4) if assessable else ""),
            "response_url": m["response_url"],
        })
    out_rows.sort(key=lambda r: (r["response_tabled"], r["response_id"]))

    fields = ["response_id", "response_tabled", "government", "classification", "committee",
              "report_title", "recommendations", "position_stated", "accepted",
              "in_part_or_in_principle", "not_accepted", "noted_no_position",
              "form_letter", "not_addressed_individually", "unreadable", "coverage", "response_url"]
    with open(DATA / "coverage.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    with open(DATA / "recommendation_positions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["source", "source_id", "label", "recommended_by", "state", "verdict"])
        w.writeheader()
        w.writerows(positions)

    def bucket(rows: list[dict]) -> dict:
        t = Counter()
        for r in rows:
            for k in ("recommendations", "position_stated", "accepted", "in_part_or_in_principle",
                      "not_accepted", "noted_no_position", "form_letter",
                      "not_addressed_individually", "unreadable"):
                t[k] += r[k]
        n = t["recommendations"]
        return {
            "responses": len(rows),
            "responses_with_no_position_at_all": sum(1 for r in rows if r["recommendations"] and r["position_stated"] == 0),
            "responses_fully_covered": sum(1 for r in rows if r["recommendations"] and r["position_stated"] == r["recommendations"]),
            "recommendations": n,
            "position_stated": t["position_stated"],
            "accepted": t["accepted"],
            "in_part_or_in_principle": t["in_part_or_in_principle"],
            "not_accepted": t["not_accepted"],
            "noted_no_position": t["noted_no_position"],
            "form_letter": t["form_letter"],
            "not_addressed_individually": t["not_addressed_individually"],
            "unreadable": t["unreadable"],
            "coverage": (round(t["position_stated"] / n, 4) if n else None),
        }

    by_year: dict[str, list] = defaultdict(list)
    by_gov: dict[str, list] = defaultdict(list)
    for r in out_rows:
        by_year[r["response_tabled"][:4]].append(r)
        by_gov[r["government"]].append(r)

    summary = {
        "definition": "A recommendation has a stated position when the government's words about it "
                      "say it is supported, agreed, accepted, endorsed, rejected, declined, not supported, "
                      "not agreed, not accepted or implemented, in full, in part or in principle. "
                      "Coverage is stated positions over recommendations the index holds for the response, "
                      "excluding dissenting recommendations and rows whose government words could not be read. "
                      "Each stated position carries the government's own verdict word, sorted three ways: "
                      "accepted (supported, agreed, accepted, endorsed or implemented, unqualified); in part or "
                      "in principle (the same sentence qualifies it); not accepted (negated, or rejected, "
                      "declined, disagreed).",
        "responses_in_corpus": len(docs),
        "responses_with_nothing_indexed": len(docs) - len(per_doc),
        "dissenting_recommendations_excluded": dissent,
        "awaiting_a_response_excluded": awaiting,
        "total": bucket(out_rows),
        "by_year": {y: bucket(v) for y, v in sorted(by_year.items())},
        "by_government": {g: bucket(v) for g, v in by_gov.items()},
        "by_classification": {k: bucket([r for r in out_rows if r["classification"] == k])
                              for k in sorted(set(r["classification"] for r in out_rows))},
    }
    (DATA / "coverage_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    t = summary["total"]
    print(f"coverage: {len(out_rows)} responses, {t['recommendations']} recommendations; "
          f"position stated {t['position_stated']} ({(t['coverage'] or 0)*100:.1f}%: "
          f"accepted {t['accepted']}, in part/principle {t['in_part_or_in_principle']}, "
          f"not accepted {t['not_accepted']}), "
          f"noted {t['noted_no_position']}, form letter {t['form_letter']}, "
          f"not individually {t['not_addressed_individually']}, unreadable {t['unreadable']}; "
          f"{summary['responses_with_nothing_indexed']} responses with nothing indexed; "
          f"{dissent} dissenting rows excluded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
