"""extract_rc_positions.py — what the government said about each recommendation.

extract_rc_recommendations.py has the recommendations, in the commission's own
words. This has the other half: for each of them, the government's words and
whether they state a position. Nothing is inferred. Where the response does not
address a recommendation, the row says so; it is not counted as a refusal and
it is not counted as an acceptance.

The two responses read so far answer in two different grammars, and the source
test of 6 September 2026 established both.

A prose response answers the way a committee response does, and coverage.py
already reads it:

    Recommendation 11.1: Clear documentation of exclusion criteria
    Services Australia should ensure that ...
    The Government accepts this recommendation.
    The Government supports the need for clear documentation ...

A block response answers with a label on a line of its own, under a line
naming which governments are answering:

    Response to Recommendation 6.41
    Responsibility: Australian, state and territory governments
    ACT and WA: Accept in principle
    Commonwealth, NSW, QLD, NT, SA, TAS, VIC: Subject to
    further consideration

Which grammar a document uses is read from the document, not configured: a
response carrying "Responsibility:" lines with labels under them is read as
blocks, and everything else as prose.

Four things about the block grammar that a rule has to handle, all of them
found in the Disability Royal Commission's response:

  * A block can answer a range at once — "Response to Recommendations
    4.1–4.21" — so the heading's numbers are expanded, ranges and lists alike.
  * A recommendation can be answered a lettered part at a time, with different
    verdicts for different parts. The row is still one recommendation. Where
    the parts disagree it sorts as "in part or in principle", which is what
    the vocabulary already means, and every exact label is kept beside it.
  * One block can carry the Commonwealth's verdict and the states' separately.
    Which is the Commonwealth's is decided by the left-hand side of the label:
    "Response", "Joint response", "Australian Government Response" and
    "Commonwealth" speak for it, and a list of states that does not name the
    Commonwealth does not. The states' verdicts are recorded beside it, because
    the document says them, but the register's figures are the Commonwealth's.
  * A label wraps across a line where the page is narrow — "Subject to" then
    "further consideration" — and is rejoined.

The verdict vocabulary is the register's existing one and is not extended for
this: coverage.py sorts the government's own word into accepted, in part or in
principle, and not accepted. A label it does not recognise states no position —
"Note" and "Subject to further consideration" both do — and the row is noted,
with the government's exact words kept and shown.

    python3 extract_rc_positions.py
    python3 extract_rc_positions.py --commission robodebt

Reads  data/rc_recommendations.csv, data/rc_documents.csv, raw/rc_text/
Writes data/rc_positions.csv  one row per recommendation per response
       data/rc_position_counts.csv  the totals, per response
"""
from __future__ import annotations

import collections
import csv
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
TEXT = HERE / "raw" / "rc_text"
RECOMMENDATIONS = DATA / "rc_recommendations.csv"
DOCUMENTS = DATA / "rc_documents.csv"
OUT = DATA / "rc_positions.csv"
COUNTS = DATA / "rc_position_counts.csv"

sys.path.insert(0, str(HERE))
import coverage as cov                    # noqa: E402
import extract_recommendations as ex      # noqa: E402

# --- the block grammar ------------------------------------------------------
BLOCK_HEAD = re.compile(r"(?m)^[ \t]*Response to Recommendations?[ \t]+(.+?)[ \t]*$", re.I)
RESPONSIBILITY = re.compile(r"(?m)^[ \t]*Responsibility:[ \t]*(.+?)[ \t]*$", re.I)
# "<who>: <verdict>" — a short left side, a short right side, no colon in it.
VERDICT_LINE = re.compile(r"^([A-Za-z][A-Za-z,’' .\-()0-9]{0,70}?):[ \t]*([A-Z][^:]{0,60})$")
# A label the page has wrapped: the rest of it is a short lower-case line.
CONTINUATION = re.compile(r"^[a-z][^:]{0,40}$")
# Whose verdict it is. "Response" and "Joint response" speak for every
# government answering, the Commonwealth among them.
COMMONWEALTH = re.compile(r"^(?:response|joint\s+response|australian\s+government\s+response"
                          r"|commonwealth)\b", re.I)
