/**
 * Build-time access to the royal commissions dataset.
 *
 * A second corpus for the recommendation index, on the same site, sharing its
 * verdict vocabulary and its test of what counts as a stated position. Not a
 * register: /methods/ admits one only where an obligation, a claimant and a
 * date all exist, and a royal commission has none of them. Nothing here is ever
 * overdue and no clock runs against anybody; what the page shows is elapsed
 * time, which is arithmetic on two tabling dates.
 *
 * Everything is read from scraper/data/ while the site builds, like the rest of
 * the dataset. The files come from harvest_royal_commissions.py,
 * extract_rc_recommendations.py and extract_rc_positions.py, and nothing here
 * decides anything the pipeline has not already decided and written down.
 */
import fs from "node:fs";
import path from "node:path";
import { parseCsv } from "./data";

const DATA_DIR = path.resolve(process.cwd(), "..", "scraper", "data");

function read(name: string): Record<string, string>[] {
  const f = path.join(DATA_DIR, name);
  if (!fs.existsSync(f)) return [];
  return parseCsv(fs.readFileSync(f, "utf8").replace(/^﻿/, ""));
}

/**
 * A report that sets recommendations out under their own numbers, and the
 * response to it. A commission can have more than one: the Royal Commission
 * into Defence and Veteran Suicide made 13 recommendations in an interim
 * report the government answered in 2022, and 122 more in its final report,
 * answered in 2024. The pair is the unit here because the numbers start again
 * at one in each of them.
 */
export interface CommissionReport {
  id: string;
  /** "Interim report", "Final report" — what the register's own note calls it. */
  label: string;
  tabled: string;
  url: string;
  responseTabled: string;
  responseUrl: string;
  /** What the report says it recommends, and what the extraction found. */
  stated: string;
  found: number;
  /** Days from the report being tabled to the response being tabled. */
  daysToRespond: number | null;
  /** Days from the report being tabled to today. */
  daysSinceReport: number;
}

export interface Commission {
  id: string;
  name: string;
  /**
   * What to call it in a space too small for its name — the first of the
   * short names the dataset holds, with "Royal Commission" taken off where it
   * is the tail of it. From the data, so a fourth commission names itself.
   */
  short: string;
  /** Its reports that carry recommendations, earliest tabling first. */
  reports: CommissionReport[];
  /** Every recommendation of every one of them. */
  found: number;
}

export interface RcRecommendation {
  commissionId: string;
  commission: string;
  /** What to call the commission where its full name will not fit. */
  commissionShort: string;
  /** Which of the commission's reports this came from, where it has more than one. */
  reportLabel: string;
  label: string;
  /**
   * The recommendation's own heading, as the report sets it — told from the
   * text below it by the type the report used, not by a guess. Empty where the
   * report's typography could not be read.
   */
  heading: string;
  /** The commission's own words. Empty where the report's boundary could not be read. */
  text: string;
  textNote: string;
  reportUrl: string;
  reportTabled: string;
  /** "position", "noted", "not addressed" or "unreadable". */
  state: string;
  /** "accepted", "in part or in principle", "not accepted", or "". */
  verdict: string;
  /** The government's own words for its verdict, exactly as written. */
  governmentLabel: string;
  /** What the states and territories said, where they answered separately. */
  otherGovernments: string;
  governmentWords: string;
  /** True where the answer runs on past what the index prints of it. */
  governmentWordsMore: boolean;
  positionNote: string;
  responseUrl: string;
  responseTabled: string;
}

const days = (from: string, to: string): number | null => {
  if (!from || !to) return null;
  const a = Date.parse(`${from}T00:00:00Z`);
  const b = Date.parse(`${to}T00:00:00Z`);
  if (Number.isNaN(a) || Number.isNaN(b)) return null;
  return Math.round((b - a) / 86_400_000);
};

const tabled = (d: Record<string, string>): string =>
  [d.tabled_senate, d.tabled_house].filter(Boolean).sort()[0] ?? "";

/** Every commission the index holds a recommendation for. */
export function commissions(): Commission[] {
  const docs = read("rc_documents.csv");
  const counts = read("rc_recommendation_counts.csv");
  const today = new Date().toISOString().slice(0, 10);
  const rows = read("rc_recommendations.csv");
  const ids = [...new Set(rows.map((r) => r.commission_id))];
  return read("royal_commissions.csv")
    .filter((c) => ids.includes(c.commission_id))
    .map((c) => {
      const mine = docs.filter((d) => d.commission_id === c.commission_id);
      const reports = mine
        .filter((d) => d.role === "report" && d.carries_recommendations)
        .sort((a, b) => tabled(a).localeCompare(tabled(b)))
        .map((report) => {
          // The response that says it answers this report, and no other.
          const response = mine.find((d) => d.role === "response" && d.answers === report.id);
          const count = counts.find((x) => x.source_id === report.id);
          const reportTabled = tabled(report);
          const responseTabled = response ? tabled(response) : "";
          return {
            id: report.id,
            label: (report.note ?? "").split(";")[0].trim(),
            tabled: reportTabled,
            url: report.url ?? "",
            responseTabled,
            responseUrl: response?.url ?? "",
            stated: count?.stated ?? "",
            found: Number(count?.found ?? 0),
            daysToRespond: days(reportTabled, responseTabled),
            daysSinceReport: days(reportTabled, today) ?? 0,
          };
        });
      const short = (c.short_names ?? "").split("|")[0].trim();
      return {
        id: c.commission_id,
        name: c.name,
        short: short.replace(/\s*Royal Commission$/, "") || c.name,
        reports,
        found: reports.reduce((n, r) => n + r.found, 0),
      };
    });
}

