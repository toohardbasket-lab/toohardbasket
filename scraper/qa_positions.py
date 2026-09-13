"""
qa_positions.py — build a human review sheet for the coverage measure.

coverage.py decides, for one recommendation, whether the government stated a
position on it. It does that in two steps, and each can fail on its own:

    1. attribution — which words in the response belong to this recommendation
    2. reading     — whether those words state a verdict, and which one

Methods says the measure is one-way: it needs an explicit verdict against a
numbered recommendation and stays silent otherwise, so it is hard to inflate.
"Hard" is not "impossible", and until this sheet is filled in there is no
measured error rate in either direction. The one known false positive, found
by hand on 8 September 2026, was an attribution failure, not a reading one:
the verdict word was real, and belonged to a different recommendation.

So a card asks one question with four answers, and a wrong answer says which
of the two steps went wrong. The counts that come out are the two directions
the site has promised to publish:

    position rows called wrong   -> the measure CAN be inflated, this often
    noted / unreadable rows wrong -> the measure misses verdicts, this often

Each card shows the recommendation, the words attributed to it with the
verdict match marked, and the surrounding text of the response document, so
attribution can be judged without opening the PDF — though the PDF is linked,
and it settles anything the cached text leaves in doubt.

Usage:
    python qa_positions.py
    python qa_positions.py --position 80 --noted 30 --seed 7
Writes qa/positions_<date>.html and qa/positions_sample_<date>.csv
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

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from coverage import find  # the same matcher the measure uses

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
TEXT_CACHE = HERE / "raw" / "otd_text"
QA = HERE / "qa"

# A match this far into the attributed words is the fragile kind: the verdict
# is not a label at the head of the row's own answer but a sentence somewhere
# below it, which is how the 8 September false positive happened.
FAR = 200

QUESTION = {
    "position": "Do these words state this verdict, on this recommendation?",
    "noted": "Is there a verdict here that the measure did not see?",
    "unreadable": "Does the response really say nothing readable about this?",
    "not individual": "Does the response answer this recommendation one by one?",
    "form letter": "Is this a closure rather than an answer?",
}


def load_text(doc_id: str) -> str:
    hits = glob.glob(str(TEXT_CACHE / f"{doc_id}_*.txt"))
    return pathlib.Path(hits[0]).read_text(encoding="utf-8", errors="replace") if hits else ""


def flat(s: str) -> str:
    return " ".join((s or "").split())


def marked(words: str, label: str) -> str:
    """The attributed words, with the verdict the measure found marked."""
    w = words.strip()
    m = find(w, label)
    if not m:
        return html.escape(flat(w))
    return (html.escape(flat(w[: m.start()])) + " <mark>"
            + html.escape(flat(m.group(0))) + "</mark> "
            + html.escape(flat(w[m.end():])))


def where(words: str, doc: str, pad_before: int = 400, pad_after: int = 250) -> tuple[str, int]:
    """The attributed words in their place in the response, so the reader can
    see what came before them and judge whether they belong to this row.

    The opening of an answer is not distinctive — "The Australian Government
    partially supports this recommendation" can occur a dozen times in one
    document — so the needle starts long and shortens only if it has to. The
    second return value is how many places the needle matched: more than one
    means the passage below may not be the passage the index read, and the
    PDF is the only way to be sure.
    """
    if not doc or not words.strip():
        return "", 0
    flat_doc, flat_words = flat(doc), flat(words)
    for n in (400, 240, 160, 100, 60):
        needle = flat_words[:n]
        if len(needle) < min(n, len(flat_words)):
            continue
        hits = flat_doc.count(needle)
        if hits:
            i = flat_doc.find(needle)
            lo, hi = max(0, i - pad_before), min(len(flat_doc), i + len(needle) + pad_after)
            return ("…" + html.escape(flat_doc[lo:i]) + "<b>"
                    + html.escape(flat_doc[i:i + len(needle)]) + "</b>"
                    + html.escape(flat_doc[i + len(needle):hi]) + "…"), hits
    return "", 0


def label_mentions(doc: str, label: str) -> int:
    """How many times the response names this recommendation number."""
    if not doc or not str(label).strip().isdigit():
        return 0
    return len(re.findall(rf"recommendation\s+{re.escape(str(label).strip())}\b", doc, re.I))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--position", type=int, default=60)
    ap.add_argument("--noted", type=int, default=25)
    ap.add_argument("--not-individual", type=int, default=10)
    ap.add_argument("--unreadable", type=int, default=5)
    ap.add_argument("--form-letter", type=int, default=0,
                    help="the pro-forma stratum already has its own sheet, from 2026-08-29")
    ap.add_argument("--far", type=int, default=10,
                    help="extra position rows whose verdict sits far from the head")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args(argv[1:])

    states = {}
    with open(DATA / "recommendation_positions.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            states[(r["source"], r["source_id"], r["label"], r["recommended_by"])] = r

    rows = []
    with open(DATA / "recommendations.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            s = states.get((r["source"], r["source_id"], r["label"], r.get("recommended_by") or ""))
            if s:
                r["_state"], r["_verdict"] = s["state"], s["verdict"]
                rows.append(r)

    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["_state"], []).append(r)

    def rid(r: dict) -> str:
        return f"{r['source']}-{r['source_id']}-{r['label']}-{r.get('recommended_by') or ''}"

    # The fragile position rows, drawn as their own stratum so the error rate
    # of the random one stays a random-sample estimate.
    far_pool = []
    for r in by.get("position", []):
        m = find((r["government_words"] or "").strip(), r["label"])
        if m and m.start() >= FAR:
            far_pool.append(r)

    rng = random.Random(args.seed)
    far_ids = {rid(r) for r in far_pool}
    plan = [("position", args.position, [r for r in by.get("position", []) if rid(r) not in far_ids]),
            ("noted", args.noted, by.get("noted", [])),
            ("not individual", args.not_individual, by.get("not individual", [])),
            ("unreadable", args.unreadable, by.get("unreadable", [])),
            ("form letter", args.form_letter, by.get("form letter", []))]

    sample = []
    for name, n, pool in plan:
        for r in rng.sample(pool, min(n, len(pool))):
            sample.append((r, name))
    for r in rng.sample(far_pool, min(args.far, len(far_pool))):
        sample.append((r, "position, verdict far from the head"))

    QA.mkdir(exist_ok=True)
    today = datetime.date.today().isoformat()

    with open(QA / f"positions_sample_{today}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "source", "source_id", "label", "state", "verdict",
                    "stratum", "checked", "note"])
        for r, stratum in sample:
            w.writerow([rid(r), r["source"], r["source_id"], r["label"],
                        r["_state"], r["_verdict"], stratum, "", ""])

    cards = []
    no_text = 0
    for i, (r, stratum) in enumerate(sample, 1):
        doc = load_text(r["source_id"] if r["source"] == "response" else (r["response_id"] or ""))
        if not doc:
            no_text += 1
        words = (r["government_words"] or "").strip()
        seen = label_mentions(doc, r["label"])

        blocks = f"<h4>Recommendation {html.escape(str(r['label']))}</h4>" \
                 f"<p class=snip>{html.escape(flat(r['recommendation']))}</p>"
        if words:
            blocks += "<h4>The words the index attributes to it</h4>" \
                      f"<p class=snip>{marked(words, r['label'])}</p>"
            ctx, hits = where(words, doc)
            if ctx:
                warn = ("" if hits == 1 else
                        f" <span class=warn>— this passage occurs {hits}× in the document; "
                        "check the PDF</span>")
                blocks += f"<h4>Where those words sit in the response{warn}</h4>" \
                          f'<p class="snip ctx">{ctx}</p>'
            else:
                blocks += "<p class=none>These words could not be found in the cached " \
                          "text of the response. Open the source.</p>"
        elif doc:
            blocks += "<h4>No words were attributed to it. The response opens:</h4>" \
                      f"<p class=snip>{html.escape(flat(doc)[:700])}</p>"
        else:
            blocks += "<p class=none>No cached text for this response. Open the source.</p>"

        link = r["response_url"] or r["url"]
        cards.append(f"""
