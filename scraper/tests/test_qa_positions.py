"""What the review sheet must show, and what it must not.

The sheet exists so a person can judge attribution — whether the words the
index prints under a recommendation are that recommendation's answer. It can
only do that if the passage it shows is the passage the index read. The first
version failed this: it looked for the first sixty characters of the answer,
and "The Australian Government partially supports this recommendation" occurs
a dozen times in one response, so the very first card showed a different
recommendation's answer under recommendation 11's heading. A reviewer reading
that card would have marked a sound row wrong, or a broken one right.

So the tests here are about finding the right occurrence, saying when there is
more than one, and never guessing.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import qa_positions as Q  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


# Two recommendations answered in identical opening words, which is the norm
# in a response that works through a list.
ANSWER = ("The Australian Government supports this recommendation. "
          "The Government will act on it ")
DOC = (
    "Recommendation 11 The Committee recommends that tenancy laws prohibit rent bidding. "
    "Australian Government response " + ANSWER + "by banning rent bidding nationally. "
    "Recommendation 12 The Committee recommends standardised rental application forms. "
    "Australian Government response " + ANSWER + "by publishing a standard form. ")

ELEVEN = ANSWER + "by banning rent bidding nationally."
TWELVE = ANSWER + "by publishing a standard form."

def bolded(ctx: str) -> str:
    return ctx.split("<b>", 1)[1].split("</b>", 1)[0] if "<b>" in ctx else ""


ctx, hits = Q.where(ELEVEN, DOC)
check("the passage shown is the one asked for, not the first lookalike",
      "rent bidding nationally" in bolded(ctx) and "standard form" not in bolded(ctx))
check("the recommendation above it is visible, so attribution can be judged",
      "Recommendation 11" in ctx)
check("one match is reported as one", hits == 1)

# Both boundaries, not one. A reader judging attribution needs the heading
# above the answer AND the next heading below it: "these words sit under
# recommendation 11, and they stop before recommendation 12 begins." Showing
# only where the answer starts leaves the question half answered, which is what
# the first reader of the sheet said out loud.
check("the context runs on to the next recommendation's heading",
      "Recommendation 12" in ctx.split("</b>")[-1])
check("and the heading above it is still there",
      "Recommendation 11" in ctx.split("<b>")[0])

# The index stores an answer only to its own character cap, so on a long answer
# the document runs past the bold before the next heading arrives. The context
# has to keep going anyway, or the cap decides what the reader can check.
LONG = ANSWER + "by banning rent bidding nationally. " + ("Further detail follows. " * 60)
BIGDOC = ("Recommendation 11 The Committee recommends that tenancy laws prohibit rent bidding. "
          "Australian Government response " + LONG +
          "Recommendation 12 The Committee recommends standardised forms. ")
stored = LONG[:300]          # what the index kept
ctxL, _ = Q.where(stored, BIGDOC)
check("a long answer still shows where the next recommendation starts",
      "Recommendation 12" in ctxL)

ctx12, _ = Q.where(TWELVE, DOC)
check("the second answer finds its own place too",
      "Recommendation 12" in ctx12 and "standard form" in bolded(ctx12))

# When the answer really is ambiguous — the whole of it occurs twice — the
# sheet must say so rather than show one and let the reader assume.
TWICE = "Noted. " * 2
ctx2, hits2 = Q.where("Noted.", "Recommendation 1 A thing. " + TWICE)
check("a passage that occurs twice is counted twice", hits2 >= 2)

check("words the cached text does not hold show nothing at all",
      Q.where("The Government has abolished the Senate.", DOC) == ("", 0))
check("an empty answer shows nothing at all", Q.where("", DOC) == ("", 0))
check("no cached text shows nothing at all", Q.where(ELEVEN, "") == ("", 0))

# The verdict the index found has to be visible in the words, or the reviewer
# is checking a claim they cannot see.
m = Q.marked("The Government accepts this recommendation. It will be done.", "3")
check("the verdict the index matched is marked", "<mark>" in m and "accepts" in m)
check("nothing is marked where there is no verdict",
      "<mark>" not in Q.marked("The Government thanks the Committee.", "3"))
check("the words are escaped, not injected",
      "&lt;script&gt;" in Q.marked("<script> The Government agrees.", "3"))

check("counting how often the response names this number",
      Q.label_mentions("Recommendation 4 ... see recommendation 4 above ... Recommendation 40", "4") == 2)
check("a number the response never names counts zero",
      Q.label_mentions("Recommendation 4 and Recommendation 5", "9") == 0)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