/** One row per recommendation: what was recommended, and what was said back. */
export function rcRecommendations(): RcRecommendation[] {
  const all = commissions();
  const names = new Map(read("royal_commissions.csv").map((c) => [c.commission_id, c.name]));
  const shorts = new Map(all.map((c) => [c.id, c.short]));
  // Only where a commission has more than one report does it matter which one a
  // row came from; naming it on every row would be noise on the other three.
  const reports = new Map(all.flatMap((c) => c.reports.length > 1
    ? c.reports.map((r) => [`${c.id}|${r.id}`, r.label.toLowerCase()] as const) : []));
  // Keyed by the report as well as the number. A commission answered twice
  // numbers each set from one, so recommendation 1 of an interim report and
  // recommendation 1 of a final report are different rows.
  const positions = new Map(
    read("rc_positions.csv").map((p) => [`${p.commission_id}|${p.report_id}|${p.label}`, p]),
  );
  return read("rc_recommendations.csv").map((r) => {
    const p = positions.get(`${r.commission_id}|${r.source_id}|${r.label}`);
    return {
      commissionId: r.commission_id,
      commission: names.get(r.commission_id) ?? r.commission_id,
      commissionShort: shorts.get(r.commission_id) ?? r.commission_id,
      reportLabel: reports.get(`${r.commission_id}|${r.source_id}`) ?? "",
      label: r.label,
      heading: r.heading ?? "",
      text: r.recommendation,
      textNote: r.note ?? "",
      reportUrl: r.report_url ?? "",
      reportTabled: r.report_tabled ?? "",
      state: p?.state ?? "",
      verdict: p?.verdict ?? "",
      governmentLabel: p?.government_label ?? "",
      otherGovernments: p?.other_governments ?? "",
      governmentWords: p?.government_words ?? "",
      governmentWordsMore: p?.government_words_more === "yes",
      positionNote: p?.note ?? "",
      responseUrl: p?.response_url ?? "",
      responseTabled: p?.response_tabled ?? "",
    };
  });
}

export interface RcFigures {
  commissions: number;
  recommendations: number;
  position: number;
  noted: number;
  notAddressed: number;
  unreadable: number;
  accepted: number;
  inPartOrInPrinciple: number;
  notAccepted: number;
  /** Recommendations whose own words could not be read from the report. */
  textUnreadable: number;
  /** Recommendations the response answers together with the states. */
  withTheStates: number;
}

/** The figures the page states, counted here so no page types a number. */
export function rcFigures(): RcFigures {
  const rows = rcRecommendations();
  const n = (f: (r: RcRecommendation) => boolean) => rows.filter(f).length;
  return {
    commissions: new Set(rows.map((r) => r.commissionId)).size,
    recommendations: rows.length,
    position: n((r) => r.state === "position"),
    noted: n((r) => r.state === "noted"),
    notAddressed: n((r) => r.state === "not addressed"),
    unreadable: n((r) => r.state === "unreadable"),
    accepted: n((r) => r.verdict === "accepted"),
    inPartOrInPrinciple: n((r) => r.verdict === "in part or in principle"),
    notAccepted: n((r) => r.verdict === "not accepted"),
    textUnreadable: n((r) => !r.text),
    withTheStates: n((r) => r.otherGovernments !== "" ||
                            r.positionNote.includes("states and territories")),
  };
}

/** The government's own labels, and how often each was used. */
export function rcLabels(): { label: string; verdict: string; n: number }[] {
  const seen = new Map<string, { label: string; verdict: string; n: number }>();
  for (const r of rcRecommendations()) {
    if (!r.governmentLabel) continue;
    const key = `${r.governmentLabel}|${r.verdict}`;
    const got = seen.get(key) ?? { label: r.governmentLabel, verdict: r.verdict, n: 0 };
    got.n += 1;
    seen.set(key, got);
  }
  return [...seen.values()].sort((a, b) => b.n - a.n);
}

export interface RcSources {
  /** Commissions the document table holds, whether or not they have been read. */
  commissionsHeld: number;
  /** Documents in the table, by the role each plays for its commission. */
  documents: number;
  reports: number;
  responses: number;
  /** Documents whose text has been read, which is what the index is built from. */
  read: number;
  /** Register records the table does not claim, which a person has looked at. */
  rejected: number;
}

/** What the document table holds, so the page need not say it from memory. */
export function rcSources(): RcSources {
  const docs = read("rc_documents.csv");
  const readable = new Set(rcRecommendations().map((r) => r.commissionId));
  return {
    commissionsHeld: new Set(docs.map((d) => d.commission_id)).size,
    documents: docs.length,
    reports: docs.filter((d) => d.role === "report").length,
    responses: docs.filter((d) => d.role === "response").length,
    read: docs.filter((d) => readable.has(d.commission_id)
      && (d.role === "response" || d.carries_recommendations)).length,
    rejected: read("rc_not_ours.csv").length,
  };
}

/** How each response was read: as prose, or as labelled blocks. */
export function rcGrammars(): { commissionId: string; grammar: string; responseId: string }[] {
  return read("rc_position_counts.csv").map((r) => ({
    commissionId: r.commission_id,
    grammar: r.grammar,
    responseId: r.response_id,
  }));
}
