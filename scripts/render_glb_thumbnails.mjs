import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(root, "data", "samples", "thumb");
const base = "http://127.0.0.1:8000";
const require = createRequire(path.join(root, "frontend", "package.json"));
const { chromium } = require("playwright");

const items = [
  ["local-apparel-adidas-jacket", "/static/samples/glb/7ad398dd7b67d87e550dee9339bee091.glb"],
  ["custom-seal-plush", "/static/samples/glb/56f0c02d0946f971d889abb90163c787.glb"],
  ["local-apparel-polo-shirt", "/static/samples/glb/3b4c212dfe1d505444538e8592346caa.glb"],
  ["local-apparel-jeans", "/static/samples/glb/e94719d68e8e34583a4f5ca549e38820.glb"],
];

const html = (src) => `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <script type="module" src="/node_modules/@google/model-viewer/dist/model-viewer.min.js"></script>
  <style>
    html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: #f6f7f9; }
    model-viewer { width: 768px; height: 768px; background: #f6f7f9; }
  </style>
</head>
<body>
  <model-viewer
    id="viewer"
    src="${src}"
    camera-orbit="0deg 72deg 2.4m"
    field-of-view="28deg"
    exposure="1"
    shadow-intensity="0.8"
    loading="eager">
  </model-viewer>
</body>
</html>`;

await fs.mkdir(outDir, { recursive: true });

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 768, height: 768 }, deviceScaleFactor: 1 });
  await page.route("**/node_modules/@google/model-viewer/dist/model-viewer.min.js", async (route) => {
    const file = path.join(root, "frontend", "node_modules", "@google", "model-viewer", "dist", "model-viewer.min.js");
    await route.fulfill({
      status: 200,
      contentType: "application/javascript",
      body: await fs.readFile(file, "utf8"),
    });
  });
  await page.route("**/thumb-render.html?*", async (route) => {
    const url = new URL(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: "text/html",
      body: html(url.searchParams.get("src")),
    });
  });

  for (const [id, src] of items) {
    const url = `${base}/thumb-render.html?src=${encodeURIComponent(src)}`;
    console.log(`[render] ${id}`);
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForSelector("model-viewer", { timeout: 10000 });
    await page.waitForFunction(() => {
      const viewer = document.querySelector("model-viewer");
      return viewer && viewer.loaded;
    }, { timeout: 60000 });
    await page.waitForTimeout(600);
    await page.screenshot({
      path: path.join(outDir, `${id}.png`),
      clip: { x: 0, y: 0, width: 768, height: 768 },
    });
  }
} finally {
  await browser.close();
}
