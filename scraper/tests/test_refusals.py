"""A label the extractor throws away has to say so.

Two omissions were found by hand in two days, and both were invisible for the
same reason: `recommendations_in` reported what it kept and nothing about what
it refused.

    14 September — 337 recommendations across 241 documents, 218 of them the
    document's own Recommendation 1, dropped because a section heading looks
    like the middle of a sentence once a PDF's line breaks are gone.

    15 September — recommendation 11 of the ASIC response, whose second-level
    bullets a PDF renders as the letter "o", dropped by the guard against
    mangled text. Found because a reader pasted the page and the count did not
    match.

Neither was a bad rule applied well. Both were a rule that refused a label and
said nothing, in a file whose output is a public index of what governments were
asked. The fix is not a better rule — it is that a refusal is now a row in
data/labels_refused.csv, with the document, the label, the reason, and the words.

These tests keep it that way.
"""
import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import extract_recommendations as E  # noqa: E402

DATA = pathlib.Path(E.__file__).resolve().parent / "data"
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


# --- every way out of the loop names itself ---------------------------------
# The guarantee is structural, so it is tested against the source rather than
# against behaviour: behaviour can only show the paths somebody thought to
# exercise, and the whole failure being prevented is a path nobody thought of.
src = pathlib.Path(E.__file__).read_text(encoding="utf-8")
body = src[src.index("def recommendations_in"):]
body = body[:body.index("\n\n\n")] if "\n\n\n" in body else body
lines = body.splitlines()

# A fixed window of preceding lines is not good enough, and the first version of
# this test proved it: a new rule inserted directly above an existing one passed,
# because the window reached back into the previous rule's own `no(...)` call.
# The block a `continue` belongs to is the one that decides, so walk back to the
# `if` that owns it and look only inside that.
def owning_block(i: int) -> list[str]:
    indent = len(lines[i]) - len(lines[i].lstrip())
    j = i - 1
    while j >= 0:
        stripped = lines[j].strip()
        if stripped and (len(lines[j]) - len(lines[j].lstrip())) < indent:
            return lines[j:i]
        j -= 1
    return lines[max(0, i - 1):i]


unaccounted = []
for i, line in enumerate(lines):
    if line.strip() != "continue":
        continue
    block = "\n".join(owning_block(i))
    # Either the refusal is recorded, or it is the is_heading test, which is not
    # a refusal at all: a label inside a sentence is a mention, and recording
    # those would bury the ones that matter under thousands of cross-references.
    if "no(" in block or "is_heading" in block:
        continue
    unaccounted.append(i + 1)

check("every discard in recommendations_in is either recorded or the heading test",
      not unaccounted,
      f"unrecorded `continue` at line(s) {unaccounted} of the function — a label can "
      f"leave without a row in labels_refused.csv, which is the fault this file exists for")


# --- the reasons are a closed set, and each is a sentence a reader can use ----
reasons_in_code = set(re.findall(r'no\(label,\s*\(?"([^"]+)"', body))
reasons_in_code |= set(re.findall(r'else\s+"([^"]+)"\)', body))
check("the code emits at least four distinct reasons", len(reasons_in_code) >= 4,
      f"found {sorted(reasons_in_code)}")
check("no reason is a bare code or an abbreviation",
      all(" " in r and r == r.lower().strip() and len(r) > 12 for r in reasons_in_code),
      f"{[r for r in reasons_in_code if ' ' not in r or len(r) <= 12]}")


# --- the file itself ---------------------------------------------------------
path = DATA / "labels_refused.csv"
check("the refusals are written out", path.exists(), str(path))

if path.exists():
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    check("the file names the document, the label, the reason, the words and the page",
          set(csv.DictReader(path.open(encoding="utf-8-sig")).fieldnames or [])
          == {"document", "label", "why", "words", "context"})
    if rows:
        unknown = sorted({r["why"] for r in rows} - reasons_in_code)
        check("every reason in the file is one the code can still emit", not unknown,
              "; ".join(unknown) + " — a reason nobody writes any more is a stale file")
        check("every row names its document and label",
              all(r["document"] and r["label"] for r in rows))
        # A refusal for being too short leaves almost nothing in `words`, which is
        # the point of it. The document context is what a reviewer reads instead.
        check("every row carries enough to be judged without opening the PDF",
              all(len(r["context"]) > 40 for r in rows),
              f"{sum(1 for r in rows if len(r['context']) <= 40)} rows carry no context")

        # A label refused in one place and kept in another is not missing from
        # anything — a contents page and a summary table both carry labels. The
        # file is only worth reading if it holds the ones that are really gone.
        held = set()
        rec = DATA / "recommendations.csv"
        if rec.exists():
            for r in csv.DictReader(rec.open(encoding="utf-8-sig")):
                if r["source"] == "response":
                    held.add((r["source_id"], r["label"]))
        both = sorted({(r["document"], r["label"]) for r in rows} & held)[:5]
        check("nothing is listed as refused that the index actually holds",
              not both, f"{both} are in both")

        print(f"\nNOTE  {len(rows)} labels the documents state and the index does not hold, "
              f"across {len({r['document'] for r in rows})} documents. That is a worklist, "
              f"not an error count: some are table fragments and some are recommendations. "
              f"Nobody has read them yet, and until somebody has, the honest thing to say "
              f"about the size of the index is that it is a floor.")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
