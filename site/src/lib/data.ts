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
   * asterisk on page 2 of her own report; the Speaker writes the sentence out.
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
   * A joint committee's report, presented to both houses. Most of the House
   * register and nearly half of the Senate's is joint, which is why neither is
   * only its own chamber's.
   */
  joint: boolean;
  /** The same report is listed on the other register too. Never add the counts. */
  alsoOnOther: boolean;
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
  /** Joint committee reports, which the other register may also list. */
  jointCommittee: number;
  ownChamber: number;
  /** Reports on both registers at once. The same for either register. */
  onBothRegisters: number;
  /** Of those, how many are past the deadline on one register but not the other. */
  deadlineDiffers: number;
  /**
   * Reports the Speaker records as answered and the President still lists as
   * outstanding. Two records of one obligation, kept by the two presiding
   * officers of the same Parliament, disagreeing about whether it is
   * discharged.
   */
  officersDisagree: number;
  officersDisagreeReports: string[];
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
  /**
   * The date the government's status report is as at, which is NOT the date of
   * the register. The President's report is as at 30 June and her "Interim*"
   * marks come from a government report as at 31 March; presenting both as one
   * date would be dating a March fact June.
   */
  beingConsideredAsAt?: string;
  /** House only: how many reports the government's own report lists. */
  governmentReportListed?: number;
  /**
   * House only: how many reports fall into each of the three statuses the
   * government's report can give. An unanswered report can only be "being
   * considered", which is why that count is not on its own a finding.
   */
  governmentStatuses?: { answered: number; considered: number; full: number; other: number };
  governmentReportMatched?: number;
  /**
   * The latest tabling date on the list of government responses this build
   * checked against. A register is only as current as the responses it has
   * seen, and that is not the same as the schedule's date or as today.
   */
  responsesCheckedTo?: string;
  /**
   * The back run of the presiding officer's own reports. Nine editions of the
   * President's report are on the public register, twice a year since June
   * 2022, and reading all of them is what turns "the government says its
   * response is being considered" from a status into a duration.
   */
  editionsRead?: number;
  editionsFrom?: string;
  consideredEveryEdition?: number;
  /** House only: the presiding officer's own on-time verdict, this period. */
  answeredOnTime?: number;
  answeredWithVerdict?: number;
  onTimeRate?: number;
  /** What counting his rows gives, where that differs from his own tally. */
  rowsMarkedOnTime?: number;
  onTimeGap?: number;
  /** House only: the answered count printed in the schedule's own summary
   *  table, where that differs from what reading its rows gives. The
   *  difference is a report the schedule still lists against a 2022 response
   *  date; it is treated here as answered, and the register says so. */
  officerSaysAnswered?: number;
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
    officerSaysAnswered: m.schedule_says_answered,
    answeredSince: m.answered_since_schedule ?? 0,
    beingConsidered: m.being_considered,
    recordsBeingConsidered: m.being_considered_recorded ?? true,
    partial: m.partial_response,
    overdue: m.overdue,
    jointCommittee: m.joint_committee ?? 0,
    ownChamber: m.own_chamber ?? 0,
    onBothRegisters: m.on_both_registers ?? 0,
    deadlineDiffers: m.deadline_differs_across_registers ?? 0,
    officersDisagree: m.officers_disagree ?? 0,
    officersDisagreeReports: m.officers_disagree_reports ?? [],
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
    beingConsideredAsAt: m.being_considered_as_at,
    governmentReportListed: m.government_report_listed,
    governmentStatuses: m.government_report_statuses,
    governmentReportMatched: m.government_report_matched,
    responsesCheckedTo: m.responses_checked_to,
    editionsRead: m.editions_read,
    editionsFrom: m.editions_from,
    consideredEveryEdition: m.being_considered_every_edition,
    answeredOnTime: m.answered_on_time,
    answeredWithVerdict: m.answered_with_a_verdict,
    onTimeRate: m.on_time_rate,
    rowsMarkedOnTime: m.rows_marked_on_time,
    onTimeGap: m.on_time_gap,
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
      joint: r.joint_committee === "True",
      alsoOnOther: r.also_on_other_register === "True",
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

