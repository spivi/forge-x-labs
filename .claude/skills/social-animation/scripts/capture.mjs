// Playwright video capture for social animations
// Usage: node capture.mjs <htmlFile> <width> <height> <durationMs> <outputDir>
import { chromium } from 'playwright';
import { resolve } from 'path';

const [,, htmlFile, width, height, durationMs, outputDir] = process.argv;

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: parseInt(width), height: parseInt(height) },
  recordVideo: {
    dir: outputDir,
    size: { width: parseInt(width), height: parseInt(height) }
  }
});

const page = await context.newPage();
await page.goto('file://' + resolve(htmlFile));
await page.waitForTimeout(parseInt(durationMs) + 500);
await page.close();
await context.close();
await browser.close();
