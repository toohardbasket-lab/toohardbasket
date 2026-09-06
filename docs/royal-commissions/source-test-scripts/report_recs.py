"""What extract_report_recommendations.py finds in a royal commission report.

The register reads an unanswered committee report with this step. A royal
commission report is the same kind of document — a numbered list of
recommendations, then a chapter arguing each — so the first question is
whether the existing code reads one. This runs its own function over a text
file and prints what comes back, with nothing changed.

    python3 report_recs.py <text file> [--rows]
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scraper"))

import extract_report_recommendations as er   # noqa: E402

body = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
found = er.recommendations_in(body)

if "--rows" in sys.argv:
    for f in found:
        print(f"{f['label']}\t{f['recommended_by']}\t{' '.join(f['recommendation'].split())[:90]}")

heads = er.HEAD.findall(body)
anywhere = sorted(set(re.findall(r"(?i)Recommendation\s+(\d{1,3}(?:\.\d{1,3})?)", body)),
                  key=lambda s: [int(p) for p in s.split(".")])
print(f"# {len(heads)} lines match the step's heading pattern (the label alone on its own line)")
print(f"# {len(anywhere)} distinct recommendation numbers appear anywhere in the text")
print(f"# {len(found)} recommendations extracted from {sys.argv[1]}")
