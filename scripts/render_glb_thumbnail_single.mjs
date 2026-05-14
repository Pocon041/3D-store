import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "frontend", "package.json"));
const { chromium } = require("playwright");

function readArg(name, fallback = null) {
  const flag = `--${name}`;
  const idx = process.argv.indexOf(flag);
  if (idx < 0 || idx + 1 >= process.argv.length) return fallback;
  return process.argv[idx + 1];
}

const src = readArg("src");
const out = readArg("out");
const size = Number(readArg("size", "768"));

if (!src || !out) {
  console.error("Usage: node scripts/render_glb_thumbnail_single.mjs --src model.glb --out thumb.png [--size 768]");
  process.exit(2);
}

const srcPath = path.resolve(root, src);
const outPath = path.resolve(root, out);
const modelViewerPath = path.join(
  root,
  "frontend",
  "node_modules",
  "@google",
  "model-viewer",
  "dist",
  "model-viewer.min.js",
);

const html = `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <script type="module" src="/model-viewer.min.js"></script>
  <style>
    html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: #f6f7f9; }
    model-viewer { width: ${size}px; height: ${size}px; background: #f6f7f9; }
  </style>
</head>
<body>
  <model-viewer
    id="viewer"
    src="/asset.glb"
    camera-orbit="0deg 72deg 2.4m"
    field-of-view="28deg"
    exposure="1"
    shadow-intensity="0.8"
    loading="eager">
  </model-viewer>
</body>
</html>`;

await fs.access(srcPath);
await fs.mkdir(path.dirname(outPath), { recursive: true });

const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: size, height: size },
    deviceScaleFactor: 1,
  });

  await page.route("**/model-viewer.min.js", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: await fs.readFile(modelViewerPath, "utf8"),
    });
  });

  await page.route("**/asset.glb", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "model/gltf-binary",
      body: await fs.readFile(srcPath),
    });
  });

  await page.route("**/thumb-render.html", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: html,
    });
  });

  await page.goto("http://thumbnail.local/thumb-render.html", {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });
  await page.waitForSelector("model-viewer", { timeout: 10000 });
  await page.waitForFunction(() => {
    const viewer = document.querySelector("model-viewer");
    return viewer && viewer.loaded;
  }, { timeout: 60000 });
  await page.waitForTimeout(600);
  await page.screenshot({
    path: outPath,
    clip: { x: 0, y: 0, width: size, height: size },
  });
} finally {
  await browser.close();
}
