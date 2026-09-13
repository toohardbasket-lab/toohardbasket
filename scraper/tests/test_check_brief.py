"""What the brief checker must catch, and what it must not call an error.

The checker exists because a brief goes stale between being sent and being
read, and the brief invites the reader to prove it. So the failure that would
matter most is the quiet one: a claim that no longer matches the brief's words
being skipped rather than reported, which would let the checker say a document
is clean when it has not read it.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import check_brief as C  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


DATA = {
    "coverage": {"position_stated": 1032, "recommendations_assessed": 3504},
    "compliance": {"rate": 0.0508, "median_days": 416},
}

# --- finding the figures in the brief's own words ---------------------------
BRIEF = C.flat("""The responses state a position on 1,030 of the
3,504 recommendations they cover: 29 per cent. Of the responses since 2000,
74 arrived within three months: 5.1 per cent.""")

check("a figure is found across the line break the PDF put in it",
      C.matches(BRIEF, "a position on {} of the {} recommendations") == ["1,030", "3,504"])
check("a pattern the brief does not carry returns nothing, and is not a match",
      C.matches(BRIEF, "a position on {} of the {} inquiries") is None)
check("commas in a figure are part of it",
      C.as_number("3,504") == 3504)

# --- resolving a key --------------------------------------------------------
check("a plain path", C.resolve(DATA, "coverage/position_stated") == (1032.0, False))
check("a difference the brief states and the dataset only implies",
      C.resolve(DATA, "coverage/recommendations_assessed - coverage/position_stated")[0] == 2472)
rate, percent = C.resolve(DATA, "compliance/rate%")
check("a rate comes back as the percentage the brief prints", percent and abs(rate - 5.08) < 0.01)
try:
    C.resolve(DATA, "coverage/no_such_thing")
    missed = False
except KeyError:
    missed = True
check("a key the dataset does not have raises rather than resolving to nothing", missed)

# --- comparing at the precision the brief used ------------------------------
def agrees(said: str, want: float) -> bool:
    places = len(said.split(".")[1]) if "." in said else 0
    return round(want, places) == round(C.as_number(said), places)


check("5.1 per cent against 5.0847 is agreement, not an erratum", agrees("5.1", 5.0847))
check("5.1 per cent against 5.2 is an erratum", not agrees("5.1", 5.16))
check("1,030 against 1,032 is an erratum", not agrees("1,030", 1032))
check("416 against 416 agrees", agrees("416", 416.0))

# --- the wording list -------------------------------------------------------
check("the wording list is not empty, or the phrase check is decoration",
      len(C.WORDING) > 0)
check("every wording entry says why, so the reader is not left guessing",
      all(len(why) > 20 for _, why in C.WORDING))

# --- a brief with no claims beside it must refuse, not pass -----------------
import tempfile  # noqa: E402

d = pathlib.Path(tempfile.mkdtemp())
lonely = d / "2099-01-01.txt"
lonely.write_text("A brief nobody has written claims for.", encoding="utf-8")
check("a brief with no claims file refuses rather than reporting it clean",
      C.check(lonely, DATA) == 1)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
