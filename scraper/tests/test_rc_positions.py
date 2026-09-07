"""What extract_rc_positions.py must not put in a government's mouth.

Every test here is a way of overstating or understating what was said: a
deferral read as a refusal, a state's verdict read as the Commonwealth's, a
block that answers twenty-one recommendations read as answering one, a label
the page wrapped read as half of itself, a recommendation the response never
mentions read as unanswered rather than unaddressed.
"""
import csv
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import extract_rc_positions as P  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def block(labels, responsibility, *verdicts, words="Some explanation follows."):
    return ("Response to Recommendation " + labels + "\n"
            + f"Responsibility: {responsibility}\n"
            + "".join(v + "\n" for v in verdicts) + words + "\n")


# --- the prose grammar ------------------------------------------------------
prose = ("Recommendation 11.1: Clear documentation\n"
         "Services Australia should ensure that there is clear documentation.\n"
         "The Government accepts this recommendation. It will produce the documentation.\n"
         "Recommendation 11.2: Something else\n"
         "Services Australia should do something else entirely.\n"
         "The Government accepts in principle this recommendation. It will consider it.\n"
         "Recommendation 11.3: A third\n"
         "Services Australia should do a third thing.\n"
         "The Government does not accept this recommendation. It will not do it.\n"
         "Recommendation 11.4: A fourth\n"
         "Services Australia should do a fourth thing.\n"
         "The Government notes this recommendation. It describes what already happens.\n")
got, grammar = P.positions_in(prose)
check("a response with no blocks in it is read as prose", grammar == "prose")
check("accepts: a position, sorted as accepted",
      got["11.1"]["state"] == "position" and got["11.1"]["verdict"] == "accepted")
check("accepts in principle: sorted as in part or in principle",
      got["11.2"]["verdict"] == "in part or in principle")
check("does not accept: sorted as not accepted",
      got["11.3"]["verdict"] == "not accepted")
check("notes: no position, and the words are kept",
      got["11.4"]["state"] == "noted" and got["11.4"]["verdict"] == ""
      and "notes this recommendation" in got["11.4"]["government_words"])

# --- the block grammar ------------------------------------------------------
blocks = (block("6.1", "Australian Government", "Response: Accept")
          + block("6.2", "Australian Government", "Response: Accept in principle")
          + block("6.3", "Australian Government", "Response: Note")
          + block("6.4", "Australian Government", "Response: Subject to further consideration"))
got, grammar = P.positions_in(blocks)
check("a response carrying Responsibility lines is read as blocks", grammar == "blocks")
check("Accept is a position, sorted as accepted",
      got["6.1"]["state"] == "position" and got["6.1"]["verdict"] == "accepted")
check("Accept in principle is sorted as in part or in principle",
      got["6.2"]["verdict"] == "in part or in principle")
check("Note states no position, and the label is kept",
      got["6.3"]["state"] == "noted" and got["6.3"]["verdict"] == ""
      and got["6.3"]["government_label"] == "Note")
check("Subject to further consideration states no position, and is not a refusal",
      got["6.4"]["state"] == "noted" and got["6.4"]["verdict"] == ""
      and got["6.4"]["government_label"] == "Subject to further consideration")

# --- one block, many recommendations ----------------------------------------
got, _ = P.positions_in(block("4.1–4.4", "Australian Government", "Response: Accept"))
check("a block that answers a range answers every recommendation in it",
      sorted(got, key=P.label_key) == ["4.1", "4.2", "4.3", "4.4"])
got, _ = P.positions_in(block("7.8 and 7.10", "Australian Government", "Response: Accept"))
check("a block that answers a list answers only what it lists",
      sorted(got, key=P.label_key) == ["7.8", "7.10"])
got, _ = P.positions_in(block("4.20–5.2", "Australian Government", "Response: Accept"))
check("a range that crosses a chapter is not expanded, because it may not be a range",
      sorted(got, key=P.label_key) == ["4.20", "5.2"])
check("and the numbers a heading names are read in order",
      P.labels_in("7.2, 7.3, 7.6 and 7.13") == ["7.2", "7.3", "7.6", "7.13"])

# --- a label the page wrapped -----------------------------------------------
wrapped = ("Response to Recommendation 6.41\n"
           "Responsibility: Australian, state and territory governments\n"
           "Commonwealth, NSW, QLD: Subject to\n"
           "further consideration\n"
           "The governments are committed to something.\n")
