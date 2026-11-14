// Screenshot a local HTML page (a review card or a recipe card) to PNG.
//
// For sessions without a preview pane (cloud, phone): the viewer shows HTML
// as source, so the agent sends the PNG instead. Uses the preinstalled
// Playwright; no project dependency.
//
// Usage (from the repo root):
//   node .agents/skills/meal-ingredient/scripts/screenshot.js <page.html> <out.png>
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const [page, out] = process.argv.slice(2);
  if (!page || !out) {
    console.error("usage: screenshot.js <page.html> <out.png>");
    process.exit(2);
  }
  const browser = await chromium.launch();
  const tab = await browser.newPage({
    viewport: { width: 760, height: 900 },
    deviceScaleFactor: 2,
  });
  await tab.goto("file://" + path.resolve(page));
  await tab.screenshot({ path: out, fullPage: true });
  await browser.close();
  console.log(`wrote ${out}`);
})();
