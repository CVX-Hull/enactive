// Spectator viewer views against the fixture API: content and provenance on each tab, the sections behind Diagnostics
// and Memory, the run picker, polling, and the greyed viewer-unavailable state.
const {test, before, after, beforeEach, afterEach} = require('node:test');
const assert = require('node:assert/strict');
const S = require('./fixtures/spectator/support.cjs');

let fx, browser, page;
before(async () => { browser = await S.launch(); });
after(async () => { if (browser) await browser.close(); });
beforeEach(async () => {
  fx = await S.startFixture();
  page = await S.open(browser, `${fx.url}#watch`);
  await S.ready(page);
});
afterEach(async () => { if (page) await page.close(); if (fx) fx.stop(); });

const go = async hash => { await page.evaluate(h => { location.hash = h; }, hash); await S.settle(page, 700); };
const open = id => page.$eval(`#${id}`, d => { d.open = true; });
const text = selector => page.$eval(selector, node => node.innerText);
const requests = async () => (await fx.state()).view_requests;
// Poll with evaluate: page.waitForFunction proved unreliable for this page's predicates.
async function waitFor(fn, arg, timeout = 8000) {
  const end = Date.now() + timeout;
  for (;;) {
    if (await page.evaluate(fn, arg).catch(() => false)) return;
    if (Date.now() > end) throw await S.stalled(page, fn, timeout);
    await S.settle(page, 100);
  }
}

test('Diagnostics: Pause conditions, game state and findings carry provenance chips', async () => {
  await go('#diagnostics');
  await waitFor(() => document.querySelectorAll('#conds li').length === 5);
  assert.match(await text('#pauseanswer'), /^No\. Waiting costs about \$\d+\.\d\d a minute/);
  assert.equal(await page.$$eval('#conds li .pv', n => n.length), 5, 'a chip on every condition');
  assert.match(await text('#conds'), /\d+(\.\d+)? s since the last operation/);
  assert.ok(await page.$$eval('#gamestate .pv.read', n => n.length) >= 2, 'a read chip on every value that was read');
  assert.match(await text('#gamestate'), /abstained: not in game/);
  assert.match(await text('#gamestate'), /passes floor/);
  assert.ok(await page.$$eval('#findings li button .pv', n => n.length) >= 3);
  const kinds = await page.$$eval('#findings .pv', n => [...new Set(n.map(x => x.textContent.trim().split(' ')[0]))]);
  for (const word of ['recorded', 'derived']) assert.ok(kinds.includes(word), `chip for source ${word}: ${kinds}`);
  assert.doesNotMatch(await text('#findings'), /Images evicted/, 'routine evictions are not findings a person follows');
});

test('a finding opens Watch at its step, and return to live restores it', async () => {
  await go('#diagnostics');
  await page.$eval('#findings li:first-child button', b => b.click());
  await waitFor(() => location.hash === '#watch' && document.getElementById('playinfo'));
  await waitFor(() => /HISTORY/.test(document.querySelector('.stagepill').textContent) && document.getElementById('backlive'));
  assert.doesNotMatch(await text('#playinfo'), /\(live\)/);
  assert.equal(await text('#backlive'), 'Return to live');
  await page.click('#backlive');
  await waitFor(() => /\(live\)/.test(document.getElementById('playinfo').textContent));
});

