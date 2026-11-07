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
  assert.match(await text('#pauseanswer'), /^No\. Waiting costs about \$\d+\.\d\d a minute/);
  assert.equal(await page.$$eval('#conds li', n => n.length), 5);
  assert.equal(await page.$$eval('#conds li .pv', n => n.length), 5, 'a chip on every condition');
  assert.match(await text('#conds'), /1 s? since|\d+(\.\d+)? s since the last operation/);
  assert.ok(await page.$$eval('#gamestate .pv.read', n => n.length) >= 2, 'a read chip on every value that was read');
  assert.match(await text('#gamestate'), /abstained: not in game/);
  assert.match(await text('#gamestate'), /passes floor/);
  assert.ok(await page.$$eval('#findings li button .pv', n => n.length) >= 3);
  const kinds = await page.$$eval('#findings .pv', n => [...new Set(n.map(x => x.textContent.trim().split(' ')[0]))]);
  for (const word of ['recorded', 'derived']) assert.ok(kinds.includes(word), `chip for source ${word}: ${kinds}`);
  assert.doesNotMatch(await text('#findings'), /Images evicted/, 'routine evictions stay on the timeline');
});

test('Supervise: a finding row is a button that moves the playhead and the strip says check is off', async () => {
  await page.click('#findings li:first-child button');
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
  const calls = (await requests()).filter(r => /^run\/[^/]+\/steps/.test(r));
  assert.ok(calls.length >= 2);
  assert.match(calls[0], /after=0&/, 'the first request starts at the beginning');
  assert.ok(calls.some(c => /after=[1-9]\d*&/.test(c)), `an incremental request after the last seen step: ${calls.join(' | ')}`);
  assert.match(await text('#playinfo'), /\(live\)/);
});

test('polling: summary is requested about every two seconds', async () => {
  const count = async () => (await requests()).filter(r => r.endsWith('/summary')).length;
  const first = await count();
  await S.settle(page, 4500);
  assert.ok(await count() >= first + 2, 'at least two more summary polls in 4.5 s');
});

test('run picker lists runs from /api/view/runs and switches the run', async () => {
  await waitFor(() => document.querySelectorAll('#runpick option').length === 30);
  const options = await page.$$eval('#runpick option', n => n.map(o => o.textContent));
  assert.ok(options.some(o => /^ceil09 · ceiling · live$/.test(o)));
  assert.ok(options.some(o => / · lost$/.test(o)), 'a run lost to infrastructure is marked');
  assert.equal(await page.$eval('#runpick', n => n.value), 'ceil09', 'the live run is selected first');
  await page.select('#runpick', 'aidA1');
  await waitFor(() => document.getElementById('runpick').value === 'aidA1');
  await S.settle(page, 2500);
  assert.ok((await requests()).some(r => r.startsWith('run/aidA1/summary')));
  assert.match(await text('#viewer-facts'), /not the live run/i);
});

test('Diagnose overview: metrics with provenance, n and denominators, reader coverage, ladder', async () => {
  await go('#run/overview');
  const body = await text('#app');
  assert.match(body, /Pace and game time/);
  assert.match(body, /Reader coverage/);
  assert.match(body, /Milestone ladder/);
  assert.match(body, /highest reached: ate/);
  assert.match(body, /below floor|passes/i);
  assert.ok(await page.$$eval('#app .state.watch', n => n.some(e => /unvalidated/i.test(e.textContent))),
    'a metric from a reader without a passing validation is labelled');
  assert.ok(await page.$$eval('#app .pv.calc', n => n.length) >= 3);
  assert.equal(await page.$eval('.subnav a[aria-current="page"]', n => n.textContent), 'Overview');
  // A long count or missing-data note never squeezes a metric name into its value.
  const squeezed = await page.$$eval('#app dl.kv:not(.wide) dt', ts => ts.map(dt => {
    const a = dt.getBoundingClientRect(), b = dt.nextElementSibling.getBoundingClientRect();
    return {name: dt.textContent.trim(), width: a.width, overlap: a.right > b.left + 1};
  }).filter(r => r.width < 100 || r.overlap));
  assert.deepEqual(squeezed, []);
  assert.doesNotMatch(body, /missing: missing/);
});

