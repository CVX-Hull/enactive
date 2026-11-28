// Mission Control bar (the control path) and its independence from the viewer, against the fixture server: element
// ids and text formats of the strip, its frame, Pause with a reason, the viewer-unavailable state, CSP, and the
// keyboard timeline.
const {test, before, after, beforeEach, afterEach} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const S = require('./fixtures/spectator/support.cjs');

const SESSION = 'c6c09be0b7d43fba2839147651a4f6a5';
let fx, browser, page;
before(async () => { browser = await S.launch(); });
after(async () => { if (browser) await browser.close(); });
async function start(options = {}) {
  fx = await S.startFixture();
  page = await S.open(browser, `${fx.url}#watch`, options);
  await S.ready(page);
}
/** How the strip shows the control path's own frame: out of the way, small, or in full. */
const stripFrame = () => page.evaluate(() => {
  const box = document.querySelector('.ctl-frame'), img = document.getElementById('frame');
  return {visible: getComputedStyle(box).visibility === 'visible', width: document.querySelector('.frame-shell').offsetWidth, hidden: img.hidden, natural: img.naturalWidth};
});
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

test('the control strip shows the session, status freshness, source details and a decoded frame', async () => {
  await start();
  const facts = await page.evaluate(() => {
    const read = id => document.getElementById(id);
    const shell = read('frame').parentElement;
    return {
      session: read('current-session-full').textContent.trim(),
      freshness: read('control-freshness').textContent,
      details: read('source-details').textContent,
      connection: read('connection').dataset.state,
      errorHidden: read('status-error').hidden,
      watchHidden: read('watch').hidden,
      frame: {complete: read('frame').complete, width: read('frame').naturalWidth, hidden: read('frame').hidden},
      inStrip: !!shell.closest('header.ctl'),
      noCheckPanel: !document.querySelector('header.ctl aside, #watch-record'),
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
  assert.ok(facts.inStrip && facts.noCheckPanel && facts.shellIsDiv && facts.pauseInStrip);
  const html = await (await fetch(fx.url)).text();
  assert.equal(html, fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8'), 'the page is served unchanged');
  assert.deepEqual(page.problems, []);
});

test('the strip\'s own frame steps aside only while Watch shows the same live frame, and returns whenever it does not', async () => {
  await start({width: 1440});
  await until(() => document.documentElement.dataset.watchStage === 'ok');
  assert.deepEqual(await stripFrame(), {visible: false, width: 63, hidden: false, natural: 640});
  // Its details stay one click away.
  await page.click('.src-details summary');
  assert.equal(await page.$eval('.src-panel', n => n.offsetHeight > 0), true);
  assert.match(await text('#source-details'), /^Session: /);
  await page.click('.src-details summary');
  // In history, on a held view, on another tab and on another run the live frame is nowhere else, so the strip shows it small.
  const peek = async why => { await until(() => document.documentElement.dataset.watchStage === undefined); const f = await stripFrame(); assert.deepEqual([f.visible, f.hidden, f.natural], [true, false, 640], why); assert.ok(f.width > 0 && f.width < 100, why); };
  const back = () => until(() => document.documentElement.dataset.watchStage === 'ok');
  await page.click('#feed-back'); await peek('history');
  await page.click('#backlive'); await back();
  await page.click('#feed-hold'); await peek('held');
  await page.click('#feed-hold'); await back();
  for (const tab of ['memory', 'curator', 'diagnostics']) {
    await page.click(`[data-nav="${tab}"]`); await peek(`the ${tab} tab`);
    await page.click('[data-nav="watch"]'); await back();
  }
  await page.click('#all-runs-btn'); await peek('All runs');
  await page.click('[data-nav="watch"]'); await back();
  await S.pick(page, 'aidA1'); await peek('another run');
  await S.pick(page, 'ceil09'); await back();
  // Without the viewer it is shown in full at once, still decoded.
  page.expect503 = true;
  await fx.viewer('down');
  await until(() => document.documentElement.dataset.viewer === 'down', null, 10000);
  const full = await stripFrame();
  assert.deepEqual([full.visible, full.width, full.hidden, full.natural], [true, 300, false, 640]);
  await fx.viewer('up');
  await until(() => document.documentElement.dataset.watchStage === 'ok', null, 12000);
});

test('the strip\'s own frame is in view while Watch still decodes a newer capture, and stays so when that fails', async () => {
  await start({width: 1440});
  // Watch decodes each capture after the control path has: the second decode of one URL is Watch's, held or refused here.
  await page.evaluate(() => {
    const real = HTMLImageElement.prototype.decode, seen = new Map();
    window.__watchDecode = 'run'; window.__release = null;
    HTMLImageElement.prototype.decode = function () {
      const n = (seen.get(this.src) || 0) + 1;
      seen.set(this.src, n);
      if (n < 2 || window.__watchDecode === 'run') return real.call(this);
      if (window.__watchDecode === 'fail') return Promise.reject(new DOMException('refused by the test', 'EncodingError'));
      return new Promise(resolve => { window.__release = () => resolve(real.call(this)); });
    };
  });
  const stage = () => until(() => document.documentElement.dataset.watchStage === 'ok' && getComputedStyle(document.querySelector('.ctl-frame')).visibility === 'hidden');
  const look = () => page.evaluate(() => ({stage: document.documentElement.dataset.watchStage, feed: Number(document.getElementById('feed-meta').textContent.match(/capture (\d+)/)[1]),
    strip: Number(document.getElementById('source-details').textContent.match(/Capture: (\d+)/)[1]), seen: getComputedStyle(document.querySelector('.ctl-frame')).visibility,
    hidden: document.getElementById('frame').hidden, left: document.getElementById('statusline').getBoundingClientRect().left}));
  const newer = async () => { const was = (await look()).strip; await fx.advance(1); await until(n => Number(document.getElementById('source-details').textContent.match(/Capture: (\d+)/)[1]) > n, was); };
  await stage();
  const first = await look();
  assert.equal(first.feed, first.strip);
  // Delayed: Watch still shows the earlier capture, so the control path's newer one is in view until Watch has painted it.
  await page.evaluate(() => { window.__watchDecode = 'delay'; });
  await newer();
  await until(() => !!window.__release);
  const delayed = await look();
  assert.deepEqual([delayed.stage, delayed.feed, delayed.strip, delayed.seen, delayed.hidden], [undefined, first.feed, first.strip + 1, 'visible', false]);
  assert.equal(delayed.left, first.left, 'its return moves nothing');
  await S.settle(page, 2500);   // and a poll later it is still there
  assert.deepEqual([(await look()).stage, (await look()).seen], [undefined, 'visible']);
  await page.evaluate(() => { window.__watchDecode = 'run'; window.__release(); });
  await stage();
  assert.equal((await look()).feed, first.strip + 1);
  // Failed: Watch keeps its last good frame, which is no longer the live one.
  await page.evaluate(() => { window.__watchDecode = 'fail'; });
  await newer();
  await S.settle(page, 2500);
  const failed = await look();
  assert.deepEqual([failed.stage, failed.feed, failed.strip, failed.seen, failed.hidden], [undefined, first.strip + 1, first.strip + 2, 'visible', false]);
  await page.evaluate(() => { window.__watchDecode = 'run'; });
  await newer();
  await stage();
  assert.equal((await look()).feed, first.strip + 3);
  assert.deepEqual(page.problems, []);
});

test('the strip\'s frame comes back when the control path moves to another session', async () => {
  await start({width: 1440});
  await until(() => document.documentElement.dataset.watchStage === 'ok');
  await page.evaluate(() => document.dispatchEvent(new CustomEvent('enactive:control', {detail: {ok: true, status: {session: 'another'}}})));
  assert.equal(await page.evaluate(() => new Promise(r => requestAnimationFrame(() => setTimeout(() => r(document.documentElement.dataset.watchStage ?? null), 50)))), null);
  await until(() => document.documentElement.dataset.watchStage === 'ok');   // the next status is the real session's again
});

test('Pause repeats only the facts of the run it would end, never those of the run being looked at', async () => {
  await start();
  const sheetFacts = async () => {
    await page.focus('#pause'); await page.keyboard.press('Enter');
    const words = await text('#sheetfacts');
    await page.keyboard.press('Escape');
    return words;
  };
  await until(() => document.getElementById('pill-spend'));
  assert.match(await sheetFacts(), /^Session c6c09be0…\. Decision \d+, \$\d\.\d\d spent \(provider-reported\)\. Pause permanently ends this run/);
  await S.pick(page, 'aidA1');
  await until(async session => { const {store} = await import('/app/data.js'); return store.summary && store.summary.session === session; }, S.SESSIONS.aidA1);
  await S.settle(page, 2500);
  assert.match(await text('#viewer-facts'), /not the live run/i);
  const archived = await sheetFacts();
  assert.match(archived, /^Session c6c09be0…\.\s+Pause permanently ends this run/);
  assert.doesNotMatch(archived, /Decision|\$/);
  await S.pick(page, 'ceil09');
  await until(async session => { const {store} = await import('/app/data.js'); return store.summary && store.summary.session === session; }, S.SESSIONS.ceil09);
  assert.match(await sheetFacts(), /Decision \d+, \$\d\.\d\d spent \(provider-reported\)/);
  assert.deepEqual((await fx.state()).pauses, []);
});

test('without the viewer page at all, the strip shows its frame in full, its status and Pause', async () => {
  fx = await S.startFixture();
  page = await browser.newPage();
  await page.setRequestInterception(true);
  page.on('request', r => (/\/app\/main\.js$/.test(r.url()) ? r.abort() : r.continue()));
  await page.setViewport({width: 1280, height: 900});
  await page.goto(fx.url, {waitUntil: 'load'});
  await until(() => document.getElementById('connection').dataset.state === 'ok' && document.getElementById('frame').naturalWidth > 0);
  const frame = await stripFrame();
  assert.deepEqual([frame.visible, frame.width, frame.hidden], [true, 300, false]);
  assert.match(await text('#statusline'), /^Running · session /);
  await page.focus('#pause'); await page.keyboard.press('Enter');
  await page.click('input[value="fault"]'); await page.click('#sheetsubmit');
  await until(() => document.getElementById('sheet').hidden);
  assert.deepEqual((await fx.state()).pauses, [{reason: 'fault'}]);
});

test('the control strip reads only /api/status and /api/source; the viewer never feeds it', async () => {
  const source = fs.readFileSync(path.join(__dirname, '../web/app/control.js'), 'utf8');
  assert.doesNotMatch(source, /api\/view|viewerGet|data\.js|^import /m);
  const fetches = [...source.matchAll(/(?:getJSON|fetch)\(\s*[`'"]([^`'"]+)/g)].map(m => m[1]);
  for (const target of fetches) assert.match(target, /^\/api\/(status|source\/|pause)/, `unexpected control-path fetch ${target}`);
  await start();
  const asked = await page.evaluate(() => performance.getEntriesByType('resource').map(e => new URL(e.name).pathname));
  assert.ok(asked.some(p => p === '/api/status'));
  assert.ok(asked.some(p => p.startsWith('/api/source/')));
});

test('the strip shows the source the status names; moving the playhead leaves the strip and Pause alone', async () => {
  await start();
  const status = await (await fetch(`${fx.origin}/api/status`)).json();
  const details = await page.evaluate(() => document.getElementById('source-details').textContent);
  assert.match(details, new RegExp(`^Session: ${SESSION}\\nSource: ${SESSION}-\\d+\\n`));
  assert.equal(details.match(/SHA-256: ([a-f0-9]{64})/)[1], status.latest_source.sha256);
  await page.focus('#tl');
  await page.keyboard.press('ArrowLeft');
  await until(() => !/\(live\)/.test(document.getElementById('playinfo').textContent));
  assert.equal(await page.$eval('#pause', b => b.disabled), false);
  assert.equal(await page.$eval('#connection', n => n.dataset.state), 'ok');
  assert.doesNotMatch(await text('#statussub'), /check/i);
  assert.deepEqual((await fx.state()).pauses, []);
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

for (const mode of ['live', 'recorded']) {
  test(`timeline keyboard and accessible name survive a redraw: ${mode}`, async () => {
    if (mode === 'live') {
      await start();
    } else {
      fx = await S.startFixture();
      await fx.viewer('nolive');
      page = await S.open(browser, `${fx.url}recorded/#watch`);
      await until(() => document.querySelector('#tl') && document.querySelector('#story .card'));
    }

    const cdp = await page.createCDPSession();
    try {
      const {root} = await cdp.send('DOM.getDocument');
      const {nodeId} = await cdp.send('DOM.querySelector', {nodeId: root.nodeId, selector: '#tl'});
      const checkAccessibility = async (edge) => {
        const {nodes: [control]} = await cdp.send('Accessibility.getPartialAXTree', {nodeId, fetchRelatives: false});
        assert.equal(control.role.value, 'slider');
        assert.equal(control.name.value, 'Timeline playhead');
        assert.equal(control.description.value,
          `Left and right arrows move one step. Hold Shift to move ten. Home goes to the first step. End goes to ${edge}.`);
      };
      const edge = mode === 'live' ? 'the live edge' : 'the latest recorded step';
      await checkAccessibility(edge);
      const now = () => page.$eval('#tl', n => Number(n.getAttribute('aria-valuenow')));
      const last = await now();
      assert.ok(last >= 100);
      await page.focus('#tl');
      await page.keyboard.press('ArrowLeft');
      assert.equal(await now(), last - 1);
      assert.doesNotMatch(await text('#playinfo'), /\(live\)/);
      await page.keyboard.press('ArrowRight');
      assert.equal(await now(), last);
      assert.equal(/\(live\)/.test(await text('#playinfo')), mode === 'live');
      await page.keyboard.down('Shift'); await page.keyboard.press('ArrowLeft'); await page.keyboard.up('Shift');
      assert.equal(await now(), last - 10);
      await page.keyboard.press('Home');
      assert.equal(await now(), 0);
      await page.keyboard.press('End');
      assert.equal(await now(), last);
      assert.equal(/live/.test(await page.$eval('#tl', n => n.getAttribute('aria-valuetext'))), mode === 'live');
      // Focus survives the redraws of a poll, and a pointer moves the same playhead.
      await S.settle(page, 2500);
      assert.equal(await page.evaluate(() => document.activeElement.id), 'tl');
      await checkAccessibility(edge);
      const box = await (await page.$('#tl')).boundingBox();
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      assert.ok(Math.abs(await now() - last / 2) <= 1);
      await page.focus('#tl');
      await page.keyboard.press('End');

      if (mode === 'live') {
        await S.pick(page, 'aidA1');
        await until(() => document.querySelector('#story-source') &&
          document.querySelector('#timeline-help')?.textContent.endsWith('the latest recorded step.'));
        const {nodeId: archivedId} = await cdp.send('DOM.querySelector', {nodeId: root.nodeId, selector: '#tl'});
        const {nodes: [archived]} = await cdp.send('Accessibility.getPartialAXTree', {nodeId: archivedId, fetchRelatives: false});
        assert.match(archived.description.value, /End goes to the latest recorded step/);
        assert.doesNotMatch(await text('#playinfo'), /\(live\)/);
      }
    } finally { await cdp.detach(); }
  });
}

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

test('viewer 503 leaves the control strip and Pause working', async () => {
  await start();
  page.expect503 = true;
  await fx.viewer('down');
  await until(() => document.getElementById('viewer').classList.contains('down'), null, 10000);
  assert.match(await text('#viewer'), /viewer unavailable/);
  assert.equal(await page.$eval('#connection', n => n.dataset.state), 'ok');
  await fx.advance(1);   // the strip keeps following new frames from the control path
  await until(capture => document.getElementById('source-details').textContent.includes(`Capture: ${capture}\n`),
    1000 + (await fx.state()).visible);
  await page.focus('#pause'); await page.keyboard.press('Enter');
  await page.click('input[value="loop"]'); await page.click('#sheetsubmit');
  await until(() => document.getElementById('sheet').hidden);
  assert.deepEqual((await fx.state()).pauses, [{reason: 'loop'}]);
});

test('first load while the viewer is down: the strip is complete and the page says viewer unavailable', async () => {
  fx = await S.startFixture();
  await fx.viewer('down');
  page = await S.open(browser, `${fx.url}#watch`);
  page.expect503 = true;
  await page.waitForFunction(() => document.getElementById('connection').dataset.state === 'ok' && document.getElementById('frame').naturalWidth > 0, {timeout: 8000, polling: 100});
  await until(() => document.getElementById('viewer').classList.contains('down'));
  assert.match(await text('#app'), /Viewer unavailable/);
  assert.equal(await page.$eval('#pause', b => b.disabled), false);
  assert.match(await page.$eval('#source-details', n => n.textContent), new RegExp(`^Session: ${SESSION}\\nSource: `));
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
  assert.ok(await page.$eval('#control-freshness', n => n.offsetHeight > 0), 'the age of the last status is in view');
  assert.equal(await page.$eval('#pause', b => b.disabled), false);
});

test('the page works under the gateway policy: CSP header present and nothing violates it', async () => {
  await start();
  const response = await fetch(fx.url);
  assert.equal(response.headers.get('content-security-policy'), "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'");
  for (const hash of ['#runs/compare', '#curator', '#memory']) { await page.evaluate(h => { location.hash = h; }, hash); await S.settle(page, 700); }
  await S.settle(page, 1500);
  assert.deepEqual(page.problems, []);
  const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
  assert.doesNotMatch(html, /<style|\sstyle=|\son[a-z]+=|<script(?![^>]*\ssrc=)/i, 'no inline style, handler or script in the page');
  // Every control-path element the vanilla control script drives is still in the page, and outside the viewer's mounts.
  for (const id of ['watch', 'frame', 'frame-note', 'statusline', 'statussub', 'control-freshness', 'status-error', 'pause-result', 'connection', 'current-session-full',
    'source-details', 'strip-viewer', 'theme', 'pause', 'fillbar', 'pause-hint', 'sheet', 'sheetform', 'sheet-title', 'sheetfacts', 'reasons', 'sheet-error', 'sheetcancel', 'sheetsubmit', 'app'])
    assert.match(html, new RegExp(`id="${id}"`), id);
  for (const klass of ['ctl-frame', 'frame-shell', 'src-details', 'src-panel']) assert.match(html, new RegExp(`class="${klass}"`), klass);
  assert.equal(html.match(/<!-- live only -->/g).length, html.match(/<!-- end live only -->/g).length);
  // The gateway serves only the page, /app/* and /vendor/*.
  assert.equal((await fetch(`${fx.origin}/style.css`)).status, 404);
  for (const asset of ['/app/app.css', '/app/main.js', '/app/control.js', '/vendor/echarts.js', '/vendor/preact.js']) {
    assert.equal((await fetch(fx.origin + asset)).status, 200, asset);
  }
});

test('phone layout: Pause leads the strip, then the stage, the timeline and the story', async () => {
  await start({width: 390, height: 800, mobile: true});
  const order = await page.evaluate(() => {
    const top = id => document.querySelector(id).getBoundingClientRect().top;
    return {pause: top('#pause'), status: top('#statusline'), stage: top('.player'), tl: top('#tl'), story: top('#story')};
  });
  assert.ok(order.pause < order.status && order.status < order.stage && order.stage < order.tl && order.tl < order.story, JSON.stringify(order));
  // A 640-pixel frame at 1:1 scrolls inside the player, never the page.
  await until(() => !document.getElementById('feed').hidden);
  await page.click('#feed-scale-1');
  await until(() => document.getElementById('feed').clientWidth === 640);
  assert.equal(await S.overflow(page), 0);
  await page.evaluate(() => localStorage.removeItem('feed-scale'));
});

test('the feed player keeps each frame at its size, never blanks, and holding the view never touches the run (#435)', async () => {
  await start();
  const feed = () => page.evaluate(() => {
    const c = document.getElementById('feed'), v = document.querySelector('.player-view');
    return {w: c.width, h: c.height, cw: c.clientWidth, vw: v.clientWidth, hidden: c.hidden, meta: document.getElementById('feed-meta').textContent};
  });
  await until(() => /^live · control path · capture \d+/.test(document.getElementById('feed-meta').textContent));
  const fitted = await feed();
  assert.deepEqual([fitted.cw, await page.$eval('#feed', c => getComputedStyle(c).objectFit)], [fitted.vw, 'contain'], 'fitted to the stage, undistorted, by default');
  await page.click('#feed-scale-1');
  await until(() => document.getElementById('feed').clientWidth === 640);
  const first = await feed();
  assert.deepEqual([first.w, first.h, first.cw, first.hidden], [640, 360, 640, false], 'drawn pixel for pixel at 1:1');
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
  // The canvas holds real pixels, not just a label.
  assert.ok(await page.evaluate(() => {
    const data = document.getElementById('feed').getContext('2d').getImageData(0, 0, 640, 360).data;
    for (let i = 3; i < data.length; i += 4) if (data[i] !== 0) return true;
    return false;
  }), 'the frame was drawn');
  // Hold freezes this view only: no Pause reaches the control path, and the run keeps going.
  await page.click('#feed-hold');
  const held = (await feed()).meta;
  await fx.advance(2);
  await S.settle(page, 2500);
  assert.equal((await feed()).meta, held);
  assert.match(held, /^held · live/);
  assert.equal((await fx.state()).pauses.length, 0);
  await page.click('#feed-hold');
  await until(previous => document.getElementById('feed-meta').textContent !== previous, held);
  // Fit scales to the column; a recorded step and Live return as expected.
  await page.click('#feed-scale-fit');
  const fit = await feed();
  assert.equal(fit.cw, fit.vw);
  // Stepping while held releases the hold and shows that step; forward moves on; Live returns.
  await page.click('#feed-hold');
  await page.click('#feed-back');
  await until(() => /^step \d+ at .* · viewer/.test(document.getElementById('feed-meta').textContent));
  assert.equal(await page.$eval('#feed-hold', b => b.getAttribute('aria-pressed')), 'false');
  const backAt = Number((await feed()).meta.match(/^step (\d+)/)[1]);
  await page.click('#feed-back');
  await until(seq => document.getElementById('feed-meta').textContent.startsWith(`step ${seq - 1} `), backAt);
  await page.click('#feed-forward');
  await until(seq => document.getElementById('feed-meta').textContent.startsWith(`step ${seq} `), backAt);
  await page.click('#backlive');
  await until(() => /^live · control path/.test(document.getElementById('feed-meta').textContent));
  // On a run that is not live there is nothing to return to, and the player shows that run's recorded frames.
  await S.pick(page, 'aidA1');
  await until(() => /^step \d+/.test(document.getElementById('feed-meta').textContent) && /RECORDED/.test(document.querySelector('.stagepill').textContent));
  assert.equal(await page.$('#backlive'), null);
  assert.deepEqual(page.problems, []);
  await page.evaluate(() => localStorage.removeItem('feed-scale'));
});

test('stream player: integer scales, wide layout, caption, liveness badges and shortcuts (#437)', async () => {
  await start();
  const q = () => page.evaluate(() => {
    const c = document.getElementById('feed');
    return {cw: c.clientWidth, hidden: c.hidden, scale: document.querySelector('.player').dataset.scale,
      wide: document.querySelector('.player').dataset.wide, beside: document.querySelector('.story').getBoundingClientRect().left >= document.querySelector('.player').getBoundingClientRect().right,
      caption: (document.getElementById('feed-caption') || {}).textContent || '', age: (document.getElementById('feed-age') || {}).textContent || '',
      behind: (document.getElementById('feed-behind') || {}).textContent || '', meta: document.getElementById('feed-meta').textContent};
  });
  await until(() => /^live · control path · capture/.test(document.getElementById('feed-meta').textContent));
  let s = await q();
  assert.match(s.caption, /^latest decision \d+ · .+ · .+ · keys /);
  assert.match(s.age, /^frame \d+ s old$/);
  const age = Number(s.age.match(/\d+/)[0]);
  await until(a => Number((document.getElementById('feed-age').textContent.match(/\d+/) || [0])[0]) >= a + 2, age, 6000);
  // A held frame keeps its caption while the run moves on.
  await page.click('#feed-hold');
  const heldCaption = (await q()).caption;
  await fx.advance(1);   // the fixture holds back four steps; this test uses all of them
  await until(() => /^1 step behind live$/.test((document.getElementById('feed-behind') || {}).textContent || ''));
  assert.equal((await q()).caption, heldCaption);
  await page.click('#feed-hold');
  await until(previous => document.getElementById('feed-caption').textContent !== previous, heldCaption);
  // Integer scales are exact multiples of the frame width; 1:1 is the frame itself.
  for (const [id, width] of [['#feed-scale-2', 1280], ['#feed-scale-3', 1920], ['#feed-scale-1', 640]]) {
    await page.click(id);
    await until(w => document.getElementById('feed').clientWidth === w, width);
  }
  // Wide gives the player the whole width with the story below it, without page overflow.
  assert.equal((await q()).beside, true);
  await page.click('#feed-wide');
  await until(() => document.querySelector('.player').dataset.wide === 'yes');
  s = await q();
  assert.deepEqual([s.wide, s.beside], ['yes', false]);
  assert.equal(await S.overflow(page), 0);
  // Behind live: hold, let the run move on, then jump back from the badge.
  await page.click('#feed-hold');
  await fx.advance(3);
  await until(() => /^3 steps behind live$/.test((document.getElementById('feed-behind') || {}).textContent || ''));
  await page.click('#feed-behind');
  await until(() => !document.getElementById('feed-behind') && document.getElementById('feed-hold').getAttribute('aria-pressed') === 'false');
  // Shortcuts act from the page body, never from a focused control or the open Pause sheet.
  const key = async k => { await page.evaluate(() => document.activeElement && document.activeElement.blur()); await page.keyboard.press(k); };
  await key('ArrowLeft');
  await until(() => /^step \d+/.test(document.getElementById('feed-meta').textContent));
  s = await q();
  assert.match(s.caption, /^decision \d+ · /);
  assert.match(s.behind, /^1 step behind live$/);
  await key('l');
  await until(() => /^live · control path/.test(document.getElementById('feed-meta').textContent));
  await key('2'); await until(() => document.querySelector('.player').dataset.scale === '2');
  await key('0'); await until(() => document.querySelector('.player').dataset.scale === 'fit');
  await key('t'); await until(() => document.querySelector('.player').dataset.wide === 'no');
  await key('Space'); await until(() => document.getElementById('feed-hold').getAttribute('aria-pressed') === 'true');
  await key('Space'); await until(() => document.getElementById('feed-hold').getAttribute('aria-pressed') === 'false');
  // After clicking a player button, arrows and letters still work; Space stays with the focused control.
  await page.click('#feed-back');
  await until(() => /^step \d+/.test(document.getElementById('feed-meta').textContent));
  const clicked = Number((await q()).meta.match(/^step (\d+)/)[1]);
  await page.keyboard.press('ArrowLeft');
  await until(seq => document.getElementById('feed-meta').textContent.startsWith(`step ${seq - 1} `), clicked);
  await page.focus('#feed-hold');
  await page.keyboard.press('t');
  await until(() => document.querySelector('.player').dataset.wide === 'yes');
  await page.keyboard.press('t');
  await until(() => document.querySelector('.player').dataset.wide === 'no');
  await page.focus('.player-bar details.keys summary');
  await page.keyboard.press('Space');
  await until(() => document.querySelector('.player-bar details.keys').open);
  assert.equal(await page.$eval('#feed-hold', b => b.getAttribute('aria-pressed')), 'false', 'Space on the shortcut list opens it');
  await page.keyboard.press('Space');
  await key('l');
  // Holding Space down toggles once.
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  await page.keyboard.down('Space');
  await page.evaluate(() => document.dispatchEvent(new KeyboardEvent('keydown', {key: ' ', repeat: true, bubbles: true})));
  await page.keyboard.up('Space');
  await until(() => document.getElementById('feed-hold').getAttribute('aria-pressed') === 'true');
  await key('Space');
  await until(() => document.getElementById('feed-hold').getAttribute('aria-pressed') === 'false');
  await page.focus('#tl');
  await page.keyboard.press('t');
  assert.equal((await q()).wide, 'no', 'the timeline keeps its keys');
  await page.focus('#pause');
  await page.keyboard.press('Enter');
  await until(() => !document.getElementById('sheet').hidden);
  await page.keyboard.press('t');
  assert.equal((await q()).wide, 'no', 'no shortcut while the Pause sheet is open');
  await page.keyboard.press('Escape');
  assert.equal((await fx.state()).pauses.length, 0);
  // The choices are remembered per browser.
  await page.click('#feed-scale-3');
  await page.reload();
  await S.ready(page);
  await until(() => document.querySelector('.player') && document.querySelector('.player').dataset.scale === '3');
  assert.deepEqual(page.problems, []);
  await page.evaluate(() => { localStorage.removeItem('feed-scale'); localStorage.removeItem('feed-wide'); });
});

test('stream player at phone width: wide and 3x scroll inside the player, never the page (#437)', async () => {
  await start({width: 390, height: 800, mobile: true});
  await until(() => !document.getElementById('feed').hidden);
  for (const id of ['#feed-wide', '#feed-scale-3']) await page.click(id);
  await until(() => document.getElementById('feed').clientWidth === 1920);
  assert.equal(await S.overflow(page), 0);
  await page.click('#feed-scale-fit');
  assert.equal(await S.overflow(page), 0);
  await page.evaluate(() => { localStorage.removeItem('feed-scale'); localStorage.removeItem('feed-wide'); });
});

test('a run whose live store was never finalized is labelled and not followed (#435)', async () => {
  fx = await S.startFixture();
  await fx.viewer('stale');
  page = await S.open(browser, `${fx.url}#watch`);
  await S.ready(page);
  await until(() => document.getElementById('runpick').selectedOptions[0]?.textContent.startsWith('ceil09'));
  const options = await page.$$eval('#runpick option', o => o.map(x => x.textContent));
  assert.match(options[0], /^aidA1 · .* · not finalized$/);
  assert.match(options.find(o => o.startsWith('ceil09')), / · live$/);
  await S.pick(page, 'aidA1');
  await until(() => /ended, not finalized/.test(document.getElementById('viewer-facts').textContent));
  await page.click('[data-nav="diagnostics"]');
  await until(() => document.querySelector('[data-view="diagnostics"] .custodian-receipt dl'));
  assert.equal(await text('#evaluation-note'), 'evaluation unfinished');
  assert.deepEqual(page.problems, []);
});

test('keyboard operation: Pause, the story cards and the findings are focusable buttons with a visible focus ring', async () => {
  await start();
  await page.focus('#pause');
  const outline = await page.$eval('#pause', n => { n.focus(); return getComputedStyle(n).outlineStyle; });
  assert.notEqual(outline, 'none');
  const cards = await page.$$eval('#story .card > .cardmain, #story .card > .acts > *', n => n.map(x => x.tagName));
  assert.ok(cards.length >= 3 && cards.every(t => t === 'BUTTON' || t === 'A'), 'story cards are buttons and links');
  await page.click('[data-nav="diagnostics"]');
  await until(() => document.querySelector('#findings li'));
  const tags = await page.$$eval('#findings li > *', n => n.map(x => x.tagName));
  assert.ok(tags.length >= 3 && tags.every(t => t === 'BUTTON'), 'finding rows are buttons');
});
