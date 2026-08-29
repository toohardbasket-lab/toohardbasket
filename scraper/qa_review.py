"""
qa_review.py — build a human review sheet for the pro-forma classifier.

The classifier makes a two-regex decision:

    template match + no acceptance  -> proforma_closure
    template match + acceptance     -> partial_proforma
    no template match               -> substantive

So `substantive` means only "does not contain the passage-of-time template".
A response that notes every recommendation and accepts none, without using
that phrasing, is currently called substantive. That is the review's most
important target: the pro-forma count may be an UNDERCOUNT, and the 59.7%
substantive share correspondingly overstated. NOTES_RE ("notes this
recommendation") is already computed and then discarded by classify() — this
sheet surfaces it so the sample can test whether it should carry weight.

Produces an HTML sheet showing, for each sampled response, the text the
classifier actually matched on with surrounding context, so a call can be
checked in seconds rather than by opening the PDF.

Usage:
    python qa_review.py                     # 5 partials + 20 pure + 20 substantive
    python qa_review.py --pure 30 --substantive 40 --seed 7
Writes qa/review_<date>.html and qa/sample_<date>.csv
"""
from __future__ import annotations

import argparse
import csv
import datetime
import glob
import html
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
TEXT_CACHE = HERE / "raw" / "otd_text"
QA = HERE / "qa"

TEMPLATE_RE = re.compile(
    r"(passage\s+of\s+time|time\s+(that\s+has\s+)?elapsed)"
    r".{0,220}?"
    r"(no\s+longer\s+(be\s+)?(appropriate|required|warranted)|"
    r"not\s+(be\s+)?(appropriate|proposed))",
    re.I | re.S)
NOTES_RE = re.compile(r"notes?\s+th(is|e|ese)\s+recommendation", re.I)
ACCEPT_RE = re.compile(
    r"(?<![\w-])government\s+"
    r"(?:(?:has|have|had|is|will|also|therefore|broadly|generally|further|"
    r"fully|partially|strongly|in[\s-]principle)\s+){0,2}"
    r"(?:accepts|accepted|supports|supported|agrees|agreed)\b"
    r"|^\s*(?:government\s+)?(?:response\s*:?\s*)?"
    r"(?:agreed|accepted|supported)"
    r"(?:\s+in\s+(?:principle|part))?\s*\.?\s*$",
    re.I | re.M)


def load_text(doc_id: str) -> str:
    hits = glob.glob(str(TEXT_CACHE / f"{doc_id}_*.txt"))
    if not hits:
        return ""
    return pathlib.Path(hits[0]).read_text(encoding="utf-8", errors="replace")