/**
 * What the President herself recorded as outstanding, edition by edition.
 *
 * The history chart reconstructs the backlog from tabling dates. These are the
 * counts she actually printed. They are not the same number, and the difference
 * is not noise: the reconstruction runs about sixty reports high in 2022 and
 * 2023 and fourteen to thirty-one low after the 2024 clear-out, because the two
 * count slightly different populations. Publishing both is the only honest way
 * to show a series that reaches back further than the record does.
 */
export interface Snapshot {
  asAt: string;
  listed: number;
  answered: number;
  outstanding: number;
  beingConsidered: number;
}

export function snapshots(): Snapshot[] {
  if (!fs.existsSync(path.join(DATA_DIR, "schedule_snapshots.csv"))) return [];
  return read("schedule_snapshots.csv")
    .filter((r) => r.as_at)
    .map((r) => ({
      asAt: r.as_at,
      listed: num(r.listed) ?? 0,
      answered: num(r.answered) ?? 0,
      outstanding: num(r.outstanding) ?? 0,
      beingConsidered: num(r.being_considered) ?? 0,
    }))
    .sort((a, b) => a.asAt.localeCompare(b.asAt));
}

// --------------------------------------------------- responses tabled, by year

/**
 * How many responses the government tabled in each year, and — for the years
 * where the documents themselves have been read — how many of them closed the
 * report with the form letter.
 *
 * These are two different populations and the chart says so. The yearly count
 * comes from the Senate response record, which runs from 2000. The classified
 * count comes from the response documents, which exist in the Tabled Documents
 * system only from mid-2022 and cover both chambers. They are not a subset of
 * one another and must never be stacked, subtracted or expressed as a share of
 * each other. What the second series is for is to say what a spike in the first
 * one was made of, in the years where that can be known.
 */
export interface ResponseYear {
  year: string;
  responses: number;
  /** Response documents read for that year — null before the corpus begins. */
  documents: number | null;
  /** Of those documents, the form-letter closures (full and partial). */
  closures: number | null;
  /** Responses that used the template for some recommendations but not all.
   *  Not counted as closures; shown as a footnote so the column adds to the
   *  published total. */
  partial: number | null;
}

export function responsesByYear(): ResponseYear[] {
  const tally = new Map<string, number>();
  for (const r of read("responses.csv")) {
    const y = (r.response_tabled ?? "").slice(0, 4);
    if (y) tally.set(y, (tally.get(y) ?? 0) + 1);
  }

  const excluded = new Set(read("scope_exclusions.csv").map((r) => r.id));
  const docs = new Map<string, { n: number; closed: number; partial: number }>();
  for (const r of read("response_documents.csv")) {
    if (excluded.has(r.id)) continue;
    const y = (r.tabled_senate || r.tabled_house || "").slice(0, 4);
    if (!y) continue;
    const cell = docs.get(y) ?? { n: 0, closed: 0, partial: 0 };
    cell.n += 1;
    // Only full form-letter closures. Counting the partials here too made the
    // column total 265 where Methods, the brief and the analysis page all say
    // 260 — and the caption's claim that these took no position on any
    // recommendation is not true of a response that used the template for some
    // and answered the rest. The partials are carried separately and footnoted.
    if (r.classification === "proforma_closure") cell.closed += 1;
    if (r.classification === "partial_proforma") cell.partial += 1;
    docs.set(y, cell);
  }

  return [...tally.keys()].sort().map((year) => {
    const d = docs.get(year);
    return {
      year,
      responses: tally.get(year) ?? 0,
      documents: d ? d.n : null,
      closures: d ? d.closed : null,
      partial: d ? d.partial : null,
    };
  });
}

/**
 * One entry per response document in the classified corpus, in tabling order,
 * for the strip on the home page. The busiest day — the date on which the most
 * form-letter closures were tabled — is marked so the strip can point at it.
 * Nothing is counted here that the closure figures do not already count; the
 * strip is those figures drawn one document at a time.
 */
