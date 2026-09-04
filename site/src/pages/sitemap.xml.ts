/**
 * /sitemap.xml — every page, so a search engine need not discover the editions
 * one link at a time. The registers change weekly and the editions never do,
 * and the change frequencies say so.
 */
import type { APIRoute } from "astro";
import { editions } from "../lib/data";

const SITE = "https://toohardbasket.org.au";

export const GET: APIRoute = () => {
  const weekly = ["/", "/house/", "/senate/", "/senate/responses/", "/recommendations/", "/as-at/"];
  const rare = ["/methods/", "/about/", "/corrections/"];
  const urls = [
    ...weekly.map((p) => ({ p, f: "weekly" })),
    ...rare.map((p) => ({ p, f: "monthly" })),
    ...editions().map((e) => ({ p: `/as-at/${e.date}/`, f: "never" })),
  ];
  const body =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    urls.map((u) => `  <url><loc>${SITE}${u.p}</loc><changefreq>${u.f}</changefreq></url>`).join("\n") +
    `\n</urlset>\n`;
  return new Response(body, { headers: { "Content-Type": "application/xml; charset=utf-8" } });
};
