// Spectator viewer views against the fixture API: Supervise content and provenance, Diagnose,
// Improve, Explore, Compare, the run picker, polling, and the greyed viewer-unavailable state.
const {test, before, after, beforeEach, afterEach} = require('node:test');
const assert = require('node:assert/strict');
const S = require('./fixtures/spectator/support.cjs');

let fx, browser, page;
before(async () => { browser = await S.launch(); });
after(async () => { if (browser) await browser.close(); });
beforeEach(async () => {
  fx = await S.startFixture();
  page = await S.open(browser, `${fx.url}#live`);
  await S.ready(page);
});
afterEach(async () => { if (page) await page.close(); if (fx) fx.stop(); });

const go = async hash => { await page.evaluate(h => { location.hash = h; }, hash); await S.settle(page, 700); };
const text = selector => page.$eval(selector, node => node.innerText);
const requests = async () => (await fx.state()).view_requests;
// Poll with evaluate: page.waitForFunction proved unreliable for this page's predicates.
async function waitFor(fn, arg, timeout = 8000) {
  const end = Date.now() + timeout;
  for (;;) {
    if (await page.evaluate(fn, arg).catch(() => false)) return;
    if (Date.now() > end) throw new Error(`condition not met in ${timeout} ms: ${fn}`);
    await S.settle(page, 100);
  }
}

test('Supervise: Pause? conditions, game state and findings carry provenance chips', async () => {
  assert.match(await text('#pauseanswer'), /^No\. Waiting costs about \$0\.12 a minute/);
  assert.equal(await page.$$eval('#conds li', n => n.length), 5);
  assert.equal(await page.$$eval('#conds li .pv', n => n.length), 5, 'a chip on every condition');
  assert.ok(await page.$$eval('#gamestate .pv.read', n => n.length) >= 7, 'a read chip on every reading');
  assert.match(await text('#gamestate'), /abstained: low contrast/);
  assert.match(await text('#gamestate'), /fails floor/);
  assert.equal(await page.$$eval('#findings li button .pv', n => n.length), 5);
  const kinds = await page.$$eval('#findings .pv', n => [...new Set(n.map(x => x.textContent.trim().split(' ')[0]))].sort());
  for (const word of ['derived', 'recorded', 'player']) assert.ok(kinds.includes(word), `chip for source ${word}: ${kinds}`);
});

test('Supervise: a finding row is a button that moves the playhead and the strip says check is off', async () => {
  await page.click('#findings li:nth-child(4) button');   // newest first: the step-69 work note is fourth
  await S.settle(page, 400);
  const info = await text('#playinfo');
  assert.doesNotMatch(info, /\(live\)/);
  assert.match(info, /return to live/);
  await page.click('#backlive');
  await S.settle(page, 300);
  assert.match(await text('#playinfo'), /\(live\)/);
});

test('Supervise: steps arrive incrementally with after= and the timeline follows live', async () => {
  const before = await page.$eval('#tl', n => Number(n.getAttribute('aria-valuemax')));
  await fx.advance(4);
  await waitFor(prev => Number(document.getElementById('tl').getAttribute('aria-valuemax')) > prev, before, 9000);
  const calls = (await requests()).filter(r => r.startsWith(`run/${'5c7e91d2a4b84f60b3d1e0a9c2f7184d'}/steps`));
  assert.ok(calls.length >= 2);
  assert.match(calls[0], /after=-1/);
  assert.ok(calls.some(c => /after=99\b/.test(c)), `an incremental request after the last seen step: ${calls.join(' | ')}`);
  assert.match(await text('#playinfo'), /\(live\)/);
});

test('polling: summary is requested about every two seconds', async () => {
  const count = async () => (await requests()).filter(r => r.endsWith('/summary')).length;
  const first = await count();
  await S.settle(page, 4500);
  assert.ok(await count() >= first + 2, 'at least two more summary polls in 4.5 s');
});

test('run picker lists runs from /api/view/runs and switches the run', async () => {
  await waitFor(() => document.querySelectorAll('#runpick option').length === 8);
  const options = await page.$$eval('#runpick option', n => n.map(o => o.textContent));
  assert.equal(options.length, 8);
  assert.match(options[0], /T5 · Ceiling · live/);
  assert.ok(options.some(o => /C2 · Reflection aid · lost/.test(o)));
  const a1 = await page.$$eval('#runpick option', n => n.find(o => /^A1/.test(o.textContent)).value);
  await page.select('#runpick', a1);
  await waitFor(id => document.getElementById('runpick').value === id, a1);
  await S.settle(page, 2500);
  assert.ok((await requests()).some(r => r.startsWith(`run/${a1}/summary`)));
  assert.match(await text('#viewer-facts'), /not the live run/i);
});

test('Diagnose overview: metrics with provenance, n and denominators, reader coverage', async () => {
  await go('#run/overview');
  const body = await text('#app');
  assert.match(body, /Where game time came from/);
  assert.match(body, /1\.67\s+game h/);
  assert.match(body, /3 missing/);
  assert.match(body, /Reader coverage/);
  assert.match(body, /BELOW FLOOR/i);
  assert.ok(await page.$$eval('#app .pv.human', n => n.length) >= 1);
  assert.equal(await page.$eval('.subnav a[aria-current="page"]', n => n.textContent), 'Overview');
});

