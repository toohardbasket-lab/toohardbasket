/**
 * Build-time access to the dataset.
 *
 * The CSVs live in scraper/data/, outside the Astro project, and are read from
 * disk while the site builds — nothing is fetched at run time and no numbers are
 * hardcoded in a page. When the weekly workflow commits new data, Pages rebuilds
 * and every figure on the site moves with it.
 */
import fs from "node:fs";
import path from "node:path";

const DATA_DIR = path.resolve(process.cwd(), "..", "scraper", "data");

/** RFC4180-ish: quoted fields may contain commas, newlines and doubled quotes. */
export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else quoted = false;
      } else field += c;
      continue;
    }
    if (c === '"') { quoted = true; continue; }
    if (c === ",") { row.push(field); field = ""; continue; }
    if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
      continue;
    }
    field += c;
  }
  row.push(field);
  if (row.length > 1 || row[0] !== "") rows.push(row);

  const header = rows.shift();
  if (!header) return [];
  return rows.map((r) => Object.fromEntries(header.map((h, i) => [h.trim(), (r[i] ?? "").trim()])));
}

function read(name: string): Record<string, string>[] {
  return parseCsv(fs.readFileSync(path.join(DATA_DIR, name), "utf8").replace(/^﻿/, ""));
}

function readJson<T>(name: string): T {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, name), "utf8")) as T;
}

const num = (v: string): number | null => {
  const t = (v ?? "").trim();
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
};

const median = (xs: number[]): number =>
  xs.length === 0 ? 0
  : [...xs].sort((a, b) => a - b).length % 2
    ? [...xs].sort((a, b) => a - b)[(xs.length - 1) / 2]
    : ([...xs].sort((a, b) => a - b)[xs.length / 2 - 1] + [...xs].sort((a, b) => a - b)[xs.length / 2]) / 2;

// ---------------------------------------------------------------- the Ledger

/**
 * One outstanding obligation. Deliberately not Senate-specific: the House, the
 * states and coronial registers produce rows of exactly this shape, so pages
 * written against this type do not change when a second register is added.
 */
export interface Obligation {
  register: string;          // register slug, e.g. "senate"
  body: string;              // the committee or commission that raised it
  title: string;             // what is owed an answer
  owedSince: string;         // ISO date the obligation began
  daysOutstanding: number;
  discharged: string | null; // ISO date of the response, or null
  /** The presiding officer records an interim response, not an answer. */
  interim: boolean;
  /**
   * The presiding officer records nothing but "the Government's response is
   * being considered". The President marks these "Interim*" and defines the
   * asterisk on page 2 of his own report; the Speaker writes the sentence out.
   */
  beingConsidered: boolean;
  /** Answered for some recommendations and not others. */
  partial: boolean;
  /**
   * Past that chamber's deadline. Not derivable from daysOutstanding alone:
   * the House's six months excludes any period when the House was dissolved,
   * so the House takes the Speaker's own verdict.
   */
  overdue: boolean;
  /**
   * A response the presiding officer records but does not treat as discharging
   * the report — on the Speaker's schedule, one dated before the current
   * reporting period on a report he still lists as awaiting one.
   */
  earlierResponse: string | null;
  /** The report itself on aph.gov.au, where the Tabled Documents index has it. */
  url: string | null;
  source: string;
}

export type RegisterSlug = "senate" | "house";

const LEDGER_FILE: Record<RegisterSlug, string> = {
  senate: "ledger_v2.csv",
  house: "house_ledger.csv",
};
const META_FILE: Record<RegisterSlug, string> = {
  senate: "ledger_meta.json",
  house: "house_ledger_meta.json",
};

/**
 * What the register is built from, and as at when. Written by the builders,
 * read here so no page can state a position the data does not support.
 */
