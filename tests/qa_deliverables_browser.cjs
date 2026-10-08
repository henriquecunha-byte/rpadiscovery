// Optional local QA: NODE_PATH must point to an installed Playwright package.
// Usage: node tests/qa_deliverables_browser.cjs <relatorio.html> <evidence-dir>
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL, fileURLToPath } = require('node:url');
const assert = require('node:assert/strict');

(async () => {
  const reportPath = path.resolve(process.argv[2]);
  const evidenceDir = path.resolve(process.argv[3]);
  fs.mkdirSync(evidenceDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const width of [1440, 375]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const external = [];
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route(/^https?:/, route => {
        external.push(route.request().url());
        return route.abort();
      });
      await page.goto(pathToFileURL(reportPath).href, { waitUntil: 'load' });
      await page.evaluate(async () => {
        await Promise.all([400, 500, 600].map(weight => document.fonts.load(`${weight} 17px Branding`)));
        await document.fonts.ready;
      });
      const content = await page.evaluate(() => ({
        pageWidth: innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        fonts: [...document.fonts].map(font => ({ family: font.family, weight: font.weight, status: font.status })),
        refs: [...document.querySelectorAll('a[href], img[src], video[src], video[poster]')]
          .flatMap(element => ['href', 'src', 'poster'].filter(attr => element.hasAttribute(attr)).map(attr => element.getAttribute(attr))),
        anchors: [...document.querySelectorAll('a[href^="#"]')].map(element => ({ href: element.getAttribute('href'), exists: !!document.getElementById(element.hash.slice(1)) })),
        headings: [...document.querySelectorAll('h1,h2')].map(element => element.textContent),
      }));
      const missing = content.refs.filter(ref => {
        const url = new URL(ref, pathToFileURL(reportPath));
        return url.protocol === 'file:' && !fs.existsSync(fileURLToPath(url));
      });
      assert.equal(content.scrollWidth, width, `horizontal page overflow at ${width}px`);
      assert.equal(content.fonts.length, 3);
      assert(content.fonts.every(font => font.status === 'loaded'), 'font did not load offline');
      assert.equal(missing.length, 0, `missing local references: ${missing}`);
      assert(content.anchors.every(anchor => anchor.exists), 'missing evidence anchor');
      assert.equal(external.length, 0, 'report attempted external requests');
      assert.equal(errors.length, 0, 'browser script errors');
      const media = await page.evaluate(async () => {
        const result = [];
        for (const video of document.querySelectorAll('video')) {
          video.muted = true;
          await video.play();
          await new Promise(resolve => setTimeout(resolve, 220));
          video.pause();
          result.push({ source: video.getAttribute('src'), duration: video.duration, time: video.currentTime, readyState: video.readyState, error: video.error?.code || null });
        }
        return result;
      });
      assert(media.every(video => video.time > 0 && video.duration > 0 && !video.error), 'offline video playback failed');
      await page.keyboard.press('Tab');
      const focus = await page.evaluate(() => ({
        label: document.activeElement.textContent,
        outline: getComputedStyle(document.activeElement).outlineStyle,
        width: getComputedStyle(document.activeElement).outlineWidth,
      }));
      assert.equal(focus.outline, 'solid');
      assert.equal(focus.width, '3px');
      await page.screenshot({ path: path.join(evidenceDir, `report-${width}.png`) });
      await page.locator('.evidence-card').first().screenshot({ path: path.join(evidenceDir, `evidence-${width}.png`) });
      results.push({ width, ...content, missing, external, errors, media, focus });
      await page.close();
    }
    fs.writeFileSync(path.join(evidenceDir, 'results.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results.map(({width, scrollWidth, fonts, missing, external, errors, media, focus}) => ({ width, scrollWidth, fonts, missing, external, errors, media, focus })), null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