test('Watch: steps arrive incrementally with after= and the timeline and story follow live', async () => {
  const before = await page.$eval('#tl', n => Number(n.getAttribute('aria-valuemax')));
  const newest = await page.$eval('#story .card .cardmain', n => n.dataset.jump);
  await fx.advance(4);
  await waitFor(prev => Number(document.getElementById('tl').getAttribute('aria-valuemax')) > prev, before, 9000);
  await waitFor(prev => document.querySelector('#story .card .cardmain').dataset.jump !== prev, newest, 9000);
  const calls = (await requests()).filter(r => /^run\/[^/]+\/steps/.test(r));
  assert.ok(calls.length >= 2);
  assert.match(calls[0], /after=0&/, 'the first request starts at the beginning');
  assert.ok(calls.some(c => /after=[1-9]\d*&/.test(c)), `an incremental request after the last seen step: ${calls.join(' | ')}`);
  const feeds = (await requests()).filter(r => /^run\/[^/]+\/feed/.test(r));
  assert.match(feeds[0], /after=0&/);
  assert.ok(feeds.slice(1).every(c => /after=[1-9]\d*&/.test(c)), 'a later poll re-reads only the recent part');
  // The overlap is replaced, never repeated.
  const ids = await page.$$eval('#story .card', n => n.map(c => c.dataset.entry));
  assert.equal(new Set(ids).size, ids.length);
  assert.match(await text('#playinfo'), /\(live\)/);
});

test('polling: summary is requested about every two seconds, and a recorded run\'s story only once', async () => {
  const count = async pattern => (await requests()).filter(r => pattern.test(r)).length;
  const first = await count(/\/summary$/);
  await S.settle(page, 4500);
  assert.ok(await count(/\/summary$/) >= first + 2, 'at least two more summary polls in 4.5 s');
  await S.pick(page, 'aidA3');
  await waitFor(() => document.getElementById('story-source'));
  const feeds = new RegExp(`^run/${S.SESSIONS.aidA3}/feed`);
  await waitFor(() => document.querySelector('#story .card'));
  const asked = await count(feeds);
  assert.ok(asked >= 1);
  await S.settle(page, 4500);
  assert.equal(await count(feeds), asked);
});

test('a run that ends has its whole story read once more, and then no more', async () => {
  const live = S.SESSIONS.ceil09;
  const feeds = async () => (await requests()).filter(r => r.startsWith(`run/${live}/feed`));
  await waitFor(() => document.querySelectorAll('#story .card').length > 20);
  const before = await page.evaluate(async () => (await import('/app/data.js')).store.feed.map(e => e.id));
  const asked = (await feeds()).length;
  await fx.viewer('ended');
  await waitFor(async () => { const {store} = await import('/app/data.js'); return store.feedFinalized === 'final' && store.feed.some(e => e.finding_kind === 'run_end'); }, null, 12000);
  const whole = (await feeds()).slice(asked);
  assert.match(whole.at(-1), /after=0&/, 'read from the beginning, not only its recent part');
  const after = await page.evaluate(async () => (await import('/app/data.js')).store.feed.map(e => ({id: e.id, seq: e.seq, kind: e.finding_kind})));
  // The final pass placed one finding at the end and one far behind the recent part; both are here, and nothing else moved or doubled.
  assert.ok(after.some(e => e.kind === 'custody_stop' && e.seq === 5));
  assert.equal(new Set(after.map(e => e.id)).size, after.length);
  assert.deepEqual(after.map(e => e.id).filter(id => before.includes(id)), before);
  await page.type('#story-search', 'found by the final pass');
  await waitFor(() => document.querySelectorAll('#story .card').length === 1);
  const settled = (await feeds()).length;
  await S.settle(page, 5000);
  assert.equal((await feeds()).length, settled);
});