export interface ScheduleMeta {
  asAt: string;              // the schedule's own as-at date
  tabled: string;            // when the presiding officer tabled it
  title: string;
  url: string;               // the schedule on aph.gov.au
  listed: number;            // reports the schedule lists
  answeredAtSchedule: number;
  answeredSince: number;     // answered between the as-at date and the rebuild
  beingConsidered: number;   // of the rows now published
  /**
   * Whether the source records "the response is being considered" at all. The
   * President marks it "Interim*"; the Speaker's schedule stopped writing it
   * out in the June 2026 edition. A zero count means one of two very different
   * things, so the pages must be able to tell them apart.
   */
  recordsBeingConsidered: boolean;
  partial: number;
  overdue: number;
  notYetDue: number;
  rows: number;
  fromSchedule: number;
  fromTracker: number;
  coversTo: string;          // the latest tabling date either source can see
  rebuilt: string;
  /** House only: the parse reconciles against the schedule's own tally. */
  agreesWithSchedule?: boolean;
  scheduleSaysOutstanding?: number;
  /** Rows the schedule lists as awaiting a response but records a response for. */
  outOfPeriod?: number;
  /** Where the being-considered count came from, when it is a second document. */
  beingConsideredSource?: string;
  beingConsideredTabled?: string;
  governmentReportMatched?: number;
  /** House only: the presiding officer's own on-time verdict, this period. */
  answeredOnTime?: number;
  answeredWithVerdict?: number;
  onTimeRate?: number;
}

export function scheduleMeta(register: RegisterSlug = "senate"): ScheduleMeta {
  const m = readJson<Record<string, any>>(META_FILE[register]);
  return {
    asAt: m.as_at,
    tabled: m.tabled,
    title: m.title,
    url: m.otd_url,
    listed: m.listed,
    answeredAtSchedule: m.answered_at_schedule,
    answeredSince: m.answered_since_schedule ?? 0,
    beingConsidered: m.being_considered,
    recordsBeingConsidered: m.being_considered_recorded ?? true,
    partial: m.partial_response,
    overdue: m.overdue,
    notYetDue: m.not_yet_due,
    rows: m.rows,
    fromSchedule: m.from_schedule ?? m.rows,
    fromTracker: m.from_tracker ?? 0,
    coversTo: m.covers_to,
    rebuilt: m.rebuilt,
    agreesWithSchedule: m.reconciles_with_schedule ?? m.parse_agrees_with_schedule,
    scheduleSaysOutstanding: m.schedule_says_outstanding,
    outOfPeriod: m.response_out_of_period,
    beingConsideredSource: m.being_considered_source,
    beingConsideredTabled: m.being_considered_tabled,
    governmentReportMatched: m.government_report_matched,
    answeredOnTime: m.answered_on_time,
    answeredWithVerdict: m.answered_with_a_verdict,
    onTimeRate: m.on_time_rate,
  };
}

/** A register's ledger: reports still awaiting a government response. */
export function ledger(register: RegisterSlug = "senate"): Obligation[] {
  return read(LEDGER_FILE[register])
    .map((r) => ({
      register,
      body: r.committee,
      title: r.title,
      owedSince: r.report_tabled,
      daysOutstanding: num(r.days_outstanding) ?? 0,
      discharged: null,
      interim: r.interim_response === "True",
      beingConsidered: r.being_considered === "True",
      partial: r.partial_response === "True",
      overdue: r.overdue === "True",
      earlierResponse: r.response_out_of_period || null,
      url: r.report_url || null,
      source: r.source,
    }))
    .filter((r) => r.daysOutstanding > 0)
    .sort((a, b) => b.daysOutstanding - a.daysOutstanding);
}

// ------------------------------------------------------- the backlog history

export interface HistoryPoint {
  asAt: string;
  basis: "reconstructed" | "observed";
  backlog: number;
  oldestDays: number | null;
  medianDays: number | null;
  overOneYear: number;
  overFiveYears: number;
}

export function history(): HistoryPoint[] {
  return read("backlog_history.csv")
    .map((r) => ({
      asAt: r.as_at,
      basis: r.basis as HistoryPoint["basis"],
      backlog: num(r.backlog) ?? 0,
      oldestDays: num(r.oldest_days),
      medianDays: num(r.median_days),
      overOneYear: num(r.over_1_year) ?? 0,
      overFiveYears: num(r.over_5_years) ?? 0,
    }))
    .sort((a, b) => a.asAt.localeCompare(b.asAt));
}

// -------------------------------------------------------------- the register

/**
 * Compliance with the response deadline. The Senate has required a response
 * within three months since 14 March 1973. Rows without both a response
 * interval and a deadline are excluded rather than counted as failures —
 * the 2000–01 registers do not record report dates.
 */
