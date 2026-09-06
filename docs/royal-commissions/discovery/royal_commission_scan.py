#!/usr/bin/env python3
"""Build a discovery-level census of Australian royal commissions.

Wikipedia list pages are used only as broad discovery indexes. The resulting
rows are candidates that require verification against official parliamentary,
gazette, archival or commission sources before publication.
"""

from __future__ import annotations

import csv
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from lxml import html


PAGES = {
    "Commonwealth": "List_of_Australian_royal_commissions",
    "New South Wales": "List_of_New_South_Wales_royal_commissions",
    "Queensland": "List_of_Queensland_commissions_of_inquiry",
    "South Australia": "List_of_South_Australian_royal_commissions",
    "Tasmania": "List_of_Tasmanian_royal_commissions",
    "Victoria": "List_of_Victorian_royal_commissions",
    "Western Australia": "List_of_Western_Australian_royal_commissions",
}

API = "https://en.wikipedia.org/w/api.php"


def clean(value: str) -> str:
    value = re.sub(r"\[[^\]]*]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ,;\n")


def get_tree(page: str):
    query = urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"}
    )
    request = urllib.request.Request(
        f"{API}?{query}",
        headers={"User-Agent": "TooHardBasketResearch/1.0 contact@toohardbasket.org.au"},
    )
    parsed = json.load(urllib.request.urlopen(request, timeout=30))["parse"]
    return html.fromstring(parsed["text"]["*"])


def anchor_url(node) -> str:
    links = node.xpath(".//a[not(starts-with(@href, '#'))]/@href")
    if not links:
        return ""
    href = links[0]
    if href.startswith("./"):
        return "https://en.wikipedia.org/wiki/" + href[2:]
    if href.startswith("/"):
        return "https://en.wikipedia.org" + href
    return href


def years_from(text: str) -> tuple[str, str, str]:
    hits = re.findall(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2})(?!\d)", text)
    if not hits:
        return "", "", ""
    start = hits[0]
    end = hits[-1] if len(hits) > 1 else hits[0]
    return start, end, "–".join((start, end)) if start != end else start


def make_row(jurisdiction: str, title: str, year_text: str, source: str, item_url: str):
    combined = f"{year_text} {title}"
    start, end, inferred = years_from(combined)
    title = clean(title)
    return {
        "candidate_id": "",
        "jurisdiction": jurisdiction,
        "title": title,
        "year_start": start,
        "year_end": end,
        "year_text": clean(year_text) or inferred,
        "inquiry_family": (
            "commission_of_inquiry"
            if "commission of inquiry" in title.lower() and "royal" not in title.lower()
            else "royal_commission"
        ),
        "discovery_source": source,
        "candidate_page": item_url,
        "verification_status": "candidate_unverified",
        "recommendation_tracking_status": "not_assessed",
        "notes": "",
    }


def extract_table(jurisdiction: str, tree, table_index: int, title_col: int, year_col: int):
    rows = []
    tables = tree.xpath("//table")
    for tr in tables[table_index].xpath(".//tr[position()>1]"):
        cells = tr.xpath("./th|./td")
        if len(cells) <= max(title_col, year_col):
            continue
        title = clean(cells[title_col].text_content())
        years = clean(cells[year_col].text_content())
        if title:
            rows.append(
                make_row(
                    jurisdiction,
                    title,
                    years,
                    "https://en.wikipedia.org/wiki/" + PAGES[jurisdiction],
                    anchor_url(cells[title_col]),
                )
            )
    return rows


def extract_lists(jurisdiction: str, tree):
    rows = []
    for ul in tree.xpath("//ul[not(ancestor::table)]"):
        classes = " ".join(
            ul.xpath("ancestor-or-self::*[@class]/@class")
        ).lower()
        if any(token in classes for token in ("reflist", "references", "navbox", "toc")):
            continue
        preceding_headings = ul.xpath("preceding::h2|preceding::h3")
        section = clean(preceding_headings[-1].text_content()).lower() if preceding_headings else ""
        if section in {"references", "see also", "external links", "footnotes", "notes"}:
            continue
        for li in ul.xpath("./li"):
            text = clean(li.text_content())
            low = text.lower()
            if "royal commission" not in low and "commission of inquiry" not in low:
                continue
            if text.startswith("List of ") or len(text) > 500:
                continue
            if text.startswith("Borchardt, Dietrich Hans"):
                continue
            # A trailing or leading bracket-free year is retained separately,
            # but the raw title is preserved for later official verification.
            years = " ".join(re.findall(r"(?:18|19|20)\d{2}(?:[–-](?:18|19|20)?\d{2})?", text))
            rows.append(
                make_row(
                    jurisdiction,
                    text,
                    years,
                    "https://en.wikipedia.org/wiki/" + PAGES[jurisdiction],
                    anchor_url(li),
                )
            )
    return rows


def extract_commonwealth(tree):
    rows = []
    for h2 in tree.xpath("//h2"):
        heading = clean(h2.text_content())
        if not heading.startswith("Held"):
            continue
        lists = h2.xpath("following::ol[1]")
        if not lists:
            continue
        for li in lists[0].xpath("./li"):
            text = clean(li.text_content())
            years = " ".join(re.findall(r"(?:18|19|20)\d{2}(?:[–-](?:18|19|20)?\d{2})?", text))
            rows.append(
                make_row(
                    "Commonwealth",
                    text,
                    years,
                    "https://en.wikipedia.org/wiki/" + PAGES["Commonwealth"],
                    anchor_url(li),
                )
            )
    return rows


def dedupe(rows):
    seen = set()
    out = []
    for row in rows:
        key = (row["jurisdiction"], re.sub(r"\W+", "", row["title"].lower()))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    for i, row in enumerate(out, 1):
        row["candidate_id"] = f"rc-candidate-{i:04d}"
    return out


def main():
    trees = {j: get_tree(p) for j, p in PAGES.items()}
    rows = extract_commonwealth(trees["Commonwealth"])
    rows += extract_lists("New South Wales", trees["New South Wales"])
    rows += extract_lists("Queensland", trees["Queensland"])
    rows += extract_table("South Australia", trees["South Australia"], 0, 1, 0)
    rows += extract_lists("Tasmania", trees["Tasmania"])
    rows += extract_table("Victoria", trees["Victoria"], 1, 1, 0)
    rows += extract_table("Western Australia", trees["Western Australia"], 0, 0, 2)
    rows = dedupe(rows)

    output = Path("royal_commissions_candidate_census.csv")
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    counts = {}
    for row in rows:
        counts[row["jurisdiction"]] = counts.get(row["jurisdiction"], 0) + 1
    print(json.dumps({"rows": len(rows), "by_jurisdiction": counts}, indent=2))


if __name__ == "__main__":
    main()