test('a one-shot read that failed while the viewer was away is repeated when it returns; one that succeeded is not', async () => {
  const archived = S.SESSIONS.aidA3;
  const reads = async name => (await requests()).filter(r => r === `run/${archived}/${name}`).length;
  await S.pick(page, 'aidA3');   // a run that is not live, whose telemetry and tools are read once
  await page.setRequestInterception(true);
  let refuse = true;
  page.on('request', async request => {
    const {pathname} = new URL(request.url());
    if (refuse && pathname.endsWith('/tools')) return request.respond({status: 503, contentType: 'application/json', body: '{"viewer":"unavailable"}'});
    request.continue();
  });
  page.expect503 = true;
  await waitFor(() => document.getElementById('story-source'));
  await page.evaluate(() => { location.hash = '#diagnostics'; });
  await waitFor(() => /Viewer unavailable|Tool statistics|tool statistics/i.test(document.getElementById('app').innerText) && document.querySelector('.ctxchart canvas'), null, 12000);
  assert.equal(await page.$('.panel table.data tbody tr td'), null, 'no tool row yet');
  const telemetry = await reads('telemetry');
  assert.equal(telemetry, 1);
  refuse = false;
  await waitFor(() => /input\s+231/.test(document.getElementById('app').innerText), null, 12000);
  const tools = await reads('tools');
  assert.equal(tools, 1, 'the one that reached the viewer');
  // Both are now held: another outage and return asks for neither again.
  await fx.viewer('down');
  await waitFor(() => document.getElementById('viewer').classList.contains('down'), null, 9000);
  await fx.viewer('up');
  await waitFor(() => !document.getElementById('viewer').classList.contains('down'), null, 12000);
  await S.settle(page, 2500);
  // A read the outage caught is logged by the fixture too, so only these two matter.
  assert.deepEqual([await reads('telemetry'), await reads('tools')], [telemetry, tools]);
});

test('two sessions that share a run name are two runs in the picker', async () => {
  const [first, second] = [S.SESSIONS.aidA1, S.SESSIONS.aidA2];
  await page.setRequestInterception(true);
  page.on('request', async request => {
    const url = new URL(request.url());
    if (url.pathname !== '/api/view/runs') return request.continue();
    const body = await (await fetch(request.url())).json();
    for (const row of body.items) if (row.session === second) row.run = 'aidA1';
    request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
  });
  await page.reload({waitUntil: 'load'});
  await waitFor(() => document.querySelectorAll('#runpick option').length === 30);
  const named = await page.$$eval('#runpick option', n => n.filter(o => /^aidA1 ·/.test(o.textContent)).map(o => o.value));
  assert.deepEqual(named, [first, second]);
  for (const session of [second, first]) {
    const from = (await requests()).length;
    await page.select('#runpick', session);
    await waitFor(async s => { const {store} = await import('/app/data.js'); return store.runId === s && store.summary && store.summary.session === s; }, session);
    assert.equal(await page.$eval('#runpick', n => n.value), session);
    const asked = (await requests()).slice(from).filter(r => r.startsWith('run/') && !r.startsWith(`run/${S.SESSIONS.ceil09}/`));
    assert.ok(asked.some(r => r === `run/${session}/summary`) && !(await requests()).some(r => r.startsWith('run/aidA1/')), asked.join(' '));
  }
});

test('run picker lists runs from /api/view/runs and switches the run', async () => {
  await waitFor(() => document.querySelectorAll('#runpick option').length === 30);
  const options = await page.$$eval('#runpick option', n => n.map(o => o.textContent));
  assert.ok(options.some(o => /^ceil09 · ceiling · live$/.test(o)));
  assert.ok(options.some(o => / · lost$/.test(o)), 'a run lost to infrastructure is marked');
  assert.equal(await page.$eval('#runpick', n => n.value), S.SESSIONS.ceil09, 'the live run is selected first');
  await S.pick(page, 'aidA1');
  await waitFor(session => document.getElementById('runpick').value === session, S.SESSIONS.aidA1);
  await S.settle(page, 2500);
  assert.ok((await requests()).some(r => r.startsWith(`run/${S.SESSIONS.aidA1}/summary`)));
  assert.match(await text('#viewer-facts'), /not the live run/i);
});

