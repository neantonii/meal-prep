// Screenshot a local HTML page (a review card or a recipe card) as screens
// of a named device, for sessions without a preview pane: the viewer shows
// HTML as source, so the agent sends the PNGs instead.
//
// The page is cut into one PNG per screen, each readable as it would be on
// that device, instead of one long strip. Devices are named, never sized
// ad hoc: the owner's MacBook below, or any of Playwright's devices.
//
// Usage (from the repo root; the preinstalled Playwright, no project
// dependency):
//   node .agents/skills/meal-ingredient/scripts/screenshot.js <page.html> <out-prefix> [device]
// writes <out-prefix>-1.png, <out-prefix>-2.png, ... and prints each path.
// device defaults to the owner's MacBook; any Playwright device name works
// too (e.g. "iPhone 15 Pro").
const path = require("path");
const { chromium, devices } = require("playwright");

// Playwright has no MacBook preset. Apple's spec for the 13" M1 Retina
// display: 2560x1600 native, default "looks like 1440 x 900", i.e. 2x.
const MACBOOK = "MacBook Air M1 (Retina)";
const OWN_DEVICES = {
  [MACBOOK]: {
    ...devices["Desktop Chrome HiDPI"],
    viewport: { width: 1440, height: 900 },
    screen: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  },
};
const DEFAULT_DEVICE = MACBOOK;
const MAX_SCREENS = 8; // a longer page is a sign to screenshot a part of it

(async () => {
  const [page, prefix, deviceName = DEFAULT_DEVICE] = process.argv.slice(2);
  if (!page || !prefix) {
    console.error("usage: screenshot.js <page.html> <out-prefix> [device]");
    process.exit(2);
  }
  const device = OWN_DEVICES[deviceName] ?? devices[deviceName];
  if (!device) {
    console.error(`unknown device "${deviceName}" (see Playwright's devices list)`);
    process.exit(2);
  }
  const browser = await chromium.launch();
  const context = await browser.newContext({ ...device });
  const tab = await context.newPage();
  await tab.goto("file://" + path.resolve(page));

  const screen = device.viewport.height;
  const total = await tab.evaluate(() => document.documentElement.scrollHeight);
  const screens = Math.min(Math.ceil(total / screen), MAX_SCREENS);
  for (let i = 0; i < screens; i++) {
    await tab.evaluate((y) => window.scrollTo(0, y), i * screen);
    const out = `${prefix}-${i + 1}.png`;
    await tab.screenshot({ path: out });
    console.log(out);
  }
  if (Math.ceil(total / screen) > MAX_SCREENS) {
    console.log(`(stopped after ${MAX_SCREENS} screens; the page is longer)`);
  }
  await browser.close();
})();
