"""Sentences in which a government response commits to a date.

The register makes no overdue claim about a royal commission, so a date in a
response is recorded, not counted against. This finds the sentences to record:
a sentence containing a future-tense verb and a date, printed with the page it
is on, so it can be quoted verbatim and linked.

    python3 dated_sentences.py <pdf>

Page numbers are the PDF's own, counted from one; a document's printed page
number can differ from it.
"""
import re
import sys

import pdfplumber

# A date: a calendar year, or a month with or without one, or a quarter.
DATE = re.compile(r"\b(?:20[2-9]\d(?:[-–/]\d\d)?"
                  r"|(?:January|February|March|April|May|June|July|August|September|"
                  r"October|November|December)\s+20[2-9]\d"
                  r"|(?:first|second|third|fourth)\s+quarter"
                  r"|(?:early|mid|late)[\s-]20[2-9]\d)\b", re.I)
FUTURE = re.compile(r"\b(?:will|would|is\s+to|are\s+to|commit|commits|committed|"
                    r"intends?|expects?|due)\b", re.I)

with pdfplumber.open(sys.argv[1]) as pdf:
    n = 0
    for i, page in enumerate(pdf.pages, 1):
        text = " ".join((page.extract_text() or "").split())
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if DATE.search(sentence) and FUTURE.search(sentence):
                n += 1
                print(f"p{i}\t{sentence}")
print(f"# {n} sentences with a future-tense verb and a date in {sys.argv[1]}")
