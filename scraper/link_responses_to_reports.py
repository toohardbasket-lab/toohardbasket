"""link_responses_to_reports.py — which report each government response answers.

A response that quotes the committee's recommendations one by one carries them
into the index itself. A response that does not — one that notes the
recommendations as a group and describes a policy instead, or closes the
report with the form letter without listing them — leaves the index with
nothing to show for the report, and a reader searching the topic finds
nothing. The House's online-gambling inquiry of 2023 is the example: 31
recommendations, answered in May 2026 by a response that sets out none of
them.

To show those recommendations the site needs the report itself, and to find
the report it needs to know which one the response answers. Three sources, in
order of strength, the same order answered_since.py uses:

  1. OTD's own documentLinks (data/response_report_links.csv) — the
     Parliament's statement of which response answers which report.
  2. data/response_report_links_manual.csv — a pairing checked by hand.
  3. The report's title, which the response's own title nearly always carries
     after the word "report:", searched on the Tabled Documents register and
     accepted only when a committee document tabled before the response
     matches it closely.

The pairing is written to data/response_reports.csv and kept: a response
already paired, or already searched and not found, is not searched again
unless --refetch is given. Nothing here changes a register or a
classification; it records which report a response is about.

    python link_responses_to_reports.py            # pair every corpus response
    python link_responses_to_reports.py --refetch  # search again for the unfound
"""
from __future__ import annotations

import csv
import datetime as dt
import pathlib
import re
import sys
import time

import requests

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
OUT = DATA / "response_reports.csv"
API = "https://otd.aph.gov.au/public-api/api"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Origin": "https://www.aph.gov.au",
    "Referer": "https://www.aph.gov.au/",
}
FIELDS = ["response_id", "report_id", "report_title", "report_tabled", "report_url",
          "basis", "checked_on"]

# The report's title, as the response's title carries it. "Australian
# Government response to the House of Representatives Standing Committee on
# Social Policy and Legal Affairs report: 'You win some, you lose more': ..."
# — everything after the first "report:" or "inquiry report:" and before a
# bracketed date.
TITLE_AFTER = re.compile(r"\b(?:report|inquiry|reports)\s*[:\-–—]\s*(.+)$", re.I)
TITLE_ON = re.compile(r"\breport\s+(?:on|into)\s+(?:the\s+)?(.+)$", re.I)
# The numbered series name their report without a colon: "...Committee of
# Public Accounts and Audit report Report 477: Commonwealth Financial..."
TITLE_NUMBERED = re.compile(r"\breport\s+(Report\s+\d{1,4}\b.*)$", re.I)
# A response to a bill inquiry often carries only the bill's name: "Australian
# Government Response to the Treasury Laws Amendment (...) Bill 2024
# [Provisions]". The bill's name is the report's title.
TITLE_BILL = re.compile(r"\bresponse\s+(?:to\s+)?(?:the\s+)?(.+\bBills?\b.+)$", re.I)
TRAILING_DATE = re.compile(r"\s*[\[(]\s*\w+\s+\d{4}\s*[\])]\s*$")
# The scaffolding of a title, which cannot carry a match: "COAG Legislation
# Amendment Bill 2021" shares four of its five words with every other
# amendment bill of that year.
NOISE = set("""the a an of and for on in to into its it report reports inquiry
australia australian government response committee legislation amendment bill
bills act provisions measures other laws treasury regulations related no""".split())


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _tokens(s: str) -> set[str]:
    return {w for w in _norm(s).split() if w not in NOISE and len(w) > 2}


def report_title_from(response_title: str) -> str:
    t = re.sub(r"\s+", " ", response_title or "").strip()
    m = TITLE_AFTER.search(t) or TITLE_ON.search(t) or TITLE_NUMBERED.search(t) or TITLE_BILL.search(t)
    if not m:
        return ""
    title = TRAILING_DATE.sub("", m.group(1)).strip(" :;,.-–—'\"“”‘’")
    return title