# A recommendation's number, either way a report writes it: "4.22" by chapter,
# or "61" straight through. Greedy, so a dotted number is never read as its
# chapter alone.
NUMBER = re.compile(r"\d{1,3}(?:\.\d{1,3})?")
# Where a document stops answering one recommendation and starts on the next.
# Both grammars head that with the recommendation's number on a line of its
# own: "Response to Recommendation 4.22" in the disability response, and
# "Recommendation 20.5: Administrative Review Council" in the robodebt one.
HEAD_LINE = re.compile(r"^[ \t]*(?:Response to[ \t]+)?Recommendations?[ \t]+"
                       r"(\d{1,3}(?:\.\d{1,3})?[^\n]*)$", re.M)
# The run of numbers a heading names, and whatever follows them.
LABEL_RUN = re.compile(r"\d{1,3}(?:\.\d{1,3})?"
                       r"(?:\s*(?:[,\u2013\u2014-]|and|to)\s*\d{1,3}(?:\.\d{1,3})?)*\s*(.*)$")
# The page number a running head is printed with, at either end of it. The
# disability response puts it after the head on a right-hand page and before it
# on a left-hand one — "Australian Government Response – Volume 4 51" and "54
# Australian Government Response – Volume 4" are the same line.
PAGE_NUMBER = re.compile(r"^\s*\d{1,4}\s+|\s+\d{1,4}\s*$")
# How many pages a line has to be printed on before it is the page's furniture
# rather than the government's words. Low, because the title is doing the work:
# what this keeps out is the response's own "Australian Government Response to
# 6.27 (a) and (b): Accept in principle", which begins like the running head
# and is printed once.
FURNITURE_TIMES = 3


def tidy_words(text: str) -> str:
    """extract_recommendations.tidy, less the part that takes the full stop off.

    That strip is right for a recommendation, which the register prints as a
    clause. It is wrong for a quotation of what a government said: it left 33
    of the robodebt answers ending on a bare word while every block answer
    ended on a stop, so the same index printed the same kind of thing two
    different ways. The paragraph numbers and the dangling label that tidy
    also takes off are the page's, and go.
    """
    text = " ".join(text.split()).strip(" :;-\u2014\u2013\u2022")
    text = ex.REPEAT_NO.sub("", ex.PARA_NO.sub("", text))
    for _ in range(3):
        trimmed = ex.TRAILING.sub("", text).strip(" :;-\u2014\u2013\u2022")
        if trimmed == text:
            break
        text = trimmed
    return text.strip()


def cut(text: str) -> tuple[str, str]:
    """The government's words, ending where a sentence ends, and whether more follows.

    Two things come off the end here and neither is the government's. A block
    runs to the next recommendation's heading, and where the page prints a
    section title in between — "Disability discrimination reform
    (Recommendations 4.23-4.34)" — the title is inside the block and is not an
    answer to anything. And an answer longer than GOV_CHARS has to stop
    somewhere: stopping at a character count stops in the middle of a word,
    which reads as a transcription error rather than as a quotation that goes
    on. Where it does go on the row says so, because a reader who cannot tell
    a whole answer from the first part of one has been told something the
    document does not say.
    """
    text = " ".join(text.split()).strip()
    more = len(text) > GOV_CHARS
    text = text[:GOV_CHARS]
    stops = [m.end() for m in SENTENCE_END.finditer(text)]
    end = (stops[-1] if stops else 0) - 1
    tail = text[end + 1:].strip()
    if end > 0 and tail:
        if more and len(tail) > TRAILING_SENTENCE:
            text = text[:text.rfind(" ")]
        elif more or len(tail) <= TRAILING_HEADING:
            text = text[:end + 1]
    return text.strip(), "yes" if more else ""


