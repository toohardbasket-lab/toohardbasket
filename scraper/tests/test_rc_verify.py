"""What verify_rc_index.py must catch.

A verifier that says everything is fine is worth nothing, so every test here is
a row that must be thrown out, and the two that must not: a document that
answers a recommendation twice in the same words, and a recommendation answered
inside a block covering a range, which names no label of its own.
"""
import csv
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import verify_rc_index as V  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


FILLER = "".join(
    f"Recommendation 7.{i} A filler heading {i}\n"
    f"A filler heading {i} The Commission should do the {i}th thing, plainly and in full.\n"
    for i in range(1, 12))
REPORT = (
    FILLER
    + "Recommendation 6.30 Expand the scope of the Centre\n"
    "The Australian Government should expand the remit of the Centre to include autism.\n"
    "Recommendation 6.31 Embed the right to equitable access\n"
    "The Commission should amend the Charter to incorporate the right to equitable access "
    "to health services for people with disability, and align it with the Act.\n"
    "Glossary\n"
)
RESPONSE = (
    "Response to Recommendations 6.1–6.29\n"
    "Responsibility: Australian Government\n"
    "Response: Subject to further consideration\n"
    "The Government is considering the framework and will report in due course.\n"
    "Response to Recommendation 6.30\n"
    "Responsibility: Australian Government\n"
    "Response: Accept\n"
    "The Government accepts the recommendation about the Centre and will expand its remit.\n"
    "Response to Recommendation 6.31\n"
    "Responsibility: Australian Government\n"
    "Response: Accept in principle\n"
    "The Government is considering the framework and will report in due course. "
    "It will amend the Charter as part of that work.\n"
)


def bed(rec_rows, pos_rows=()):
    d = pathlib.Path(tempfile.mkdtemp())
    V.TEXT = d / "text"; V.TEXT.mkdir()
    (V.TEXT / "99_1.txt").write_text(REPORT, encoding="utf-8")
    (V.TEXT / "77_1.txt").write_text(RESPONSE, encoding="utf-8")
    V._cache.clear(); V._lines.clear()
    V.RECOMMENDATIONS, V.POSITIONS = d / "rc_recommendations.csv", d / "rc_positions.csv"
    V.COMMISSIONS, V.COUNTS, V.DROPPED = d / "c.csv", d / "counts.csv", d / "dropped.csv"
    with V.COMMISSIONS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "name", "short_names", "notes"])
        w.writeheader()
        w.writerow({"commission_id": "example", "name": "Royal Commission into Something",
                    "short_names": "", "notes": ""})
    rec_fields = ["commission_id", "source", "source_id", "label", "heading", "recommendation"]
    with V.RECOMMENDATIONS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rec_fields)
        w.writeheader(); w.writerows(rec_rows)
    pos_fields = ["commission_id", "report_id", "label", "response_id", "state",
                  "government_label", "government_words"]
    with V.POSITIONS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=pos_fields)
        w.writeheader(); w.writerows(pos_rows)
    return d


def rec(label, heading, text):
    return {"commission_id": "example", "source": "report", "source_id": "99",
            "label": label, "heading": heading, "recommendation": text}


def pos(label, state, gov_label, words):
    return {"commission_id": "example", "report_id": "99", "label": label, "response_id": "77",
            "state": state, "government_label": gov_label, "government_words": words}


GOOD = rec("6.31", "Embed the right to equitable access",
           "Embed the right to equitable access The Commission should amend the Charter to "
           "incorporate the right to equitable access to health services for people with "
           "disability, and align it with the Act.")

# --- the recommendation side ------------------------------------------------
bed([GOOD])
check("a row whose words, heading and number are all the report's is kept",
      V.check_recommendation(GOOD, "Royal Commission into Something") == "verified")

wrong_number = {**GOOD, "label": "6.30"}
check("the right words under the wrong number are thrown out",
      V.check_recommendation(wrong_number, "Royal Commission into Something")
      == "label does not match")

