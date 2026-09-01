"""
build_ledger.py — The Ledger: every committee report currently awaiting a
government response, and how long it has waited.

Sources:
  1. The President of the Senate's twice-yearly schedule of outstanding
     responses. Fetched from Online Tabled Documents, not from a
     hand-downloaded file: the President presents the schedule to the Senate,
     OTD carries it under the category "Presented by the President", and the
     PDF hangs off the document's file endpoint. www.aph.gov.au answers 403 to
     anything that is not a browser, so its archive page is not a usable
     source; OTD's public API is. Committee
     headings are BOLD; entry rows are regular type with columns at fixed
     x-positions (title <250, date 250-330, response received 330-420,
     within-3-months 420+). Verified against the 30 June 2025 schedule.
  2. data/responses.csv — responses tabled SINCE the schedule date remove
     entries from the ledger (current outstanding = schedule minus
     answered-since).

Usage:
    python build_ledger.py                    # fetch and parse the latest schedule
    python build_ledger.py "ledger/1 January to 30 June 2025 final.pdf" 2025-06-30
Writes data/ledger.csv, records what it used in data/ledger_meta.json, and
prints a summary.
"""
from __future__ import annotations
import csv, json, re, sys, pathlib, urllib.request
from datetime import date
from collections import defaultdict
import pdfplumber

HERE = pathlib.Path(__file__).parent
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2})\b")
DATE_RE_TABLE = re.compile(r"^\s*(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{2}|\d{4})\.?\s*$")

# The date column starts around x=247 in the 30 June 2025 schedule; match the
# date TOKEN by pattern and position rather than slicing characters at a
# boundary (which clips leading digits).
DATE_TOKEN_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{2}$")
X_DATE_MIN, X_DATE_MAX, X_RESP_MAX = 230, 345, 475


# --- fetching the schedule from Online Tabled Documents -------------------
#
# The President's reports sit in OTD under the category "Presented by the
# President" — about 130 documents, so the sweep is small and does not need a
# date window. The title carries the as-at date ("... as at 31 December 2025"),
# which is the date the register publishes as its position, so it is read from
# the document rather than passed in by hand.

OTD_SEARCH = "https://otd.aph.gov.au/public-api/api/search"
OTD_DOC = "https://otd.aph.gov.au/public-api/api/documents/{doc_id}"
OTD_FILE = "https://otd.aph.gov.au/public-api/api/documents/{doc_id}/files/{file_id}"
OTD_PAGE = "https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{doc_id}"

UA = "toohardbasket/1.0 (+https://toohardbasket.org.au; a public-interest register)"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json",
           "User-Agent": UA}

SCHEDULE_TITLE = re.compile(
    r"president.{0,3}s report to the senate on the status of government responses", re.I)
AS_AT = re.compile(r"as at (\d{1,2}) ([A-Za-z]+) (\d{4})", re.I)
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}


def _post(payload: dict) -> dict:
    req = urllib.request.Request(OTD_SEARCH, data=json.dumps(payload).encode(),
                                 headers=HEADERS)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def _get(url: str) -> bytes:
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
        return r.read()


def as_at_date(title: str) -> date | None:
    m = AS_AT.search(title or "")
    if not m:
        return None
    day, month, year = m.groups()
    if month.lower() not in MONTHS:
        return None
    try:
        return date(int(year), MONTHS[month.lower()], int(day))
    except ValueError:
        return None