# What can follow a number when the line is not a heading but the tail of a
# sentence the page broke: a lower-case word, or the punctuation that ends a
# clause or closes a bracket. "as part of the process set out in /
# Recommendation 74." and "against wellbeing targets (see / Recommendation 11)
# as part of the check" each ended one of the Defence and Veteran Suicide
# answers before it began. No document in this corpus heads a recommendation
# with a full stop after the number — 361 of that response's headings use a
# colon and one line in it uses a stop, and that line is a cross-reference.
CONTINUES = frozenset("abcdefghijklmnopqrstuvwxyz.)],;")


def is_heading(line: str) -> bool:
    """Does this line head a recommendation, or only begin with the look of one?

    "The Government will consider / Recommendation 7.26 as part of its review
    of the Disability Discrimination Act" is one sentence that the page broke
    in two, and its second line opens exactly like a heading. What separates
    them is what follows the number: a heading stops there or gives a title,
    which starts with a capital or a colon; a sentence carries on in lower
    case. Reading those three lines as headings truncated two answers and put
    a third under the wrong number.
    """
    head = HEAD_LINE.match(line.rstrip())
    if not head:
        return False
    run = LABEL_RUN.match(head.group(1).strip())
    return not (run and run.group(1).lstrip()[:1] in CONTINUES)


def furniture(body: str, title: str) -> set[str]:
    """The lines this document prints on page after page.

    A response is read as one stream of text, so the running head lands in the
    middle of any answer that crosses a page — 120 of the 228 answers, before
    this — and gets published as though the government had written it.

    Repeating is not enough to convict a line: "The Government accepts this
    recommendation." is printed 49 times in the robodebt response and is the
    government's answer every time. What a running head is, is the document
    saying its own name, so this asks the register what the document is called
    and takes the lines that begin the way the title does. The disability
    response heads its pages "Australian Government Response to the Disability
    Royal Commission" and, underneath, "Australian Government Response –
    Volume 7 132", which the register's title does not name but its first
    three words do. The robodebt response heads them "GOVERNMENT RESPONSE |
    ROYAL COMMISSION INTO THE ROBODEBT SCHEME 32", which its title gives whole.

    The report side does the same thing from the commission's name; a response
    is not named after the commission, so the name it is filed under in the
    Tabled Documents register is the one to use.
    """
    words = re.sub(r"\[.*?\]", " ", title or "").split()
    if len(words) < 3:
        return set()
    # The head may carry a word the register's title does not. The final
    # Defence and Veteran Suicide response is filed as "Government Response to
    # the Final report of the Royal Commission Inquiry into Defence and Veteran
    # Suicide" and heads its pages "Australian Government Response to the Royal
    # Commission into Defence and Veteran Suicide", so an anchored match on the
    # title's first three words missed it and three answers were published with
    # the head inside them. Only what a document puts in front of its own name
    # is allowed to differ, and only at the front.
    stem = re.compile(r"(?:the\s+|australian\s+)?" + r"\s+".join(re.escape(w) for w in words[:3]),
                      re.I)
    counted: collections.Counter = collections.Counter()
    for line in body.split("\n"):
        line = re.sub(r"[^\S\n]+", " ", line).strip()
        line = PAGE_NUMBER.sub("", line).strip()
        if line and len(line) <= 120 and not line.endswith(".") and stem.match(line):
            counted[line] += 1
    return {k for k, n in counted.items() if k and n >= FURNITURE_TIMES}


def is_furniture(line: str, heads: set[str]) -> bool:
    return PAGE_NUMBER.sub("", line.strip()).strip() in heads

