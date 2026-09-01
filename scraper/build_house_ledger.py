"""Build the House of Representatives ledger from the Speaker's schedule.

The House analogue of build_ledger.py. Deliberately the same shape, because the
two registers must report the same things the same way (see
claude/thb-register-spec.md).

Source: "Speaker's Schedule of the Status of Government Responses to Committee
Reports", presented to the House at roughly six-monthly intervals, in the last
sitting weeks of the winter and spring sittings.

    Report title | Date tabled or published | Date of government response |
    Responded in period specified

**Read the third column.** Like the President's report, this is a status list of
every report requiring a response, not a list of outstanding ones. Its values:

    a date                        the response has been received
    'No response to date'         nothing has been received
    'Partial response received'   Public Accounts and Audit, answered by
                                  executive minute one recommendation at a
                                  time; page 3 of the schedule says these are
                                  "not considered complete or removed from the
                                  schedule until all recommendations have been
                                  responded to"
    'Fully responded'             as above, now complete

The fourth column carries the deadline verdict — 'Yes', 'No', or 'Time not
expired' — and it is the Speaker's, not ours. That matters: the 29 September
2010 resolution gives six months but excludes any period when the House was
dissolved, so a date subtraction of our own would be wrong. Take his answer.

**Two things the Speaker's schedule does not have**, both of which the President's
report does, and both of which must be disclosed rather than left as empty
columns:

  - It does not record "the Government's response is being considered". The
    November 2025 schedule wrote that sentence out; this one records only "No
    response to date". That fact lives in the *government's* own status report,
    presented within a day or two of the Speaker's and covering the same date,
    and this builder now reads it as a second source.

    The rule for that second source is narrow and absolute: **it may set a flag
    on a row; it may never add or remove one.** Which reports are outstanding is
    the Speaker's to say. What the government has said about them is the
    government's. This is exactly what the President of the Senate does — his
    "Interim*" is derived from the same government report — so the two registers
    end up reporting the same fact from the same place.
  - It is a rolling document. Page 2: responses received during the period are
    listed, "and the report it relates to is then removed from subsequent
    schedules". So a single schedule cannot give the answered history the
    President's report gives; that needs the back run, which OTD holds from
    December 2022.

Finding it: the Speaker's schedules sit in OTD under the category "Presented by
Presiding Officer", NOT under the document type "Government response" where the
older ones were filed. Searching only the old location is how the 30 June 2026
schedule was missed for a day and the House was wrongly called nine months
stale.

Format note: the schedule was a Word table up to November 2025 and is a PDF
from June 2026. This reads the PDF.

Output: data/house_ledger.csv, matching ledger_v2.csv column-for-column so the
site can treat both registers through one Obligation type, plus
data/house_ledger_meta.json.

Usage:  python build_house_ledger.py [--as-at YYYY-MM-DD] [--keep-pdf]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import pathlib
import re
import sys
import urllib.request

import pdfplumber

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
LEDGER = HERE / "ledger"

OTD_SEARCH = "https://otd.aph.gov.au/public-api/api/search"
OTD_DOC = "https://otd.aph.gov.au/public-api/api/documents/{doc_id}"
OTD_FILE = "https://otd.aph.gov.au/public-api/api/documents/{doc_id}/files/{file_id}"
OTD_PAGE = "https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{doc_id}"

UA = "toohardbasket/1.0 (+https://toohardbasket.org.au; a public-interest register)"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json",
           "User-Agent": UA}

SCHEDULE_TITLE = re.compile(r"speaker.{0,3}s schedule of the status of government responses", re.I)
AS_AT = re.compile(r"as at (\d{1,2}) ([A-Za-z]+) (\d{4})", re.I)
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}

# Dates in this schedule are dd/mm/yy and may carry a footnote marker: "6/3/25*v".
DATE_CELL = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*\*?\s*[a-z]{0,3}\s*$")

# "responses received since 21 November 2025 (the reporting date of the last
# schedule) and outstanding as at 30 June 2026" — page 4.
PERIOD_START = re.compile(r"received since (\d{1,2}) ([A-Za-z]+) (\d{4})", re.I)

NO_RESPONSE = "No response to date"
PARTIAL = "Partial response received"
COMPLETE = "Fully responded"
DEADLINE_VERDICTS = {"Yes", "No", "Time not expired", "Time has not expired"}

# The committee heading sits in the second cell of its row; a title that wrapped
# across a page break comes back as a lone cell in the first.
COMMITTEE_CELL, TITLE_CELL = 1, 0


def _post(payload: dict) -> dict:
    req = urllib.request.Request(OTD_SEARCH, data=json.dumps(payload).encode(),
                                 headers=HEADERS)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def _get(url: str) -> bytes:
    with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
        return r.read()


def as_at_date(title: str) -> dt.date | None:
    m = AS_AT.search(title or "")
    if not m:
        return None
    day, month, year = m.groups()
    if month.lower() not in MONTHS:
        return None
    try:
        return dt.date(int(year), MONTHS[month.lower()], int(day))
    except ValueError:
        return None


def parse_date(day: str, month: str, year: str) -> dt.date | None:
    d, m, y = int(day), int(month), int(year)
    y = y if y > 999 else (2000 + y if y < 90 else 1900 + y)
    try:
        return dt.date(y, m, d)
    except ValueError:
        return None


def cell_date(text: str) -> dt.date | None:
    m = DATE_CELL.match(text or "")
    return parse_date(*m.groups()) if m else None


def find_latest_schedule() -> dict:
    """Return metadata for the most recent Speaker's schedule held by OTD."""
    docs, page = [], 1
    while True:
        d = _post({"sortBy": 0, "sortDirection": 0, "pageSize": 100, "currentPage": page,
                   "tableHouse": True, "tableSenate": True,
                   "documentCategories": ["Presented by Presiding Officer"]})
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
        sys.exit(f"No Speaker's schedule found in OTD (swept {len(docs)} documents in "
                 "the presiding officers' category) — refusing to rebuild the ledger.")
    found.sort(key=lambda t: t[0])
    at, doc = found[-1]

    meta = json.loads(_get(OTD_DOC.format(doc_id=doc["id"])).decode())["document"]
    files = meta.get("files") or []
    if not files:
        sys.exit(f"Schedule {doc['id']} has no attached file — refusing to rebuild.")
    f = files[0]
    return {"as_at": at, "doc_id": doc["id"], "file_id": f["fileId"],
            "file_name": f["name"], "title": doc["title"],
            "tabled": (doc.get("tabledHouse") or doc.get("tabledSenate") or "")[:10],
            "url": OTD_PAGE.format(doc_id=doc["id"]),
            "parliament": meta.get("parliamentNumber") or doc.get("parliamentNumber"),
            "schedules_seen": len(found)}