def find_latest_schedule() -> dict:
    """Return metadata for the most recent President's schedule held by OTD."""
    docs, page = [], 1
    while True:
        d = _post({"sortBy": 0, "sortDirection": 0, "pageSize": 100, "currentPage": page,
                   "tableHouse": True, "tableSenate": True,
                   "documentCategories": ["Presented by the President"]})
        docs += d["results"]
        if page >= d["pageCount"]:
            break
        page += 1

    found = []
    for x in docs:
        title = x.get("title") or ""
        if not SCHEDULE_TITLE.search(title):
            continue
        at = as_at_date(title)
        if at:
            found.append((at, x))
    if not found:
        sys.exit(f"No President's schedule found in OTD (swept {len(docs)} documents "
                 "in the President's category) — refusing to rebuild the ledger.")
    found.sort(key=lambda t: t[0])
    at, doc = found[-1]

    meta = json.loads(_get(OTD_DOC.format(doc_id=doc["id"])).decode())["document"]
    files = [f for f in (meta.get("files") or []) if f["name"].lower().endswith(".pdf")]
    if not files:
        sys.exit(f"Schedule {doc['id']} has no PDF attached — refusing to rebuild.")
    return {"as_at": at, "doc_id": doc["id"], "file_id": files[0]["fileId"],
            "file_name": files[0]["name"], "title": doc["title"],
            "tabled": (doc.get("tabledSenate") or "")[:10],
            "url": OTD_PAGE.format(doc_id=doc["id"]),
            "schedules_seen": len(found)}


def fetch_schedule(info: dict) -> pathlib.Path:
    """Download the schedule PDF into ledger/, keeping every one we have used."""
    dest = HERE / "ledger" / f"presidents_{info['as_at'].isoformat()}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 50_000:
        return dest
    blob = _get(OTD_FILE.format(doc_id=info["doc_id"], file_id=info["file_id"]))
    if len(blob) < 50_000 or not blob.startswith(b"%PDF"):
        sys.exit(f"Downloaded {len(blob)} bytes from OTD and it is not a plausible "
                 "PDF — refusing to rebuild the ledger.")
    dest.write_bytes(blob)
    return dest


def _strip_footnote(words: list[str]) -> list[str]:
    """Drop trailing lone-digit footnote markers (e.g. 'operations 2')."""
    while words and words[-1].isdigit() and len(words[-1]) <= 2:
        words = words[:-1]
    return words


