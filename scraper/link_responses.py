"""
link_responses.py — decide which tabled "Government response" documents are
actually responses to a parliamentary committee report.

The OTD document type `Government response` is broader than this project's
claim. Alan's QA of the classifier sample turned up three kinds of document
sitting in the corpus that answer no committee report at all:

  * status-of-responses schedules (a LIST of outstanding responses, not a response)
  * Migration Act s486O statements answering Commonwealth Ombudsman assessments
  * responses to royal commissions, independent reviews and the INSLM

They inflate the denominator behind "two in five responses to Parliament
answered nothing", and every one of them lands in the `substantive` class
because it contains no pro-forma template. The statistic and its denominator
have to describe the same population.

Titles alone cannot separate them — plenty of genuine responses never use the
word "committee" ("Australian Government Response to Treasury Laws Amendment
(Financial Market Infrastructure) Bill" answers a legislation committee report).
So each response is instead tested against the harvested universe of committee
reports: does it answer a report that actually exists?

    score >= 0.80  matched     in scope
    0.50 - 0.79    probable    in scope, flagged
    < 0.50         unmatched   candidate for exclusion — needs a human call

Writes data/response_links.csv (every response, its best match and score) and
qa/scope_<date>.html, a grouped confirmation sheet where a whole family can be
excluded in one click.

Usage:
    python link_responses.py
"""
from __future__ import annotations

import csv
import datetime
import html
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
QA = HERE / "qa"

STOP = {"report", "reports", "inquiry", "inquiries", "committee", "australian",
        "government", "response", "responses", "senate", "joint", "standing",
        "select", "references", "legislation", "statutory", "into", "the",
        "final", "interim", "first", "second", "third", "provisions", "bill",
        "bills", "related"}

# "Australian Government response to the X Committee report: <title>" — strip
# everything up to and including the report reference so the comparison is
# title against title.
PREFIX = re.compile(r"^.*?\bgovernment\s+response(?:s)?\s+to\s+(?:the\s+)?", re.I)
AFTER_REPORT = re.compile(r"\breports?\s*[::]\s*", re.I)

# Families to group the unmatched by, so a decision can be made per family
# rather than per document.
FAMILIES = [
    ("Status-of-responses schedules — a list of outstanding responses, not a response",
     re.compile(r"status of government responses", re.I)),
    ("Migration Act s486O — answers the Commonwealth Ombudsman, not a committee",
     re.compile(r"486O|Ombudsman", re.I)),
    ("Royal commissions — a different claimant",
     re.compile(r"royal commission", re.I)),
    ("Independent reviews and monitors — not a committee report",
     re.compile(r"independent (review|national security)|\bINSLM\b|independent monitor", re.I)),
]


def toks(s: str) -> frozenset[str]:
    return frozenset(w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()
                     if len(w) > 3 and w not in STOP)


def response_body(title: str) -> str:
    body = PREFIX.sub("", title)
    parts = AFTER_REPORT.split(body, maxsplit=1)
    return parts[-1] if len(parts) > 1 else body


def load(name: str) -> list[dict]:
    return list(csv.DictReader(open(DATA / name, newline="", encoding="utf-8-sig")))


