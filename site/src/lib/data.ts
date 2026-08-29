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
  source: string;
}

/** The Senate ledger: reports still awaiting a government response. */
export function ledger(): Obligation[] {
  return read("ledger_v2.csv")
    .map((r) => ({
      register: "senate",
      body: r.committee,
      title: r.title,
      owedSince: r.report_tabled,
      daysOutstanding: num(r.days_outstanding) ?? 0,
      discharged: null,
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