def fetch_schedule(info: dict) -> pathlib.Path:
    dest = LEDGER / f"speakers_{info['as_at'].isoformat()}{pathlib.Path(info['file_name']).suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 50_000:
        return dest
    blob = _get(OTD_FILE.format(doc_id=info["doc_id"], file_id=info["file_id"]))
    if len(blob) < 50_000:
        sys.exit(f"Downloaded only {len(blob)} bytes from OTD — refusing to rebuild.")
    if dest.suffix == ".pdf" and not blob.startswith(b"%PDF"):
        sys.exit("Downloaded file is not a PDF — the schedule's format has changed.")
    dest.write_bytes(blob)
    return dest


def period_start(pdf) -> dt.date | None:
    """The reporting date of the previous schedule, as this one states it."""
    for page in pdf.pages[:6]:
        m = PERIOD_START.search((page.extract_text() or "").replace("\n", " "))
        if m:
            day, month, year = m.groups()
            if month.lower() in MONTHS:
                try:
                    return dt.date(int(year), MONTHS[month.lower()], int(day))
                except ValueError:
                    return None
    return None


GOVT_TITLE = re.compile(
    r"status of government responses in the house of representatives", re.I)
GOVT_STATUS_DATE = re.compile(r"^\s*(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{2,4})\s*$")
GOVT_COMMITTEE = re.compile(
    r"(\((House|Joint|Senate)[^)]*\)|[\u2013\u2014-]\s*(Joint|House|Senate)\s+\w+)\s*$")
