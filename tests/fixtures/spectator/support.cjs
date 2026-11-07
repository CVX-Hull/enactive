// Shared test support: start the fixture server, drive the page with puppeteer, collect console errors.
const {spawn} = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

const SERVER = path.join(__dirname, 'server.py');
// Screenshots stay project-local and git-ignored unless SPECTATOR_SHOTS names another directory.
const SHOTS = process.env.SPECTATOR_SHOTS || path.join(__dirname, '..', '..', '..', '.runtime', 'spectator-shots');

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
/** The error for a wait that ran out, with what the page had recorded, so a failure under load is diagnosable (#421). */
async function stalled(page, fn, timeout) {
  const state = await page.evaluate(() => ({ready: document.readyState, app: (document.getElementById('app') || {}).childElementCount}))
    .catch(error => ({unreadable: error.message}));
  return new Error(`condition not met in ${timeout} ms: ${fn}\npage: ${JSON.stringify(state)}\n`
    + `problems: ${JSON.stringify(page.problems || [])}`);
}
/** Poll a predicate in the page. (page.waitForFunction proved unreliable for this page's predicates.) */
async function until(page, fn, arg, timeout = 10000) {
  const end = Date.now() + timeout;
  for (;;) {
    if (await page.evaluate(fn, arg).catch(() => false)) return;
    if (Date.now() > end) throw await stalled(page, fn, timeout);
    await settle(page, 100);
  }
}
async function ready(page) {
  await until(page, () => document.getElementById('connection') && document.getElementById('connection').dataset.state === 'ok'
    && document.getElementById('frame') && !document.getElementById('frame').hidden && document.getElementById('frame').naturalWidth > 0);
  await until(page, () => document.querySelector('#app .panel, #app .insuf'));
  const hash = new URL(page.url()).hash;
  if (hash === '' || hash === '#live') await until(page, () => document.querySelector('#conds li, #pauseanswer') && document.querySelector('#tl canvas'));
}
async function overflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

module.exports = {startFixture, launch, open, shot, settle, ready, until, stalled, overflow, SHOTS};