export function compliance() {
  const rows = read("responses.csv");
  const usable = rows
    .map((r) => ({ days: num(r.days_to_respond), deadline: num(r.deadline_days) }))
    .filter((r): r is { days: number; deadline: number } => r.days !== null && !!r.deadline);
  const onTime = usable.filter((r) => r.days <= r.deadline).length;
  return {
    total: rows.length,
    assessable: usable.length,
    onTime,
    rate: usable.length ? onTime / usable.length : 0,
    medianDays: Math.round(median(usable.map((r) => r.days))),
    excluded: rows.length - usable.length,
  };
}

/**
 * The longest waits across both chambers, for the home page.
 *
 * Combining the two lists is fine and comparing their totals is not: a list of
 * individual reports says nothing about which chamber is worse, and every row
 * names its own. The counts stay separate everywhere else.
 */
export function longestWaits(n: number): Obligation[] {
  return [...ledger("senate"), ...ledger("house")]
    .sort((a, b) => b.daysOutstanding - a.daysOutstanding)
    .slice(0, n);
}

/** The House, in the few numbers the home page needs from it. */
export function houseFigures() {
  const rows = ledger("house");
  const meta = scheduleMeta("house");
  return {
    outstanding: rows.length,
    overdue: rows.filter((r) => r.overdue).length,
    beingConsidered: rows.filter((r) => r.beingConsidered).length,
    asAt: meta.asAt,
    oldest: rows[0],
  };
}

/** Everything the home page needs, read once. */
export function homeFigures() {
  const led = ledger();
  const hist = history();
  const observed = hist.filter((p) => p.basis === "observed");
  const reconstructed = hist.filter((p) => p.basis === "reconstructed");
  const peak = reconstructed.reduce((a, b) => (b.backlog > a.backlog ? b : a), reconstructed[0]);
  const waits = led.map((r) => r.daysOutstanding);

  return {
    ledger: led,
    history: hist,
    outstanding: led.length,
    oldest: led[0],
    medianWait: Math.round(median(waits)),
    overFiveYears: waits.filter((d) => d > 1826).length,
    overOneYear: waits.filter((d) => d > 365).length,
    peak,
    asAt: (observed.at(-1) ?? reconstructed.at(-1))!.asAt,
    compliance: compliance(),
    schedule: scheduleMeta(),
    beingConsidered: led.filter((r) => r.beingConsidered).length,
    partial: led.filter((r) => r.partial).length,
    house: houseFigures(),
  };
}

/** 4,291 → "11 years, 9 months". Deliberately plain; no "almost" or "nearly". */
export function humanDuration(days: number): string {
  const years = Math.floor(days / 365.25);
  const months = Math.floor((days - years * 365.25) / 30.44);
  if (years === 0) return `${months} month${months === 1 ? "" : "s"}`;
  const y = `${years} year${years === 1 ? "" : "s"}`;
  return months === 0 ? y : `${y}, ${months} month${months === 1 ? "" : "s"}`;
}

export const fmt = (n: number): string => n.toLocaleString("en-AU");

/** ISO dates are for the data files; readers get "25 November 2014". */
export function formatDate(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-AU", {
    day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  });
}

/** Compact form for table columns: "25 Nov 2014". */
export function formatDateShort(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-AU", {
    day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
  });
}


// -------------------------------------------------------- the response corpus

/**
 * Government responses tabled since mid-2022, and how they answered.
 *
 * The corpus is the OTD document type `Government response`, which is broader
 * than this project's claim: it also carries status schedules, Migration Act
 * s486O statements to the Ombudsman, royal commission responses and responses
 * to statutory reviews. Those are excluded by id in scope_exclusions.csv, with
 * a reason on every row, so the denominator describes the same population as
 * the claim. Excluding them is the conservative move: it removes documents that
 * would otherwise be counted as substantive.
 */
export interface ClosureFigures {
  corpus: number;       // documents after scope exclusions
  proforma: number;     // form-letter closures addressing no recommendation
  partial: number;      // the template used for some recommendations, not all
  substantive: number;
  rate: number;         // proforma / corpus
  excluded: number;
  exclusions: { reason: string; label: string; count: number }[];
}

const EXCLUSION_LABELS: Record<string, string> = {
  status_schedule: "Schedules of outstanding responses — a list, not a response",
  s486O_ombudsman: "Migration Act s486O statements — answering the Ombudsman, not a committee",
  royal_commission: "Responses to royal commissions — a different claimant",
  independent_review: "Responses to statutory reviews and monitors — not a committee report",
};