def parse_schedule(pdf_path: str, schedule_date: date) -> list[dict]:
    """Read the President's report as a table, and read its status column.

    The report is not a list of outstanding responses. It is a status list of
    every committee report that requires one, with four columns:

        Committee and report title | Date report tabled/presented |
        Response received | Response provided within 3 months

    The third column is what decides whether a report is still owed an answer:

        a date      the response has been received
        '-'         nothing has been received
        'Interim'   an interim response has been received
        'Interim*'  the government report says only that "the Government's
                    response is being considered" (defined on page 2 of the
                    report itself) — a holding line, not an answer

    Treating every listed row as outstanding, which an earlier version of this
    file did, would have published around 150 answered reports as unanswered.
    The register follows the President's own column.

    Pages render as a 12-column grid (merged cells) or a plain 4-column one,
    and the grid's columns shift by one on some pages, so the cells are read by
    position among the populated cells rather than at fixed indices: the cell
    that looks like a date is the tabling date, the cell before it is the
    title, and the two after it are the status columns.
    """
    rows: list[dict] = []
    committee = ""
    heading_open = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[2:]:                     # listing starts page 3
            table = page.extract_table()
            if not table:
                continue
            for raw in table:
                cells = [(c or "").replace("\n", " ").strip() for c in raw]
                filled = [c for c in cells if c]
                if not filled:
                    continue
                if "Committee and report title" in filled[0]:
                    continue                            # repeated table header

                at = next((i for i, c in enumerate(filled)
                           if DATE_RE_TABLE.match(c)), None)
                if at is None or at == 0:
                    if len(filled) == 1:
                        # A committee heading, which may run over two rows
                        # ("Administration of Sports Grants—" / "Senate
                        # Select"). Join them; start again after a report row.
                        if heading_open:
                            sep = "" if committee.endswith(("\u2014", "\u2013", "-")) else " "
                            committee = (committee + sep + filled[0]).strip()
                        else:
                            committee = filled[0]
                        heading_open = True
                    continue
                heading_open = False

                title = " ".join(filled[:at]).strip()
                date_text = filled[at]
                resp = filled[at + 1] if at + 1 < len(filled) else ""
                within = filled[at + 2] if at + 2 < len(filled) else ""
                if resp in ("Yes", "No"):
                    # The response cell is blank — nothing has been received —
                    # so what follows the date is the within-3-months answer.
                    resp, within = "", resp

                m = DATE_RE_TABLE.match(date_text)
                d, mo, yy = (int(x) for x in m.groups())
                year = yy if yy > 999 else (
                    2000 + yy if yy <= (schedule_date.year % 100) + 1 else 1900 + yy)
                try:
                    tabled = date(year, mo, d)
                except ValueError:
                    tabled = None

                # The status column, as the President records it.
                being_considered = resp.startswith("Interim*")
                interim = resp.startswith("Interim")
                # Public Accounts and Audit responds by executive minute, one
                # recommendation at a time, so its status column is a narrative
                # that ends in a verdict. "Incomplete response" means the
                # report is still owed an answer in part.
                partial = resp.endswith("Incomplete response")
                complete = resp.endswith("Complete response")
                received = None
                rm = DATE_RE_TABLE.match(resp.rstrip("*"))
                if rm:
                    rd, rmo, ryy = (int(x) for x in rm.groups())
                    try:
                        received = date(ryy if ryy > 999 else
                                        (2000 + ryy if ryy < 90 else 1900 + ryy), rmo, rd)
                    except ValueError:
                        received = None

                notes = ""
                if not tabled:
                    notes += "unparsed tabling date; "
                if not title:
                    notes += "no title in source row; "
                if not resp:
                    notes += "no status recorded in the schedule; "
                elif (received is None and not interim and not partial and not complete
                        and resp not in ("-", "\u2013", "\u2014")):
                    notes += f"unrecognised status {resp!r}; "

                rows.append({
                    "committee": committee,
                    "title": title,
                    "report_tabled": tabled.isoformat() if tabled else "",
                    "schedule_status": resp,
                    "response_received": received.isoformat() if received else "",
                    "within_3_months": within,
                    "interim_received": interim,
                    "being_considered": being_considered,
                    "partial_response": partial,
                    "complete_response": complete,
                    "notes": notes,
                })
    return rows


def norm_tokens(s: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if len(w) > 3}


# Words that carry no identifying weight. Committee report titles are mostly
# scaffolding — "... Amendment (...) Bill 2023 [Provisions] and related bills" —
# and matching on the scaffolding pairs unrelated reports from the same sitting
# week. Committee names are worse: nearly every one of them ends in the same
# three words. Both lists are subtracted before anything is compared.
TITLE_NOISE = {
    "bill", "bills", "provisions", "provision", "related", "amendment",
    "amendments", "legislation", "legislative", "measures", "other", "report",
    "reports", "reporting", "inquiry", "inquiries", "into", "interim", "final",
    "first", "second", "third", "fourth", "committee", "australia",
    "australian", "government", "response", "responses", "consequential",
    "matter", "matters", "review",
}
COMMITTEE_NOISE = {
    "committee", "committees", "legislation", "references", "joint", "select",
    "standing", "senate", "house", "representatives", "parliament",
    "parliamentary", "statutory", "affairs",
}
YEAR = re.compile(r"^(19|20)\d{2}$")