STATES = ("position", "noted", "not addressed", "unreadable")
GOV_CHARS = 900
# A fragment this short at the end, with no sentence in it, is the page's doing
# rather than the government's: the section title the response prints between
# one block and the next.
TRAILING_HEADING = 120
# Where a sentence ends: a stop, and then the next thing starting afresh. The
# bare stop is not enough — "(Recommendations 4.23-4.34)" has two of them, and
# cutting at one leaves the quotation ending in the middle of a number.
SENTENCE_END = re.compile(r"[.!?][”’\")\]]?(?=\s+[\"“(A-Z0-9]|$)")
# How much of a sentence may be given up to end the quotation at a full stop.
# Beyond this the sentence is cut at a word instead, because dropping half a
# page of the government's answer to tidy an ending is the worse of the two.
TRAILING_SENTENCE = 300

FIELDS = ["commission_id", "report_id", "label", "response_id", "response_tabled", "response_url",
          "state", "verdict", "government_label", "other_governments",
          "government_words", "government_words_more", "note"]
COUNT_FIELDS = ["commission_id", "report_id", "response_id", "grammar", "recommendations", "position",
                "noted", "not addressed", "unreadable", "accepted",
                "in part or in principle", "not accepted"]


def labels_in(heading: str) -> list[str]:
    """The recommendations a block heading names, with ranges expanded.

    "6.24–6.25" and "11.1 to 11.2" are ranges; "7.8 and 7.10" and
    "7.2, 7.3, 7.6 and 7.13" are lists. A range runs within one chapter, and
    one that does not is left as the two numbers it names rather than guessed
    at.
    """
    out: list[str] = []
    for part in re.split(r",|\band\b", heading):
        span = re.search(r"(?:(\d+)\.)?(\d+)\s*(?:–|—|-|\bto\b)\s*(?:(\d+)\.)?(\d+)", part)
        if span and span.group(1) == span.group(3) and int(span.group(2)) <= int(span.group(4)):
            prefix = f"{span.group(1)}." if span.group(1) else ""
            out += [f"{prefix}{n}"
                    for n in range(int(span.group(2)), int(span.group(4)) + 1)]
        else:
            out += NUMBER.findall(part)
    seen: list[str] = []
    for n in out:
        if n not in seen:
            seen.append(n)
    return seen


def heading_labels(line: str) -> list[str]:
    """The recommendations a heading names, or none if it is not a heading."""
    head = HEAD_LINE.match(line.rstrip())
    return labels_in(head.group(1)) if head and is_heading(line) else []


def said_from(lines: list[str], start: int, heads: set[str],
              mine: list[str] = ()) -> tuple[str, str]:
    """The government's words under a heading, to the next heading.

    Twelve lines were taken here once, which is not a rule about the document
    but about the page it happened to be laid out on: it swept up the running
    head, the next block's heading and its particulars, and stopped in the
    middle of whatever sentence line twelve ended on.

    A heading immediately below another, with nothing between them but the
    particulars, is a document answering two things in one place. The
    disability response does it for "Response to Recommendations 7.18, 7.19,
    7.21, 7.22 and 7.23" followed at once by "Response to Recommendation 7.20"
    — six recommendations, one body, printed under the second heading — and
    again where a block is broken into "Recommendation 6.31 (a)" and "(b)".
    Stopping at the second heading would leave five rows with no words at all,
    so an empty body steps over one heading and keeps reading. It steps over
    at most one, because two headings with a body between them are two answers
    and running them together would put one government's words under another
    recommendation's number.
    """
    said: list[str] = []
    stepped, split = False, False
    i = start
    while i < len(lines):
        line = lines[i].strip()
        if is_heading(line):
            if said or stepped:
                # A block broken into parts — "Recommendation 6.31 (a)" and
                # "(b)", each answered separately — stops here with only the
                # first part quoted. The rest is still this recommendation's
                # answer, so the row has to say the answer goes on.
                split = any(x in mine for x in heading_labels(line))
                break
            stepped = True
        elif not is_furniture(line, heads) and not (
                not said and (RESPONSIBILITY.match(lines[i]) or VERDICT_LINE.match(line))):
            said.append(line)
        i += 1
    words, more = cut(" ".join(said))
    return words, more or ("yes" if split else "")