BEING_CONSIDERED = "is being considered"


def find_government_report(near: str, parliament: int | None) -> dict | None:
    """The government's own status report, presented beside the Speaker's.

    It carries no as-at date in its title — only in its filename — so it is
    found by title and by being tabled within a fortnight of the Speaker's
    schedule. The search results are not in date order, so the whole category is
    swept; narrowing to the current Parliament cuts it from about 5,200
    documents to 1,700. Returns None rather than failing: the register is the
    Speaker's and must build without this.
    """
    if not near:
        return None
    target = dt.date.fromisoformat(near)
    query = {"sortBy": 0, "sortDirection": 0, "pageSize": 100,
             "tableHouse": True, "tableSenate": True,
             "documentCategories": ["Government Document"]}
    if parliament:
        query["parliamentNumbers"] = [parliament]
    page = 1
    while True:
        d = _post({**query, "currentPage": page})
        for x in d["results"]:
            if not GOVT_TITLE.search(x.get("title") or ""):
                continue
            tabled = (x.get("tabledHouse") or x.get("tabledSenate") or "")[:10]
            if not tabled:
                continue
            if abs((dt.date.fromisoformat(tabled) - target).days) > 14:
                continue
            meta = json.loads(_get(OTD_DOC.format(doc_id=x["id"])).decode())["document"]
            files = [f for f in (meta.get("files") or [])
                     if f["name"].lower().endswith(".pdf")]
            if not files:
                continue
            return {"doc_id": x["id"], "file_id": files[0]["fileId"],
                    "file_name": files[0]["name"], "title": x["title"],
                    "tabled": tabled, "url": OTD_PAGE.format(doc_id=x["id"])}
        if page >= d["pageCount"] or page >= 60:
            break
        page += 1
    return None


def parse_government_report(pdf_path: pathlib.Path) -> list[dict]:
    """Committee and report title | Date report tabled | Status, as a sentence.

    Titles wrap over several one-cell rows, and committee headings sit in the
    same cell as those continuations — they are told apart by the committee
    suffix every committee name carries ("(House, Standing)", "- Joint
    Statutory"). Short tables are rotated column headers, not the listing.
    """
    rows: list[dict] = []
    committee = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if len(table) < 5:
                    continue
                for raw in table:
                    cells = [(c or "").replace("\n", " ").strip() for c in raw]
                    idx = [(i, c) for i, c in enumerate(cells) if c]
                    if not idx or any("Committee and report title" in c for _, c in idx):
                        continue
                    at = next((k for k, (_, c) in enumerate(idx)
                               if GOVT_STATUS_DATE.match(c)), None)
                    if at is None:
                        if len(idx) == 1:
                            text = idx[0][1]
                            if GOVT_COMMITTEE.search(text):
                                committee = text
                            elif rows:
                                rows[-1]["title"] += " " + text
                        continue
                    title = " ".join(c for _, c in idx[:at]).strip()
                    if not title:
                        continue                      # a stray date cell
                    status = next((c for _, c in idx[at + 1:]
                                   if not GOVT_STATUS_DATE.match(c)), "")
                    m = GOVT_STATUS_DATE.match(idx[at][1])
                    tabled = parse_date(*m.groups())
                    if tabled is None:
                        continue
                    rows.append({"committee": committee,
                                 "title": re.sub(r"\s+", " ", title).strip(),
                                 "report_tabled": tabled,
                                 "status": status})
    return rows


def norm_tokens(text: str) -> frozenset[str]:
    return frozenset(w for w in re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
                     if len(w) > 3)


