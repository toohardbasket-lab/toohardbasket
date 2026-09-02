/**
 * The search index, as a file the page fetches once.
 *
 * It is about three megabytes of text, which Cloudflare serves compressed. The
 * page loads without it and fetches it in the background, so the first search
 * is instant on a warm connection and merely slow on a cold one — rather than
 * the page itself being slow for everyone, including the readers who never
 * search.
 *
 * Field names are one letter because they repeat four thousand times and the
 * payload is the whole cost of this page.
 */
import type { APIRoute } from "astro";
import { recommendations } from "../lib/data";

export const GET: APIRoute = () => {
  const rows = recommendations().map((r) => ({
    t: r.text,
    g: r.governmentWords,
    c: r.committee,
    d: r.documentTitle,
    l: r.label,
    b: r.recommendedBy,
    k: r.classification,
    w: r.tabled,
    h: r.chamber,
    u: r.url,
    s: r.source,
  }));
  return new Response(JSON.stringify(rows), {
    headers: { "content-type": "application/json; charset=utf-8" },
  });
};