def distinctive(tokens: set[str], noise: set[str]) -> set[str]:
    return {t for t in tokens - noise if not YEAR.match(t)}


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
                r["_title"] = norm_tokens(r["inquiry"])
                r["_cttee"] = norm_tokens(r["committee"])
                answered.append(r)

    def best_match(s: dict):
        """Find the response, if any, that answers this schedule entry.

        Matching titles is the whole job, and it has to be tight in both
        directions. Too loose and the register drops reports that are still
        outstanding: an earlier version pooled title and committee tokens and
        allowed a 180-day date band, which let one response to a sexual consent
        report "answer" a foreign bribery bill report from the same committee —
        71 of 282 entries were culled that way, against 16 responses actually
        tabled. Too tight and the register keeps publishing a report as
        unanswered after the government has answered it, which is the error
        that matters most.

        So: titles are compared to titles (committee names are shared
        boilerplate and cannot carry the match), the report dates must
        substantially agree, and the committee has to overlap at all.
        """
        if not s["report_tabled"]:
            return None
        s_title = norm_tokens(s["title"])
        s_cttee = norm_tokens(s["committee"])
        s_date = date.fromisoformat(s["report_tabled"])
        if not s_title:
            return None

        s_key = distinctive(s_title, TITLE_NOISE)
        s_cttee_key = distinctive(s_cttee, COMMITTEE_NOISE)

        best, best_key = None, (0.0, -10 ** 6)
        for c in answered:
            refs = [c["report_last_tabled"], c["report_first_tabled"]]
            gaps = [abs((date.fromisoformat(x) - s_date).days) for x in refs if x]
            if not gaps:
                continue
            gap = min(gaps)      # multi-report inquiries: any of its report dates
            if gap > 31:         # tabled vs presented, and out-of-session gaps
                continue
            # Different committees do not answer each other's reports.
            c_cttee_key = distinctive(c["_cttee"], COMMITTEE_NOISE)
            if s_cttee_key and c_cttee_key and not (s_cttee_key & c_cttee_key):
                continue

            c_key = distinctive(c["_title"], TITLE_NOISE)

            # Two ways to be the same report. Either the distinctive words
            # agree — the words left once the legislative scaffolding is
            # stripped out — or the titles agree almost completely, which is
            # how a title made entirely of scaffolding ("Help to Buy Bill 2023
            # and the Help to Buy (Consequential Provisions) Bill 2023") gets
            # matched without letting two different bills from one sitting week
            # match each other on the word "bill".
            shared_key = s_key & c_key
            d_ratio = (len(shared_key) / min(len(s_key), len(c_key))
                       if s_key and c_key else 0.0)
            ok_distinct = len(shared_key) >= 2 and d_ratio >= 0.6

            f_ratio = (len(s_title & c["_title"])
                       / max(1, min(len(s_title), len(c["_title"]))))
            # A title with nothing distinctive in it at all — "Final report",
            # "Progress report" — cannot be matched on words, so the date has
            # to carry it.
            ok_full = f_ratio >= 0.8 and (bool(s_key and c_key) or gap <= 3)

            if not (ok_distinct or ok_full):
                continue
            ratio = max(d_ratio if ok_distinct else 0.0, f_ratio if ok_full else 0.0)
            key = (ratio, -gap)
            if key > best_key:
                best, best_key = c, key
        return best

    out = []
    for s in schedule_rows:
        entry = dict(s)
        tabled = date.fromisoformat(s["report_tabled"]) if s["report_tabled"] else None

        if s["response_received"] or s["complete_response"]:
            # The President records a response. That settles it.
            entry["status"] = "answered_at_schedule"
            entry["response_tabled"] = s["response_received"]
            entry["days_outstanding"] = (
                (date.fromisoformat(s["response_received"]) - tabled).days
                if s["response_received"] and tabled else "")
            out.append(entry)
            continue

        entry["status"] = "outstanding"
        entry["response_tabled"] = ""
        entry["days_outstanding"] = (today - tabled).days if tabled else ""

        # Between the schedule's as-at date and today, responses keep arriving.
        cand = best_match(s)
        if cand:
            entry["status"] = "answered_since_schedule"
            entry["response_tabled"] = cand["response_tabled"]
            entry["days_outstanding"] = (date.fromisoformat(cand["response_tabled"])
                                         - tabled).days if tabled else ""
        out.append(entry)
    return out