export interface StripCell {
  tabled: string;
  kind: "closure" | "busiest" | "other";
}
export function responseStrip(): {
  cells: StripCell[];
  total: number;
  closures: number;
  others: number;
  busiestDay: string;
  busiestCount: number;
  from: string;
  to: string;
} {
  const excluded = new Set(read("scope_exclusions.csv").map((r) => r.id));
  const docs = read("response_documents.csv")
    .filter((r) => !excluded.has(r.id))
    .map((r) => ({
      id: Number(r.id),
      tabled: (r.tabled_senate || r.tabled_house || "").slice(0, 10),
      closure: r.classification === "proforma_closure",
    }))
    .filter((r) => r.tabled)
    .sort((a, b) => a.tabled.localeCompare(b.tabled) || a.id - b.id);

  const perDay = new Map<string, number>();
  for (const d of docs) if (d.closure) perDay.set(d.tabled, (perDay.get(d.tabled) ?? 0) + 1);
  const [busiestDay, busiestCount] = [...perDay.entries()].sort((a, b) => b[1] - a[1])[0] ?? ["", 0];

  const cells: StripCell[] = docs.map((d) => ({
    tabled: d.tabled,
    kind: !d.closure ? "other" : d.tabled === busiestDay ? "busiest" : "closure",
  }));
  const closures = docs.filter((d) => d.closure).length;
  return {
    cells, total: docs.length, closures, others: docs.length - closures,
    busiestDay, busiestCount, from: docs[0]?.tabled ?? "", to: docs.at(-1)?.tabled ?? "",
  };
}

// ------------------------------------------------------------------ editions

/**
 * One file per weekly build, written by scraper/snapshot_edition.py after the
 * publishability gate: what both registers and the closure figures said on
 * that date. Published unchanged at /as-at/<date>/, so a figure quoted from
 * this site stays reachable at the page that showed it. Editions are numbered
 * in date order, from the first one kept.
 */
export interface EditionRow {
  title: string; committee: string; tabled: string; days: number; status: string;
  url: string; both: boolean;
}
export interface EditionRegister {
  schedule_as_at: string; schedule_tabled: string; schedule_url: string;
  outstanding_at_schedule: number; answered_since_schedule: number;
  outstanding: number; overdue: number; being_considered: number; longest_days: number;
  rows: EditionRow[];
}
export interface Edition {
  number: number;
  date: string;
  responses_checked_to: string;
  dataset_tag: string;
  senate: EditionRegister;
  house: EditionRegister;
  corpus: { documents_read: number; form_letter_closures: number; read_from: string; read_to: string };
  recommendations: { rows: number; awaiting_a_response: number };
}

export function editions(): Edition[] {
  const dir = path.join(DATA_DIR, "editions");
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
    .sort()
    .map((f, i) => ({ number: i + 1, ...(JSON.parse(fs.readFileSync(path.join(dir, f), "utf8")) as Omit<Edition, "number">) }));
}

/** The edition this build is publishing — the latest kept. */
export function currentEdition(): Edition | null {
  return editions().at(-1) ?? null;
}

/**
 * What moved between the two latest editions, by report title: how many left
 * each register (answered, or otherwise taken off) and how many joined it.
 */
export function editionDiff(): { since: string; senate: { left: number; joined: number }; house: { left: number; joined: number } } | null {
  const all = editions();
  if (all.length < 2) return null;
  const [prev, cur] = all.slice(-2);
  const diff = (a: EditionRow[], b: EditionRow[]) => {
    const key = (r: EditionRow) => `${r.tabled}|${r.title}`;
    const was = new Set(a.map(key)), is = new Set(b.map(key));
    return { left: [...was].filter((k) => !is.has(k)).length, joined: [...is].filter((k) => !was.has(k)).length };
  };
  return { since: prev.date, senate: diff(prev.senate.rows, cur.senate.rows), house: diff(prev.house.rows, cur.house.rows) };
}

