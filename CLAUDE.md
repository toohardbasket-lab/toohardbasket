# Working on The Too Hard Basket

Read this before touching anything. It is the standing context for any
session working on this repository — what the project will not compromise
on, and the handful of facts that cost real time to learn.

## What this is

A public register of what Australian governments were asked to answer, when
they answered, and what they said. Published by the Australian Public
Interest Alliance (APIA), a Western Australian non-profit. Live at
toohardbasket.org.au. Built by one person, Alan Hewitt, which the site says
on its About page.

Its authority rests on one thing: **every published figure is mechanical and
reproducible from the published dataset, and the code that produces it is
public.** A reader who disagrees can disagree with something specific. That
is the whole product. Protect it ahead of any feature.

## The rules that are not negotiable

- **Nothing is inferred.** A recommendation counts as answered only where
  the government's own words state a position. "Noted" is no position.
  Where the words cannot be read, the row says so; it is not counted as
  unanswered and it is not guessed at.
- **A figure that cannot be reproduced does not go out.** This has already
  bitten once: a hand-typed "191 responses, 46 form letters" in a draft
  email was never true at any point in the dataset's history. Every figure
  in the media pack now comes from `scraper/brief_figures.py`. If you find
  yourself typing a number into a document, stop and add it to that script.
- **Published editions are never rewritten.** Each weekly edition is frozen
  at `/as-at/<date>/` and tagged `edition-<date>`, so a figure quoted from
  the site on a date stays where it was quoted. Fix forward, and record it
  in the corrections log.
- **The registers follow the presiding officers.** The Senate rows are the
  President's status column and the House rows are the Speaker's. The site
  does not second-guess them; where the two officers disagree, it says so.
- **Never add the two registers together.** They overlap — currently by 24
  reports — so 82 plus 38 is not 120 awaiting, it is 96 distinct reports.
  `brief_figures.py` reports both and names the trap.

## Two machines, and which one to use

Alan's working copy is `D:\toohardbasket`, reached through `device_bash`.
That copy is the source of truth. Do the work there.

The cloud container is for things the Windows machine cannot do:

- **Astro will not build on the device.** `node_modules` there holds win32
  binaries and the device shell is Linux. Site builds happen in the cloud
  container against a copy — and that copy goes stale fast, so refresh it
  before trusting anything you build from it.
- Anything needing a library or tool that is only in the cloud container.

Do not stage files just to read or edit them. Read and edit in place on the
device with `device_bash`.

## Windows and PowerShell gotchas

- **PowerShell does not expand `*` for external commands.** `git am 0029-*.patch`
  fails with "could not open '0029-*.patch'". Run globbing commands yourself
  through `device_bash`, which is bash.
- **`git push` needs Alan.** The device VM has no GitHub credentials. Commit
  on the device, then ask him to push. Do not try to work around it.
- **Deleting on the mount is blocked by default.** `rm` fails with
  "Operation not permitted" until `device_request_delete_permission` is
  granted, and the grant does not survive bridge reconnects.
- Stale `.git/index.lock` and `.git/rebase-apply` have blocked `git am` more
  than once. Check for them before assuming a patch is bad.

## The weekly job

`.github/workflows/update-dataset.yml`, Tuesdays 06:00 Perth (`0 22 * * 1`,
with `TZ: Australia/Canberra` set at job level so `date +%F` is the Canberra
date). It rebuilds everything from source and **commits nothing unless every
gate passes** — parser tests, refresh tests, recommendation verification,
removal tests, coverage tests, digest tests. A failure leaves the site
showing the previous edition, which is the intended behaviour.

`watch-batches.yml` runs Wednesday to Saturday and does the fast path:
harvest, classify, pair, then the alerts.

`heartbeat.yml` runs Wednesdays and asks whether the weekly job succeeded in
the last eight days, because a scheduled run that never starts looks exactly
like a register with nothing to report.

### The alarms, and why each exists

All four open a GitHub issue, which reaches Alan by email at
alan@earthstar.com.au (repo watched on All Activity; notification default
set to that address). Verified end to end on 6 September 2026.

- **`batch_alert.py`** — a day on which five or more reports were closed
  with the form letter. The register's most reportable event is a day, not
  a number. Days already reported are in `data/alerted_batches.json`.
- **`digest.py`** — one message listing what was tabled since the last one,
  ordered by the longest wait. Deliberately **not** one message per
  response, and deliberately **no judgement about newsworthiness** — it
  computes the comparisons and leaves the judgement to a person. Seen ids in
  `data/digested_responses.json`.
- **`statsnet_alert.py`** — the Senate StatsNet scrape falls back to cached
  cells when aph.gov.au refuses it, which keeps the build green while the
  compliance series quietly stops moving. This says so after a fortnight.
- **The failure alarm and the heartbeat** — the build broke, or never ran.

Every alarm must be silent by default, must never fail the job (`sys.exit(0)`
on any exception), and must record what it has said so it does not repeat.

## Conventions

- Commit messages say **why**, in prose, in the register's voice. Look at
  recent ones before writing one.
- New behaviour arrives with tests that pin the ways it could mislead, not
  just the happy path. `scraper/tests/` runs in the workflow as gates.
- Data files live in `scraper/data/` and are committed by the weekly job.
- Patch files are relayed between working copies and are gitignored.

## Where things are

```
scraper/            the pipeline, one script per step; run order is in the workflow
scraper/data/       the published dataset (CSV + JSON)
scraper/tests/      the gates
site/               Astro 7, built by Cloudflare Pages from main
.github/workflows/  the three jobs above
```

`brief_figures.py` computes every figure the evidence brief and the media
email quote, including a `the_pitch` block for the covering email. Run it
before either document goes anywhere.
