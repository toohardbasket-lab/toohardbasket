"""What must be true of the site whether the royal commissions index is a draft
or is published, so that going live cannot be done by halves.

The index touches four things outside its own two pages: the navigation bar,
the live methods page, the sitemap and the weekly job. The first three are
governed by one flag in site/src/lib/draft.ts. The fourth cannot be — a GitHub
workflow does not read a TypeScript file — so it is checked here instead.

While the index is a draft its block in update-dataset.yml carries
`continue-on-error: true`, which lets that block fail without stopping the run.
That is right for a draft nothing published depends on, and wrong the moment a
page reads its files: the site's rule is that a step which cannot stand behind
what it wrote stops the build. Published-with-continue-on-error is the state
this file exists to make impossible.
"""
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent.parent
DRAFT_TS = HERE / "site" / "src" / "lib" / "draft.ts"
WORKFLOW = HERE / ".github" / "workflows" / "update-dataset.yml"

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def flag() -> bool:
    m = re.search(r"export const ROYAL_COMMISSIONS_DRAFT\s*=\s*(true|false)\s*;",
                  DRAFT_TS.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit("REFUSING: draft.ts does not set ROYAL_COMMISSIONS_DRAFT")
    return m.group(1) == "true"


def rc_block(body: str) -> str:
    """The royal commissions step of the weekly job, up to the next step."""
    start = body.find("\n      - name: Royal commissions")
    if start < 0:
        return ""
    rest = body[start + 1:]
    end = rest.find("\n      - name: ")
    return rest if end < 0 else rest[:end]


check("draft.ts exists and says which state the site is in", DRAFT_TS.exists())
check("the weekly job exists", WORKFLOW.exists())

draft = flag()
body = WORKFLOW.read_text(encoding="utf-8")
block = rc_block(body)
check("the weekly job has a royal commissions step", bool(block))
forgiving = "continue-on-error: true" in block

print(f"\n  the index is {'a draft' if draft else 'PUBLISHED'}; its step "
      f"{'does not gate' if forgiving else 'gates'} the run")

if draft:
    check("a draft does not gate the weekly run", forgiving)
else:
    check("a published index gates the weekly run: delete the `continue-on-error: true` "
          "line from the royal commissions step", not forgiving)

# The pages the flag governs must be the pages that exist, or the sitemap will
# offer an address the site does not build.
pages = re.search(r"ROYAL_COMMISSIONS_PAGES\s*=\s*\[([^\]]*)\]", DRAFT_TS.read_text(encoding="utf-8"))
listed = re.findall(r'"([^"]+)"', pages.group(1)) if pages else []
built = [HERE / "site" / "src" / "pages" / (p.strip("/") + ".astro") for p in listed]
check("every page the flag names is a page the site builds",
      bool(listed) and all(p.exists() for p in built))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
    sys.exit(1)
print("all tests passed")
