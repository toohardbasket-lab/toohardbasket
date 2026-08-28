"""
thb_parser.py — parsing core for The Too Hard Basket inquiry-response dataset.

Two register formats:
  * "classic"  — Senate StatsNet Classic year pages, 2000–2011.
                 Structure: committee heading, then entries of the form
                 "Title—Report presented D, tabled D" / "Response tabled D".
  * "statsnet" — Senate StatsNet (2012 onward), a 4-column table
                 (Inquiry / Committee / Report / Government response).
                 parse_statsnet_text() handles the flattened text form;
                 the live scraper feeds it per-row cell text.

Design rules (credibility depends on these):
  - Never guess a date. A line that fails to parse is recorded in
    row["notes"] and surfaces in validation, not silently dropped.
  - The clock starts at the report's TABLED date (presented-only dates
    are used as fallback and flagged), and for multi-report inquiries
    the LAST report tabled is used for the headline days figure — the
    conservative choice — with the first-tabled date also recorded.
  - Deadline: Senate order of 14 March 1973 — response within 3 months.
    We encode this as 90 days (deadline_days column, adjustable).
"""

from __future__ import annotations
import re
from datetime import date
from dataclasses import dataclass, field, asdict

DEADLINE_DAYS = 90

MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

LONG_DATE_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
SLASH_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

# 'tbled' is a real typo on the 2011 page — accept it.
REPORT_LINE_RE = re.compile(r"—?Reports?\s+(?:presented|tabled|tbled)\b", re.I)
STANDALONE_REPORT_RE = re.compile(r"^Reports?\s+(?:presented|tabled|tbled)\b", re.I)
# 'Reaponse' is a real typo in the 2009 register — accept it.
RESPONSE_LINE_RE = re.compile(
    r"^(Response|Reaponse|Interim response|Replacement response|Final response|"
    r"Further response)s?\b", re.I)

COMMITTEE_SPLIT_RES = [
    re.compile(r"\s((?:Select Committee|Joint Select Committee|Joint Standing Committee|"
               r"Joint Committee|Parliamentary Joint Committee|Parliamentary Standing Committee|"
               r"Standing Committee)\s+(?:of|on|for)\s.+)$"),
    re.compile(r"\s([A-Z][A-Za-z,'’()&\- ]+?(?:References|Legislation)\s+Committee)$"),
    re.compile(r"\s([A-Z][A-Za-z,'’()&\- ]+?\sCommittee)$"),
]


def parse_long_date(text: str) -> date | None:
    """'23 August 2010' -> date. Returns None on failure."""
    m = LONG_DATE_RE.search(text)
    if not m:
        return None
    day, month, year = int(m.group(1)), MONTHS.get(m.group(2).lower()), int(m.group(3))
    if not month:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def all_long_dates(text: str) -> list[date]:
    out = []
    for m in LONG_DATE_RE.finditer(text):
        month = MONTHS.get(m.group(2).lower())
        if month:
            try:
                out.append(date(int(m.group(3)), month, int(m.group(1))))
            except ValueError:
                pass
    return out


