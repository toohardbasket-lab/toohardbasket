"""List the Tabled Documents register, and filter it here rather than there.

harvest_responses.py posts to the same search endpoint with an empty
searchTerm and asks for one document type. Passing a searchTerm to that
endpoint returned the same 17,380 records as passing none, so the term is not
filtering and nothing here relies on it: this walks the register and matches
the title with a regular expression locally.

    python3 otd_search.py                                  # every document
    python3 otd_search.py --type "Royal commission"        # one type
    python3 otd_search.py --title 'robodebt'               # title regex, case-insensitive

Prints id | tabled Senate | tabled House | type | title, then a count.
"""
import json
import re
import sys
import urllib.request

SEARCH = "https://otd.aph.gov.au/public-api/api/search"

args = sys.argv[1:]
def opt(name, default=""):
    return args[args.index(name) + 1] if name in args else default

types = [opt("--type")] if "--type" in args else []
title = re.compile(opt("--title", "."), re.I)

rows, page = [], 1
while True:
    payload = {"searchTerm": "", "documentCategories": [], "documentTypes": types,
               "departments": [], "parliamentNumbers": [], "isDisallowable": [],
               "sortBy": 1, "sortDirection": 1, "pageSize": 100, "currentPage": page,
               "tableHouse": True, "tableSenate": True}
    req = urllib.request.Request(SEARCH, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Accept": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=60))
    results = data.get("results") or []
    rows += results
    if len(results) < 100:
        break
    page += 1

kept = 0
for d in rows:
    name = " ".join(str(d.get("title") or "").split())
    if not title.search(name):
        continue
    kept += 1
    print("|".join([str(d.get("id", "")),
                    (d.get("tabledSenate") or "")[:10],
                    (d.get("tabledHouse") or "")[:10],
                    str(d.get("typeDescription") or ""),
                    name]))
terms = []
if types:
    terms.append(f"type {types[0]!r}")
if "--title" in args:
    terms.append(f"title /{opt('--title')}/")
print(f"# {kept} of {len(rows)} register records match"
      + (" " + " and ".join(terms) if terms else ""))
