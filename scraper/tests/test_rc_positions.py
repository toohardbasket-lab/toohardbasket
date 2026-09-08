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

mixed = ("Response to Recommendation 6.32\n"
         "Responsibility: Australian Government\n"
         "Response to 6.32 (a): Accept\n"
         "Response to 6.32 (b): Note\n"
         "The Government is committed to something.\n")
got, _ = P.positions_in(mixed)
check("a position stated on one part and withheld on another is still a position",
      got["6.32"]["state"] == "position")
check("and the row says so, because 'in part or in principle' is the register's "
      "word there and not the government's",
      "not on others" in got["6.32"]["note"]
      and got["6.32"]["government_label"] == "Accept; Note")

agreed = ("Response to Recommendation 6.33\n"
          "Responsibility: Australian Government\n"
          "Response to 6.33 (a): Accept\n"
          "Response to 6.33 (b): Accept in principle\n"
          "The Government is committed to something.\n")
check("where every part states a verdict, no such note is added",
      "not on others" not in P.positions_in(agreed)[0]["6.33"]["note"])

# --- what is the government's words, and what is the page's -----------------
TITLE = "Australian Government Response to the Example Royal Commission"
HEAD = TITLE + "\n"

paged = (block("6.1", "Australian Government", "Response: Accept",
               words=("The Government will do the first thing, at length and over several\n"
                      + HEAD + "Australian Government Response - Volume 4 51\n"
                      + "years, beginning with the second half of it."))
         + block("6.2", "Australian Government", "Response: Accept",
                 words="The Government will do the second thing.")
         + block("6.3", "Australian Government", "Response: Accept",
                 words="The Government will do the third thing.")
         + block("6.4", "Australian Government", "Response: Accept",
                 words="The Government will do the fourth thing.")
         + HEAD + "Australian Government Response - Volume 4 52\n"
         + block("6.5", "Australian Government", "Response: Accept",
                 words="The Government will do the fifth thing.")
         + HEAD + "Australian Government Response - Volume 4 53\n")
got, _ = P.positions_in(paged, TITLE)
check("the running head does not become the government's words",
      "Volume" not in got["6.1"]["government_words"]
      and "Royal Commission" not in got["6.1"]["government_words"])
check("and the sentence it interrupted is rejoined",
      got["6.1"]["government_words"] ==
      "The Government will do the first thing, at length and over several years, "
      "beginning with the second half of it.")

repeated = (block("6.1", "Australian Government", "Response: Accept",
                  words="The Government accepts this recommendation.")
            + block("6.2", "Australian Government", "Response: Accept",
                    words="The Government accepts this recommendation.")
            + block("6.3", "Australian Government", "Response: Accept",
                    words="The Government accepts this recommendation."))
got, _ = P.positions_in(repeated, TITLE)
check("a sentence the government repeats on every page is still its answer",
      got["6.2"]["government_words"] == "The Government accepts this recommendation.")

# The disability response prints "Response to Recommendations 7.18, 7.19, 7.21,
# 7.22 and 7.23" and, immediately under it, "Response to Recommendation 7.20":
# six recommendations, one body, printed below the second heading.
shared = ("Response to Recommendations 6.1, 6.2 and 6.4\n"
          "Responsibility: Australian Government\n"
          "Joint Response: Accept in principle\n"
          "Response to Recommendation 6.3\n"
          "Responsibility: Australian Government\n"
          "Joint Response: Accept in principle\n"
          "All four of these will be done together, in one programme of work.\n")
got, _ = P.positions_in(shared, TITLE)
check("two headings printed back to back share the answer below them",
      all(got[x]["government_words"]
          == "All four of these will be done together, in one programme of work."
          for x in ("6.1", "6.2", "6.3", "6.4")))

# "The Government will consider / Recommendation 7.26 as part of its review of
# the Disability Discrimination Act" is one sentence the page broke in two.
split = block("6.1", "Australian Government", "Response: Accept",
              words=("The Government will amend the Act. It will consider\n"
                     "Recommendation 6.9 as part of that review, which is underway."))
