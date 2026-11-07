// Shared test support: start the fixture server, drive the page with puppeteer, collect console errors.
const {spawn} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const SERVER = path.join(__dirname, 'server.py');
const SHOTS = process.env.SPECTATOR_SHOTS || '/private/tmp/claude-501/-Users-shilongdai-Developer-CDDA-Player/67f32725-983a-4997-a335-17325909c74b/scratchpad/web-shots';

function startFixture(attention = 'required') {
  return new Promise((resolve, reject) => {
    const child = spawn(process.env.PYTHON || 'python3', ['-I', SERVER, '--attention', attention], {stdio: ['ignore', 'pipe', 'inherit']});
    let buffer = '';
    const timer = setTimeout(() => { child.kill(); reject(new Error('fixture server did not start')); }, 8000);
    child.stdout.on('data', chunk => {
      buffer += chunk;
      const line = buffer.split('\n')[0];
      if (!buffer.includes('\n')) return;
      clearTimeout(timer);
      const {url} = JSON.parse(line);
      const origin = url.replace(/\/$/, '');
      const post = (route) => fetch(origin + route, {method: 'POST'}).then(r => r.json());
      resolve({url, origin, stop: () => child.kill(),
        state: () => fetch(origin + '/__fixture/state').then(r => r.json()),
        viewer: mode => post(`/__fixture/viewer?mode=${mode}`), advance: n => post(`/__fixture/advance?n=${n}`)});
    });
    child.on('exit', code => { clearTimeout(timer); reject(new Error(`fixture server exited early (${code})`)); });
  });
}

async function launch() {
  const puppeteer = require('puppeteer');
  return puppeteer.launch({headless: true, args: ['--no-sandbox']});
}

/** Open a page, recording console errors, page errors and failed same-origin requests (except expected 503s). */
async function open(browser, url, {width = 1280, height = 900, scheme = 'light', mobile = false} = {}) {
  const page = await browser.newPage();
  await page.setViewport({width, height, deviceScaleFactor: 1, isMobile: mobile, hasTouch: mobile});
  await page.emulateMediaFeatures([{name: 'prefers-color-scheme', value: scheme}]);
  const problems = [];
  // The gateway's policy has no 'unsafe-inline': any violation is a test failure.
  await page.evaluateOnNewDocument(() => document.addEventListener('securitypolicyviolation',
    e => console.error(`CSP violation: ${e.violatedDirective} ${e.blockedURI}`)));
  // A failed HTTP load is reported twice (console and response); keep the response, which names the URL.
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) problems.push(`console: ${m.text()}`); });
  page.on('pageerror', e => problems.push(`pageerror: ${e.message}`));
  page.on('requestfailed', r => problems.push(`requestfailed: ${r.url()} ${r.failure() && r.failure().errorText}`));
  page.expect503 = false;     // set while a test deliberately turns the viewer off
  page.on('response', r => {
    const url = new URL(r.url());
    if (r.status() < 400 || url.pathname === '/favicon.ico') return;
    if (r.status() === 503 && page.expect503 && url.pathname.startsWith('/api/view/')) return;
    problems.push(`http ${r.status()}: ${url.pathname}`);
  });
  page.problems = problems;
  await page.goto(url, {waitUntil: 'load'});
  return page;
}

async function shot(page, name) {
  fs.mkdirSync(SHOTS, {recursive: true});
  await page.screenshot({path: path.join(SHOTS, `${name}.png`), fullPage: true});
}

const settle = (page, ms = 400) => new Promise(r => setTimeout(r, ms));
async function ready(page) {
  await page.waitForSelector('#statusline', {timeout: 8000, polling: 100});
  await page.waitForFunction(() => document.getElementById('connection').dataset.state === 'ok'
    && document.getElementById('frame') && !document.getElementById('frame').hidden && document.getElementById('frame').naturalWidth > 0, {timeout: 8000, polling: 100});
  await page.waitForFunction(() => document.querySelector('#app .panel, #app .insuf'), {timeout: 8000, polling: 100});
  const hash = new URL(page.url()).hash;
  if (hash === '' || hash === '#live') await page.waitForSelector('#conds li, #tl canvas', {timeout: 8000});
  if (hash === '' || hash === '#live') await page.waitForSelector('#tl canvas', {timeout: 8000});
}
async function overflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

module.exports = {startFixture, launch, open, shot, settle, ready, overflow, SHOTS};
