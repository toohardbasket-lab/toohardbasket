/**
 * The responses the search index holds no recommendation from — see
 * responsesQuotingNothing() — as a small file the search page fetches with
 * the index, so a topic can be matched against them and the document named.
 */
import type { APIRoute } from "astro";
import { responsesQuotingNothing } from "../lib/data";

export const GET: APIRoute = () => {
  const docs = responsesQuotingNothing().map((d) => ({
    i: d.id, d: d.title, c: d.committee, p: d.department, w: d.tabled, h: d.chamber, k: d.classification, u: d.url,
  }));
  return new Response(JSON.stringify(docs), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
