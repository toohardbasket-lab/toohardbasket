# Discovery pack, 6 September 2026

Four files produced by ChatGPT on 6 September 2026 as a first scan of the
royal commissions problem, committed here unchanged as a record of where the
work started.

- `royal_commission_scan.py` — the script that built the census, by scraping
  Wikipedia list pages.
- `royal_commissions_candidate_census.csv` — its output: candidate rows for
  Commonwealth, state and territory commissions.
- `royal_commissions_source_map.csv` — official seed pages by jurisdiction.
- `royal_commissions_initial_scan.md` — the accompanying design note.

**Nothing in these files is verified and nothing in them is to be cited.**
The census is scraped from Wikipedia; 388 of its 682 rows carry no link, one
title contains stylesheet text, and a commission appointed by more than one
government appears under each. The design note proposes extracting positions
with a language model and a confidence score, which is not how this register
works: see `CLAUDE.md`. The source map of official seed pages is the part
with value in it, and only the APH Parliamentary Library and the Western
Australian Parliamentary Library entries have been checked.

Figures from this pack do not appear in `../source-test-2026-09.md`. Every
number there was produced by a command that is printed beside it.
