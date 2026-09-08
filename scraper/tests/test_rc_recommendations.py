"""What extract_rc_recommendations.py must get right about a report's own words.

Everything tested here is a way of publishing something the commission did not
say: a heading swept into the recommendation, a page footer left in the middle
of it, another report's numbering picked up, a recommendation that runs on for
a megabyte because the report names nothing after it. The last of those must
end as a row with no text and a note, because a recommendation whose end cannot
be read is not the same as one that does not exist.
"""
import csv
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import extract_rc_recommendations as E  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


NAME = "Royal Commission into the Example Scheme"


def found(body, name=NAME):
    return E.recommendations_in(body, name)


# --- the two heading shapes -------------------------------------------------
body = ("Recommendation 10.1: A short title\n"
        "The Commonwealth should do the first thing, and should do it well.\n"
        "Recommendation 10.2 A title with no colon\n"
        "The Commonwealth should do the second thing, and should do it soon.\n"
        "Glossary\n")
got = found(body)
check("reads a heading with a colon and one without",
      sorted(got) == ["10.1", "10.2"])
check("keeps the report's heading with the recommendation, because only weight "
      "separates them and plain text has no weight",
      got["10.1"]["recommendation"].startswith("A short title The Commonwealth should do"))
check("stops at the next recommendation's heading",
      got["10.1"]["recommendation"].endswith("do it well"))
check("stops the last one where the report names something else",
      got["10.2"]["recommendation"].endswith("do it soon"))

# --- the last one, with nothing after it ------------------------------------
runaway = ("Recommendation 1.1: A title\n"
           "The Commonwealth should do the thing. " + ("More of the report. " * 800))
got = found(runaway)
check("a recommendation the report names nothing after: a row, with no text",
      got["1.1"]["recommendation"] == "" and "could not be read" in got["1.1"]["note"])

# --- more than one occurrence ------------------------------------------------
twice = ("Recommendation 2.1: A title\n"
         "The Commonwealth should do the thing, and should do it properly and soon.\n"
         "Recommendation 2.2: Another\n"
         "The Commonwealth should do another thing, and should do that one properly too.\n"
         "Chapter 2\n"
         "Recommendation 2.1: A title\n"
         "The Commonwealth should do the thing. " + ("And here is the argument for it. " * 20) +
         "\nAppendix A\n")
got = found(twice)
check("where a number appears twice, the shorter text is kept",
      got["2.1"]["recommendation"].endswith("properly and soon"))

contents = ("Recommendation 3.1: A title ................................... 44\n"
            "Recommendation 3.2: Another\n"
            "The Commonwealth should do a thing that is long enough to be a recommendation.\n"
            "Glossary\n")
got = found(contents)
check("a contents entry is not a recommendation", "3.1" not in got or
      not got["3.1"]["recommendation"])
check("and the note says a contents entry is all there was",
      "3.1" in got and "contents entry" in got["3.1"]["note"])

# --- numbering that is not this report's ------------------------------------
other = ("Recommendation 4.1: A title\n"
         "The Commonwealth should do the thing.\n"
         "Recommendation 28 of the Mental Health Royal Commission recommended something else.\n"
         "Glossary\n")
got = found(other)
check("a bare number with no chapter is another report's numbering, and is left alone",
      sorted(got) == ["4.1"])

inline = ("Recommendation 5.1: A title\n"
          "The Commonwealth should do the thing, as set out in Recommendation 5.9 above.\n"
          "Glossary\n")
check("a number inside a sentence is a cross-reference, not a heading",
      sorted(found(inline)) == ["5.1"])

# --- the page footer --------------------------------------------------------
across = ("Recommendation 6.1: A title\n"
          "The Commonwealth should do the first half of the thing.\n"
          "646 Royal Commission into the Example Scheme\n"
          "and the second half of the thing, which matters.\n"
          "Glossary\n")
got = found(across)
check("the line every page carries is taken out of the middle of a recommendation",
      "Royal Commission into the Example" not in got["6.1"]["recommendation"])
check("and both halves of the recommendation survive it",
      got["6.1"]["recommendation"].endswith("which matters"))
check("without the commission's name it is left alone, rather than guessed at",
      "Royal Commission into the Example" in found(across, name="")["6.1"]["recommendation"])

# --- a heading swept in at the end ------------------------------------------
swept = ("Recommendation 7.1: A title\n"
         "The Commonwealth should do the thing, and should do it properly and soon.\n"
         "Improving the Australian Public Service\n"
         "Recommendation 7.2: Another\n"
         "The Commonwealth should do another thing, and should do that properly too.\n"
         "Glossary\n")