def match_government(rows: list[dict], govt: list[dict]) -> tuple[int, int]:
    """Set being_considered from the government's own words. Never adds a row."""
    matched = considered = 0
    for r in rows:
        tabled = dt.date.fromisoformat(r["report_tabled"])
        t = norm_tokens(r["title"])
        best, score = None, 0
        for g in govt:
            if abs((g["report_tabled"] - tabled).days) > 2:
                continue
            overlap = len(t & norm_tokens(g["title"]))
            if overlap > score:
                best, score = g, overlap
        if best is None or score < 2:
            continue
        matched += 1
        if BEING_CONSIDERED in best["status"].replace("\u2019", "'"):
            r["being_considered"] = True
            considered += 1
    return matched, considered


def summary_counts(pdf) -> dict:
    """The schedule's own tally, by Parliament — the check on our parse.

    Columns: awaiting (time expired) | awaiting (time not expired) |
             received (time expired) | received (time not expired)
    """
    totals = {"awaiting_expired": 0, "awaiting_current": 0,
              "received_expired": 0, "received_current": 0}
    keys = list(totals)
    for page in pdf.pages[:6]:
        for table in page.extract_tables():
            for raw in table:
                cells = [(c or "").replace("\n", " ").strip() for c in raw]
                filled = [c for c in cells if c]
                if len(filled) != 5 or not re.match(r"^\d+(st|nd|rd|th)$", filled[0]):
                    continue
                if not all(c.isdigit() for c in filled[1:]):
                    continue
                for k, v in zip(keys, filled[1:]):
                    totals[k] += int(v)
    return totals