test('Diagnose tools: table, transition matrix, filtered calls and the frame a call produced', async () => {
  await go('#run/tools');
  assert.match(await text('#app table'), /input\s+1320/);
  assert.ok(await page.$('#app .chart.trans canvas'));
  await page.select('select[aria-label="Status filter"]', 'refused');
  await waitFor(() => document.querySelectorAll('.tall tbody tr').length === 1);
  assert.ok((await requests()).some(r => /calls\?tool=&status=refused/.test(r)));
  await page.click('.tall tbody tr button');
  await waitFor(() => document.querySelector('.frame.small img'));
  assert.match(await page.$eval('.frame.small img', i => i.getAttribute('src')), /^\/api\/view\/run\/.+\/frame\//);
});

test('Diagnose programs, memory, handoffs: insufficient sample, audit labels, cited frames, identity check', async () => {
  await go('#run/programs');
  assert.match(await text('#app'), /Insufficient sample\./);
  await go('#run/memory');
  assert.match(await text('#app'), /wrong\s+HUMAN/i);
  await page.click('.data tbody tr:nth-child(2) button');
  await S.settle(page, 300);
  assert.match(await text('#app'), /Thirst appears after about 2 game hours/);
  await page.click('.chips button');
  await waitFor(() => document.querySelector('.frame.small img'));
  await go('#run/handoffs');
  assert.match(await text('#app'), /Identity check/);
  assert.match(await text('#app'), /Baytown/);
});

test('Diagnose context: costliest requests open the replayed context, exact versus reconstructed is labelled', async () => {
  await go('#run/context');
  assert.ok(await page.$('#app .chart.reqchart canvas'));
  await page.click('.data tbody tr button');
  await waitFor(() => document.querySelector('.ctx-bar'));
  assert.match(await text('#app'), /exact: replayed from the recorded manifest/);
  assert.ok((await requests()).some(r => /\/context\/req-/.test(r)));
});

test('Improve: change cards with verdicts, failure modes ranked deaths first, components by arm', async () => {
  await go('#improve/changes');
  assert.equal(await page.$$eval('.card', n => n.length), 3);
  assert.match(await text('.verdict'), /moved the wrong way/i);
  await page.click('.card:nth-child(2)');
  await S.settle(page, 300);
  assert.match(await text('#app'), /untested/);
  assert.match(await text('#app'), /No per-run values/);
  await go('#improve/failures');
  assert.match(await text('.data tbody tr:first-child'), /^Death/);
  await go('#improve/components');
  const heads = await page.$$eval('.data thead th', n => n.map(x => x.textContent.replace(/\s+/g, ' ').trim()));
  assert.deepEqual(heads.slice(1).map(h => h.replace(/n = \d+$/, '')), ['Ceiling', 'Zoom aid', 'Game-help aid', 'Reflection aid']);
  assert.match(await text('#app'), /Excluded: C2/);
});

test('Explore: filters re-query the viewer; CSV mirrors the cohort; deaths are aligned', async () => {
  await go('#explore');
  assert.match(await text('#cohortsum'), /Median \[IQR\]/);
  await page.select('select[data-cf="arm"]', 'Ceiling');
  await S.settle(page, 500);
  assert.ok((await requests()).some(r => /explore\?arm=Ceiling&/.test(r)));
  const csv = await page.$eval('textarea.csv', n => n.value);
  assert.match(csv, /^run,label,arm,start,outcome/);
  assert.equal(await page.$$eval('#alignbody .seq', n => n.length), 2);
  assert.equal(await page.$$eval('#alignbody .seq span', n => n.length), 24);
});

test('Compare: survival table says "not reached", the split by start re-queries, versions table is shown', async () => {
  await go('#compare');
  assert.match(await text('#app table'), /not reached/);
  assert.ok(await page.$('#app .chart.km canvas'));
  await page.$eval('#strat', box => box.click());
  await waitFor(() => /S2 player-chosen start/.test(document.querySelector('#app table').innerText));
  assert.ok((await requests()).some(r => /compare\?group=start/.test(r)));
  assert.match(await text('#app'), /Are these runs comparable\?/);
});

test('viewer unavailable greys interpretive panels, says so in the strip and a banner, then recovers', async () => {
  page.expect503 = true;
  await fx.viewer('down');
  await waitFor(() => document.getElementById('viewer').classList.contains('down'), null, 9000);
  assert.match(await text('#viewer'), /viewer unavailable/);
  assert.match(await text('.banner.down'), /Pause and the operator check do not use the viewer/);
  assert.equal(await page.$eval('[data-viewer="down"] .panel', n => getComputedStyle(n).opacity), '0.5');
  assert.match(await page.title(), /viewer unavailable/);
  await fx.viewer('up');
  await waitFor(() => !document.getElementById('viewer').classList.contains('down'), null, 12000);
  assert.equal(await page.$('.banner.down'), null);
});