test('Diagnostics metrics: provenance, n and denominators, reader coverage, ladder', async () => {
  await go('#diagnostics/metrics');
  await waitFor(() => document.querySelector('#more-metrics .dbody'));
  const body = await text('#more-metrics');
  assert.match(body, /Pace and game time/);
  assert.match(body, /Milestone ladder/);
  assert.match(body, /highest reached: ate/);
  assert.ok(await page.$$eval('#more-metrics .state.watch', n => n.some(e => /unvalidated/i.test(e.textContent))),
    'a metric from a reader without a passing validation is labelled');
  assert.ok(await page.$$eval('#more-metrics .pv.calc', n => n.length) >= 3);
  // A long count or missing-data note never squeezes a metric name into its value.
  const squeezed = await page.$$eval('#more-metrics dl.kv:not(.wide) dt', ts => ts.map(dt => {
    const a = dt.getBoundingClientRect(), b = dt.nextElementSibling.getBoundingClientRect();
    return {name: dt.textContent.trim(), width: a.width, overlap: a.right > b.left + 1};
  }).filter(r => r.width < 90 || r.overlap));
  assert.deepEqual(squeezed, []);
  assert.doesNotMatch(body, /missing: missing/);
  await go('#diagnostics/readers');
  await waitFor(() => document.querySelector('#more-readers table.data'));
  assert.match(await text('#more-readers'), /below floor|passes/i);
});

