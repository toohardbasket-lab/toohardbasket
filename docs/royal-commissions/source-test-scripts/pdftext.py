"""PDF to text, the way the pipeline does it.

harvest_report_pdfs.py reads a report with pdfplumber, page by page, and joins
the pages with a newline. Anything the source test says about what the existing
extractor can and cannot find has to be said about that same text, so this is
the same three lines and nothing else.

    python3 pdftext.py <pdf> <out.txt>

Prints the page count and the number of characters, so a scanned page — which
comes back empty — shows up as pages without characters.
"""
import io
import sys

import pdfplumber

src, dst = sys.argv[1], sys.argv[2]
pages = []
with pdfplumber.open(io.BytesIO(open(src, "rb").read())) as pdf:
    for page in pdf.pages:
        pages.append(page.extract_text() or "")
body = "\n".join(pages)
open(dst, "w", encoding="utf-8").write(body)
empty = sum(1 for p in pages if not p.strip())
print(f"{src}: {len(pages)} pages, {len(body)} characters, {empty} pages with no text")