def main(argv: list[str]) -> int:
    reports = [r for r in load("committee_reports.csv")
               if r["tabled_senate"] or r["tabled_house"]]
    resps = load("response_documents.csv")
    if not reports or not resps:
        print("missing committee_reports.csv or response_documents.csv", file=sys.stderr)
        return 1

    # The OTD report universe only reaches back to mid-2022, but the flush
    # answered reports far older than that — a pro-forma closure that matches
    # nothing here is usually answering a pre-2022 report, not a non-committee
    # document. responses.csv carries the inquiry titles back to 2000, so it is
    # used as a second index. Without it the filter would delete the very
    # documents the project's central finding rests on.
    idx = [(r, toks(r["title"]), (r["tabled_senate"] or r["tabled_house"])[:10]) for r in reports]
    for r in load("responses.csv"):
        title = (r.get("inquiry") or "").strip()
        if not title:
            continue
        idx.append(({"id": "", "title": title + "  [pre-2022 register]"},
                    toks(title), (r.get("report_first_tabled") or "")[:10]))

    linked = []
    for x in resps:
        rt = (x["tabled_senate"] or x["tabled_house"] or "")[:10]
        t = toks(response_body(x["title"]))
        best, score = None, 0.0
        for rep, rtok, rd in idx:
            if not t or not rtok:
                continue
            if rt and rd > rt:            # a report cannot be answered before it exists
                continue
            s = len(t & rtok) / min(len(t), len(rtok))
            if s > score:
                best, score = rep, s
        verdict = "matched" if score >= 0.80 else "probable" if score >= 0.50 else "unmatched"
        linked.append({
            "id": x["id"], "classification": x["classification"],
            "tabled": rt, "title": x["title"],
            "score": f"{score:.2f}", "verdict": verdict,
            "match_id": best["id"] if best else "",
            "match_title": best["title"] if best else "",
            "url": x["url"],
        })

    with open(DATA / "response_links.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linked[0].keys()))
        w.writeheader(); w.writerows(linked)

    # Families are decided by what a document IS, from its title, not by
    # whether it happened to match a report. A s486O statement can match a
    # register inquiry title by coincidence; it is still not a committee
    # response. So families are applied to the whole corpus first, and the
    # match score is only used to surface anything else that answers no
    # report we know of.
    groups, claimed = [], set()
    for label, rx in FAMILIES:
        members = [r for r in linked if r["id"] not in claimed and rx.search(r["title"])]
        claimed |= {r["id"] for r in members}
        if members:
            groups.append((label, members))
    leftover = [r for r in linked
                if r["id"] not in claimed and r["verdict"] == "unmatched"]
    if leftover:
        groups.append(("Answers no report in either source — check individually", leftover))
    unmatched = [r for r in linked if r["verdict"] == "unmatched"]

    QA.mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()
    counts = Counter(r["verdict"] for r in linked)
    cls_un = Counter(r["classification"] for r in unmatched)

    sections = ""
    for gi, (label, members) in enumerate(groups):
        rows = "".join(f"""
      <tr data-id="{m['id']}">
        <td><input type="checkbox" class="ex" checked></td>
        <td class="cls">{m['classification'].replace('_',' ')}</td>
        <td class="t">{html.escape(m['title'])[:150]}</td>
        <td class="num">{m['score']}</td>
        <td class="m">{html.escape(m['match_title'])[:90] or '—'}</td>
        <td><a href="{html.escape(m['url'])}" target="_blank" rel="noopener">source</a></td>
      </tr>""" for m in members)
        sections += f"""
  <section class="grp" data-grp="{gi}">
    <h2>{html.escape(label)} <span class="n">{len(members)}</span></h2>
    <p class="ctl"><button data-all="1">exclude all</button>
       <button data-all="0">keep all</button></p>
    <table><thead><tr><th>exclude</th><th>class</th><th>title</th>
      <th class="num">best score</th><th>closest committee report</th><th></th></tr></thead>
      <tbody>{rows}</tbody></table>
  </section>"""

    doc = f"""<!doctype html><html lang="en-AU"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Response corpus scope — {today}</title><style>
 :root {{ color-scheme: light dark; --s:#fcfcfb; --i:#111; --m:#666; --r:#ddd; --a:#2a78d6; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --s:#1a1a19; --i:#fff; --m:#999; --r:#333; --a:#3987e5; }} }}
 body {{ margin:0; background:var(--s); color:var(--i); font:14px/1.5 ui-sans-serif,system-ui,sans-serif; }}
 .wrap {{ width:min(76rem,100% - 2rem); margin-inline:auto; padding-block:2rem 6rem; }}
 h1 {{ font-size:1.35rem; margin:0 0 .3rem; }} h2 {{ font-size:1rem; margin:2rem 0 .4rem; }}
 .n {{ color:var(--m); font-weight:400; }}
 .lede {{ color:var(--m); max-width:46rem; }}
 table {{ width:100%; border-collapse:collapse; }}
 th {{ text-align:left; font-size:.68rem; letter-spacing:.08em; text-transform:uppercase;
       color:var(--m); font-weight:500; border-bottom:1px solid var(--r); padding:.4rem .5rem .4rem 0; }}
 td {{ border-bottom:1px solid var(--r); padding:.45rem .5rem .45rem 0; vertical-align:top; }}
 .cls, .m {{ color:var(--m); font-size:.8rem; }} .num {{ text-align:right; font-variant-numeric:tabular-nums; }}
 .t {{ max-width:34rem; }} .ctl button {{ font:inherit; padding:.2rem .6rem; margin-right:.4rem; cursor:pointer; }}
 .bar {{ position:sticky; bottom:0; background:var(--s); border-top:1px solid var(--r);
         padding:.7rem 0; display:flex; gap:1rem; align-items:center; }}
 #status {{ color:var(--m); }}
</style></head><body><div class="wrap">
<h1>Which documents belong in the response corpus? — {today}</h1>
<p class="lede">{len(resps)} tabled “Government response” documents tested against
{len(reports):,} committee reports and the 2000-2026 register. <b>{counts['matched']}</b> matched a report,
<b>{counts['probable']}</b> probable, <b>{counts['unmatched']}</b> matched nothing.
The unmatched are below, grouped. Every row is ticked to exclude by default —
untick anything that really is a committee response. Classes among the unmatched:
{', '.join(f'{v} {k.replace("_"," ")}' for k, v in cls_un.items())}.</p>
{sections}
<div class="bar"><button id="dl">Download decisions CSV</button><span id="status"></span></div>
</div><script>
const KEY="thb-scope-{today}";
const rows=()=>[...document.querySelectorAll("tr[data-id]")].map(tr=>({{
  id:tr.dataset.id, exclude:tr.querySelector(".ex").checked?"exclude":"keep",
  title:tr.querySelector(".t").textContent.trim()}}));
function save(){{ try{{localStorage.setItem(KEY,JSON.stringify(rows()));}}catch(e){{}}
  const n=rows().filter(r=>r.exclude==="exclude").length;
  document.getElementById("status").textContent=n+" of "+rows().length+" marked exclude"; }}
try{{ for(const r of JSON.parse(localStorage.getItem(KEY)||"[]")){{
  const tr=document.querySelector('tr[data-id="'+r.id+'"]');
  if(tr) tr.querySelector(".ex").checked = r.exclude==="exclude"; }} }}catch(e){{}}
document.addEventListener("click",e=>{{
  const b=e.target.closest("button[data-all]"); if(!b) return;
  b.closest(".grp").querySelectorAll(".ex").forEach(c=>c.checked=b.dataset.all==="1"); save(); }});
document.addEventListener("change",save); save();
document.getElementById("dl").onclick=()=>{{
  const csv=[["id","decision","title"],...rows().map(r=>[r.id,r.exclude,r.title])]
    .map(r=>r.map(x=>'"'+String(x).replace(/"/g,"'")+'"').join(",")).join("\\n");
  const a=document.createElement("a");
  a.href=URL.createObjectURL(new Blob([csv],{{type:"text/csv"}}));
  a.download="scope_decisions_{today}.csv"; a.click(); }};
</script></body></html>"""

    out = QA / f"scope_{today}.html"
    out.write_text(doc, encoding="utf-8")
    print(f"{len(resps)} responses vs {len(reports):,} committee reports and the 2000-2026 register")
    print(f"verdicts: {dict(counts)}")
    print(f"unmatched by class: {dict(cls_un)}")
    for label, members in groups:
        print(f"  {len(members):>3}  {label}")
    print(f"\nwrote {DATA / 'response_links.csv'}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
