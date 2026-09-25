// Holding page build (25 September 2026).
//
// While the register is offline, `npm run build` writes this single page
// instead of the site, so every address on toohardbasket.org.au shows the same
// short notice. The full site is untouched in src/ and builds again with
// `npm run build:full`; to bring it back, revert the commit that added this
// file and switched the build script.
import { mkdirSync, rmSync, writeFileSync, copyFileSync, existsSync } from "node:fs";

const out = new URL("../dist/", import.meta.url);
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

const MESSAGE = "This site is temporarily offline. Please check back later.";

const page = `<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Too Hard Basket</title>
<meta name="description" content="${MESSAGE}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<style>
  html { background: #fbfaf7; color: #1f1f1f; }
  @media (prefers-color-scheme: dark) { html { background: #161616; color: #e8e6e1; } }
  body { margin: 0; min-height: 100vh; display: grid; place-items: center;
         font: 18px/1.5 Georgia, "Times New Roman", serif; }
  main { max-width: 32rem; padding: 2rem 1rem; text-align: center; }
  h1 { font-size: 1.6rem; font-weight: 600; margin: 0 0 0.75rem; }
  p { margin: 0; }
</style>
</head>
<body>
<main>
  <h1>The Too Hard Basket</h1>
  <p>${MESSAGE}</p>
</main>
</body>
</html>
`;

writeFileSync(new URL("index.html", out), page);
writeFileSync(new URL("404.html", out), page);
writeFileSync(new URL("robots.txt", out), "User-agent: *\nAllow: /\n");

for (const f of ["_headers", "favicon.ico", "favicon.svg"]) {
  const src = new URL(`../public/${f}`, import.meta.url);
  if (existsSync(src)) copyFileSync(src, new URL(f, out));
}
console.log("Holding page written to dist/ (index.html and 404.html).");