def blocks_in(body: str, title: str = "") -> list[dict]:
    """Every answer block: which recommendations, who is responsible, what they said."""
    lines = body.splitlines()
    heads = furniture(body, title)
    heading: list[str] = []
    out = []
    for i, line in enumerate(lines):
        head = BLOCK_HEAD.match(line)
        if head and is_heading(line):
            heading = labels_in(head.group(1))
        if not RESPONSIBILITY.match(line):
            continue
        verdicts = []
        j = i + 1
        while j < len(lines):
            m = VERDICT_LINE.match(lines[j].strip())
            if not m:
                break
            who, said = m.group(1).strip(), m.group(2).strip()
            # A label the page wrapped: take the rest of it from the next line.
            if j + 1 < len(lines) and CONTINUATION.match(lines[j + 1].strip()):
                said = f"{said} {lines[j + 1].strip()}"
                j += 1
            verdicts.append((who, said))
            j += 1
        out.append({"labels": list(heading),
                    "responsibility": RESPONSIBILITY.match(line).group(1),
                    "verdicts": verdicts,
                    "words": said_from(lines, j, heads, heading)})
    return out


def from_blocks(body: str, title: str = "") -> dict[str, dict]:
    """label -> the Commonwealth's position, with the other governments' beside it."""
    found: dict[str, dict] = {}
    for block in blocks_in(body, title):
        mine = [said for who, said in block["verdicts"] if COMMONWEALTH.match(who)]
        others = [f"{who}: {said}" for who, said in block["verdicts"]
                  if not COMMONWEALTH.match(who)]
        verdicts = [cov.verdict(said) for said in mine]
        stated = [v for v in verdicts if v]
        if not block["words"][0]:
            continue
        if not mine:
            state, verdict = "noted", ""
        elif not stated:
            # Every label is one the vocabulary does not recognise: "Note",
            # "Subject to further consideration". The words are kept; no
            # position is claimed from them.
            state, verdict = "noted", ""
        elif len(set(verdicts)) == 1:
            state, verdict = "position", stated[0]
        else:
            # The parts disagree, or some part states nothing. One
            # recommendation, answered partly — which is what the existing
            # vocabulary already means.
            state, verdict = "position", "in part or in principle"
        notes = []
        if "state" in block["responsibility"].lower():
            notes.append("answered with the states and territories together")
        # A sorted verdict is the register's word, not the government's, and
        # where they could differ the row has to say so. "In part or in
        # principle" is fair when the parts are accepted and accepted in
        # principle; it is not what the government said when one part was
        # accepted and another was noted, because nobody qualified anything —
        # a position was stated on one part and withheld on the other. The
        # register's own CLAUDE.md carries the same lesson under a different
        # name: interim_response does not mean an interim response. So where
        # the parts do not all state a verdict, the row carries the fact
        # rather than leaving the sorted word to speak for the government.
        if len(mine) > 1 and len(stated) != len(mine):
            notes.append("the government states a position on some parts of this "
                         "recommendation and not on others")
        for label in block["labels"]:
            keep = found.get(label)
            if keep and keep["state"] == "position" and state != "position":
                continue
            found[label] = {
                "state": state, "verdict": verdict,
                "government_label": "; ".join(mine),
                "other_governments": "; ".join(others),
                "government_words": block["words"][0],
                "government_words_more": block["words"][1],
                "note": "; ".join(notes),
            }
    return found


# --- the prose grammar ------------------------------------------------------
# The heading, not every mention. extract_recommendations.py looks for the
# label anywhere, which is right for a committee response that names the
# recommendation it is answering in a sentence. Here it cut an answer in half:
# the robodebt response wrote "The Government accepts this recommendation. As
# noted in the response to recommendation 20.4, ..." and the register
# published the eleven words before the mention.
BY_CHAPTER, STRAIGHT_THROUGH = r"\d{1,3}\.\d{1,3}", r"\d{1,3}"