/** The long-run rate, for the reference line: the years before the clear-out. */
export function typicalYear(rows: ResponseYear[], upTo = "2023") {
  const years = rows.filter((r) => r.year <= upTo);
  const counts = years.map((r) => r.responses).sort((a, b) => a - b);
  const mean = counts.reduce((a, b) => a + b, 0) / (counts.length || 1);
  return {
    mean,
    median: counts[Math.floor(counts.length / 2)] ?? 0,
    min: counts[0] ?? 0,
    max: counts[counts.length - 1] ?? 0,
    from: years[0]?.year ?? "",
    to: upTo,
    years: years.length,
  };
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
  // The deadline is recomputed here rather than read from the row, so this and
  // complianceDetail() can never publish two rates from one file. Until 2
  // September the column said 90 days for every row while this site published
  // the calendar-month rule, and the two disagreed by ten responses.
  const usable = rows
    .map((r) => ({ days: num(r.days_to_respond), deadline: deadlineDays(r.report_last_tabled) }))
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
  /** The latest tabling date in the corpus: how current these figures are. */
  readTo: string;
  /** Documents no text could be got from. They are in the corpus and are
   *  classified as neither closure nor substantive, so a number above zero
   *  means the closure rate is understated by up to that many documents. */
  unreadable: number;
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

  const dates = kept
    .map((r) => r.tabled_senate || r.tabled_house)
    .filter(Boolean)
    .sort();

  return {
    corpus: kept.length,
    proforma,
    partial: count("partial_proforma"),
    substantive: count("substantive"),
    rate: kept.length ? proforma / kept.length : 0,
    readTo: dates[dates.length - 1] ?? "",
    unreadable: count("unreadable"),
    excluded: excl.length,
    exclusions: [...byReason.entries()]
      .map(([reason, count]) => ({ reason, label: EXCLUSION_LABELS[reason] ?? reason, count }))
      .sort((a, b) => b.count - a.count),
  };
}

// ---------------------------------------------------------------- corrections

/**
 * The reports removed from a register because the government answered them
 * after the schedule was printed.
 *
 * A schedule is a snapshot and the register is not: between the presiding
 * officer's as-at date and today the government keeps tabling responses, and
 * every one of those is a report the register would otherwise show as
 * unanswered. Removing them silently is not enough — the count on the page
 * would then differ from the presiding officer's own and nothing would say
 * why — so each removal is published with the response that caused it.
 */
export interface AnsweredSince {
  title: string;
  body: string;
  owedSince: string;
  responseId: string;
  responseTabled: string;
  responseTitle: string;
  basis: string;
  /** Where the removal can be checked: the response document where there is
   *  one, and otherwise the register page that records the response. Empty
   *  only if neither source gave a link, in which case the row is shown
   *  without one rather than dropped. */
  url: string;
}

/**
 * Where a removal's evidence can be read. A response the Senate's own register
 * accounts for carries the scraper's key for the page it was read from —
 * "statsnet/2026" — which was being printed into the link as it stood, and so
 * pointed at /senate/statsnet/2026 on this site, which does not exist. The
 * key names the year of the register; the Parliament's page takes the year as
 * a date range and opens on the government-responses tab.
 */
function sourceUrl(source: string): string {
  const m = /^(?:fixtures\/)?statsnet\/(\d{4})$/.exec(source);
  if (m) {
    return `https://www.aph.gov.au/Parliamentary_Business/Statistics/Senate_StatsNet?from=${m[1]}-01-01&to=${m[1]}-12-31#/government-responses`;
  }
  return /^https?:\/\//.test(source) ? source : "";
}

export function answeredSince(register: RegisterSlug): AnsweredSince[] {
  const file = `answered_since_${register}.csv`;
  if (!fs.existsSync(path.join(DATA_DIR, file))) return [];
  // Filtering on response_id dropped every removal the Senate's own response
  // register accounted for, because those rows have no Tabled Documents id.
  // The page's count included them and its list did not, so it said sixteen
  // and showed two. A removal is publishable when it names a date.
  return read(file)
    .filter((r) => r.response_tabled)
    .map((r) => ({
      title: r.title,
      body: r.committee,
      owedSince: r.report_tabled,
      responseId: r.response_id,
      responseTabled: r.response_tabled,
      responseTitle: r.response_title,
      basis: r.removal_basis,
      url: r.response_id
        ? `https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/${r.response_id}`
        : sourceUrl(r.response_source ?? ""),
    }))
    .sort((a, b) => a.responseTabled.localeCompare(b.responseTabled));
}