got, _ = P.positions_in(wrapped)
check("a verdict the page wrapped is put back together",
      got["6.41"]["government_label"] == "Subject to further consideration")

# --- who is answering -------------------------------------------------------
split = ("Response to Recommendation 6.2\n"
         "Responsibility: Australian, state and territory governments\n"
         "Commonwealth: Subject to further consideration\n"
         "ACT, NSW, NT, QLD, SA, TAS, VIC, WA: Accept in principle\n"
         "The governments are committed to something.\n")
got, _ = P.positions_in(split)
check("the states' verdict is not read as the Commonwealth's",
      got["6.2"]["state"] == "noted" and got["6.2"]["verdict"] == "")
check("but it is recorded, because the document says it",
      "Accept in principle" in got["6.2"]["other_governments"])

states_only = ("Response to Recommendation 6.5\n"
               "Responsibility: state and territory governments\n"
               "NSW, SA: Accept\n"
               "The states are committed to something.\n")
got, _ = P.positions_in(states_only)
check("a block with no Commonwealth line states no Commonwealth position",
      got["6.5"]["state"] == "noted" and got["6.5"]["verdict"] == "")

joint = block("6.6", "Australian, state and territory governments", "Joint response: Accept")
check("a joint response speaks for the Commonwealth too",
      P.positions_in(joint)[0]["6.6"]["verdict"] == "accepted")

# --- parts that disagree ----------------------------------------------------
parts = ("Response to Recommendation 6.31\n"
         "Responsibility: Australian, state and territory governments\n"
         "Joint Response to 6.31 (a): Accept\n"
         "Joint Response to 6.31 (b): Accept in principle\n"
         "The governments are committed to something.\n")
got, _ = P.positions_in(parts)
check("a recommendation answered part by part is still one recommendation",
      list(got) == ["6.31"])
check("and where the parts disagree it sorts as in part or in principle, "
      "with both labels kept",
      got["6.31"]["verdict"] == "in part or in principle"
      and got["6.31"]["government_label"] == "Accept; Accept in principle")

# --- end to end -------------------------------------------------------------
def bed(text, labels=("6.1", "6.2", "6.3")):
    d = pathlib.Path(tempfile.mkdtemp())
    P.TEXT = d / "text"; P.TEXT.mkdir()
    P.RECOMMENDATIONS, P.DOCUMENTS = d / "rc_recommendations.csv", d / "rc_documents.csv"
    P.OUT, P.COUNTS = d / "rc_positions.csv", d / "rc_position_counts.csv"
    with P.RECOMMENDATIONS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "label"])
        w.writeheader()
        w.writerows({"commission_id": "example", "label": x} for x in labels)
    with P.DOCUMENTS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "role", "id", "tabled_senate",
                                          "tabled_house", "url"])
        w.writeheader()
        w.writerow({"commission_id": "example", "role": "response", "id": "77",
                    "tabled_senate": "2024-05-05", "tabled_house": "",
                    "url": "https://example.invalid/77"})
    if text is not None:
        (P.TEXT / "77_1.txt").write_text(text, encoding="utf-8")
    return d


bed(block("6.1", "Australian Government", "Response: Accept"))
rc = P.main(["extract_rc_positions.py"])
rows = {r["label"]: r for r in csv.DictReader(P.OUT.open(encoding="utf-8-sig"))}
counts = list(csv.DictReader(P.COUNTS.open(encoding="utf-8-sig")))[0]
check("a row for every recommendation, whether the response answers it or not",
      rc == 0 and sorted(rows) == ["6.1", "6.2", "6.3"])
check("a recommendation the response never mentions says so, and is not a refusal",
      rows["6.2"]["state"] == "not addressed" and rows["6.2"]["verdict"] == ""
      and "does not address" in rows["6.2"]["note"])
check("the totals add up to the recommendations",
      int(counts["recommendations"]) == 3
      and int(counts["position"]) + int(counts["noted"]) + int(counts["not addressed"])
      + int(counts["unreadable"]) == 3)
check("and the response is linked from every row",
      all(r["response_url"] == "https://example.invalid/77" for r in rows.values()))

bed(None)
check("a response that has not been read: refuses rather than writing every "
      "recommendation as unanswered",
      P.main(["extract_rc_positions.py"]) == 1 and not P.OUT.exists())

bed("A response document with no recommendation in it at all.\n")
check("a response nothing can be read from: refuses",
      P.main(["extract_rc_positions.py"]) == 1 and not P.OUT.exists())

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