def parse_slash_date(text: str) -> date | None:
    """'1/4/2026' (d/m/yyyy, en-AU) -> date."""
    m = SLASH_DATE_RE.search(text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def split_inquiry_committee(line: str) -> tuple[str, str]:
    """Split the merged 'Inquiry title Committee name' text-form line.
    HTML scraping supplies the two cells separately and skips this."""
    for rx in COMMITTEE_SPLIT_RES:
        m = rx.search(line)
        if m:
            return line[: m.start()].strip(), m.group(1).strip()
    return line.strip(), ""


@dataclass
class Row:
    era: str                       # 'classic' | 'statsnet'
    committee: str
    inquiry: str                   # report/inquiry title ('' if committee-only)
    report_first_tabled: str = ""  # ISO dates
    report_last_tabled: str = ""
    response_tabled: str = ""
    days_to_respond: int | None = None       # from report_last_tabled
    days_from_first_report: int | None = None
    deadline_days: int = DEADLINE_DAYS
    days_overdue: int | None = None
    interim_only: bool = False
    source: str = ""
    notes: str = ""
    raw: str = field(default="", repr=False)

    def finalise(self):
        rl = date.fromisoformat(self.report_last_tabled) if self.report_last_tabled else None
        rf = date.fromisoformat(self.report_first_tabled) if self.report_first_tabled else None
        rs = date.fromisoformat(self.response_tabled) if self.response_tabled else None
        if rl and rs:
            self.days_to_respond = (rs - rl).days
            self.days_overdue = max(0, self.days_to_respond - self.deadline_days)
        if rf and rs:
            self.days_from_first_report = (rs - rf).days
        return self


# ---------------------------------------------------------------- classic ----

def _classic_report_dates(segment: str) -> tuple[date | None, date | None, str]:
    """From 'Report presented X, tabled Y' (or variants) return
    (first_tabled, last_tabled, note). Prefer tabled over presented."""
    note = ""
    tabled = all_long_dates(re.sub(r"presented\s+\d{1,2}\s+\w+\s+\d{4},?\s*", "", segment)) \
        if "tabled" in segment.lower() or "tbled" in segment.lower() else []
    if not tabled:
        tabled = all_long_dates(segment)
        if tabled:
            note = "presented date used (no tabled date)"
    if not tabled:
        return None, None, "no report date parsed"
    return min(tabled), max(tabled), note


PARLIAMENT_SECTION_RE = re.compile(r"^\d+(st|nd|rd|th)\s+Parliament$", re.I)


def parse_classic_text(text: str, source: str = "") -> list[Row]:
    """Parse the text of a Classic year page (2000–2011).

    Two modes: if the text carries '## ' committee markers (emitted by
    classic_scraper's HTML reducer), headings are explicit and any bare
    line is an entry title — including 2000/2001-era entries that have no
    report date recorded. Without markers (hand-captured fixtures), the
    original heuristic applies: a line with no report pattern is a heading."""
    marker_mode = text.lstrip().startswith("## ") or "\n## " in text
    rows: list[Row] = []
    committee = ""
    current: Row | None = None

    for rawline in text.splitlines():
        line = rawline.strip()
        if not line:
            continue
        # skip page furniture
        if line.startswith(("Government responses to committee reports",
                            "Number of government responses",
                            "Tabled or presented in", "Presented in",
                            "Previous page", "Next page", "HOME ", "Senate StatsNet",
                            "StatsNET:")):
            continue

        if RESPONSE_LINE_RE.match(line):
            if current is None:
                continue
            d = parse_long_date(line.split("tabled")[-1]) or parse_long_date(line)
            is_interim = line.lower().startswith("interim")
            if d:
                iso = d.isoformat()
                if not current.response_tabled or not is_interim:
                    # final/replacement responses supersede interim ones
                    if current.response_tabled and is_interim:
                        pass
                    else:
                        current.response_tabled = iso
                        current.interim_only = is_interim
            else:
                current.notes += "unparsed response line; "
            current.raw += " | " + line
            continue

        has_inline_report = bool(REPORT_LINE_RE.search(line))
        is_standalone = bool(STANDALONE_REPORT_RE.match(line))
        # Source quirk (2002 register): some RESPONSE lines are written
        # "Report presented X, tabled Y". A bare report-dates line while an
        # unanswered entry is open is that entry's response, not a new entry.
        if is_standalone and current is not None and not current.response_tabled:
            d = parse_long_date(line.split("tabled")[-1]) or parse_long_date(line)
            if d:
                current.response_tabled = d.isoformat()
                current.notes += "response line written as 'Report …' in register; "
                current.raw += " | " + line
                continue
        if has_inline_report or is_standalone:
            if current is not None:
                rows.append(current.finalise())
            if is_standalone:
                title, seg = "", line
            else:
                m = REPORT_LINE_RE.search(line)
                title, seg = line[: m.start()].strip(" —-"), line[m.start():]
            first, last, note = _classic_report_dates(seg)
            current = Row(era="classic", committee=committee, inquiry=title,
                          report_first_tabled=first.isoformat() if first else "",
                          report_last_tabled=last.isoformat() if last else "",
                          source=source, notes=note + ("; " if note else ""), raw=line)
            continue

        # President's schedule entries: "…—Tabled by the President of the Senate <date>"
        m = re.search(r"—Tabled by the President[^0-9]*", line)
        if m:
            if current is not None:
                rows.append(current.finalise())
            d = parse_long_date(line[m.start():])
            current = Row(era="classic", committee=committee,
                          inquiry=line[: m.start()].strip(" —-"),
                          report_first_tabled=d.isoformat() if d else "",
                          report_last_tabled=d.isoformat() if d else "",
                          source=source,
                          notes="" if d else "no report date parsed; ", raw=line)
            continue

        if marker_mode:
            if line.startswith("## "):
                if current is not None:
                    rows.append(current.finalise())
                    current = None
                head = line[3:].strip()
                if not PARLIAMENT_SECTION_RE.match(head):
                    committee = head
            else:
                # bare line = entry title with no report date recorded
                # (the 2000/2001 registers list only title + response date)
                if current is not None:
                    rows.append(current.finalise())
                current = Row(era="classic", committee=committee, inquiry=line,
                              source=source,
                              notes="report date not recorded in register; ",
                              raw=line)
            continue

        # heuristic mode: anything else is a committee heading
        if current is not None:
            rows.append(current.finalise())
            current = None
        committee = line

    if current is not None:
        rows.append(current.finalise())

    if marker_mode:
        # Merge pattern (2003, 2008, 2010 registers): a RUN of report lines
        # followed by ONE response covering them all — the register counts
        # the run as a single item. Merge each run into the responding row.
        merged: list[Row] = []
        run: list[Row] = []
        for r in rows:
            if not r.response_tabled and r.report_last_tabled:
                if run and run[-1].committee != r.committee:
                    merged.extend(run)
                    run = []
                run.append(r)
                continue
            if run and r.response_tabled and r.report_last_tabled \
                    and r.committee == run[-1].committee:
                firsts = [x.report_first_tabled or x.report_last_tabled for x in run] \
                         + [r.report_first_tabled or r.report_last_tabled]
                r.inquiry = "; and ".join([x.inquiry for x in run] + [r.inquiry])
                r.report_first_tabled = min(firsts)
                r.report_last_tabled = max(x.report_last_tabled for x in run + [r])
                r.notes += f"single response covers {len(run) + 1} reports; "
                run = []
                merged.append(r.finalise())
                continue
            merged.extend(run)
            run = []
            merged.append(r)
        merged.extend(run)
        rows = merged
    return rows


# --------------------------------------------------------------- statsnet ----

def parse_statsnet_cells(inquiry: str, committee: str,
                         report_cell: str, response_cell: str,
                         source: str = "") -> Row:
    """Parse one table row given its four cell texts (the scraper's path)."""
    tabled = [parse_slash_date(l) for l in report_cell.splitlines()
              if "tabled" in l.lower()]
    tabled = [d for d in tabled if d]
    note = ""
    if not tabled:
        tabled = [d for l in report_cell.splitlines()
                  if (d := parse_slash_date(l))]
        if tabled:
            note = "presented date used (no tabled date); "
    resp = [parse_slash_date(l) for l in response_cell.splitlines()
            if "tabled" in l.lower()]
    resp = [d for d in resp if d]
    if not resp:
        resp = [d for l in response_cell.splitlines() if (d := parse_slash_date(l))]
        if resp:
            note += "response presented date used; "
    # Clock start: latest report tabled — UNLESS a later report post-dates the
    # response (a response to an earlier report of a multi-report inquiry),
    # in which case the clock runs from the report the response follows.
    last = max(tabled) if tabled else None
    if tabled and resp and max(resp) < max(tabled):
        prior = [d for d in tabled if d <= max(resp)]
        if prior:
            last = max(prior)
            note += "a later report post-dates this response; clock uses the report it follows; "
    row = Row(era="statsnet", committee=committee.strip(), inquiry=inquiry.strip(),
              report_first_tabled=min(tabled).isoformat() if tabled else "",
              report_last_tabled=last.isoformat() if last else "",
              response_tabled=max(resp).isoformat() if resp else "",
              source=source, notes=note,
              raw=f"{inquiry} || {report_cell} || {response_cell}")
    if not tabled:
        row.notes += "no report date parsed; "
    if not resp:
        row.notes += "no response date parsed; "
    return row.finalise()


def parse_statsnet_text(text: str, source: str = "") -> list[Row]:
    """Parse the flattened text form of the StatsNet table (fixture path).
    Rows are 'report block' then 'response block', separated by blank lines."""
    blocks, buf = [], []
    for line in text.splitlines():
        if line.strip():
            buf.append(line.strip())
        elif buf:
            blocks.append(buf)
            buf = []
    if buf:
        blocks.append(buf)

    rows: list[Row] = []
    i = 0
    while i < len(blocks):
        rep = blocks[i]
        if i + 1 < len(blocks) and any(l.lower().startswith("response") for l in blocks[i + 1]):
            resp = blocks[i + 1]
            i += 2
        else:  # malformed pairing — flag, keep going
            resp = []
            i += 1
        inquiry, committee = split_inquiry_committee(rep[0])
        row = parse_statsnet_cells(inquiry, committee,
                                   "\n".join(rep[1:]), "\n".join(resp), source)
        if not committee:
            row.notes += "committee split failed; "
        rows.append(row)
    return rows


def rows_to_dicts(rows: list[Row]) -> list[dict]:
    out = []
    for r in rows:
        d = asdict(r)
        d.pop("raw", None)
        out.append(d)
    return out