/**
 * Reports on either register whose recommendations cannot be searched, because
 * the Tabled Documents register — which supplies every report PDF this site
 * reads — holds nothing before 2022.
 *
 * Read from data/reports_manual.csv, which is the list of exactly those reports
 * and is rebuilt from the registers by harvest_manual_reports.py. Counting the
 * register rows here instead looked equivalent and was not: one of the two
 * ledgers does not always carry the id column, so every row in it counted as
 * missing and the page published 91 where the answer was 26. The list that
 * drives the collection is the only thing that can be trusted to say how much
 * of it is left.
 *
 * The gap runs oldest-first, which is the wrong way round for this site: the
 * reports it hides are the ones that have waited longest, and the ones a reader
 * arriving from the home page is most likely to look for. The number falls as
 * they are collected, and the sentences that admit it disappear at zero.
 */
export function registerReportsWithoutSource(): {
  total: number;          // reports on either register with no readable document
  predating: number;      // those tabled before the Tabled Documents index begins
  oldestTabled: string;   // the oldest of them, so the page can name a date
  collected: number;      // reports whose documents have since been fetched
} {
  const manualPath = path.join(DATA_DIR, "reports_manual.csv");
  if (!fs.existsSync(manualPath)) {
    return { total: 0, predating: 0, oldestTabled: "", collected: 0 };
  }
  const all = read("reports_manual.csv");
  const rows = all.filter((r) => (r.collected ?? "").trim().toLowerCase() !== "yes");
  // Two different reasons a report has no document, and they deserve different
  // sentences. Most are older than the register itself, which is the failure
  // that matters: it hides exactly the longest waits. The rest are recent
  // reports the register happens not to index, which is untidy but not a story.
  const old = rows.filter((r) => (r.report_tabled ?? "") < "2022-01-01");
  const dates = rows.map((r) => r.report_tabled ?? "").filter(Boolean).sort();
  return {
    total: rows.length,
    predating: old.length,
    oldestTabled: dates[0] ?? "",
    collected: all.length - rows.length,
  };
}

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
 *
 * The deadline is three calendar months from tabling, not ninety days. The
 * Senate's 1973 resolution says three months, the President's own report says
 * three months, and her "Response provided within 3 months" column marks a
 * 92-day response Yes. Testing 90 days instead counted eleven responses late
 * that the Senate counts on time — an error running against the government,
 * on a site whose whole claim is that every figure it gives is a floor.
 */

/** Days from a tabling date to three calendar months later. 89 to 92. */
function deadlineDays(tabled: string): number {
  if (!tabled) return 92;              // no report date: the longest, in the
  const d = new Date(`${tabled}T00:00:00Z`);   // government's favour
  const due = new Date(d);
  due.setUTCMonth(due.getUTCMonth() + 3);
  // JS rolls 30 November + 3 months to 2 March; the Senate would read the last
  // day of February, so pull it back when the day of the month has moved.
  if (due.getUTCDate() !== d.getUTCDate()) due.setUTCDate(0);
  return Math.round((due.getTime() - d.getTime()) / 86_400_000);
}
const GOVERNMENTS: { name: string; from: string; to: string }[] = [
  { name: "Howard", from: "1996-03-11", to: "2007-12-03" },
  { name: "Rudd / Gillard", from: "2007-12-03", to: "2013-09-18" },
  { name: "Abbott / Turnbull / Morrison", from: "2013-09-18", to: "2022-05-23" },
  { name: "Albanese", from: "2022-05-23", to: "2099-01-01" },
];

/**
 * The first bucket is the rule itself, which is a different number of days for
 * each report, so every bucket is a test on the row rather than a day range.
 */
