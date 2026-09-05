"""Tests for the stated-position test in coverage.py.

Each case is a sentence of the kind the government actually writes against a
recommendation, and the state the site must give it. A change to the patterns
that flips one of these is a change to what the site publishes, and should be
made on purpose.

    python tests/test_coverage.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import coverage as C  # noqa: E402

CASES = [
    # --- stated positions: labels
    ("Supported", True),
    ("Supported in principle The Australian Government considers that", True),
    ("Agreed in part. The Government supports re-writing the compliance", True),
    ("Not supported. The Government considers the existing framework adequate.", True),
    ("Accepted", True),
    ("Agreed in-principle The Government will", True),
    ("Partially accepted. The Government agrees to the first limb", True),
    # --- stated positions: verb with the recommendation as object
    ("The Government supports this recommendation. The Department will", True),
    ("The Australian Government supports this recommendation in principle.", True),
    ("The Australian Government agrees in principle with this Recommendation.", True),
    ("The Government accepts the Committee’s recommendation.", True),
    ("The Government does not agree to this recommendation. All applicants", True),
    ("The Australian Government does not support this recommendation.", True),
    ("The Government rejects the recommendation.", True),
    ("The Government agrees to Recommendation 4.", True),
    ("The Government notes this recommendation, which is directed to ASIC. The Government supports ASIC in considering", False),
    ("The Government accepts in principle this recommendation.", True),
    ("The Government partially accepts this recommendation.", True),
    ("The Government is unable to accept this recommendation at this time.", True),
    ("This recommendation has been implemented", True),
    ("The recommendation has been partially implemented: the votes of Members", True),
    # --- noted, no position
    ("The Government notes this recommendation.", False),
    ("The Government notes this recommendation. The Southern Ocean Observing System is a joint initiative", False),
    ("Noted The Government is committed to supporting all victim-survivors", False),
    ("Noted. The Australian Government is working to minimise social and economic impacts", False),
    ("The Australian Government acknowledges the range of views presented to the inquiry and notes this recommendation is a matter for States and Territories", False),
    ("The Australian Government notes this recommendation. The Australian Government supports the use of betterment funding in principle", False),
    # 'support' as an ordinary word, not a verdict on the recommendation
    ("Our bilateral and regional initiatives cover a broad range of support, including economic governance", False),
    ("The Government will support a proactive approach to raise awareness of these recommendations", False),
    ("The Government is delivering a dedicated Pacific Support Vessel.", False),
    # --- the form letter
    ("The Government notes this recommendation. However, given the passage of time since this report was tabled, a substantive Government response is no longer appropriate.", False),
    # --- other prose with no verdict word
    ("The Government has no plans to change the longstanding moratorium on nuclear power in Australia", False),
    ("This recommendation is for the Senate to respond to", False),
    ("", False),
]


def main() -> int:
    bad = []
    for words, want in CASES:
        got = C.position(words)
        if got != want:
            bad.append((words, want, got))
    # The form letter must be its own state, never a position.
    fl = C.state({"source": "response", "government_words": CASES[-4][0]})
    if fl != "form letter":
        bad.append((CASES[-4][0], "form letter", fl))
    if C.state({"source": "report", "government_words": ""}) != "not individual":
        bad.append(("report row", "not individual", "?"))
    if C.state({"source": "response", "government_words": ""}) != "unreadable":
        bad.append(("empty response row", "unreadable", "?"))
    for words, want, got in bad:
        print(f"FAIL want {want!r} got {got!r}: {words[:90]}")
    print(f"{len(CASES) + 3 - len(bad)} of {len(CASES) + 3} coverage cases pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
