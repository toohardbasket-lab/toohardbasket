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

export interface Commission {
  id: string;
  name: string;
  /** The report documents, earliest tabling first. */
  reportTabled: string;
  reportUrl: string;
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

export interface RcRecommendation {
  commissionId: string;
  commission: string;
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

/** Every commission the register holds a recommendation for. */
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
      const report = mine
        .filter((d) => d.role === "report" && d.carries_recommendations)
        .sort((a, b) => tabled(a).localeCompare(tabled(b)))[0];
      const response = mine
        .filter((d) => d.role === "response")
        .sort((a, b) => tabled(a).localeCompare(tabled(b)))[0];
      const count = counts.find((x) => x.commission_id === c.commission_id);
      const reportTabled = report ? tabled(report) : "";
      const responseTabled = response ? tabled(response) : "";
      return {
        id: c.commission_id,
        name: c.name,
        reportTabled,
        reportUrl: report?.url ?? "",
        responseTabled,
        responseUrl: response?.url ?? "",
        stated: count?.stated ?? "",
        found: Number(count?.found ?? 0),
        daysToRespond: days(reportTabled, responseTabled),
        daysSinceReport: days(reportTabled, today) ?? 0,
      };
    });
}

/** One row per recommendation: what was recommended, and what was said back. */
export function rcRecommendations(): RcRecommendation[] {
  const names = new Map(read("royal_commissions.csv").map((c) => [c.commission_id, c.name]));
  const positions = new Map(
    read("rc_positions.csv").map((p) => [`${p.commission_id}|${p.label}`, p]),
  );
  return read("rc_recommendations.csv").map((r) => {
    const p = positions.get(`${r.commission_id}|${r.label}`);
    return {
      commissionId: r.commission_id,
      commission: names.get(r.commission_id) ?? r.commission_id,
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