export function closures(): ClosureFigures {
  const excl = read("scope_exclusions.csv");
  const excluded = new Set(excl.map((r) => r.id));
  const kept = read("response_documents.csv").filter((r) => !excluded.has(r.id));

  const count = (c: string) => kept.filter((r) => r.classification === c).length;
  const proforma = count("proforma_closure");

  const byReason = new Map<string, number>();
  for (const r of excl) byReason.set(r.reason, (byReason.get(r.reason) ?? 0) + 1);

  return {
    corpus: kept.length,
    proforma,
    partial: count("partial_proforma"),
    substantive: count("substantive"),
    rate: kept.length ? proforma / kept.length : 0,
    excluded: excl.length,
    exclusions: [...byReason.entries()]
      .map(([reason, count]) => ({ reason, label: EXCLUSION_LABELS[reason] ?? reason, count }))
      .sort((a, b) => b.count - a.count),
  };
}

// ---------------------------------------------------------------- corrections

export interface Correction {
  date: string;        // ISO date the change was made
  page: string;        // where it appeared
  what: string;        // what changed
  source: string;      // the record that settled it
  reportedBy: string;  // who told us, if they wanted to be named
}

/**
 * The corrections log. Empty is a legitimate state and is published as such —
 * an empty table is a claim ("nothing has needed correcting since we started"),
 * which is checkable, where saying nothing at all is not.
 */
export function corrections(): Correction[] {
  return read("corrections.csv")
    .filter((r) => r.date)
    .map((r) => ({
      date: r.date,
      page: r.page,
      what: r.what_changed,
      source: r.source,
      reportedBy: r.reported_by,
    }))
    .sort((a, b) => b.date.localeCompare(a.date));
}

// ------------------------------------------------- compliance, in more detail

/**
 * The response deadline, examined closely enough to survive a hostile read.
 *
 * Three deliberate choices, all of which favour the government:
 *  - the interval runs from the report's *last* tabling, not its first;
 *  - reports still awaiting a response are not in the denominator at all, so
 *    this measures only responses that eventually arrived;
 *  - rows without a report date are excluded rather than counted as failures.
 */
const GOVERNMENTS: { name: string; from: string; to: string }[] = [
  { name: "Howard", from: "1996-03-11", to: "2007-12-03" },
  { name: "Rudd / Gillard", from: "2007-12-03", to: "2013-09-18" },
  { name: "Abbott / Turnbull / Morrison", from: "2013-09-18", to: "2022-05-23" },
  { name: "Albanese", from: "2022-05-23", to: "2099-01-01" },
];

const BUCKETS: { label: string; lo: number; hi: number }[] = [
  { label: "Within 90 days — the rule", lo: 0, hi: 90 },
  { label: "91 days to 6 months", lo: 91, hi: 180 },
  { label: "6 months to a year", lo: 181, hi: 365 },
  { label: "1 to 2 years", lo: 366, hi: 730 },
  { label: "2 to 5 years", lo: 731, hi: 1826 },
  { label: "Over 5 years", lo: 1827, hi: Infinity },
];

export interface ComplianceDetail {
  assessable: number;
  onTime: number;
  rate: number;
  medianDays: number;
  within180: number;   // share answered within twice the deadline
  within365: number;   // share answered within a year
  firstYear: number;
  lastYear: number;
  excluded: number;
  excludedYears: string;
  buckets: { label: string; count: number; share: number }[];
  governments: {
    name: string;
    byResponse: { n: number; onTime: number; rate: number };
    byReport: { n: number; onTime: number; rate: number };
  }[];
}