def overlap(a: str, b: str) -> float:
    """How much of each title the other carries — the lesser of the two
    directions, so a candidate with a subtitle of its own ("Government
    Amendments to ...") scores below the report that is simply the title."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    both = len(ta & tb)
    return min(both / len(ta), both / len(tb))


def search(session: requests.Session, title: str, before: str) -> list[dict]:
    body = {"pageSize": 25, "currentPage": 1, "searchString": title,
            "dateFrom": "2000-01-01", "dateTo": before or time.strftime("%Y-%m-%d"),
            "documentCategories": [], "documentTypes": [], "authors": [],
            "tableSenate": True, "tableHouse": True, "additionalDocumentTypes": [],
            "departments": [], "parliamentNumbers": [], "isDisallowable": [],
            "sortBy": "relevance", "sortDirection": "descending"}
    r = session.post(f"{API}/search", json=body, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json().get("results") or []


def is_response(title: str) -> bool:
    return bool(re.match(r"\s*(?:australian\s+)?government(?:'s|’s)?\s+response", title or "", re.I))


# The words that tell two reports of one inquiry apart. A response to the
# final report was pairing with the interim report on the strength of every
# other word; a response to a 2016 bill's inquiry with the 2023 bill's.
STAGE = re.compile(r"\b(interim|final|first|second|third|fourth|fifth|progress|advisory|annual)\b", re.I)
YEAR = re.compile(r"\b(19|20)\d{2}\b")


def agree(title: str, candidate: str) -> bool:
    """Same stage words and the same years, or no pairing."""
    st = {w.lower() for w in STAGE.findall(title)}
    sc = {w.lower() for w in STAGE.findall(candidate)}
    if st != sc:
        return False
    yt = set(YEAR.findall(title) and re.findall(r"\b(?:19|20)\d{2}\b", title))
    yc = set(re.findall(r"\b(?:19|20)\d{2}\b", candidate))
    return yt <= yc


def best(results: list[dict], title: str, before: str) -> tuple[dict | None, float]:
    """The committee document that carries this title, tabled before the response."""
    top, score = None, 0.0
    # "Interim Report" or "Report 6/2021" is not enough to search on: too
    # many documents carry those words and nothing else in common.
    if len(_tokens(title)) < 3:
        return None, 0.0
    for d in results:
        dtitle = d.get("title") or ""
        if is_response(dtitle):
            continue
        who = f"{d.get('author') or ''} {d.get('department') or ''}"
        if not re.search(r"committee|commission", who, re.I):
            continue
        tabled = ((d.get("tabledSenate") or d.get("tabledHouse") or "")[:10])
        if before and tabled and tabled > before:
            continue
        if not agree(title, dtitle):
            continue
        s = overlap(title, dtitle)
        if s > score:
            top, score = d, s
    return top, score


def existing() -> dict[str, dict]:
    if not OUT.exists():
        return {}
    with OUT.open(newline="", encoding="utf-8-sig") as f:
        return {r["response_id"]: r for r in csv.DictReader(f)}


def main(argv: list[str]) -> int:
    refetch = "--refetch" in argv
    excluded = {r["id"] for r in csv.DictReader(open(DATA / "scope_exclusions.csv", encoding="utf-8-sig"))}
    docs = [r for r in csv.DictReader(open(DATA / "response_documents.csv", encoding="utf-8-sig"))
            if r["id"] not in excluded]
    otd_links: dict[str, dict] = {}
    p = DATA / "response_report_links.csv"
    if p.exists():
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            otd_links.setdefault(r["response_id"], r)
    manual: dict[str, str] = {}
    p = DATA / "response_report_links_manual.csv"
    if p.exists():
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            manual[r["response_id"]] = r["report_id"]
    reports_index = {r["id"]: r for r in csv.DictReader(open(DATA / "committee_reports.csv", encoding="utf-8-sig"))}

    rows = existing()
    today = dt.date.today().isoformat()
    session = requests.Session()
    counts = {"otd link": 0, "by hand": 0, "title search": 0, "not found": 0, "kept": 0}
    searched = 0
    for d in docs:
        rid = d["id"]
        prior = rows.get(rid)
        if prior and prior["report_id"]:
            counts["kept"] += 1
            continue
        if prior and not refetch:
            counts["kept"] += 1
            continue
        tabled_resp = d["tabled_senate"] or d["tabled_house"]
        row = {"response_id": rid, "report_id": "", "report_title": "", "report_tabled": "",
               "report_url": "", "basis": "", "checked_on": today}
        link = otd_links.get(rid)
        if link:
            idx = reports_index.get(link["report_id"], {})
            row.update(report_id=link["report_id"], report_title=link["report_title"],
                       report_tabled=(idx.get("tabled_senate") or idx.get("tabled_house") or ""),
                       report_url=f"https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{link['report_id']}",
                       basis="otd link")
            counts["otd link"] += 1
        elif rid in manual:
            mid = manual[rid]
            idx = reports_index.get(mid, {})
            row.update(report_id=mid, report_title=idx.get("title", ""),
                       report_tabled=(idx.get("tabled_senate") or idx.get("tabled_house") or ""),
                       report_url=f"https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{mid}",
                       basis="by hand")
            counts["by hand"] += 1
        else:
            title = report_title_from(d["title"])
            hit, score = (None, 0.0)
            if title:
                try:
                    hit, score = best(search(session, title, tabled_resp), title, tabled_resp)
                except Exception as e:  # noqa: BLE001 — a failed search is a row not found, and is retried next run
                    print(f"  {rid}: search failed: {str(e)[:80]}", file=sys.stderr)
                searched += 1
                time.sleep(0.2)
            # Four fifths of the title's distinctive words, the same bar
            # answered_since.py sets: below it, no link is the right answer.
            if hit and score >= 0.8:
                row.update(report_id=str(hit["id"]), report_title=(hit.get("title") or "").strip(),
                           report_tabled=((hit.get("tabledSenate") or hit.get("tabledHouse") or "")[:10]),
                           report_url=f"https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/{hit['id']}",
                           basis=f"title search ({score:.2f})")
                counts["title search"] += 1
            else:
                row["basis"] = "not found" if title else "no title in response"
                counts["not found"] += 1
        rows[rid] = row

    tmp = OUT.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: int(r["response_id"])))
    tmp.replace(OUT)
    paired = sum(1 for r in rows.values() if r["report_id"])
    print(f"{len(docs)} responses in the corpus; {paired} paired with their report "
          f"({searched} searched this run): " + ", ".join(f"{v} {k}" for k, v in counts.items() if v))
    print(f"wrote {OUT.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
