"""
build_ledger.py — The Ledger: every committee report currently awaiting a
government response, and how long it has waited.

Sources:
  1. The President of the Senate's twice-yearly schedule of outstanding
     responses (PDF, e.g. ledger/presidents_2025-06-30.pdf). Committee
     headings are BOLD; entry rows are regular type with columns at fixed
     x-positions (title <250, date 250-330, response received 330-420,
     within-3-months 420+). Verified against the 30 June 2025 schedule.
  2. data/responses.csv — responses tabled SINCE the schedule date remove
     entries from the ledger (current outstanding = schedule minus
     answered-since).

Usage:
    python build_ledger.py "ledger/1 January to 30 June 2025 final.pdf" 2025-06-30
Writes data/ledger.csv and prints a summary.
"""
from __future__ import annotations
import csv, re, sys, pathlib
from datetime import date
from collections import defaultdict
import pdfplumber

HERE = pathlib.Path(__file__).parent
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2})\b")

# The date column starts around x=247 in the 30 June 2025 schedule; match the
# date TOKEN by pattern and position rather than slicing characters at a
# boundary (which clips leading digits).
DATE_TOKEN_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{2}$")
X_DATE_MIN, X_DATE_MAX, X_RESP_MAX = 230, 345, 475


def _strip_footnote(words: list[str]) -> list[str]:
    """Drop trailing lone-digit footnote markers (e.g. 'operations 2')."""
    while words and words[-1].isdigit() and len(words[-1]) <= 2:
        words = words[:-1]
    return words


def parse_schedule(pdf_path: str, schedule_date: date) -> list[dict]:
    rows: list[dict] = []
    committee_parts: list[str] = []
    committee = ""
    current: dict | None = None
    pending: list[str] = []   # orphan title lines awaiting owner

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[2:]:  # listing starts page 3
            words = page.extract_words(extra_attrs=["fontname"])
            lines: dict[int, list] = defaultdict(list)
            for w in words:
                lines[round(w["top"])].append(w)
            for top in sorted(lines):
                ws = sorted(lines[top], key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in ws).strip()
                if not text or text.isdigit():          # page numbers
                    continue
                bold = sum(1 for w in ws if "Bold" in w["fontname"])
                if bold > len(ws) * 0.6:
                    if ("Committee and report title" in text or "tabled/presented" in text
                            or "within 3 months" in text or "Date report" in text
                            or ("Response" in text and len(text) < 45)):
                        continue                        # table header lines
                    committee_parts.append(text)
                    continue
                # regular line — first flush any pending committee heading
                if committee_parts:
                    if pending and current:      # orphans before a new committee
                        current["title"] += " " + " ".join(pending)
                        pending = []
                    committee = " ".join(committee_parts)
                    committee_parts = []
                date_word = next((w for w in ws if DATE_TOKEN_RE.match(w["text"])
                                  and X_DATE_MIN <= w["x0"] <= X_DATE_MAX), None)
                if date_word:
                    title_words = _strip_footnote(
                        [w["text"] for w in ws if w["x0"] < date_word["x0"] - 2])
                    resp_words = [w["text"] for w in ws
                                  if date_word["x1"] < w["x0"] <= X_RESP_MAX]
                    # titles can wrap BEFORE the dated line (pending buffer) or
                    # AFTER it. Decide where held lines belong: a dated line
                    # whose title starts mid-phrase takes them as its prefix;
                    # otherwise they finish the previous entry.
                    first = title_words[0] if title_words else ""
                    if pending and (not first or first[0].islower()
                                    or first[0] in ")]—-&" or first[0].isdigit()):
                        title_words = pending + title_words
                        pending = []
                    elif pending and current:
                        current["title"] += " " + " ".join(pending)
                        pending = []
                    elif pending:
                        title_words = pending + title_words
                        pending = []
                    d, mo, yy = (int(x) for x in date_word["text"].split("."))
                    year = 2000 + yy if yy <= (schedule_date.year % 100) + 1 else 1900 + yy
                    try:
                        tabled = date(year, mo, d)
                    except ValueError:
                        tabled = None
                    if current:
                        rows.append(current)
                    current = {"committee": committee,
                               "title": " ".join(title_words),
                               "report_tabled": tabled.isoformat() if tabled else "",
                               "interim_received": " ".join(resp_words).startswith("Interim"),
                               "notes": "" if tabled else "unparsed date; "}
                else:
                    cont = _strip_footnote(
                        [w["text"] for w in ws if w["x0"] < X_DATE_MIN])
                    if cont:
                        pending.extend(cont)
        if pending and current:
            current["title"] += " " + " ".join(pending)
        if current:
            rows.append(current)
    return rows


