/**
 * Facts about the publisher, kept out of the page prose so they are edited in
 * one place and can be checked against the record.
 *
 * Sources: apia.org.au/governance and apia.org.au/about (read 29 Aug 2026),
 * ABN Lookup (23 Aug 2026). Keep this in step with apia.org.au — the two sites
 * disagreeing with each other is exactly what a hostile reader is looking for.
 */
const PLACEHOLDER = /^«.*»$/;

export const ABOUT = {
  founderName: "Alan Hewitt",
  founderRole: "APIA's President",

  entityName: "Australian Public Interest Alliance Incorporated",
  abn: "33 842 796 620",
  incorporationNumber: "IARN A1046494Z",
  state: "Western Australia",
  act: "Associations Incorporation Act 2015 (WA)",
  site: "https://apia.org.au",
  governancePage: "https://apia.org.au/governance/",

  /**
   * APIA's governance page states a committee of three and refers readers to
   * the public register maintained by Consumer Protection (WA).
   *
   * soloOperated records the reality Alan confirmed on 29 Aug 2026: the work is
   * one person's, and the other two committee members provide the governance an
   * incorporated association requires without directing the project. The About
   * page says so, because "a committee of three" implies more institutional
   * weight than exists, and a reader who discovered that later would be right to
   * wonder what else was oversold.
   *
   * If names are added here once members consent, the page uses them.
   */
  committeeSize: 3,
  committeeNames: [] as string[],
  soloOperated: true,

  /** Verified 29 Aug 2026 on apia.org.au/governance and ABN Lookup. */
  acncRegistered: false,
  dgrEndorsed: false,
  fundingStatement:
    "APIA is self-funded by its founder and has received no external funding to date.",
} as const;

/** Every placeholder that is still unfilled. */
export function unfilled(): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(ABOUT)) {
    if (typeof v === "string" && PLACEHOLDER.test(v)) out.push(k);
    if (Array.isArray(v) && v.some((x) => PLACEHOLDER.test(x))) out.push(k);
  }
  return out;
}

export function validateAbout(): void {
  const missing = unfilled();
  if (missing.length) {
    throw new Error(
      `About page has unfilled placeholders in src/lib/about.ts: ${missing.join(", ")}. ` +
      `Fill them before building — an About page with a placeholder in it should never go live.`
    );
  }
}

const WORDS = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
export const inWords = (n: number): string => WORDS[n] ?? String(n);