<article class="card" data-id="{html.escape(rid(r))}" data-stratum="{html.escape(stratum)}"
         data-state="{html.escape(r['_state'])}">
  <header>
    <span class="n">{i}/{len(sample)}</span>
    <span class="cls state">{html.escape(r['_state'])}</span>
    {f'<span class="cls v">{html.escape(r["_verdict"])}</span>' if r["_verdict"] else ''}
    <span class="meta">{html.escape((r['department'] or r['committee'] or '—'))[:70]} ·
      {html.escape((r['response_tabled'] or r['tabled'] or '')[:10])} ·
      names “recommendation {html.escape(str(r['label']))}” <b>{seen}</b>×</span>
  </header>
  <p class="title">{html.escape(r['document_title'] or r['report_title'])[:220]}</p>
  <p class="why">{html.escape(QUESTION.get(r['_state'], ''))}</p>
  {blocks}
  <p class="links"><a href="{html.escape(link)}" target="_blank" rel="noopener">response on aph.gov.au →</a></p>
  <div class="verdict">
    <label><input type="radio" name="v{i}" value="correct"> correct</label>
    <label><input type="radio" name="v{i}" value="wrong words"> wrong words</label>
    <label><input type="radio" name="v{i}" value="wrong reading"> wrong reading</label>
    <label><input type="radio" name="v{i}" value="unsure"> unsure</label>
    <input type="text" class="note" placeholder="note (optional)">
  </div>