def parse_schedule(pdf_path: pathlib.Path) -> list[dict]:
    """Walk the schedule's table, carrying the committee down over its reports."""
    rows: list[dict] = []
    committee = ""

    with pdfplumber.open(pdf_path) as pdf:
        summary = summary_counts(pdf)
        since = period_start(pdf)
        for page in pdf.pages:
            for table in page.extract_tables():
                cleaned = [[(c or "").replace("\n", " ").strip() for c in raw]
                           for raw in table]
                # Tables with no date anywhere are the rotated column headers and
                # the summary tally, not the listing. Skip them whole.
                if not any(cell_date(c) for raw in cleaned for c in raw[1:]):
                    continue

                for cells in cleaned:
                    idx = [(i, c) for i, c in enumerate(cells) if c]
                    if not idx or any("Report title" in c for _, c in idx):
                        continue

                    if len(idx) == 1:
                        at, text = idx[0]
                        if at == COMMITTEE_CELL:
                            committee = text
                        elif at == TITLE_CELL and rows:
                            # A title that wrapped over a page break.
                            rows[-1]["title"] = f"{rows[-1]['title']} {text}".strip()
                        continue

                    if idx[0][0] != TITLE_CELL:
                        continue
                    values = [c for _, c in idx]
                    title, rest = values[0], values[1:]
                    if not rest:
                        continue
                    tabled = cell_date(rest[0])
                    if tabled is None:
                        continue                       # not a report row

                    resp = rest[1] if len(rest) > 1 else ""
                    within = rest[2] if len(rest) > 2 else ""
                    if resp in DEADLINE_VERDICTS:
                        # The response cell is blank, so the deadline verdict has
                        # shifted left into it.
                        resp, within = "", resp

                    received = cell_date(resp)
                    partial = resp.startswith(PARTIAL)
                    complete = resp.startswith(COMPLETE)
                    nothing = resp.startswith(NO_RESPONSE) or resp == ""

                    # A response dated before this reporting period began is an
                    # oddity: the schedule says a report is removed once its
                    # response is received, so such a row should not be here at
                    # all, and the Speaker's page-4 tally counts it as still
                    # awaiting. It is recorded and reported, but NOT published as
                    # outstanding: the row itself gives a response date and the
                    # government's own status report gives the same one, so two
                    # records say the report was answered and only an aggregate
                    # says otherwise. Publishing an answered report as unanswered
                    # is the one error this project cannot afford.
                    out_of_period = bool(received and since and received < since)

                    notes = ""
                    if out_of_period:
                        notes += (f"response of {received.isoformat()} predates this "
                                  f"reporting period, which began {since.isoformat()}; "
                                  "the schedule's own tally still counts the report as "
                                  "awaiting one; ")
                    if received is None and not (partial or complete or nothing):
                        notes += f"unrecognised status {resp!r}; "
                    if within and within not in DEADLINE_VERDICTS:
                        notes += f"unrecognised deadline verdict {within!r}; "

                    rows.append({
                        "committee": committee,
                        "title": re.sub(r"\s+", " ", title).strip(),
                        "report_tabled": tabled,
                        "schedule_status": resp,
                        "response_received": received,
                        "response_out_of_period": received if out_of_period else None,
                        "within_period": within,
                        "partial_response": partial,
                        "complete_response": complete,
                        "notes": notes,
                    })
    return rows, summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-at", help="Compute days outstanding at this date (default: today)")
    ap.add_argument("--keep-pdf", action="store_true", help="(kept for compatibility)")
    args = ap.parse_args()
    as_at = dt.date.fromisoformat(args.as_at) if args.as_at else dt.date.today()

    info = find_latest_schedule()
    path = fetch_schedule(info)
    print(f"schedule: {info['title']}")
    print(f"  OTD {info['doc_id']} presented {info['tabled']} -> {path.name}")

    records, summary = parse_schedule(path)
    out_of_period = [r for r in records if r["response_out_of_period"]]
    if len(records) < 40:
        sys.exit(f"Only {len(records)} report rows parsed — implausibly few. "
                 "Refusing to overwrite the ledger; check the document format.")

    # The Speaker gives his own verdict on whether each answered report was
    # responded to in time, which is the only on-time measure the House has:
    # there is no register of House responses going back to 2000 as there is for
    # the Senate. It therefore covers only the responses THIS schedule records —
    # those received since the previous one — and the site must say so.
    answered_verdicts = [r["within_period"] for r in records
                         if (r["response_received"] or r["complete_response"])
                         and r["within_period"] in ("Yes", "No")]
    on_time = answered_verdicts.count("Yes")

    outstanding = [r for r in records
                   if r["response_received"] is None and not r["complete_response"]]
    answered = [r for r in records if r not in outstanding]

    # The schedule counts itself on page 4. If our parse disagrees, say so loudly
    # rather than publishing a number the source contradicts.
    expected_out = summary["awaiting_expired"] + summary["awaiting_current"]
    expected_ans = summary["received_expired"] + summary["received_current"]
    agree = len(outstanding) == expected_out and len(answered) == expected_ans
    print(f"parsed {len(records)} report rows across "
          f"{len({r['committee'] for r in records})} committees")
    if out_of_period:
        print(f"  {len(out_of_period)} row(s) carry a response from before this "
              "reporting period. The Speaker's tally counts them as awaiting one; "
              "the rows themselves record a response, and so does the government's "
              "report, so they are published as answered:")
        for r in out_of_period:
            print(f"    {r['response_out_of_period']}  {r['title'][:58]}")
    reconciled = len(outstanding) + len(out_of_period) == expected_out and \
        len(answered) - len(out_of_period) == expected_ans
    print(f"  outstanding {len(outstanding)} (schedule's own tally says {expected_out})"
          f"   answered {len(answered)} (tally says {expected_ans})")
    if agree:
        print("  reconciled with the schedule's tally: AGREE")
    elif reconciled:
        print(f"  reconciled with the schedule's tally once the {len(out_of_period)} "
              "out-of-period response(s) are accounted for")
    else:
        print("  *** DOES NOT RECONCILE with the schedule's own tally — investigate ***")

    rows = []
    for r in outstanding:
        overdue = r["within_period"] == "No"
        rows.append({
            "days_outstanding": (as_at - r["report_tabled"]).days,
            "report_tabled": r["report_tabled"].isoformat(),
            "committee": r["committee"],
            "title": r["title"],
            "interim_response": False,
            # The Speaker's schedule does not record "being considered"; the
            # government's own status report does. Never fabricate it here.
            "being_considered": False,
            "partial_response": r["partial_response"],
            "response_out_of_period": (r["response_out_of_period"].isoformat()
                                       if r["response_out_of_period"] else ""),
            "overdue": overdue,
            "interim_report": bool(re.search(r"\binterim\b", r["title"], re.I)),
            "source": "speakers_schedule",
            "notes": r["notes"],
        })
    rows.sort(key=lambda x: -x["days_outstanding"])

    # The government's own status report, presented beside the Speaker's, says
    # what it has told each committee. It may flag a row; it may never add or
    # remove one.
    govt_info = find_government_report(info["tabled"], info.get("parliament"))
    govt_matched = govt_considered = 0
    govt_path = None
    if govt_info:
        govt_path = LEDGER / f"govt_house_{info['as_at'].isoformat()}.pdf"
        if not (govt_path.exists() and govt_path.stat().st_size > 50_000):
            govt_path.write_bytes(_get(OTD_FILE.format(doc_id=govt_info["doc_id"],
                                                       file_id=govt_info["file_id"])))
        govt_rows = parse_government_report(govt_path)
        govt_matched, govt_considered = match_government(rows, govt_rows)
        print(f"government report: OTD {govt_info['doc_id']} presented "
              f"{govt_info['tabled']}, {len(govt_rows)} reports listed")
        print(f"  matched {govt_matched} of {len(rows)} outstanding reports; "
              f"{govt_considered} recorded as \"the Government's response is being "
              "considered\"")
        if govt_matched < len(rows):
            print(f"  {len(rows) - govt_matched} row(s) not found in the government's "
                  "report — left unflagged rather than assumed")
    else:
        print("government report: not found in OTD near this schedule — "
              "being-considered left unrecorded")

    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / "house_ledger.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    meta = {
        "as_at": info["as_at"].isoformat(),
        "tabled": info["tabled"],
        "title": info["title"],
        "otd_id": info["doc_id"],
        "otd_url": info["url"],
        "pdf": path.name,
        "listed": len(records),
        "answered_at_schedule": len(answered),
        "outstanding_at_schedule": len(outstanding),
        "schedule_says_outstanding": expected_out,
        "schedule_says_answered": expected_ans,
        "parse_agrees_with_schedule": agree,
        "partial_response": sum(1 for r in rows if r["partial_response"]),
        "overdue": sum(1 for r in rows if r["overdue"]),
        "not_yet_due": sum(1 for r in rows if not r["overdue"]),
        "answered_on_time": on_time,
        "answered_with_a_verdict": len(answered_verdicts),
        "on_time_rate": (on_time / len(answered_verdicts)) if answered_verdicts else 0,
        "response_out_of_period": len(out_of_period),
        "reconciles_with_schedule": bool(agree or reconciled),
        "being_considered": govt_considered,
        "being_considered_recorded": bool(govt_info),
        "being_considered_source": govt_info["url"] if govt_info else "",
        "being_considered_tabled": govt_info["tabled"] if govt_info else "",
        "government_report_matched": govt_matched,
        "rows": len(rows),
        "covers_to": max(r["report_tabled"] for r in rows),
        "rebuilt": as_at.isoformat(),
    }
    (DATA / "house_ledger_meta.json").write_text(json.dumps(meta, indent=2) + "\n",
                                                 encoding="utf-8")

    noted = [r for r in records if r["notes"] and not r["response_out_of_period"]]
    # `rows` was written before the government's report was read, so rewrite it.
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    if noted:
        print(f"  {len(noted)} row(s) the parser could not classify — review:")
        for r in noted[:8]:
            print(f"    {r['title'][:52]} | {r['notes']}")
    print(f"  overdue {meta['overdue']}   within time {meta['not_yet_due']}   "
          f"answered in part {meta['partial_response']}")
    if answered_verdicts:
        print(f"  of the {len(answered_verdicts)} answered reports the Speaker gives a "
              f"verdict on, {on_time} were responded to within six months "
              f"({on_time / len(answered_verdicts) * 100:.0f}%)")
    print(f"wrote {out} ({len(rows)} rows, as at {as_at}) and house_ledger_meta.json")


if __name__ == "__main__":
    main()