def norm_tokens(s: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if len(w) > 3}


def reconcile(schedule_rows: list[dict], responses_csv: str,
              schedule_date: date, today: date) -> list[dict]:
    """Mark schedule entries answered since the schedule date; compute days."""
    # Match schedule entries to answered-since responses by TITLE TOKENS
    # first, with report dates as a sanity band: the schedule may use the
    # presented date where our register uses tabled, and gaps of weeks occur
    # when a report is presented out of session.
    answered: list[dict] = []
    with open(responses_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["response_tabled"] and r["response_tabled"] > schedule_date.isoformat():
                r["_tokens"] = norm_tokens(r["inquiry"] + " " + r["committee"])
                answered.append(r)

    def best_match(s: dict):
        s_tokens = norm_tokens(s["title"] + " " + s["committee"])
        if not s["report_tabled"]:
            return None
        s_date = date.fromisoformat(s["report_tabled"])
        best, best_score = None, 0
        for c in answered:
            refs = [c["report_last_tabled"], c["report_first_tabled"]]
            gaps = [abs((date.fromisoformat(x) - s_date).days) for x in refs if x]
            if not gaps:
                continue
            gap = min(gaps)   # multi-report inquiries: any of its report dates
            if gap > 180:
                continue
            overlap = len(s_tokens & c["_tokens"])
            # exact-ish date needs modest overlap; distant date needs strong
            need = 2 if gap <= 7 else 3
            if overlap >= need and overlap > best_score:
                best, best_score = c, overlap
        return best

    out = []
    for s in schedule_rows:
        entry = dict(s)
        entry["status"] = "outstanding"
        entry["response_tabled"] = ""
        entry["days_outstanding"] = ((today - date.fromisoformat(s["report_tabled"])).days
                                     if s["report_tabled"] else "")
        cand = best_match(s)
        if cand:
            entry["status"] = "answered_since_schedule"
            entry["response_tabled"] = cand["response_tabled"]
            entry["days_outstanding"] = (date.fromisoformat(cand["response_tabled"])
                                         - date.fromisoformat(s["report_tabled"])).days
        out.append(entry)
    return out


def main(argv):
    pdf_path = argv[1] if len(argv) > 1 else str(HERE / "ledger" / "presidents_2025-06-30.pdf")
    schedule_date = date.fromisoformat(argv[2]) if len(argv) > 2 else date(2025, 6, 30)
    today = date.fromisoformat(argv[3]) if len(argv) > 3 else date.today()

    rows = parse_schedule(pdf_path, schedule_date)
    print(f"schedule rows parsed: {len(rows)}")
    ledger = reconcile(rows, str(HERE / "data" / "responses.csv"), schedule_date, today)

    outstanding = [r for r in ledger if r["status"] == "outstanding" and r["days_outstanding"] != ""]
    answered = [r for r in ledger if r["status"] == "answered_since_schedule"]
    outstanding.sort(key=lambda r: -r["days_outstanding"])

    out = HERE / "data" / "ledger.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["status", "committee", "title", "report_tabled",
                                          "days_outstanding", "interim_received",
                                          "response_tabled", "notes"])
        w.writeheader()
        for r in sorted(ledger, key=lambda r: (r["status"], -(r["days_outstanding"] or 0))):
            w.writerow(r)

    import statistics
    days = [r["days_outstanding"] for r in outstanding]
    print(f"as at {today}: {len(outstanding)} reports outstanding "
          f"({len(answered)} on the schedule answered since {schedule_date})")
    if days:
        print(f"oldest: {days[0]:,} days | median: {statistics.median(days):,.0f} days | "
              f">1 year: {sum(1 for d in days if d > 365)} | "
              f">5 years: {sum(1 for d in days if d > 1826)}")
        print("\ntop 10 longest outstanding:")
        for r in outstanding[:10]:
            print(f"  {r['days_outstanding']:>6,}d  {r['report_tabled']}  "
                  f"{('[interim] ' if r['interim_received'] else '')}{r['title'][:64]}")
    print(f"wrote {out} ({len(ledger)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