def label_pattern(numbering: str) -> "re.Pattern[str]":
    return re.compile(r"^[ \t]*Recommendation[ \t]+(" + numbering + r")\b", re.M)


LABEL = label_pattern(BY_CHAPTER)


def numbering_in(body: str) -> str:
    """How this response numbers the recommendations, counted rather than assumed.

    The same question the report side asks of the report, asked again here
    rather than carried across, because a response is a different document and
    could number them its own way. Neither of the two that answer in prose is
    close: the robodebt response heads 56 by chapter and 1 straight through,
    the Antisemitism response none by chapter and 14 straight through.
    """
    by_chapter = {m.group(1) for m in label_pattern(BY_CHAPTER).finditer(body)}
    straight = {m.group(1) for m in label_pattern(STRAIGHT_THROUGH).finditer(body)}
    return BY_CHAPTER if len(by_chapter) >= len(straight) else STRAIGHT_THROUGH


# Something was printed under the heading and it is a sentence, not a contents
# entry: at least one sentence ending, and a few words in front of it.
NAMED_ONLY = re.compile(r"\w[^.!?]{20,}[.!?]")

# The answer's opening sentence, where it is about the recommendation.
OPENING = re.compile(r"^.*?[.!?](?=\s|$)")
ABOUT_IT = re.compile(r"\brecommendations?\b", re.I)
# A qualifier the document hyphenates onto the verdict — "agrees-in-principle".
# coverage.py reads the verdict from it but its label stops at the verb, and a
# label that says "agrees" where the document says "agrees-in-principle" is the
# misstatement this index is most careful about everywhere else.
HYPHENATED = re.compile(r"\s*-\s*(?:in\s*-?\s*principle|in\s*-?\s*part|in\s+full)\b", re.I)


# Where the government's answer plainly ends and the document moves on, other
# than at the next recommendation's heading, which is_heading decides.
# extract_recommendations.GOV_END is the same list read anywhere in the line,
# which is what cut recommendation 20.5's answer at its own cross-reference.
PROSE_END = re.compile(r"^[ \t]*(?:Response\s+to\s+the\s+recommendations?"
                       r"|(?:Chapter|Appendix|Attachment)\s+\d)", re.I | re.M)


def prose_end(raw: str) -> int:
    """How far the government's answer runs.

    To the next recommendation's heading, and a heading is capitalised and at
    the start of a line. The robodebt response answers "The Government accepts
    this recommendation. As noted in the response to / recommendation 20.4, on
    29 September 2023, ..." and where the page happens to break before that
    mention, a rule that stopped at any line beginning with the word published
    eleven words of a four-hundred-word answer.
    """
    def line_from(start: int) -> str:
        stop = raw.find("\n", start)
        return raw[start:stop if stop >= 0 else len(raw)]

    stops = [m.start() for m in PROSE_END.finditer(raw, 1)]
    stops += [m.start() for m in HEAD_LINE.finditer(raw)
              if m.start() > 0 and is_heading(line_from(m.start()))]
    return min(stops, default=len(raw))


def label_said(words: str, label: str) -> str:
    """The government's own verdict words, to the end of them.

    coverage.py finds the verb; where the document hyphenates the qualifier
    onto it the label has to carry that too. "The Australian Government agrees"
    is not what the response to recommendation 96 says, and the difference
    between agreeing and agreeing in principle is the whole of what this column
    is for.
    """
    found = cov.find(words, label)
    if not found:
        return ""
    tail = HYPHENATED.match(words, found.end())
    return words[found.start():tail.end() if tail else found.end()].strip()