def snippets(rx: re.Pattern, text: str, pad: int = 130, limit: int = 3) -> list[str]:
    out = []
    for m in list(rx.finditer(text))[:limit]:
        lo, hi = max(0, m.start() - pad), min(len(text), m.end() + pad)
        before = html.escape(text[lo:m.start()].replace("\n", " "))
        hit = html.escape(text[m.start():m.end()].replace("\n", " "))
        after = html.escape(text[m.end():hi].replace("\n", " "))
        out.append(f"…{before}<mark>{hit}</mark>{after}…")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pure", type=int, default=20)
    ap.add_argument("--substantive", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv[1:])

    rows = list(csv.DictReader(open(DATA / "response_documents.csv",
                                    newline="", encoding="utf-8-sig")))
    by = {"partial_proforma": [], "proforma_closure": [], "substantive": []}
    for r in rows:
        by.setdefault(r["classification"], []).append(r)

    # Targeted stratum: substantive responses that note several recommendations
    # and accept none. If the template test is missing non-answers, they are
    # here. Reviewed separately from the random sample so the error rate for
    # each question stays interpretable.
    targeted = []
    for r in by["substantive"]:
        t = load_text(r["id"])
        if not t:
            continue
        if len(NOTES_RE.findall(t)) >= 3 and len(ACCEPT_RE.findall(t)) == 0:
            targeted.append(r)
    targeted_ids = {r["id"] for r in targeted}

    rng = random.Random(args.seed)
    pure_pool = by["proforma_closure"]
    subs_pool = [r for r in by["substantive"] if r["id"] not in targeted_ids]
    sample = ([(r, "partial") for r in by.get("partial_proforma", [])]
              + [(r, "pure") for r in rng.sample(pure_pool, min(args.pure, len(pure_pool)))]
              + [(r, "substantive") for r in rng.sample(subs_pool, min(args.substantive, len(subs_pool)))]
              + [(r, "targeted") for r in targeted])

    QA.mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()

    with open(QA / f"sample_{today}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "classification", "stratum", "verdict", "note"])
        for r, stratum in sample:
            w.writerow([r["id"], r["classification"], stratum, "", ""])

    cards = []
    for i, (r, stratum) in enumerate(sample, 1):
        text = load_text(r["id"])
        tmpl = snippets(TEMPLATE_RE, text)
        acc = snippets(ACCEPT_RE, text)
        notes_n = len(NOTES_RE.findall(text))
        opening = html.escape(" ".join(text.split())[:700])
        cls = r["classification"]

        why = {"proforma_closure": "template matched, no government acceptance found",
               "partial_proforma": "template matched AND a government acceptance found",
               "substantive": "no template match — note this is the only test"}[cls]

        blocks = ""
        if tmpl:
            blocks += "<h4>Template match</h4>" + "".join(f"<p class=snip>{s}</p>" for s in tmpl)
        if acc:
            blocks += "<h4>Acceptance match</h4>" + "".join(f"<p class=snip>{s}</p>" for s in acc)
        if not tmpl and not acc:
            blocks += "<p class=none>No pattern matched. Judge from the opening below.</p>"

        cards.append(f"""
<article class="card" data-id="{r['id']}" data-stratum="{stratum}">
  <header>
    <span class="n">{i}/{len(sample)}</span>
    <span class="cls {cls}">{cls.replace('_',' ')}</span>
    <span class="cls stratum">{stratum}</span>
    <span class="meta">{html.escape(r['department'] or '—')[:60]} ·
      {html.escape((r['tabled_senate'] or r['tabled_house'] or '')[:10])} ·
      {int(r['text_length'] or 0):,} chars ·
      <b>{notes_n}</b> × “notes this recommendation”</span>
  </header>
  <p class="title">{html.escape(r['title'])[:220]}</p>
  <p class="why">Classifier: {why}</p>
  {blocks}
  <details><summary>Opening 700 characters</summary><p class="open">{opening}</p></details>
  <p class="links"><a href="{html.escape(r['url'])}" target="_blank" rel="noopener">source on aph.gov.au →</a></p>
  <div class="verdict">
    <label><input type="radio" name="v{r['id']}" value="correct"> correct</label>
    <label><input type="radio" name="v{r['id']}" value="wrong"> wrong</label>
    <label><input type="radio" name="v{r['id']}" value="unsure"> unsure</label>
    <input type="text" class="note" placeholder="note (optional)">
  </div>
</article>""")

    counts = {k: len(v) for k, v in by.items()}
    doc = f"""<!doctype html><html lang="en-AU"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pro-forma classifier review — {today}</title>
<style>
 :root {{ color-scheme: light dark; --s:#fcfcfb; --i:#111; --m:#666; --r:#ddd; --a:#2a78d6; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --s:#1a1a19; --i:#fff; --m:#999; --r:#333; --a:#3987e5; }} }}
 body {{ margin:0; background:var(--s); color:var(--i); font:15px/1.55 ui-sans-serif,system-ui,sans-serif; }}
 .wrap {{ width:min(58rem,100% - 2rem); margin-inline:auto; padding-block:2rem 6rem; }}
 h1 {{ font-size:1.4rem; margin:0 0 .3rem; }}
 .lede {{ color:var(--m); margin:0 0 2rem; }}
 .card {{ border:1px solid var(--r); padding:1rem 1.1rem; margin-bottom:1.25rem; }}
 .card header {{ display:flex; gap:.75rem; align-items:baseline; flex-wrap:wrap; margin-bottom:.4rem; }}
 .n {{ font-variant-numeric:tabular-nums; color:var(--m); font-size:.8rem; }}
 .cls {{ font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; padding:.1rem .4rem; border:1px solid var(--r); }}
 .cls.proforma_closure {{ border-color:var(--a); color:var(--a); }}
 .meta {{ color:var(--m); font-size:.78rem; }}
 .title {{ font-weight:600; margin:.2rem 0 .5rem; }}
 .why {{ color:var(--m); font-size:.82rem; margin:.2rem 0 .8rem; }}
 h4 {{ font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; color:var(--m); margin:.9rem 0 .3rem; }}
 .snip {{ font-size:.85rem; margin:.25rem 0; }}
 mark {{ background:color-mix(in srgb, var(--a) 22%, transparent); color:inherit; }}
 .none {{ font-size:.85rem; color:var(--m); font-style:italic; }}
 .open {{ font-size:.82rem; color:var(--m); }}
 details summary {{ font-size:.8rem; color:var(--m); cursor:pointer; }}
 .links {{ font-size:.8rem; }}
 .verdict {{ display:flex; gap:1rem; align-items:center; flex-wrap:wrap;
             border-top:1px solid var(--r); margin-top:.9rem; padding-top:.7rem; font-size:.85rem; }}
 .verdict input[type=text] {{ flex:1; min-width:12rem; padding:.25rem .4rem;
             border:1px solid var(--r); background:transparent; color:inherit; }}
 .bar {{ position:sticky; bottom:0; background:var(--s); border-top:1px solid var(--r);
         padding:.7rem 0; display:flex; gap:1rem; align-items:center; }}
 button {{ font:inherit; padding:.35rem .8rem; cursor:pointer; }}
 #status {{ color:var(--m); font-size:.85rem; }}
</style></head><body><div class="wrap">
<h1>Pro-forma classifier review — {today}</h1>
<p class="lede">Population: {counts.get('substantive',0)} substantive ·
 {counts.get('proforma_closure',0)} pro-forma closure ·
 {counts.get('partial_proforma',0)} partial. Sample below: {len(sample)}.
 Mark each call correct or wrong, then download the verdicts.<br>
 The substantive cards matter most — the classifier tests only for the
 passage-of-time template, so a response that answers nothing in different
 words is currently counted as substantive.</p>
{''.join(cards)}
<div class="bar">
  <button id="dl">Download verdicts CSV</button>
  <span id="status"></span>
</div>
</div>
<script>
const KEY = "thb-qa-{today}";
function collect() {{
  return [...document.querySelectorAll(".card")].map(c => ({{
    id: c.dataset.id, stratum: c.dataset.stratum,
    cls: c.querySelector(".cls").textContent.trim().replace(/ /g,"_"),
    v: (c.querySelector("input[type=radio]:checked") || {{}}).value || "",
    note: c.querySelector(".note").value.replace(/"/g, "'")
  }}));
}}
function save() {{
  try {{ localStorage.setItem(KEY, JSON.stringify(collect())); }} catch (e) {{}}
  const done = collect().filter(r => r.v).length;
  document.getElementById("status").textContent = done + " of " + collect().length + " reviewed";
}}
try {{
  const prev = JSON.parse(localStorage.getItem(KEY) || "[]");
  for (const r of prev) {{
    const c = document.querySelector('.card[data-id="' + r.id + '"]');
    if (!c) continue;
    if (r.v) {{ const el = c.querySelector('input[value="' + r.v + '"]'); if (el) el.checked = true; }}
    if (r.note) c.querySelector(".note").value = r.note;
  }}
}} catch (e) {{}}
document.addEventListener("change", save);
document.addEventListener("input", save);
save();
document.getElementById("dl").onclick = () => {{
  const rows = [["id","classification","stratum","verdict","note"],
    ...collect().map(r => [r.id, r.cls, r.stratum, r.v, r.note])];
  const csv = rows.map(r => r.map(x => '"' + String(x) + '"').join(",")).join("\\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {{type:"text/csv"}}));
  a.download = "verdicts_{today}.csv";
  a.click();
}};
</script></body></html>"""

    out = QA / f"review_{today}.html"
    out.write_text(doc, encoding="utf-8")
    missing = sum(1 for r, _ in sample if not load_text(r["id"]))
    print(f"population: {counts}")
    print(f"sample: {len(sample)} "
          f"({len(by.get('partial_proforma', []))} partial + {min(args.pure, len(by['proforma_closure']))} pure "
          f"+ {min(args.substantive, len(subs_pool))} random substantive "
          f"+ {len(targeted)} targeted), seed {args.seed}")
    if missing:
        print(f"warning: {missing} sampled responses have no cached text")
    print(f"wrote {out}")
    print(f"wrote {QA / f'sample_{today}.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