got = found(swept)
check("a trailing fragment with no sentence in it belongs to what comes next",
      got["7.1"]["recommendation"].endswith("properly and soon"))

unpunctuated = ("Recommendation 8.1: A title\n"
                "The Commonwealth should consult people with disability, representative "
                "organisations and other key stakeholders\n"
                "Glossary\n")
check("a recommendation that ends without a full stop is not trimmed",
      found(unpunctuated)["8.1"]["recommendation"].endswith("other key stakeholders"))

# --- telling the heading from the recommendation ----------------------------
def sidecar(rows):
    """A typography sidecar: (font, size, text) per line."""
    d = pathlib.Path(tempfile.mkdtemp()) / "99_1.lines.tsv"
    d.write_text("\n".join(f"{f}\t{s}\t{t}" for f, s, t in rows) + "\n", encoding="utf-8")
    return d


got = E.headings_in(sidecar([
    ("Calibri-Bold", 11, "Recommendation 10.1: Design policies and processes with emphasis"),
    ("Calibri-Bold", 11, "on the people they are meant to serve"),
    ("Calibri", 11, "Services Australia design its policies and processes."),
]))
check("a heading that wraps is read to the end of the wrap",
      got["10.1"] == "Design policies and processes with emphasis on the people they are meant to serve")

got = E.headings_in(sidecar([
    ("DINPro-Medium", 13, "Recommendation 6.1 A short heading"),
    ("ArialMT", 11, "The Australian Government should do the thing."),
    ("DINPro-Medium", 16, "A section heading, larger"),
]))
check("the heading stops where the type changes", got["6.1"] == "A short heading")

got = E.headings_in(sidecar([
    ("Calibri-Bold", 11, "Recommendation 7.1: The first"),
    ("Calibri-Bold", 11, "Recommendation 7.2: The second"),
    ("Calibri", 11, "The Commonwealth should do the thing."),
]))
check("one recommendation's heading never swallows the next one's",
      got == {"7.1": "The first", "7.2": "The second"})

check("no sidecar at all: no headings, and nothing invented",
      E.headings_in(pathlib.Path("/nowhere/99_1.lines.tsv")) == {})

check("the split happens only where the text begins with the heading",
      E.split_heading("A title The Commonwealth should act.", "A title")
      == ("A title", "The Commonwealth should act."))
check("and where it does not, the row keeps the whole block and no heading",
      E.split_heading("The Commonwealth should act.", "Some other title")
      == ("", "The Commonwealth should act."))
check("no heading found: the block is left exactly as it was",
      E.split_heading("The Commonwealth should act.", "")
      == ("", "The Commonwealth should act."))

# --- where a recommendation stops, when the words do not say ----------------
LINES = [
    ("Calibri-Bold", 16, "Improving the Australian Public Service"),
    ("Calibri-Bold", 11, "Recommendation 23.8: Documenting decisions and discussions"),
    ("Calibri", 11, "The Commission should develop standards for documenting decisions."),
    ("Calibri-Bold", 16, "Closing observations"),
    ("Calibri", 11, "Section 34 of the Cth FOI Act should be repealed."),
]
stops = E.section_headings_in(sidecar(LINES))
check("a section heading is the report's own, found by the type it is set in",
      stops == ["Closing observations", "Improving the Australian Public Service"])

sample = "\n".join(t for _, _, t in LINES)
got = E.recommendations_in(sample, "", E.stops_in(sample, stops),
                           {"23.8": "Documenting decisions and discussions"})
check("the last recommendation in a list stops at the report's next section heading",
      got["23.8"]["recommendation"].endswith("standards for documenting decisions"))
check("and it is not left unreadable", got["23.8"]["note"] == "")

# A one-word divider set large and bold: matching it as a prefix stopped a
# dozen recommendations at the first line of their own text.
DIVIDER = [
    ("Calibri-Bold", 20, "Services"),
    ("Calibri-Bold", 11, "Recommendation 10.1: A title"),
    ("Calibri", 11, "Services Australia should design its policies with care for recipients."),
    ("Calibri-Bold", 16, "The concept of vulnerability"),
]
sample = "\n".join(t for _, _, t in DIVIDER)
got = E.recommendations_in(sample, "", E.stops_in(sample, E.section_headings_in(sidecar(DIVIDER))),
                           {"10.1": "A title"})
check("a heading is matched as a whole line, not as the start of one",
      got["10.1"]["recommendation"].endswith("care for recipients"))