def from_prose(body: str, title: str = "") -> dict[str, dict]:
    """label -> the government's words after the recommendation, and their verdict.

    The split is extract_recommendations.py's, which knows where a government
    stops quoting and starts answering, and the verdict is coverage.py's.
    Neither is re-implemented here.
    """
    def line_at(start: int) -> str:
        stop = body.find("\n", start)
        return body[start:stop if stop >= 0 else len(body)]

    label = label_pattern(numbering_in(body))
    marks = [(m.group(1), m.start(), m.end()) for m in label.finditer(body)
             if is_heading(line_at(m.start()))]
    heads = furniture(body, title)
    found: dict[str, dict] = {}
    for i, (label, start, end) in enumerate(marks):
        stop = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        segment = body[end:stop]
        hand = ex.HANDOVER.search(segment)
        if not hand:
            # A response can name a recommendation and still answer nothing.
            # The Royal Commission on Antisemitism and Social Cohesion put five
            # of its fourteen recommendations in a confidential report, and
            # both the public report and the response print, under the number
            # and nothing else, "This recommendation is contained in the
            # confidential Interim Report." The recommendation is not public,
            # so no position on it can be.
            #
            # That is a response addressing a recommendation and stating no
            # position, which is what noted means here. It is not "not
            # addressed", which on this index means the response does not
            # mention the recommendation at all — and saying that of a
            # recommendation the response names by number would be false.
            #
            # No words are published for it. Under every other heading in a
            # prose response the recommendation is reprinted first and the
            # government's answer follows, so what sits under these headings
            # could be either, and this index does not put words in a
            # government's mouth on a guess.
            if NAMED_ONLY.search(segment) and not ex.LEADERS.search(segment):
                found.setdefault(label, {
                    "state": "noted", "verdict": "", "government_label": "",
                    "other_governments": "", "government_words": "",
                    "government_words_more": "",
                    "note": "the response names this recommendation and states no position on it",
                })
            continue
        raw = segment[hand.start():]
        raw = raw[:prose_end(raw)]
        raw = "\n".join(l for l in raw.split("\n") if not is_furniture(l, heads))
        words, more = cut(tidy_words(ex.GOV_LABEL.sub("", raw.strip())))
        if not words:
            continue
        # Read the position from the answer's opening sentence where that
        # sentence is about the recommendation, and from the whole answer
        # otherwise. These responses open by saying what they are doing —
        # "The Government agrees to this recommendation." — and what follows is
        # the reasoning, which can carry a verdict word about something else.
        # The final Defence and Veteran Suicide response answers recommendation
        # 42 "The Government notes this recommendation" and then says all
        # related recommendations "will be implemented with regard to the
        # recommendations of the Twenty-Year Review". Read whole, that is an
        # acceptance the government did not state. It is the only row of the
        # 191 answered in prose that the two readings disagree about.
        opening = OPENING.match(words)
        decisive = opening.group(0) if opening and ABOUT_IT.search(opening.group(0)) else words
        state = cov.state({"source": "response", "government_words": decisive, "label": label})
        verdict = cov.verdict(decisive, label) if state == "position" else ""
        keep = found.get(label)
        if keep and keep["state"] == "position" and state != "position":
            continue
        found[label] = {"state": state, "verdict": verdict,
                        "government_label": (label_said(decisive, label)
                                             if state == "position" else ""),
                        "other_governments": "", "government_words": words,
                        "government_words_more": more, "note": ""}
    return found


# --- both -------------------------------------------------------------------
def read(path: pathlib.Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(path: pathlib.Path, fields: list[str], rows: list[dict]) -> None:
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    tmp.replace(path)


def text_for(document_id: str) -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(TEXT.glob(f"{document_id}_*.txt")))


def positions_in(body: str, title: str = "") -> tuple[dict[str, dict], str]:
    """The positions a response states, and which grammar it was read as."""
    if blocks_in(body, title):
        return from_blocks(body, title), "blocks"
    return from_prose(body, title), "prose"


