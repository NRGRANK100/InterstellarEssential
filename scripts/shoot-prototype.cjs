// Screenshots each .phone screen in /tmp/prototype.html using headless chrome.
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const SHELL = '/root/.cache/puppeteer/chrome-headless-shell/linux-131.0.6778.204/chrome-headless-shell-linux64/chrome-headless-shell';
const OUT = '/tmp/proto';
const IDS = ['welcome', 'tone', 'scan', 'results', 'recs'];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: SHELL,
    headless: 'shell',
    args: ['--no-sandbox', '--force-device-scale-factor=2', '--hide-scrollbars'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1000, deviceScaleFactor: 2 });
  await page.goto('file:///tmp/prototype.html', { waitUntil: 'networkidle0' });

  for (const id of IDS) {
    const el = await page.$('#' + id);
    await el.screenshot({ path: path.join(OUT, `${id}.png`) });
    console.log('shot', id);
  }
  await browser.close();
})();