wrong_heading = {**GOOD, "heading": "Expand the scope of the Centre"}
check("a heading the report does not put over those words is thrown out",
      V.check_recommendation(wrong_heading, "Royal Commission into Something")
      == "heading does not sit above the text")

invented = {**GOOD, "recommendation": "The Commission should abolish the Charter entirely and "
            "replace it with something else that the report never mentions at all."}
check("words that are not in the report are thrown out",
      V.check_recommendation(invented, "Royal Commission into Something")
      == "text not in the document")

missing = {**GOOD, "source_id": "404"}
check("a document that has not been read is not quietly passed",
      V.check_recommendation(missing, "Royal Commission into Something")
      == "source text missing")

# --- the position side ------------------------------------------------------
good_pos = pos("6.31", "position", "Accept in principle",
               "The Government is considering the framework and will report in due course. "
               "It will amend the Charter as part of that work.")
bed([GOOD], [good_pos])
check("a position whose words follow the recommendation's own block is kept",
      V.check_position(good_pos) == "verified")

check("a label the government did not use is thrown out",
      V.check_position({**good_pos, "government_label": "Not accepted"})
      == "the government's label is not in the document")
check("and \"Accept\" is not read out of \"Accept in principle\", which is the "
      "misstatement that would matter most",
      V.check_position({**good_pos, "government_label": "Accept"})
      == "the government's label is not in the document")

check("words the response does not contain are thrown out",
      V.check_position({**good_pos, "government_words": "The Government rejects this "
                        "recommendation and will do nothing about it whatsoever."})
      == "the government's words are not in the document")

check("a position taken from another recommendation's block is thrown out",
      V.check_position({**good_pos, "label": "6.30", "government_label": "Accept"})
      == "the words sit under another recommendation's heading")

# The same opening sentence appears under the range block and again under 6.31.
# The first occurrence is not the one the row was taken from, and a check that
# looked only there threw out a row that was right.
duplicated = pos("6.31", "position", "Accept in principle",
                 "The Government is considering the framework and will report in due course.")
check("words a response uses twice are found under the block they belong to",
      V.check_position(duplicated) == "verified")

# A recommendation answered inside a block covering a range names no label of
# its own; the words are the document's, and where they sit proves nothing.
in_a_range = pos("6.20", "noted", "Subject to further consideration",
                 "The Government is considering the framework and will report in due course.")
check("a recommendation answered inside a range is verified on its words alone",
      V.check_position(in_a_range) == "verified")

check("a recommendation the response does not address needs no words",
      V.check_position(pos("6.20", "not addressed", "", "")) == "verified")

# --- what it does with them -------------------------------------------------
FILL_ROWS = [rec(f"7.{i}", f"A filler heading {i}",
                 f"A filler heading {i} The Commission should do the {i}th thing, plainly "
                 "and in full.") for i in range(1, 12)]
d = bed([GOOD, wrong_number] + FILL_ROWS,
        [good_pos, pos("6.30", "position", "Accept in principle",
                       "The Government is considering the framework.")])
rc = V.main(["verify_rc_index.py"])
kept = list(csv.DictReader(V.RECOMMENDATIONS.open(encoding="utf-8-sig")))
dropped = list(csv.DictReader(V.DROPPED.open(encoding="utf-8-sig")))
positions = list(csv.DictReader(V.POSITIONS.open(encoding="utf-8-sig")))
check("the unverified row is removed from the index, not flagged in it",
      rc == 0 and "6.30" not in [r["label"] for r in kept] and "6.31" in [r["label"] for r in kept])
check("and it is written out with the reason",
      any(r["why"] == "label does not match" for r in dropped))
check("the position of a removed recommendation goes with it",
      [p["label"] for p in positions] == ["6.31"]
      and any(r["why"] == "its recommendation was not verified" for r in dropped))

bed([invented])
check("nothing verified: refuses rather than publishing an empty index",
      V.main(["verify_rc_index.py"]) == 1)

bed([GOOD] + [{**invented, "label": f"9.{i}"} for i in range(1, 10)])
check("a tenth of the index failing is a broken rule, and it refuses",
      V.main(["verify_rc_index.py"]) == 1)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
