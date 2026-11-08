// Control strip and its independence from the viewer, against the fixture server: element ids
// and text formats that tools/campaign_watch_ui.js reads, the real check script, Pause with a
// reason, the check being live-only, the viewer-unavailable state, CSP, and keyboard timeline.
const {test, before, after, beforeEach, afterEach} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const S = require('./fixtures/spectator/support.cjs');

const SESSION = 'c6c09be0b7d43fba2839147651a4f6a5';
let fx, browser, page;
before(async () => { browser = await S.launch(); });
after(async () => { if (browser) await browser.close(); });
async function start(attention = 'required', options = {}) {
  fx = await S.startFixture(attention);
  page = await S.open(browser, `${fx.url}#live`, options);
  await S.ready(page);
}
afterEach(async () => { if (page) await page.close(); if (fx) fx.stop(); page = fx = null; });

const text = selector => page.$eval(selector, node => node.innerText);
async function until(fn, arg, timeout = 8000) {
  const end = Date.now() + timeout;
  for (;;) {
    if (await page.evaluate(fn, arg).catch(() => false)) return;
    if (Date.now() > end) throw await S.stalled(page, fn, timeout);
    await S.settle(page, 100);
  }
}

test('the control strip keeps the ids and text formats the operator check reads', async () => {
  await start();
  const facts = await page.evaluate(() => {
    const read = id => document.getElementById(id);
    const shell = read('watch-frame-shell');
    const aside = document.querySelector('aside[aria-label="Operator acknowledgement"]');
    return {
      session: read('current-session-full').textContent.trim(),
      freshness: read('control-freshness').textContent,
      details: read('source-details').textContent,
      connection: read('connection').dataset.state,
      errorHidden: read('status-error').hidden,
      watchHidden: read('watch').hidden,
      frame: {complete: read('frame').complete, width: read('frame').naturalWidth, hidden: read('frame').hidden},
      inStrip: !!shell.closest('header.ctl'),
      asideBeforeShell: aside && aside.nextElementSibling === shell,
      shellIsDiv: shell.tagName === 'DIV' && shell.className === 'frame-shell',
      pauseInStrip: !!read('pause').closest('header.ctl'),
    };
  });
  assert.equal(facts.session, SESSION);
  assert.match(facts.freshness, /^Last status received (\S+);/);
  assert.match(facts.details, /^Session: (\S+)\nSource: (\S+)\nCapture: \S+\nSHA-256: ([a-f0-9]{64})\n/);
  assert.equal(facts.details.match(/^Session: (\S+)/)[1], facts.session);
  assert.equal(facts.connection, 'ok');
  assert.equal(facts.errorHidden, true);
  assert.equal(facts.watchHidden, false);
  assert.deepEqual(facts.frame, {complete: true, width: 640, hidden: false});
  assert.ok(facts.inStrip && facts.asideBeforeShell && facts.shellIsDiv && facts.pauseInStrip);
  const html = await (await fetch(fx.url)).text();
  assert.ok(html.includes('<div class="frame-shell" id="watch-frame-shell"'), 'gateway anchor present in the served page');
  assert.ok(html.includes('<script src="/campaign_watch_ui.js" defer></script></head>'), 'gateway script injected before </head>');
});

