"""make_og_card.py — draw the link preview card.

A link to this site pasted into an editor's Slack, an email, or a message to a
colleague shows whatever the platform can find. With nothing to find it shows a
bare URL, which reads as a link the sender is not sure about. That matters here
more than on most sites, because the way this register travels is one journalist
sending it to another.

What the card shows is the register itself: the number of reports awaiting a
response, the date the data is current to, and the domain. Not a logo and not an
illustration — the whole argument of this site is that the number is the story,
and a card that shows the number is the least decorative thing it could be.

It is drawn here rather than in a browser because the weekly job already has
Python and the data, and adding a headless build of the site to get one PNG
would be a second way for the job to fail. The fonts are the ones the site
serves, so the card and the page it links to are set in the same type.

Writes site/public/og.png (1200x630). Run after the registers are built.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
from datetime import date

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
FONTS = HERE.parent / "site" / "public" / "fonts"
OUT = HERE.parent / "site" / "public" / "og.png"

W, H = 1200, 630
MARGIN = 84

# The site's own light palette. A card is shown on whatever background the
# platform uses, so it commits to one look rather than trying to be both.
SURFACE = (252, 252, 251)
INK = (11, 11, 11)
SECONDARY = (82, 81, 78)
MUTED = (111, 109, 102)
RULE = (222, 220, 213)
BLUE = (33, 104, 194)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS / name
    if not path.exists():
        sys.exit(f"{path} is missing — the card is set in the fonts the site serves.")
    return ImageFont.truetype(str(path), size)


def meta(name: str) -> dict:
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def rows(name: str) -> list[dict]:
    p = DATA / name
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def human(iso: str) -> str:
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    return f"{d.day} {d.strftime('%B')} {d.year}"


def wrap(d, text: str, f, width: int) -> list[str]:
    """Greedy wrap to a pixel width. Text that runs off the right edge of a
    link preview is the one flaw everyone sees and nobody can report."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if d.textlength(trial, font=f) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def duration(days: int) -> str:
    """Years and months, the way the registers say it. '12 years' for 4,299
    days is a rounding the site would have to correct."""
    years, months = days // 365, round((days % 365) / 30.44)
    if months == 12:
        years, months = years + 1, 0
    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    return " and ".join(parts) or f"{days} days"


def main() -> int:
    senate, house = meta("ledger_meta.json"), meta("house_ledger_meta.json")
    # House first, as on the site: the House register is the one the site
    # leads with, and a card that reverses the order reads as a different site.
    counts = [("House", len(rows("house_ledger.csv"))),
              ("Senate", len(rows("ledger_v2.csv")))]
    on_both = senate.get("on_both_registers") or house.get("on_both_registers") or 0
    if not any(n for _, n in counts):
        sys.exit("Both registers are empty — refusing to draw a card that says nothing.")

    longest = 0
    for f in ("ledger_v2.csv", "house_ledger.csv"):
        for r in rows(f):
            try:
                longest = max(longest, int(r.get("days_outstanding") or 0))
            except ValueError:
                pass

    checked = sorted(x for x in (senate.get("responses_checked_to"),
                                 house.get("responses_checked_to")) if x)
    checked_to = checked[0] if checked else ""

    img = Image.new("RGB", (W, H), SURFACE)
    d = ImageDraw.Draw(img)
    inner = W - 2 * MARGIN

    serif = lambda s: font("source-serif-4-latin-600-normal.woff2", s)
    serif_r = lambda s: font("source-serif-4-latin-400-normal.woff2", s)
    sans = lambda s: font("source-sans-3-latin-600-normal.woff2", s)
    sans_r = lambda s: font("source-sans-3-latin-400-normal.woff2", s)

    d.rectangle([0, 0, W, 8], fill=BLUE)

    y = MARGIN
    d.text((MARGIN, y), "THE TOO HARD BASKET", font=sans(22), fill=MUTED)
    y += 58

    # Two figures, side by side, never added. A joint committee report is
    # listed by both presiding officers, so a total
    # would double-count them — and the site says on every page that the two
    # counts are never added. A card that adds them would be the first thing a
    # departmental officer noticed.
    f_big, f_lab = sans(132), sans(26)
    x = MARGIN
    for i, (label, n) in enumerate(counts):
        figure = f"{n:,}"
        d.text((x, y), figure, font=f_big, fill=INK)
        fw = d.textlength(figure, font=f_big)
        d.text((x, y + 148), label.upper(), font=f_lab, fill=MUTED)
        x += fw + 46
        if i == 0:
            # A hairline, not a mid-dot: at this size a dot reads as a decimal
            # point between the two figures, which is the one thing they must
            # never look like.
            d.line([(x, y + 22), (x, y + 168)], fill=RULE, width=2)
            x += 46
    y += 200

    for line in wrap(d, "committee reports awaiting a government response",
                     serif(40), inner):
        d.text((MARGIN, y), line, font=serif(40), fill=INK)
        y += 52
    y += 6

    if longest:
        both = (f"{on_both} reports are on both" if on_both
                else "a joint committee report is listed on both")
        note = (f"The two registers are never added: {both}. "
                f"The longest wait is {longest:,} days — {duration(longest)}.")
        for line in wrap(d, note, serif_r(26), inner):
            d.text((MARGIN, y), line, font=serif_r(26), fill=SECONDARY)
            y += 36

    d.line([(MARGIN, H - MARGIN - 40), (W - MARGIN, H - MARGIN - 40)], fill=RULE, width=1)
    d.text((MARGIN, H - MARGIN - 22), "toohardbasket.org.au", font=sans(26), fill=INK)
    if checked_to:
        tail = f"Responses checked to {human(checked_to)}"
        tw = d.textlength(tail, font=sans_r(24))
        d.text((W - MARGIN - tw, H - MARGIN - 20), tail, font=sans_r(24), fill=MUTED)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} — " + ", ".join(f"{n} {l}" for l, n in counts)
          + f", responses checked to {checked_to or 'unknown'}, "
            f"{OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
