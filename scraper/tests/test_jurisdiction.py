"""What the jurisdiction measure must and must not count.

The measure exists to say how often the limit bites: the Commonwealth is the
only government this site can read, and sometimes the Commonwealth's own answer
says the matter is somebody else's. The failure that would matter is counting a
shared responsibility as a hand-over, because "all Australian governments have
a shared responsibility, and states and territories lead delivery" is the
Commonwealth including itself. Four rows read the wrong way before the guard
was written, so most of these tests are sentences that must NOT count.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import jurisdiction as J  # noqa: E402

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def hands_over(words: str) -> bool:
    return J.points_elsewhere(words) is not None


# --- the answer hands the matter over ---------------------------------------
for words in [
    "Supported in principle. This is a matter for state and territory government consideration.",
    "This recommendation is principally a matter for state and territory governments.",
    "Delivery of adult public dental services is the primary responsibility of states and territories.",
    "Legislation governing firearms use and possession is the responsibility of state and "
    "territory governments.",
    "We note that board appointments are ultimately the responsibility of states and territories.",
    "Waste collection falls within the remit of local governments.",
    "Planning approval is a matter for the Western Australian Government.",
]:
    check(f"counts: {words[:52]}…", hands_over(words))

# --- the answer keeps the matter, or shares it ------------------------------
for words in [
    "The National Plan recognises all Australian governments have a shared responsibility, "
    "and that states and territories lead delivery.",
    "This is the responsibility of Commonwealth, state and territory governments together.",
    "Responsibility sits with both the Australian Government and state and territory authorities.",
    "Established pest management is a shared responsibility between industry and governments, "
    "noting it is primarily the responsibility of state and territory governments.",
    "The Government is working with state and territory governments to deliver the reform.",
    "The Australian Government will consult the states and territories before legislating.",
    "The Government agrees and will implement this recommendation in full.",
    "This is a matter for the Australian Government alone.",
]:
    check(f"does not count: {words[:52]}…", not hands_over(words))

# --- a sentence that shares it does not become a hand-over further along -----
both = ("Funding is a shared responsibility of all governments. Delivery is the responsibility "
        "of state and territory governments.")
check("a later sentence that does hand it over still counts", hands_over(both))
check("and the words returned come from that sentence, not the shared one",
      "Delivery" in J.sentence_around(both, *J.points_elsewhere(both).span()))

# --- naming another government is a different, weaker thing -----------------
check("a recommendation naming state and territory governments is counted as naming one",
      bool(J.OTHER_GOVERNMENT.search(
          "The committee recommends that state and territory governments undertake a mapping.")))
check("naming a place is not naming a government",
      not J.OTHER_GOVERNMENT.search("Victoria Police attended the Queensland border."))
check("working with them still counts as naming them — naming is not being addressed to",
      bool(J.OTHER_GOVERNMENT.search(
          "The committee recommends the Australian Government work with state and territory "
          "education authorities.")))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