# A section heading that wraps has a second line that also turns up as an
# ordinary wrapped line inside a recommendation.
WRAPPED = [
    ("DINPro-Medium", 16, "Realising the human rights of people"),
    ("DINPro-Medium", 16, "with disability"),
    ("DINPro-Medium", 13, "Recommendation 6.31 Embed the right to equitable access"),
    ("ArialMT", 11, "The Commission should amend the Charter to include the rights of people"),
    ("ArialMT", 11, "with disability"),
    ("ArialMT", 11, "and align it with the Act."),
]
sample = "\n".join(t for _, _, t in WRAPPED)
got = E.recommendations_in(sample, "", E.stops_in(sample, E.section_headings_in(sidecar(WRAPPED))),
                           {"6.31": "Embed the right to equitable access"})
check("a wrapped section heading matches only where the whole of it does",
      got["6.31"]["recommendation"].endswith("and align it with the Act"))

# The recommendation's own heading can wrap onto a line the report uses as a
# section heading elsewhere; stopping there would cut it off inside its title.
OWN = [
    ("DINPro-Medium", 16, "mainstream services"),
    ("DINPro-Medium", 13, "Recommendation 12.6 Disability flags in data collection for"),
    ("DINPro-Medium", 13, "mainstream services"),
    ("ArialMT", 11, "All governments should collect disability data in mainstream services."),
    ("DINPro-Medium", 16, "A later section"),
]
sample = "\n".join(t for _, _, t in OWN)
got = E.recommendations_in(sample, "", E.stops_in(sample, E.section_headings_in(sidecar(OWN))),
                           {"12.6": "Disability flags in data collection for mainstream services"})
check("a recommendation is never stopped inside its own heading",
      got["12.6"]["recommendation"].endswith("data in mainstream services"))

check("no sidecar: no section headings, and the old behaviour stands",
      E.section_headings_in(pathlib.Path("/nowhere/x.lines.tsv")) == [])

# --- what the report says it recommends -------------------------------------
check("the report's own count is read from its own words",
      E.stated_total("The following is a list of 57 recommendations of this Commission.")
      == ("57", ""))
check("a report that states two different totals: neither is adopted",
      E.stated_total("a list of 57 recommendations ... a total of 58 recommendations")
      == ("", "the report states 57 and 58; neither is adopted"))
check("a report that states none: said, not guessed",
      E.stated_total("There are recommendations in this report.")[0] == "")

# --- end to end -------------------------------------------------------------
def bed(text, stated="a list of 2 recommendations"):
    d = pathlib.Path(tempfile.mkdtemp())
    E.DATA, E.TEXT = d, d / "text"
    E.TEXT.mkdir()
    E.DOCUMENTS, E.COMMISSIONS = d / "rc_documents.csv", d / "royal_commissions.csv"
    E.OUT, E.COUNTS = d / "rc_recommendations.csv", d / "rc_recommendation_counts.csv"
    with E.COMMISSIONS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "name", "short_names", "notes"])
        w.writeheader(); w.writerow({"commission_id": "example", "name": NAME,
                                     "short_names": "", "notes": ""})
    with E.DOCUMENTS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["commission_id", "role", "carries_recommendations",
                                          "id", "title", "tabled_senate", "tabled_house", "url"])
        w.writeheader(); w.writerow({"commission_id": "example", "role": "report",
                                     "carries_recommendations": "yes", "id": "99",
                                     "title": "A report", "tabled_senate": "2024-01-01",
                                     "tabled_house": "", "url": "https://example.invalid/99"})
    if text is not None:
        (E.TEXT / "99_1.txt").write_text(stated + "\n" + text, encoding="utf-8")
    return d


bed(body)
rc = E.main(["extract_rc_recommendations.py"])
out = list(csv.DictReader(E.OUT.open(encoding="utf-8-sig")))
counts = list(csv.DictReader(E.COUNTS.open(encoding="utf-8-sig")))
check("writes a row per recommendation, with the report it came from",
      rc == 0 and len(out) == 2 and out[0]["report_url"] == "https://example.invalid/99")
check("records what was found against what the report states",
      counts[0]["found"] == "2" and counts[0]["stated"] == "2" and counts[0]["agree"] == "yes")

bed(body, stated="a list of 3 recommendations")
E.main(["extract_rc_recommendations.py"])
counts = list(csv.DictReader(E.COUNTS.open(encoding="utf-8-sig")))
check("a disagreement is recorded rather than resolved",
      counts[0]["found"] == "2" and counts[0]["stated"] == "3" and counts[0]["agree"] == "no")

bed(None)
check("a report that has not been read: refuses rather than writing an empty index",
      E.main(["extract_rc_recommendations.py"]) == 1 and not E.OUT.exists())

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