test('Diagnose tools: table, transition matrix, filtered calls and the frame a call produced', async () => {
  await go('#run/tools');
  assert.match(await text('#app table'), /input\s+231/);
  assert.ok(await page.$('#app .chart.trans canvas'));
  await page.select('select[aria-label="Status filter"]', 'refused');
  await waitFor(() => document.querySelectorAll('.tall tbody tr').length === 1);
  assert.ok((await requests()).some(r => /calls\?tool=&status=refused/.test(r)));
  await page.select('select[aria-label="Status filter"]', 'ok');
  await waitFor(() => document.querySelectorAll('.tall tbody tr').length > 50);
  await page.click('.tall tbody tr button');
  await waitFor(() => document.querySelector('.frame.small img'));
  assert.match(await page.$eval('.frame.small img', i => i.getAttribute('src')), /^\/api\/view\/run\/.+\/frame\//);
});

test('Diagnose programs, memory, handoffs: insufficient sample, audit labels, cited frames, identity check', async () => {
  await go('#run/programs');
  assert.match(await text('#app'), /Insufficient sample\./);
  assert.match(await text('#app'), /Program runs/);
  await go('#run/memory');
  assert.match(await text('#app'), /Ongoing indefinite survival/);
  assert.match(await text('#app'), /confirm: identity or world error/);
  assert.ok(await page.$('#app .pv.human'));
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
  assert.match(await text('#app'), /reconstructed|exact: replayed/);
  assert.ok((await requests()).some(r => /\/context\/request-\d+\?actor=/.test(r)));
});

test('Improve: change cards with verdicts, failure modes ranked deaths first, components by arm', async () => {
  await go('#improve/changes');
  assert.equal(await page.$$eval('.card', n => n.length), 4);
  assert.match(await text('.verdict'), /moved the wrong way/i);
  const title = async () => text('.panel:nth-of-type(2) h2');
  const first = await title();
  await page.click('.card:nth-child(2)');
  await S.settle(page, 300);
  assert.notEqual(await title(), first);
  assert.match(await text('#app'), /Computed/);
  assert.match(await text('#app'), /Recorded/);
  await go('#improve/failures');
  assert.match(await text('.data tbody tr:first-child'), /^Death/);
  await go('#improve/components');
  const heads = await page.$$eval('.data thead th', n => n.map(x => x.textContent.replace(/\s+/g, ' ').replace(/n = \d+$/, '').trim()));
  for (const arm of ['ceiling', 'zoom-aid', 'game-help-aid', 'reflection-aid']) assert.ok(heads.includes(arm), `${arm} in ${heads}`);
  // Every arm is visible at desktop width without scrolling the table sideways.
  const fit = await page.$eval('.data', t => [t.parentElement.scrollWidth, t.parentElement.clientWidth]);
  assert.ok(fit[0] <= fit[1], `components table ${fit[0]} px overflows its ${fit[1]} px panel`);
  assert.match(await text('#app'), /Excluded: \S+/);
});

test('Explore: filters re-query the viewer; CSV mirrors the cohort; deaths are aligned', async () => {
  await go('#explore');
  assert.match(await text('#cohortsum'), /Median \[IQR\]/);
  await page.select('select[data-cf="arm"]', 'ceiling');
  await S.settle(page, 600);
  assert.ok((await requests()).some(r => /explore\?arm=ceiling&/.test(r)));
  const csv = await page.$eval('textarea.csv', n => n.value);
  assert.match(csv, /^run,arm,start,outcome/);
  const sequences = await page.$$eval('#alignbody .seq', n => n.length);
  assert.ok(sequences >= 1);
  assert.equal(await page.$$eval('#alignbody .seq span', n => n.length), sequences * 13);
});

test('Compare: survival table says "not reached", the split by start re-queries, versions table is shown', async () => {
  await go('#compare');
  assert.match(await text('#app table'), /not reached/);
  assert.ok(await page.$('#app .chart.km canvas'));
  await page.$eval('#strat', box => box.click());
  await waitFor(() => /S2/.test(document.querySelector('#app table').innerText));
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

test('chart tooltips escape run and tool names before ECharts renders them as HTML', async () => {
  const out = await page.evaluate(async () => {
    const {dotsOption, transitionsOption} = await import('/app/charts.js');
    const evil = '<img src=x onerror=alert(1)>"&';
    const dots = dotsOption([{arm: 'a', runs: [{run: evil, target: 1}]}], null, 'm').tooltip.formatter({name: evil, value: [1, 0]});
    const trans = transitionsOption([{tool: evil, calls: 1}], [[evil, evil, 2]], x => x).tooltip.formatter({value: [0, 0, 2]});
    return [dots, trans];
  });
  for (const html of out) { assert.ok(!html.includes('<img'), html); assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;&quot;&amp;/); }
});