type Timed = { days: number; deadline: number };
const BUCKETS: { label: string; test: (r: Timed) => boolean }[] = [
  { label: "Within three months — the rule", test: (r) => r.days <= r.deadline },
  { label: "Three months to six", test: (r) => r.days > r.deadline && r.days <= 180 },
  { label: "6 months to a year", test: (r) => r.days > 180 && r.days <= 365 },
  { label: "1 to 2 years", test: (r) => r.days > 365 && r.days <= 730 },
  { label: "2 to 5 years", test: (r) => r.days > 730 && r.days <= 1826 },
  { label: "Over 5 years", test: (r) => r.days > 1826 },
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
      deadline: deadlineDays(r.report_last_tabled),
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
    rate: rows.filter((r) => r.days <= r.deadline).length / n,
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
      const count = rows.filter(b.test).length;
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
 * The recommendation floor, built by scraper/count_recommendations.py.
 *
 * NOT a count of recommendations closed. It is the number of recommendations
 * in the closures that prove their own structure: labels running 1..N with no
 * gaps and the notes sentence appearing exactly N times, N at least two. Every
 * other closure is excluded with a reason, including the 45 that closed a
 * report without noting a single recommendation. Any page using this must say
 * "at least" and link to the working.
 */
export interface RecommendationFloor {
  closures: number;        // form-letter closures in total
  counted: number;         // those whose structure can be verified
  recommendations: number; // the floor itself
  sentences: number;       // notes sentences across the whole corpus
  /** The template sentence's own count across the same documents. It is the
   *  number the brief quotes, and it is slightly larger than `sentences`
   *  because the template appears in forms the stricter "notes this
   *  recommendation" pattern does not match. One of the two has to be the
   *  published figure; this is it, and the page says what it counts. */
  templateUses: number;
  reasons: { why: string; count: number }[];
}

export function recommendationFloor(): RecommendationFloor {
  const rows = read("recommendation_counts.csv");
  const counted = rows.filter((r) => r.counted === "yes");
  const reasons = new Map<string, number>();
  for (const r of rows) {
    if (!r.excluded_because) continue;
    // The disagreement reason carries each document's two numbers; group it.
    const why = /^\d/.test(r.excluded_because)
      ? "the notes sentences and the recommendation labels disagree"
      : r.excluded_because;
    reasons.set(why, (reasons.get(why) ?? 0) + 1);
  }
  return {
    closures: rows.length,
    counted: counted.length,
    recommendations: counted.reduce((t, r) => t + (num(r.recommendations_counted) ?? 0), 0),
    sentences: rows.reduce((t, r) => t + (num(r.notes_sentences) ?? 0), 0),
    templateUses: (() => {
      const counted = new Set(rows.map((r) => String(r.id)));
      return read("response_documents.csv")
        .filter((r) => counted.has(String(r.id)))
        .reduce((t, r) => t + (num(r.template_hits) ?? 0), 0);
    })(),
    reasons: [...reasons.entries()]
      .map(([why, count]) => ({ why, count }))
      .sort((a, b) => b.count - a.count),
  };
}

/**
 * The closure analysis behind /senate/responses/, counted on the scoped corpus
 * (see closures()). Documents, not recommendations: the count of reports
 * closed with the template is exact, and the recommendation question is
 * answered separately and conservatively by recommendationFloor().
 */
// ------------------------------------------------------- the recommendations

/**
 * One recommendation, as the record shows it.
 *
 * Two sources, and the difference matters enough to be on the page. A
 * recommendation from a REPORT is the committee's own words, taken from the
 * report it tabled — those are the ones still awaiting a response, so no
 * government document quotes them. A recommendation from a RESPONSE is the
 * committee's words as the GOVERNMENT reproduced them, quoted in its own answer
 * — which is why it can carry what the government said in reply.
 *
 * No status is invented. `governmentWords` is the sentence the government
 * actually wrote about this recommendation, or empty where it wrote none.
 */
export interface Recommendation {
  source: "report" | "response";
  sourceId: string;
  label: string;
  /** Named when the recommendation is a dissenting, minority or party one. */
  recommendedBy: string;
  /**
   * The document this came from also contains recommendations that are not the
   * committee's, even where this row's own author could not be established.
   * Some responses mark a dissent only in prose — "The Australian Greens made a
   * further 22 recommendations" — which no per-row test can reach.
   */
  documentHasOtherAuthors: boolean;
  text: string;
  governmentWords: string;
  classification: string;
  committee: string;
  department: string;
  documentTitle: string;
  tabled: string;
  chamber: string;
  url: string;
  /**
   * The response that answered (or closed) the report this row is from, and
   * the report itself, where each is known. A response-derived row always
   * has its response; it has its report where the Parliament links the two
   * or the title search found it. A report-derived row always has its
   * report; it has a response only when the report was answered by one that
   * quotes no recommendation, which is why the report was read.
   */
  responseUrl: string;
  responseTabled: string;
  reportUrl: string;
  /**
   * What the response did with this recommendation, from coverage.py:
   * "position" (a verdict word used of the recommendation), "noted" (words,
   * no verdict), "form letter", "not individual", "unreadable", "awaiting",
   * "dissent", or "" when the positions file has not been built.
   */
  position: string;
}

/** The state coverage.py gave each index row, keyed the way that file keys it. */
function positionStates(): Map<string, string> {
  const f = path.join(DATA_DIR, "recommendation_positions.csv");
  const m = new Map<string, string>();
  if (!fs.existsSync(f)) return m;
  for (const r of read("recommendation_positions.csv")) {
    m.set(`${r.source}|${r.source_id}|${r.label}|${r.recommended_by ?? ""}`, r.state);
  }
  return m;
}

export function recommendations(): Recommendation[] {
  const states = positionStates();
  return read("recommendations.csv").map((r) => ({
    position: states.get(`${r.source}|${r.source_id}|${r.label}|${r.recommended_by ?? ""}`) ?? "",
    source: r.source as Recommendation["source"],
    sourceId: r.source_id,
    label: r.label,
    recommendedBy: r.recommended_by ?? "",
    documentHasOtherAuthors: (r.document_has_other_authors ?? "") === "yes",
    text: r.recommendation,
    governmentWords: r.government_words ?? "",
    classification: r.response_classification,
    committee: r.committee ?? "",
    department: r.department ?? "",
    documentTitle: r.document_title ?? "",
    tabled: r.tabled ?? "",
    chamber: r.chamber ?? "",
    url: r.url ?? "",
    responseUrl: r.response_url ?? "",
    responseTabled: r.response_tabled ?? "",
    reportUrl: r.report_url ?? "",
  }));
}

/** How many rows the verification step removed, so the page can say so. */
export function recommendationsDropped(): number {
  const f = path.join(DATA_DIR, "recommendations_dropped.csv");
  return fs.existsSync(f) ? read("recommendations_dropped.csv").length : 0;
}

/**
 * The responses the search cannot show a single recommendation from.
 *
 * A search for "gambling" found nothing about the House's online-gambling
 * inquiry, because the government's response of May 2026 notes the
 * committee's 31 recommendations as a group and describes a package of
 * reforms, and never sets one recommendation out. The index is built from
 * responses that quote recommendations one by one, so that document, and the
 * fifty-odd like it, were invisible to the page whose purpose is to show
 * what happened to what committees asked for. They are listed here so the
 * search can name them — with the fact that they quote nothing, which is the
 * point — and link to them.
 */
export interface QuietResponse {
  id: string;
  title: string;
  committee: string;
  department: string;
  tabled: string;
  chamber: "senate" | "house";
  classification: string;
  url: string;
}

/**
 * How many responses in the corpus yield nothing of their own, and how many of
 * those had their report read instead. The search page used to print a typed
 * figure for the first — 255, on a page whose whole argument is that its
 * numbers are counted — and it was wrong by the time it was read.
 */
export function quietResponseCounts(): { ofTheirOwn: number; reportReadInstead: number; nothingAtAll: number } {
  const excluded = new Set(read("scope_exclusions.csv").map((r) => r.id));
  const rows = read("recommendations.csv");
  const own = new Set(rows.filter((r) => r.source === "response").map((r) => r.source_id));
  const viaReport = new Set(rows.filter((r) => r.source === "report" && r.response_id).map((r) => r.response_id));
  const corpus = read("response_documents.csv").filter((r) => !excluded.has(r.id));
  const quiet = corpus.filter((r) => !own.has(r.id));
  const readInstead = quiet.filter((r) => viaReport.has(r.id));
  return { ofTheirOwn: quiet.length, reportReadInstead: readInstead.length,
           nothingAtAll: quiet.length - readInstead.length };
}

export function responsesQuotingNothing(): QuietResponse[] {
  const excluded = new Set(read("scope_exclusions.csv").map((r) => r.id));
  // A response is accounted for if the index holds rows from it, or rows
  // from the report it answered — the second is what happens when the
  // response quotes nothing and the report was read instead.
  const rows = read("recommendations.csv");
  const quoted = new Set([
    ...rows.filter((r) => r.source === "response").map((r) => r.source_id),
    ...rows.filter((r) => r.source === "report" && r.response_id).map((r) => r.response_id),
  ]);
  const committeeOf = (title: string) => {
    const m = /response(?:s)?\s+to\s+(?:the\s+)?(.*?)\s*(?:\breport\b|\binquiry\b|:|$)/i.exec(title || "");
    const name = m ? m[1].replace(/\s+/g, " ").replace(/^[\s,:–—-]+|[\s,:–—-]+$/g, "") : "";
    return /committee|commission/i.test(name) && name.length <= 120 ? name : "";
  };
  return read("response_documents.csv")
    .filter((r) => !excluded.has(r.id) && !quoted.has(r.id))
    .map((r) => ({
      id: r.id,
      title: r.title,
      committee: committeeOf(r.title),
      department: r.department || r.author || "",
      tabled: r.tabled_senate || r.tabled_house || "",
      chamber: (r.tabled_senate ? "senate" : "house") as "senate" | "house",
      classification: r.classification,
      url: r.url,
    }))
    .sort((a, b) => b.tabled.localeCompare(a.tabled));
}

export interface ClosureDetail extends ClosureFigures {
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
    byYear,
    slowest,
  };
}