def label_key(label: str) -> list[int]:
    return [int(p) for p in label.split(".")]


def main(argv: list[str]) -> int:
    wanted = {argv[i + 1] for i, a in enumerate(argv) if a == "--commission"}
    # Keyed by the report, not by the commission. A commission can be answered
    # more than once and number each set from one: Defence and Veteran Suicide
    # made recommendations 1 to 13 in an interim report and 1 to 122 in its
    # final report, so thirteen numbers mean two different things and a row is
    # only identified by which report it came out of.
    recommendations = collections.defaultdict(list)
    for r in read(RECOMMENDATIONS):
        if not wanted or r["commission_id"] in wanted:
            recommendations[(r["commission_id"], r["source_id"])].append(r["label"])
    responses = [d for d in read(DOCUMENTS) if d["role"] == "response"
                 and any(c == d["commission_id"] for c, _ in recommendations)]
    if not responses:
        print("no response documents for any commission with recommendations", file=sys.stderr)
        return 1
    # A response that does not say which report it answers is not read against
    # all of them: it is refused, and the seed is where that is fixed.
    unpaired = [d for d in responses
                if (d["commission_id"], (d.get("answers") or "").strip()) not in recommendations]
    for d in unpaired:
        print(f"  OTD {d['id']}: does not say which report it answers — set `answers` in "
              f"rc_seed.csv", file=sys.stderr)
    if unpaired:
        print(f"REFUSING: {len(unpaired)} responses are not paired with a report", file=sys.stderr)
        return 1

    rows, counts, unread, empty = [], [], [], []
    for d in sorted(responses, key=lambda d: d["tabled_senate"] or d["tabled_house"]):
        body = text_for(d["id"])
        if not body.strip():
            unread.append(d)
            continue
        found, grammar = positions_in(body, d.get("title", ""))
        if not found:
            empty.append(d)
            continue
        report_id = (d.get("answers") or "").strip()
        labels = recommendations[(d["commission_id"], report_id)]
        tally = collections.Counter()
        for label in sorted(labels, key=label_key):
            got = found.get(label)
            if got is None:
                got = {"state": "not addressed", "verdict": "", "government_label": "",
                       "other_governments": "", "government_words": "",
                       "government_words_more": "",
                       "note": "the response does not address this recommendation"}
            tally[got["state"]] += 1
            if got["verdict"]:
                tally[got["verdict"]] += 1
            rows.append({"commission_id": d["commission_id"], "report_id": report_id,
                         "label": label, "response_id": d["id"],
                         "response_tabled": d["tabled_senate"] or d["tabled_house"],
                         "response_url": d["url"], **got})
        counts.append({"commission_id": d["commission_id"], "report_id": report_id,
                       "response_id": d["id"],
                       "grammar": grammar, "recommendations": len(labels),
                       **{k: tally[k] for k in STATES},
                       **{k: tally[k] for k in ("accepted", "in part or in principle",
                                                "not accepted")}})
        print(f"{d['commission_id']}: OTD {d['id']} answering OTD {report_id}, read as {grammar}; "
              + ", ".join(f"{tally[k]} {k}" for k in STATES if tally[k])
              + (" — " + ", ".join(f"{tally[k]} {k}" for k in
                 ("accepted", "in part or in principle", "not accepted") if tally[k])))

    for d in unread:
        print(f"  OTD {d['id']}: no cached text — run harvest_rc_text.py", file=sys.stderr)
    for d in empty:
        print(f"  OTD {d['id']}: no recommendation was found in it by either grammar",
              file=sys.stderr)
    if unread or empty:
        print(f"REFUSING: {len(unread) + len(empty)} responses could not be read",
              file=sys.stderr)
        return 1

    write(OUT, FIELDS, rows)
    write(COUNTS, COUNT_FIELDS, counts)
    print(f"{len(rows)} positions in {OUT.name}; totals in {COUNTS.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