test('Diagnostics tools: table, transition matrix, filtered calls and the frame a call produced', async () => {
  await go('#diagnostics');
  await waitFor(() => /input\s+231/.test(document.getElementById('app').innerText));
  assert.equal((await requests()).some(r => /\/calls/.test(r)), false, 'a closed section fetches nothing');
  await open('more-calls');
  await waitFor(() => document.querySelector('#more-calls .chart.trans canvas') && document.querySelector('.calls tbody tr'));
  await page.select('select[aria-label="Status filter"]', 'refused');
  await waitFor(() => document.querySelectorAll('.calls tbody tr').length === 1);
  assert.ok((await requests()).some(r => /calls\?tool=&status=refused/.test(r)));
  await page.select('select[aria-label="Status filter"]', 'ok');
  await waitFor(() => document.querySelectorAll('.calls tbody tr').length > 50);
  await page.$eval('.calls tbody tr button', b => b.click());
  await waitFor(() => document.querySelector('.frame.small img'));
  assert.match(await page.$eval('.frame.small img', i => i.getAttribute('src')), /^\/api\/view\/run\/.+\/frame\//);
});

test('Memory player records: audit labels, cited frames, handoffs and their identity check', async () => {
  await go('#memory/player');
  await waitFor(() => document.querySelector('#more-sources .chips button'));
  const body = await text('#more-sources');
  assert.match(body, /Ongoing indefinite survival/);
  assert.match(body, /confirm: identity or world error/);
  assert.ok(await page.$('#more-sources .pv.human'));
  await page.$eval('#more-sources .chips button', b => b.click());
  await waitFor(() => document.querySelector('.frame.small img'));
  assert.match(await text('#more-sources'), /Identity check/);
  assert.match(await text('#more-sources'), /Baytown/);
});

test('Diagnostics requests: the costliest open a context replayed on request, exact versus reconstructed is labelled', async () => {
  await go('#diagnostics');
  await waitFor(() => document.getElementById('more-requests'));
  await open('more-requests');
  await waitFor(() => document.querySelector('#more-requests tbody tr button'));
  assert.equal((await requests()).some(r => /\/context\//.test(r)), false);
  await page.$eval('#more-requests tbody tr:nth-child(2) button', b => b.click());
  await page.$eval('#more-requests #load-context', b => b.click());
  await waitFor(() => document.querySelector('#more-requests .ctx-bar'));
  assert.match(await text('#more-requests'), /reconstructed|exact: replayed/);
  assert.ok((await requests()).some(r => /\/context\/request-\d+\?actor=/.test(r)));
});

test('Across runs: change cards with verdicts, failure modes ranked deaths first, components by arm', async () => {
  await go('#diagnostics/changes');
  await waitFor(() => document.querySelectorAll('#more-runs .card').length === 4);
  assert.match(await text('#more-runs .verdict'), /moved the wrong way/i);
  const title = async () => text('#more-runs .panel:nth-of-type(2) h2');
  const first = await title();
  await page.$eval('#more-runs .card:nth-child(2)', b => b.click());
  await S.settle(page, 300);
  assert.notEqual(await title(), first);
  assert.match(await text('#more-runs'), /Computed/);
  assert.match(await text('#more-runs'), /Recorded/);
  await go('#diagnostics/failures');
  await waitFor(() => /^Death/.test(document.querySelector('#more-runs .data tbody tr:first-child')?.innerText || ''));
  await go('#diagnostics/components');
  await waitFor(() => [...document.querySelectorAll('#more-runs .data thead th')].some(x => /ceiling/.test(x.textContent)));
  const heads = await page.$$eval('#more-runs .data thead th', n => n.map(x => x.textContent.replace(/\s+/g, ' ').replace(/n = \d+$/, '').trim()));
  for (const arm of ['ceiling', 'zoom-aid', 'game-help-aid', 'reflection-aid']) assert.ok(heads.includes(arm), `${arm} in ${heads}`);
  // Every arm is visible at desktop width without scrolling the table sideways.
  const fit = await page.$eval('#more-runs .data', t => [t.parentElement.scrollWidth, t.parentElement.clientWidth]);
  assert.ok(fit[0] <= fit[1], `components table ${fit[0]} px overflows its ${fit[1]} px panel`);
  assert.match(await text('#more-runs'), /Excluded: \S+/);
});

test('Explore: filters re-query the viewer; CSV mirrors the cohort; deaths are aligned', async () => {
  await go('#diagnostics/explore');
  await waitFor(() => document.getElementById('cohortsum'));
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
  await go('#diagnostics/compare');
  await waitFor(() => document.querySelector('#more-runs .chart.km canvas'));
  assert.match(await text('#more-runs table'), /not reached/);
  await page.$eval('#strat', box => box.click());
  await waitFor(() => /S2/.test(document.querySelector('#more-runs table').innerText));
  assert.ok((await requests()).some(r => /compare\?group=start/.test(r)));
  assert.match(await text('#more-runs'), /Are these runs comparable\?/);
});

test('viewer unavailable greys interpretive panels, says so in the strip and a banner, then recovers', async () => {
  page.expect503 = true;
  await fx.viewer('down');
  await waitFor(() => document.getElementById('viewer').classList.contains('down'), null, 9000);
  assert.match(await text('#viewer'), /viewer unavailable/);
  assert.match(await text('.banner.down'), /The control strip and Pause do not use the viewer/);
  assert.equal(await page.$eval('[data-viewer="down"] .panel', n => getComputedStyle(n).opacity), '0.5');
  assert.match(await page.title(), /viewer unavailable/);
  await fx.viewer('up');
  await waitFor(() => !document.getElementById('viewer').classList.contains('down'), null, 12000);
  assert.equal(await page.$('.banner.down'), null);
});

test('chart tooltips escape run and tool names before ECharts renders them as HTML', async () => {
  const out = await page.evaluate(async () => {
    const {dotsOption, transitionsOption, contextOption} = await import('/app/charts.js');
    const evil = '<img src=x onerror=alert(1)>"&';
    const dots = dotsOption([{arm: 'a', runs: [{run: evil, target: 1}]}], null, 'm').tooltip.formatter({name: evil, value: [1, 0]});
    const trans = transitionsOption([{tool: evil, calls: 1}], [[evil, evil, 2]], x => x).tooltip.formatter({value: [0, 0, 2]});
    const context = contextOption([{index: 0, request_id: evil, seq: 1, prompt_tokens: 10, cache_read: 1}], []).tooltip.formatter([{dataIndex: 0}]);
    return [dots, trans, context];
  });
  for (const html of out) { assert.ok(!html.includes('<img'), html); assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;&quot;&amp;/); }
});