export interface CoverageBucket {
  responses: number;
  responsesWithNoPositionAtAll: number;
  responsesFullyCovered: number;
  recommendations: number;
  positionStated: number;
  notedNoPosition: number;
  formLetter: number;
  notAddressedIndividually: number;
  unreadable: number;
  /** positionStated / recommendations, or null when nothing is assessable. */
  coverage: number | null;
}

export interface Coverage {
  definition: string;
  responsesInCorpus: number;
  responsesWithNothingIndexed: number;
  dissentingExcluded: number;
  total: CoverageBucket;
  byYear: { year: string; bucket: CoverageBucket }[];
  byClassification: Record<string, CoverageBucket>;
}

/**
 * For each recommendation the index holds, did the response state a position
 * on it? Read from coverage_summary.json, which coverage.py writes from the
 * same recommendations.csv the search page is built from.
 */
export function coverage(): Coverage | null {
  const f = path.join(DATA_DIR, "coverage_summary.json");
  if (!fs.existsSync(f)) return null;
  type Raw = {
    responses: number; responses_with_no_position_at_all: number; responses_fully_covered: number;
    recommendations: number; position_stated: number; noted_no_position: number; form_letter: number;
    not_addressed_individually: number; unreadable: number; coverage: number | null;
  };
  const bucket = (b: Raw): CoverageBucket => ({
    responses: b.responses,
    responsesWithNoPositionAtAll: b.responses_with_no_position_at_all,
    responsesFullyCovered: b.responses_fully_covered,
    recommendations: b.recommendations,
    positionStated: b.position_stated,
    notedNoPosition: b.noted_no_position,
    formLetter: b.form_letter,
    notAddressedIndividually: b.not_addressed_individually,
    unreadable: b.unreadable,
    coverage: b.coverage,
  });
  const s = readJson<{
    definition: string; responses_in_corpus: number; responses_with_nothing_indexed: number;
    dissenting_recommendations_excluded: number; total: Raw; by_year: Record<string, Raw>;
    by_classification: Record<string, Raw>;
  }>("coverage_summary.json");
  return {
    definition: s.definition,
    responsesInCorpus: s.responses_in_corpus,
    responsesWithNothingIndexed: s.responses_with_nothing_indexed,
    dissentingExcluded: s.dissenting_recommendations_excluded,
    total: bucket(s.total),
    byYear: Object.entries(s.by_year).sort(([a], [b]) => a.localeCompare(b))
      .map(([year, b]) => ({ year, bucket: bucket(b) })),
    byClassification: Object.fromEntries(Object.entries(s.by_classification).map(([k, b]) => [k, bucket(b)])),
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