got, _ = P.positions_in(split, TITLE)
check("a sentence that breaks before a number is not read as the next heading",
      got["6.1"]["government_words"].endswith("which is underway.")
      and "6.9" not in got)

# The robodebt response answers "The Government accepts this recommendation. As
# noted in the response to recommendation 20.4, ..." and the mention is not a
# heading either.
crossed = ("Recommendation 20.4: A fourth thing\n"
           "The Commonwealth should do the fourth thing.\n"
           "The Government accepts this recommendation. It will do the fourth thing.\n"
           "Recommendation 20.5: A fifth thing\n"
           "The Commonwealth should do the fifth thing.\n"
           "The Government accepts this recommendation. As noted in the response to\n"
           "recommendation 20.4, this work is already underway.\n")
got, grammar = P.positions_in(crossed, TITLE)
check("a prose answer is not cut off where it mentions another recommendation",
      grammar == "prose" and got["20.5"]["government_words"].endswith("already underway."))

# --- named, and answered with nothing ----------------------------------------
# Five of the Antisemitism commission's fourteen recommendations are in a
# confidential report. Both the public report and the response print, under the
# number and nothing else, "This recommendation is contained in the confidential
# Interim Report." Saying the response does not address them would be false: it
# names them.
named = ("Recommendation 20.4: A fourth thing\n"
         "The Commonwealth should do the fourth thing.\n"
         "The Government accepts this recommendation. It will do the fourth thing.\n"
         "Recommendation 20.5: A fifth thing\n"
         "This recommendation is contained in the confidential Interim Report.\n")
got, _ = P.positions_in(named, TITLE)
check("a recommendation the response names and answers nothing about is noted",
      got["20.5"]["state"] == "noted" and got["20.5"]["verdict"] == "")
check("and no words are put in the government's mouth for it",
      got["20.5"]["government_words"] == "" and got["20.5"]["government_label"] == "")
check("and the row says what happened rather than leaving it blank",
      "names this recommendation" in got["20.5"]["note"])

# A contents page names every recommendation in the document. It is not the
# response addressing any of them, and reading it as one would turn every
# recommendation a response never answers into an answered one.
contents = ("Recommendation 20.4 ....................... 12\n"
            "Recommendation 20.5 ....................... 14\n"
            "Recommendation 20.4: A fourth thing\n"
            "The Commonwealth should do the fourth thing.\n"
            "The Government accepts this recommendation. It will do the fourth thing.\n")
got, _ = P.positions_in(contents, TITLE)
check("a contents entry is not the response addressing a recommendation",
      "20.5" not in got)

# Nor is a heading with nothing under it at all.
bare = ("Recommendation 20.4: A fourth thing\n"
        "The Commonwealth should do the fourth thing.\n"
        "The Government accepts this recommendation. It will do the fourth thing.\n"
        "Recommendation 20.5: A fifth thing\n")
got, _ = P.positions_in(bare, TITLE)
check("nor is a heading with nothing under it", "20.5" not in got)

# --- how much of it is published --------------------------------------------
titled = block("6.1", "Australian Government", "Response: Accept",
               words=("The Government will do the thing, and has funded it.\n"
                      "Disability discrimination reform (Recommendations 6.2-6.4)"))
got, _ = P.positions_in(titled, TITLE)
check("a section title left at the end of a block is not part of the answer",
      got["6.1"]["government_words"] == "The Government will do the thing, and has funded it."
      and got["6.1"]["government_words_more"] == "")

long_answer = block("6.1", "Australian Government", "Response: Accept",
                    words=" ".join(["The Government will do the thing thoroughly."] * 40))
got, _ = P.positions_in(long_answer, TITLE)
check("an answer longer than the register prints stops at the end of a sentence",
      got["6.1"]["government_words"].endswith("thoroughly.")
      and len(got["6.1"]["government_words"]) <= P.GOV_CHARS)
check("and the row says the answer goes on, rather than reading as the whole of it",
      got["6.1"]["government_words_more"] == "yes")

