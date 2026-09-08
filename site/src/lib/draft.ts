/**
 * What is built but not published.
 *
 * The royal commissions index lives on the site and is not part of it yet. The
 * site's rule is that everything it publishes is finished and reproducible, so
 * until the index clears that bar it must not appear in the navigation, in the
 * sitemap, on the live methods page, or in a search engine — even if the branch
 * it is on is merged.
 *
 * Before this file, three separate things had to be remembered on the day it
 * goes live: a nav item, a section of /methods/, and a line in the weekly job.
 * Three things to remember at merge is how a half-finished page reaches the
 * public. Now there is one:
 *
 *     ROYAL_COMMISSIONS_DRAFT = false
 *
 * and tests/test_going_live.py refuses the fourth — a `continue-on-error` in
 * the royal commissions block of update-dataset.yml, which lets that block fail
 * without stopping the run. A published index has to gate the run like the rest
 * of the dataset, so the flag and that line cannot disagree.
 *
 * While the flag is true, the pages are still built and still reachable at
 * their own addresses, which is what makes them reviewable, and they carry
 * `noindex`. In `astro dev` the nav item shows anyway, so working on the index
 * does not mean typing its URL every time.
 */
export const ROYAL_COMMISSIONS_DRAFT = true;

/** The pages the index is made of, in the order a sitemap would list them. */
export const ROYAL_COMMISSIONS_PAGES = ["/royal-commissions/", "/methods/royal-commissions/"];