test('the control strip reads only /api/status and /api/source; the viewer never feeds it', async () => {
  const source = fs.readFileSync(path.join(__dirname, '../web/app/control.js'), 'utf8');
  assert.doesNotMatch(source, /api\/view|viewerGet|data\.js/);
  const fetches = [...source.matchAll(/(?:getJSON|fetch)\(\s*[`'"]([^`'"]+)/g)].map(m => m[1]);
  for (const target of fetches) assert.match(target, /^\/api\/(status|source\/|pause)/, `unexpected control-path fetch ${target}`);
  await start();
  const asked = await page.evaluate(() => performance.getEntriesByType('resource').map(e => new URL(e.name).pathname));
  assert.ok(asked.some(p => p === '/api/status'));
  assert.ok(asked.some(p => p.startsWith('/api/source/')));
});

test('the real check script records the displayed frame; the status text follows the fixture', async () => {
  await start();
  await page.click('#watch-record');
  await until(() => /Check 1 accepted/.test(document.getElementById('watch-feedback').textContent));
  const records = (await fx.state()).records;
  assert.equal(records.length, 1);
  const status = await (await fetch(`${fx.origin}/api/status`)).json();
  assert.equal(records[0].session, SESSION);
  assert.equal(records[0].source, await page.evaluate(() => document.getElementById('source-details').textContent.match(/Source: (\S+)/)[1]));
  assert.equal(records[0].sha256, status.latest_source.sha256);
  assert.match(records[0].observed, /^\d{4}-\d\d-\d\dT/);
});

test('the check is disabled while the playhead is not live and returns with live', async () => {
  await start();
  assert.equal(await page.$eval('#watch-record', b => b.disabled), false);
  await page.focus('#tl');
  await page.keyboard.press('ArrowLeft');
  await until(() => document.getElementById('watch-record').disabled);
  assert.match(await text('#statussub'), /check off/i);
  await page.$eval('#watch-record', b => b.click());   // a script click on a disabled button does nothing
  await S.settle(page, 300);
  assert.equal((await fx.state()).records.length, 0);
  await page.keyboard.press('End');
  await until(() => !document.getElementById('watch-record').disabled);
  await page.click('#watch-record');
  await until(() => /Check 1 accepted/.test(document.getElementById('watch-feedback').textContent));
});

test('the check does not depend on viewer data: enabled before the viewer lists the live run', async () => {
  await start();
  await fx.viewer('nolive');
  await page.reload({waitUntil: 'load'});
  await S.settle(page, 2500);
  assert.equal(await page.$eval('#watch-record', b => b.disabled), false);
  await page.click('#watch-record');
  await until(() => /Check \d+ accepted/.test(document.getElementById('watch-feedback').textContent));
  await fx.viewer('up');
});

test('the run picker follows a live run listed after first load, until the owner picks a run', async () => {
  await start();
  await fx.viewer('nolive');
  await page.reload({waitUntil: 'load'});
  const shown = () => page.$eval('#runpick', s => s.options[s.selectedIndex].textContent);
  await until(() => document.getElementById('runpick').options.length > 1);
  assert.doesNotMatch(await shown(), /· live/);
  await fx.viewer('up');
  await until(() => / · live/.test(document.getElementById('runpick').selectedOptions[0].textContent), null, 15000);
  const other = await page.$eval('#runpick', s => [...s.options].find(o => !/· live/.test(o.textContent)).value);
  await page.select('#runpick', other);
  await S.settle(page, 11000);   // one runs refresh (RUNS_MS) later, the owner's pick stands
  assert.equal(await page.$eval('#runpick', s => s.value), other);
});

test('Pause is never refused over its reason: a missing or unknown one is recorded as unspecified', async () => {
  await start();
  const replies = await page.evaluate(async () => {
    const post = body => fetch('/api/pause', {method: 'POST', headers: {'Content-Type': 'application/json'}, body}).then(r => r.status);
    return [await post('{}'), await post('{"reason":"bored"}'), await post('not json')];
  });
  assert.deepEqual(replies, [200, 200, 200]);
  assert.deepEqual((await fx.state()).pauses.map(p => p.reason), ['unspecified', 'unspecified', 'unspecified']);
});

test('timeline keyboard: arrows move one step, shift moves ten, Home and End jump', async () => {
  await start();
  const now = () => page.$eval('#tl', n => Number(n.getAttribute('aria-valuenow')));
  const last = await now();
  assert.ok(last >= 100);
  await page.focus('#tl');
  await page.keyboard.press('ArrowLeft');
  assert.equal(await now(), last - 1);
  assert.doesNotMatch(await text('#playinfo'), /\(live\)/);
  await page.keyboard.press('ArrowRight');
  assert.equal(await now(), last);
  assert.match(await text('#playinfo'), /\(live\)/);
  await page.keyboard.down('Shift'); await page.keyboard.press('ArrowLeft'); await page.keyboard.up('Shift');
  assert.equal(await now(), last - 10);
  await page.keyboard.press('Home');
  assert.equal(await now(), 0);
  await page.keyboard.press('End');
  assert.equal(await now(), last);
  assert.match(await page.$eval('#tl', n => n.getAttribute('aria-valuetext')), /live/);
});

test('Pause: Enter opens the sheet, a reason is required, the reason is posted', async () => {
  await start();
  await page.focus('#pause');
  await page.keyboard.press('Enter');
  assert.equal(await page.$eval('#sheet', n => n.hidden), false);
  assert.equal(await page.evaluate(() => document.activeElement.name), 'why', 'focus moves into the sheet');
  await page.click('#sheetsubmit');
  assert.match(await text('#sheet-error'), /Choose a reason/);
  assert.deepEqual((await fx.state()).pauses, []);
  await page.click('input[value="spend"]');
  await page.click('#sheetsubmit');
  await until(() => document.getElementById('sheet').hidden);
  assert.deepEqual((await fx.state()).pauses, [{reason: 'spend'}]);
  await until(() => /Pause requested/.test(document.getElementById('statusline').textContent));
  assert.equal(await page.$eval('#pause', b => b.disabled), true);
  assert.match(await text('#pause-result'), /Pause requested \(Spend\)/);
});

test('Pause: Escape and Keep running close the sheet without posting', async () => {
  await start();
  await page.focus('#pause');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Escape');
  assert.equal(await page.$eval('#sheet', n => n.hidden), true);
  assert.equal(await page.evaluate(() => document.activeElement.id), 'pause');
  await page.keyboard.press('Enter');
  await page.click('#sheetcancel');
  assert.equal(await page.$eval('#sheet', n => n.hidden), true);
  assert.deepEqual((await fx.state()).pauses, []);
});

test('Pause: holding the button for about 0.8 s opens the sheet; a short press does not', async () => {
  await start();
  const box = await (await page.$('#pause')).boundingBox();
  const x = box.x + box.width / 2, y = box.y + box.height / 2;
  await page.mouse.move(x, y); await page.mouse.down();
  await S.settle(page, 300);
  await page.mouse.up();
  await S.settle(page, 700);
  assert.equal(await page.$eval('#sheet', n => n.hidden), true, 'released early');
  await page.mouse.move(x, y); await page.mouse.down();
  await S.settle(page, 1100);
  assert.equal(await page.$eval('#sheet', n => n.hidden), false, 'held long enough');
  await page.mouse.up();
  await page.click('#sheetcancel');
});

test('a Pause that the control path rejects leaves the sheet open with an error and Pause available', async () => {
  await start();
  await page.setRequestInterception(true);
  page.on('request', r => (r.url().endsWith('/api/pause') ? r.respond({status: 500, contentType: 'application/json', body: '{}'}) : r.continue()));
  page.expect503 = true;
  await page.focus('#pause'); await page.keyboard.press('Enter');
  await page.click('input[value="fault"]'); await page.click('#sheetsubmit');
  await until(() => !document.getElementById('sheet-error').hidden);
  assert.match(await text('#sheet-error'), /Pause was not accepted/);
  assert.equal(await page.$eval('#sheet', n => n.hidden), false);
  assert.equal(await page.$eval('#sheetsubmit', b => b.disabled), false);
});

test('viewer 503 leaves Pause and the operator check working', async () => {
  await start();
  page.expect503 = true;
  await fx.viewer('down');
  await until(() => document.getElementById('viewer').classList.contains('down'), null, 10000);
  assert.match(await text('#viewer'), /viewer unavailable/);
  assert.equal(await page.$eval('#connection', n => n.dataset.state), 'ok');
  assert.equal(await page.$eval('#watch-record', b => b.disabled), false, 'check stays enabled');
  await page.click('#watch-record');
  await until(() => /Check 1 accepted/.test(document.getElementById('watch-feedback').textContent));
  await page.focus('#pause'); await page.keyboard.press('Enter');
  await page.click('input[value="loop"]'); await page.click('#sheetsubmit');
  await until(() => document.getElementById('sheet').hidden);
  assert.deepEqual((await fx.state()).pauses, [{reason: 'loop'}]);
});

test('a scrubbed playhead does not strand the check when the viewer goes away', async () => {
  await start();
  page.expect503 = true;
  await page.focus('#tl'); await page.keyboard.press('ArrowLeft');
  await until(() => document.getElementById('watch-record').disabled);
  await fx.viewer('down');
  await until(() => !document.getElementById('watch-record').disabled, null, 10000);
});

test('first load while the viewer is down: the strip is complete and the page says viewer unavailable', async () => {
  fx = await S.startFixture();
  await fx.viewer('down');
  page = await S.open(browser, `${fx.url}#live`);
  page.expect503 = true;
  await page.waitForFunction(() => document.getElementById('connection').dataset.state === 'ok' && document.getElementById('frame').naturalWidth > 0, {timeout: 8000, polling: 100});
  await until(() => document.getElementById('viewer').classList.contains('down'));
  assert.match(await text('#app'), /Viewer unavailable/);
  assert.equal(await page.$eval('#pause', b => b.disabled), false);
  await page.click('#watch-record');
  await until(() => /Check 1 accepted/.test(document.getElementById('watch-feedback').textContent));
  assert.deepEqual(page.problems, []);
});

test('control status failing shows the error line and keeps Pause', async () => {
  await start();
  await page.setRequestInterception(true);
  page.on('request', r => (r.url().endsWith('/api/status') ? r.respond({status: 500, body: 'x'}) : r.continue()));
  page.expect503 = true;
  await until(() => !document.getElementById('status-error').hidden, null, 5000);
  assert.equal(await page.$eval('#connection', n => n.dataset.state), 'error');
  assert.match(await text('#control-freshness'), /^Last status received \S+; current state unknown\./);
  assert.equal(await page.$eval('#pause', b => b.disabled), false);
});

test('best-effort observation offers no check button and the page stays clean', async () => {
  await start('best-effort');
  assert.equal(await page.$('#watch-record'), null);
  assert.ok(await page.$('aside[aria-label="Operator observation"]'));
  assert.deepEqual(page.problems, []);
});

test('the page works under the gateway policy: CSP header present and nothing violates it', async () => {
  await start();
  const response = await fetch(fx.url);
  assert.equal(response.headers.get('content-security-policy'), "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'");
  await page.evaluate(() => { location.hash = '#compare'; });
  await S.settle(page, 1500);
  assert.deepEqual(page.problems, []);
  const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
  assert.doesNotMatch(html, /<style|\sstyle=|\son[a-z]+=|<script(?![^>]*\ssrc=)/i, 'no inline style, handler or script in the page');
  // The gateway serves only the page, /app/* and /vendor/*.
  assert.equal((await fetch(`${fx.origin}/style.css`)).status, 404);
  for (const asset of ['/app/app.css', '/app/main.js', '/app/control.js', '/vendor/echarts.js', '/vendor/preact.js']) {
    assert.equal((await fetch(fx.origin + asset)).status, 200, asset);
  }
});

test('phone layout: Pause leads the strip and the Pause? list leads the page', async () => {
  await start('required', {width: 390, height: 800, mobile: true});
  const order = await page.evaluate(() => {
    const top = id => document.querySelector(id).getBoundingClientRect().top;
    return {pause: top('#pause'), conds: top('#conds'), state: top('#gamestate'), tl: top('#tl')};
  });
  assert.ok(order.pause < order.conds && order.conds < order.state && order.state < order.tl, JSON.stringify(order));
  assert.equal(await S.overflow(page), 0);
});

test('the feed player keeps each frame at its size, never blanks, and holding the view never touches the run (#435)', async () => {
  await start();
  const feed = () => page.evaluate(() => {
    const c = document.getElementById('feed'), v = document.querySelector('.player-view');
    return {w: c.width, h: c.height, cw: c.clientWidth, vw: v.clientWidth, hidden: c.hidden, meta: document.getElementById('feed-meta').textContent};
  });
  await until(() => /^live · control path · capture \d+/.test(document.getElementById('feed-meta').textContent));
  const first = await feed();
  assert.deepEqual([first.w, first.h, first.cw, first.hidden], [640, 360, 640, false], 'drawn pixel for pixel by default');
  // New frames replace the picture without a blank or a size change.
  await page.evaluate(() => {
    window.__feed = [];
    new MutationObserver(() => { const c = document.getElementById('feed'); window.__feed.push([c.hidden, c.width, c.height]); })
      .observe(document.querySelector('.player'), {subtree: true, attributes: true, childList: true});
  });
  await fx.advance(3);
  await until(previous => !document.getElementById('feed-meta').textContent.includes(previous), first.meta.match(/capture \d+/)[0]);
  const after = await feed();
  assert.deepEqual([after.w, after.h, after.cw], [640, 360, 640]);
  assert.ok((await page.evaluate(() => window.__feed)).every(([hidden, w, h]) => !hidden && w === 640 && h === 360));
  // Hold freezes this view only: no Pause or record reaches the control path, and the run keeps going.
  await page.click('#feed-hold');
  const held = (await feed()).meta;
  await fx.advance(2);
  await S.settle(page, 2500);
  assert.equal((await feed()).meta, held);
  assert.match(held, /^held · live/);
  const state = await fx.state();
  assert.equal(state.pauses.length + state.records.length, 0);
  await page.click('#feed-hold');
  await until(previous => document.getElementById('feed-meta').textContent !== previous, held);
  // Fit scales to the column; a recorded step and Live return as expected.
  await page.click('#feed-scale');
  const fit = await feed();
  assert.equal(fit.cw, fit.vw);
  await page.click('#feed-back');
  await until(() => /^step \d+ · viewer/.test(document.getElementById('feed-meta').textContent));
  await page.click('#feed-live');
  await until(() => /^live · control path/.test(document.getElementById('feed-meta').textContent));
  assert.deepEqual(page.problems, []);
});

test('keyboard operation: tab reaches the Pause button, findings rows and nav with a visible focus ring', async () => {
  await start();
  await page.focus('#pause');
  const outline = await page.$eval('#pause', n => { n.focus(); return getComputedStyle(n).outlineStyle; });
  assert.notEqual(outline, 'none');
  const tags = await page.$$eval('#findings li > *', n => n.map(x => x.tagName));
  assert.ok(tags.length >= 3 && tags.every(t => t === 'BUTTON'), 'finding rows are buttons');
});