# The disability response answers 6.31 under "Recommendation 6.31 (a)" and
# again under "(b)", with a different verdict for each part.
in_parts = ("Response to Recommendation 6.1\n"
            "Responsibility: Australian, state and territory governments\n"
            "Joint Response to 6.1 (a): Accept\n"
            "Joint Response to 6.1 (b): Accept in principle\n"
            "Recommendation 6.1 (a)\n"
            "The Government will do the first part of it, in full.\n"
            "Recommendation 6.1 (b)\n"
            "The Government will consider the second part of it.\n")
got, _ = P.positions_in(in_parts, TITLE)
check("a recommendation answered part by part quotes the first part",
      got["6.1"]["government_words"]
      == "The Government will do the first part of it, in full.")
check("and says the answer goes on, because the other part is its answer too",
      got["6.1"]["government_words_more"] == "yes")
check("with both verdicts kept, and sorted as answered in part",
      got["6.1"]["government_label"] == "Accept; Accept in principle"
      and got["6.1"]["verdict"] == "in part or in principle")

one_long_sentence = block("6.1", "Australian Government", "Response: Accept",
                          words="The Government will " + "do the thing and " * 90 + "stop.")
got, _ = P.positions_in(one_long_sentence, TITLE)
check("a single sentence too long to print is cut at a word, not inside one",
      got["6.1"]["government_words"].endswith(("do", "the", "thing", "and"))
      and got["6.1"]["government_words_more"] == "yes")

# --- end to end -------------------------------------------------------------
def bed(text, labels=("6.1", "6.2", "6.3")):
    d = pathlib.Path(tempfile.mkdtemp())
    P.TEXT = d / "text"; P.TEXT.mkdir()
    P.RECOMMENDATIONS, P.DOCUMENTS = d / "rc_recommendations.csv", d / "rc_documents.csv"
    P.OUT, P.COUNTS = d / "rc_positions.csv", d / "rc_position_counts.csv"
    with P.RECOMMENDATIONS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "source_id", "label"])
        w.writeheader()
        w.writerows({"commission_id": "example", "source_id": "55", "label": x} for x in labels)
    with P.DOCUMENTS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "role", "id", "answers",
                                          "tabled_senate", "tabled_house", "url"])
        w.writeheader()
        w.writerow({"commission_id": "example", "role": "response", "id": "77",
                    "answers": "55", "tabled_senate": "2024-05-05", "tabled_house": "",
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

# --- a recommendation the response names and does not answer ----------------
# The Australian Government's response to the Disability Royal Commission
# answers 172 of 222 and lists the other 50 in an appendix, under its own
# sentence saying whose responsibility they are. Read as silence, those fifty
# rows said the response did not address them.
LIST = """Appendix B 287
Appendix B: State and territory
recommendations
The table below includes the 50 Disability Royal Commission recommendations
within the sole responsibility of state and territory governments.
State and territory recommendations
5.3: Review and update of disability strategies and plans
6.4: Terms and definitions in guardianship and administration legislation
6.5: Objects of guardianship and administration legislation
6.7: Decision-making ability
6.8: Formal supporters
6.9: Representatives as a last resort
"""
CAPTION = ("The table below includes the 50 Disability Royal Commission recommendations "
           "within the sole responsibility of state and territory governments.")
unanswered = {"5.3", "6.4", "6.5", "6.7", "6.8", "6.9"}

got = P.named_in_a_list(LIST, unanswered)
check("every recommendation in the list is found",
      set(got) == unanswered)
check("and each carries the list's own sentence, rebuilt across the line the page broke",
      set(got.values()) == {CAPTION})
check("the heading between the sentence and the list is not mistaken for the sentence",
      "State and territory recommendations 5.3" not in " ".join(got.values()))

check("a recommendation the response does answer is not looked for in a list",
      P.named_in_a_list(LIST, unanswered - {"5.3"}).get("5.3") is None)

check("too few to be a list: a number opening a line is a cross-reference, not a list",
      P.named_in_a_list(LIST, {"5.3", "6.4"}) == {})

check("a list with no sentence above it: nothing is put in the government's mouth",
      P.named_in_a_list("\n".join(LIST.splitlines()[6:]), unanswered) == {})

check("a caption too short to be a sentence is not one",
      P.caption_above(["Yes.", "5.3: A recommendation"], 1) == "")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