def main(argv):
    info = None
    if len(argv) > 2:
        pdf_path, schedule_date = argv[1], date.fromisoformat(argv[2])
        today = date.fromisoformat(argv[3]) if len(argv) > 3 else date.today()
    else:
        info = find_latest_schedule()
        pdf_path = str(fetch_schedule(info))
        schedule_date = info["as_at"]
        today = date.fromisoformat(argv[1]) if len(argv) > 1 else date.today()
        print(f"schedule: {info['title']}")
        print(f"  OTD {info['doc_id']} tabled {info['tabled']} -> {pathlib.Path(pdf_path).name}")

    rows = parse_schedule(pdf_path, schedule_date)
    print(f"schedule rows parsed: {len(rows)}")
    if len(rows) < 100:
        sys.exit(f"Only {len(rows)} rows parsed from {pdf_path} — implausibly few. "
                 "Refusing to overwrite the ledger; check the PDF layout.")
    ledger = reconcile(rows, str(HERE / "data" / "responses.csv"), schedule_date, today)

    outstanding = [r for r in ledger if r["status"] == "outstanding" and r["days_outstanding"] != ""]
    answered = [r for r in ledger if r["status"] == "answered_since_schedule"]
    at_schedule = [r for r in ledger if r["status"] == "answered_at_schedule"]
    print(f"the President records a response for {len(at_schedule)} of {len(ledger)} reports")
    print(f"  still owed an answer at {schedule_date}: {len(ledger) - len(at_schedule)} — "
          f"{sum(1 for r in ledger if r['being_considered'])} recorded only as "
          f"\"the Government's response is being considered\", "
          f"{sum(1 for r in ledger if r['partial_response'])} answered in part, "
          f"{sum(1 for r in ledger if r['status'] != 'answered_at_schedule' and not r['being_considered'] and not r['partial_response'] and not r['interim_received'])} with nothing received")
    outstanding.sort(key=lambda r: -r["days_outstanding"])

    out = HERE / "data" / "ledger.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["status", "committee", "title", "report_tabled",
                                          "days_outstanding", "interim_received",
                                          "being_considered", "partial_response",
                                          "schedule_status", "within_3_months",
                                          "response_tabled", "notes"],
                           extrasaction="ignore")
        w.writeheader()
        for r in sorted(ledger, key=lambda r: (r["status"], -(r["days_outstanding"] or 0))):
            w.writerow(r)

    import statistics
    days = [r["days_outstanding"] for r in outstanding]
    print(f"as at {today}: {len(outstanding)} reports outstanding "
          f"({len(answered)} on the schedule answered since {schedule_date}, "
          f"from {len(set(r['response_tabled'] + r['title'] for r in answered))} "
          "matched responses)")
    if answered:
        print("\nremoved as answered since the schedule — check each one:")
        for r in sorted(answered, key=lambda r: r["response_tabled"]):
            print(f"  {r['response_tabled']}  {r['report_tabled']}  {r['title'][:70]}")
        print()
    if days:
        print(f"oldest: {days[0]:,} days | median: {statistics.median(days):,.0f} days | "
              f">1 year: {sum(1 for d in days if d > 365)} | "
              f">5 years: {sum(1 for d in days if d > 1826)}")
        print("\ntop 10 longest outstanding:")
        for r in outstanding[:10]:
            print(f"  {r['days_outstanding']:>6,}d  {r['report_tabled']}  "
                  f"{('[interim] ' if r['interim_received'] else '')}{r['title'][:64]}")
    meta = {
        "as_at": schedule_date.isoformat(),
        "built": today.isoformat(),
        "pdf": pathlib.Path(pdf_path).name,
        "listed": len(ledger),
        "answered_at_schedule": len(at_schedule),
        "outstanding_at_schedule": len(outstanding) + len(answered),
        "answered_since_schedule": len(answered),
        "being_considered_at_schedule": sum(1 for r in ledger if r["being_considered"]),
        "partial_response_at_schedule": sum(1 for r in ledger if r["partial_response"]),
    }
    if info:
        meta.update({"otd_id": info["doc_id"], "otd_url": info["url"],
                     "title": info["title"], "tabled": info["tabled"]})
    (HERE / "data" / "ledger_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {out} ({len(ledger)} rows) and data/ledger_meta.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
