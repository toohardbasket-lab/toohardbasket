"""check_brief.py — hold a published brief to the dataset it was built from.

The media brief tells a journalist: "Run it and diff the result against this
document." That promise was not keepable. The brief left the repository as a
PDF, so the only way to check it was to read the PDF against brief_figures.py
by eye — which was done on 10 September and found nine figures and one phrase
that had moved since the brief was written, none of them because anything was
wrong when it was written. Between a brief going out and a journalist reading
it, the dataset rebuilds.

So the brief's own text is kept here, and beside it a list of claims: for each
sentence carrying a figure, the sentence with the figure knocked out and the
path in brief_figures.py that should fill it. This script puts them back and
says which ones no longer agree. A journalist running it gets the same errata
sheet the author does, from the same command.

A claim that cannot be found in the brief at all is a failure too, and a loud
one: it means the text and the claims have drifted apart, and a checker that
quietly skips what it cannot match would report a clean brief for a file it had
never read.

    python check_brief.py                        # the newest brief in docs/briefs
    python check_brief.py 2026-09-08             # one by its date
    python check_brief.py --all                  # every brief on file

Exit 1 if any figure has moved, so the weekly job can carry it.

The claims file is csv: `keys,pattern`. The pattern is the brief's own words
with {} where each figure goes, matched on flattened whitespace so a line break
in the PDF text does not matter. `keys` is one path per {}, in order,
slash-separated, and may be:

    coverage/position_stated            a figure
    compliance/rate%                    a rate, written in the brief as a
                                        percentage ("5.1 per cent")
    a/b - c/d                           a difference, for a figure the brief
                                        states that the dataset only implies
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
BRIEFS = HERE.parent / "docs" / "briefs"


def flat(s: str) -> str:
    return " ".join(s.split())


def figures() -> dict:
    """brief_figures.py's own output, run rather than cached."""
    out = subprocess.run([sys.executable, str(HERE / "brief_figures.py"), "--json"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def value_at(data: dict, path: str):
    node = data
    for part in path.split("/"):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


def resolve(data: dict, key: str) -> tuple[float, bool]:
    """The number a key stands for, and whether it is a percentage."""
    key = key.strip()
    if " - " in key:
        left, right = key.split(" - ", 1)
        a, pa = resolve(data, left)
        b, _ = resolve(data, right)
        return a - b, pa
    percent = key.endswith("%")
    v = value_at(data, key.rstrip("%"))
    return (float(v) * 100 if percent else float(v)), percent


def as_number(text: str) -> float:
    return float(text.replace(",", ""))


def matches(brief: str, pattern: str) -> list[str] | None:
    """The figures the brief has where the pattern's {} are, or None."""
    parts = [re.escape(p) for p in flat(pattern).split("{}")]
    rx = re.compile(r"([\d,]+(?:\.\d+)?)".join(parts))
    m = rx.search(brief)
    return list(m.groups()) if m else None


# Wording the brief must not carry. Each one was wrong in a way no figure check
# would catch, and each was found by hand once.
WORDING = [
    ("responses checked to",
     "the date is the newest tabling the harvest holds, not a guarantee that "
     "everything tabled by then has been seen — write \"harvested to\""),
]


def check(path: pathlib.Path, data: dict) -> int:
    brief = flat(path.read_text(encoding="utf-8"))
    claims_path = path.with_suffix(".claims.csv")
    if not claims_path.exists():
        print(f"REFUSING: {path.name} has no claims file beside it "
              f"({claims_path.name}); a brief nobody has written claims for "
              f"has not been checked, and must not be reported as clean",
              file=sys.stderr)
        return 1

    moved, missing, ok = [], [], 0
    with claims_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            keys = [k for k in row["keys"].split("|") if k.strip()]
            found = matches(brief, row["pattern"])
            if found is None:
                missing.append((row["pattern"], "the brief does not say this"))
                continue
            if len(found) != len(keys):
                missing.append((row["pattern"],
                                f"{len(found)} figures in the brief, {len(keys)} keys"))
                continue
            for key, said in zip(keys, found):
                try:
                    want, percent = resolve(data, key)
                except KeyError:
                    missing.append((row["pattern"], f"brief_figures.py has no {key}"))
                    continue
                got = as_number(said)
                # Compare at the precision the brief printed. "5.1 per cent"
                # against 5.0847 is agreement; against 5.2 is not.
                places = len(said.split(".")[1]) if "." in said else 0
                if round(want, places) != round(got, places):
                    shown = f"{want:,.{places}f}"
                    moved.append((said, shown, key, row["pattern"]))
                else:
                    ok += 1

    wording = [(bad, why) for bad, why in WORDING if bad in brief]

    print(f"\n{path.name} — {ok} figures agree, {len(moved)} moved, "
          f"{len(missing)} claims unmatched, {len(wording)} phrases to fix")
    if moved:
        print("\n  IN THE BRIEF            SHOULD NOW READ    FROM")
        for said, shown, key, pattern in moved:
            print(f"  {said:<22}  {shown:<17}  {key}")
            print(f"      …{flat(pattern)[:96]}")
    for bad, why in wording:
        print(f"\n  PHRASE  “{bad}” — {why}")
    for pattern, why in missing:
        print(f"\n  UNMATCHED  {why}\n      …{flat(pattern)[:96]}")
    return 1 if (moved or missing or wording) else 0


def main(argv: list[str]) -> int:
    if not BRIEFS.exists():
        print(f"no briefs on file at {BRIEFS}", file=sys.stderr)
        return 1
    texts = sorted(BRIEFS.glob("*.txt"))
    if not texts:
        print(f"no briefs on file at {BRIEFS}", file=sys.stderr)
        return 1
    wanted = [a for a in argv[1:] if not a.startswith("--")]
    if "--all" in argv:
        chosen = texts
    elif wanted:
        chosen = [p for p in texts if p.stem in wanted]
        if not chosen:
            print(f"no brief named {', '.join(wanted)}; on file: "
                  f"{', '.join(p.stem for p in texts)}", file=sys.stderr)
            return 1
    else:
        chosen = [texts[-1]]

    data = figures()
    worst = 0
    for p in chosen:
        worst = max(worst, check(p, data))
    print(f"\nfigures computed {data.get('generated', '?')}")
    if worst:
        print("Anything above is an erratum for a document already sent out. "
              "Send the corrections to whoever has it.")
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))