export function complianceDetail(): ComplianceDetail {
  const all = read("responses.csv");
  const rows = all
    .map((r) => ({
      days: num(r.days_to_respond),
      deadline: num(r.deadline_days),
      responseTabled: r.response_tabled,
      reportTabled: r.report_last_tabled,
    }))
    .filter((r): r is { days: number; deadline: number; responseTabled: string; reportTabled: string } =>
      r.days !== null && !!r.deadline);

  const n = rows.length;
  const share = (test: (d: number) => boolean) => rows.filter((r) => test(r.days)).length / n;
  const year = (iso: string) => Number((iso || "").slice(0, 4));

  const excludedRows = all.filter((r) => num(r.days_to_respond) === null);
  const exYears = [...new Set(excludedRows.map((r) => year(r.response_tabled)).filter(Boolean))].sort();

  const slice = (field: "responseTabled" | "reportTabled", g: typeof GOVERNMENTS[number]) => {
    const sub = rows.filter((r) => r[field] >= g.from && r[field] < g.to);
    const onTime = sub.filter((r) => r.days <= r.deadline).length;
    return { n: sub.length, onTime, rate: sub.length ? onTime / sub.length : 0 };
  };

  return {
    assessable: n,
    onTime: rows.filter((r) => r.days <= r.deadline).length,
    rate: share((d) => d <= 90),
    medianDays: Math.round(median(rows.map((r) => r.days))),
    within180: share((d) => d <= 180),
    within365: share((d) => d <= 365),
    firstYear: Math.min(...rows.map((r) => year(r.responseTabled)).filter(Boolean)),
    lastYear: Math.max(...rows.map((r) => year(r.responseTabled)).filter(Boolean)),
    excluded: excludedRows.length,
    excludedYears:
      exYears.length < 2 ? exYears.join("")
      : `${exYears.slice(0, -1).join(", ")} and ${exYears[exYears.length - 1]}`,
    buckets: BUCKETS.map((b) => {
      const count = rows.filter((r) => r.days >= b.lo && r.days <= b.hi).length;
      return { label: b.label, count, share: count / n };
    }),
    governments: GOVERNMENTS.map((g) => ({
      name: g.name,
      byResponse: slice("responseTabled", g),
      byReport: slice("reportTabled", g),
    })),
  };
}

/** 420 -> "14 months". For the headline gap, where "1 year, 1 month" reads weakly. */
export function inMonths(days: number): string {
  const m = Math.round(days / 30.44);
  return `${m} month${m === 1 ? "" : "s"}`;
}

// ------------------------------------------------- how responses answered

/**
 * The closure analysis behind /senate/responses/.
 *
 * Counted on the scoped corpus (see closures()). The recommendation total is
 * the number of individual recommendations disposed of by a template sentence
 * — a better measure of what was closed than the document count, because one
 * document can dispose of sixty-eight.
 */
export interface ClosureDetail extends ClosureFigures {
  recommendationsClosed: number;
  byYear: { year: string; closures: number; responses: number; share: number }[];
  slowest: { days: number; reportTabled: string; responseTabled: string; inquiry: string } | null;
}

export function closureDetail(): ClosureDetail {
  const excluded = new Set(read("scope_exclusions.csv").map((r) => r.id));
  const rows = read("response_documents.csv").filter((r) => !excluded.has(r.id));
  const pro = rows.filter((r) => r.classification === "proforma_closure");
  const year = (r: Record<string, string>) => (r.tabled_senate || r.tabled_house || "").slice(0, 4);

  const years = [...new Set(rows.map(year).filter(Boolean))].sort();
  const byYear = years.map((y) => {
    const responses = rows.filter((r) => year(r) === y).length;
    const cl = pro.filter((r) => year(r) === y).length;
    return { year: y, closures: cl, responses, share: responses ? cl / responses : 0 };
  });

  const reg = read("responses.csv")
    .map((r) => ({ days: num(r.days_to_respond), reportTabled: r.report_last_tabled,
                   responseTabled: r.response_tabled, inquiry: r.inquiry }))
    .filter((r): r is { days: number; reportTabled: string; responseTabled: string; inquiry: string } =>
      r.days !== null);
  const slowest = reg.length ? reg.reduce((a, b) => (b.days > a.days ? b : a)) : null;

  return {
    ...closures(),
    recommendationsClosed: pro.reduce((t, r) => t + (num(r.notes_recommendation) ?? 0), 0),
    byYear,
    slowest,
  };
}

/** One response document by OTD id, so a page can cite counts instead of typing them. */
export function responseDoc(id: string) {
  const r = read("response_documents.csv").find((x) => x.id === id);
  if (!r) throw new Error(`No response document with OTD id ${id} — check the id against the dataset.`);
  return {
    id: r.id,
    title: r.title,
    classification: r.classification,
    templateHits: num(r.template_hits) ?? 0,
    recommendationsNoted: num(r.notes_recommendation) ?? 0,
    acceptances: num(r.accept_support_agree) ?? 0,
    tabled: r.tabled_senate || r.tabled_house,
    url: r.url,
  };
}