</article>""")

    counts = {k: len(v) for k, v in sorted(by.items())}
    strata = {}
    for _, s in sample:
        strata[s] = strata.get(s, 0) + 1
    doc_html = f"""<!doctype html><html lang="en-AU"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coverage measure review — {today}</title>
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
 .cls.v {{ border-color:var(--a); color:var(--a); }}
 .meta {{ color:var(--m); font-size:.78rem; }}
 .title {{ font-weight:600; margin:.2rem 0 .5rem; }}
 .why {{ color:var(--m); font-size:.82rem; margin:.2rem 0 .8rem; }}
 h4 {{ font-size:.7rem; letter-spacing:.08em; text-transform:uppercase; color:var(--m); margin:.9rem 0 .3rem; }}
 .snip {{ font-size:.85rem; margin:.25rem 0; }}
 .ctx {{ color:var(--m); }}
 .ctx b {{ color:var(--i); font-weight:400; }}
 mark {{ background:color-mix(in srgb, var(--a) 22%, transparent); color:inherit; }}
 .none {{ font-size:.85rem; color:var(--m); font-style:italic; }}
 .warn {{ text-transform:none; letter-spacing:0; color:#b3541e; }}
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
<h1>Coverage measure review — {today}</h1>
<p class="lede">Population: {" · ".join(f"{v:,} {k}" for k, v in counts.items())}.
 Sample below: {len(sample)} — {" · ".join(f"{v} {k}" for k, v in strata.items())}, seed {args.seed}.<br>
 Two things can go wrong and they are counted apart.
 <b>Wrong words</b>: the text shown is not this recommendation's answer.
 <b>Wrong reading</b>: the words are right and the index read them wrongly —
 it called a verdict that is not there, or missed one that is.
 The position cards are the ones that decide whether the number can be
 inflated; the noted and unreadable cards say how much it misses.</p>
{''.join(cards)}
<div class="bar">
  <button id="dl">Download verdicts CSV</button>
  <span id="status"></span>
</div>
</div>
<script>
const KEY = "thb-positions-{today}";
function collect() {{
  return [...document.querySelectorAll(".card")].map(c => ({{
    id: c.dataset.id, stratum: c.dataset.stratum, state: c.dataset.state,
    v: (c.querySelector("input[type=radio]:checked") || {{}}).value || "",
    note: c.querySelector(".note").value.replace(/"/g, "'")
  }}));
}}
function save() {{
  try {{ localStorage.setItem(KEY, JSON.stringify(collect())); }} catch (e) {{}}
  const all = collect();
  document.getElementById("status").textContent =
    all.filter(r => r.v).length + " of " + all.length + " reviewed";
}}
try {{
  for (const r of JSON.parse(localStorage.getItem(KEY) || "[]")) {{
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
  const rows = [["row","state","stratum","checked","note"],
    ...collect().map(r => [r.id, r.state, r.stratum, r.v, r.note])];
  const csv = rows.map(r => r.map(x => '"' + String(x) + '"').join(",")).join("\\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {{type:"text/csv"}}));
  a.download = "positions_verdicts_{today}.csv";
  a.click();
}};
</script></body></html>"""

    out = QA / f"positions_{today}.html"
    out.write_text(doc_html, encoding="utf-8")
    print(f"population: {counts}")
    print(f"fragile position rows (verdict {FAR}+ chars in): {len(far_pool)} of {len(by.get('position', []))}")
    print(f"sample: {len(sample)} — {strata}, seed {args.seed}")
    if no_text:
        print(f"warning: {no_text} sampled rows have no cached response text")
    print(f"wrote {out}")
    print(f"wrote {QA / f'positions_sample_{today}.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
