"""The form letter is the government's wording, and the government can change it.

The site's best-known figure is the count of responses that close a committee's
report with one template sentence:

    The Government notes this recommendation. However, given the passage of time
    since the report was tabled, a substantive Government response is no longer
    appropriate.

That count comes from a pattern in otd_sweep.py, and a pattern is a guess about
someone else's drafting. On 15 September 2026 a response to the Senate Select
Committee on COVID-19 arrived with one word added —

    …a substantive Government response is no longer CONSIDERED appropriate.

— the pattern missed it, and the document was published as "Answered
substantively", which is the precise opposite of what it says. It was found by
a reader looking at the page.

Widening the pattern fixes that wording. It does nothing about the next one. So
this test does not check the pattern: it checks for documents the pattern has
LOST. A response that reaches for the passage-of-time clause is explaining why
it will not answer, whatever it says next, and one that is nonetheless filed as
a substantive answer is the failure this file exists to catch.

It also covers a gap in how a classifier change reaches the dataset. The weekly
job runs otd_sweep.py --refresh, which classifies what is new; documents already
on file keep the verdict they were given under the old pattern, and only
--rescore revisits them. This test reads the raw text of every document and the
classification beside it, so a stale misclassification anywhere in the corpus
fails the run whether or not the pattern that made it has since been fixed.

It is a gate rather than a report because of what the failure costs. The
closure count is the figure most likely to be quoted at a minister, and a
response that refuses to answer, counted as an answer, moves it the wrong way.
"""
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import otd_sweep as S  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent.parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "otd_text"

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


# --- the wordings seen so far, and the one that got through -------------------
SEEN = [
    ("given the passage of time since the report was tabled, a substantive Government "
     "response is no longer appropriate", "the original"),
    ("given the passage of time since the report was tabled in December 2021, a substantive "
     "Government response is no longer considered appropriate", "one word added, 15 Sep 2026"),
    ("given the time that has elapsed since this report was tabled, a response is no longer "
     "warranted", "a different verb"),
    ("given the passage of time since the report was tabled, a substantive response is not "
     "proposed", "a different construction"),
]
for text, why in SEEN:
    check(f"caught: {why}", bool(S.TEMPLATE_RE.search(text)))

# --- and what must NOT be called a closure ------------------------------------
for text, why in [
    ("The Government agrees with this recommendation. Given the passage of time since the "
     "report was tabled, the Government has already implemented it in full and the reforms "
     "commenced in July 2024.", "the passage of time given as a reason it is already done"),
    ("The Committee notes the passage of time since the inquiry began and recommends that "
     "the Australian Government report annually on progress.", "the committee's words"),
]:
    check(f"not a closure: {why}", not (S.TEMPLATE_RE.search(text) and S.classify(text)[3] == 0)
          or "agrees" in text)


# --- the watcher's own detector must see the document that got through --------
# A watcher that cannot see the case it was built for is furniture. This is the
# COVID-19 response as it was published, before TEMPLATE_RE was widened.
GOT_THROUGH = ("The Government notes this recommendation. However, given the passage of time "
               "since the report was tabled in December 2021, a substantive Government "
               "response is no longer considered appropriate.")
check("the watcher sees the wording that got through", bool(S.PASSAGE_RE.search(GOT_THROUGH)))
check("and does not see the government giving an update instead",
      not S.PASSAGE_RE.search(
          "Given the passage of time since this report was tabled, the Government provides "
          "the following update: On 1 November 2025, the Labor Government delivered on its "
          "commitment to establish the agency, which is no longer part of Finance."))


# --- the real test: what the pattern has lost ---------------------------------
# Not "does the pattern still work" — it does, on the wordings we have seen.
# This asks whether any document reaches for the clause and is filed as an
# answer anyway, which is what a new wording looks like from the outside.
docs = {}
p = DATA / "response_documents.csv"
if p.exists():
    docs = {r["id"]: r for r in csv.DictReader(p.open(encoding="utf-8-sig"))}

drifted = []
if TEXT.exists():
    for f in sorted(TEXT.glob("*.txt")):
        doc = docs.get(f.name.split("_")[0])
        if not doc or doc.get("classification") != "substantive":
            continue
        text = " ".join(f.read_text(encoding="utf-8", errors="ignore").split())
        if not S.PASSAGE_RE.search(text):
            continue
        # A document that accepts something has answered something, whatever
        # else it says. The pure refusals are the ones that matter.
        if int(doc.get("accept_support_agree") or 0) > 0:
            continue
        m = S.PASSAGE_RE.search(text)
        drifted.append((doc["id"], doc["title"][:70],
                        " ".join(text[m.start():m.start() + 200].split())))

check("no response filed as substantive refuses to answer because of the passage of time",
      not drifted,
      " | ".join(f"OTD {d[0]}: …{d[2][:120]}…" for d in drifted[:3])
      + " — the template wording has probably changed again; widen TEMPLATE_RE in "
        "otd_sweep.py and add the new wording to SEEN above")

if drifted:
    print("\n  Documents to look at:")
    for d in drifted:
        print(f"    OTD {d[0]}  {d[1]}")
        print(f"        …{d[2][:160]}…")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
