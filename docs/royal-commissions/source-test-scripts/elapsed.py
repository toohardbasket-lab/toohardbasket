"""Elapsed time from a report to its response, and from a report to today.

The register makes no overdue claim about a royal commission: no statute
requires a government to answer one, so there is no deadline to be past. What
it can show is elapsed time, which is arithmetic on two tabling dates.

    python3 elapsed.py [YYYY-MM-DD]     # the day to count to, default today
"""
import sys
from datetime import date

today = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()

# Tabling dates from the Tabled Documents register, ids in brackets.
PAIRS = [
    ("Robodebt: report tabled in the Senate [2743] to response tabled in the House [4163]",
     date(2023, 7, 7), date(2023, 11, 13)),
    ("Robodebt: report tabled in the Senate [2743] to today",
     date(2023, 7, 7), today),
    ("Robodebt: report tabled in the Senate [2743] to the closed chapter tabled in the House [15488]",
     date(2023, 7, 7), date(2026, 3, 12)),
    ("Disability: report tabled in the Senate [3444] to response tabled in the Senate [6874]",
     date(2023, 9, 29), date(2024, 7, 31)),
    ("Disability: report tabled in the Senate [3444] to today",
     date(2023, 9, 29), today),
]
for name, a, b in PAIRS:
    print(f"{(b - a).days:>5} days  {name} ({a} to {b})")
