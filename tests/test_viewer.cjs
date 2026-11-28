// Spectator page: the four run tabs and the All runs workspace render in light, dark, narrow and phone widths without
// console errors, failed requests or horizontal overflow, and each does its job. Browser behavior against the fixture
// server only: no game, no provider, and no claim about the real viewer's data.
const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const S = require('./fixtures/spectator/support.cjs');

const ROUTES = ['#watch', '#memory', '#memory?version=v2', '#memory/articles', '#memory/facts', '#memory/usage', '#curator', '#curator?csess=session-h-002-1',
  '#diagnostics', '#diagnostics/metrics', '#diagnostics/readers', '#diagnostics/calls', '#diagnostics/requests',
  '#runs/lineage', '#runs/compare', '#runs/explore', '#runs/changes', '#runs/failures', '#runs/archive', '#runs/archive/containers', '#runs/archive/player'];
const CONFIGS = [['light', 1440, 'light', false], ['dark', 1440, 'dark', false], ['narrow', 900, 'light', false], ['phone', 390, 'light', true]];
let fx, browser;
before(async () => { fx = await S.startFixture(); browser = await S.launch(); });
after(async () => { if (browser) await browser.close(); if (fx) fx.stop(); });

const openPage = (url, options) => S.open(browser, url, options);

const go = async (page, hash) => { await page.evaluate(h => { location.hash = h; }, hash); await S.settle(page, 100); };
const text = (page, selector) => page.$eval(selector, node => node.innerText);
const click = (page, selector) => page.$eval(selector, node => node.click());
const flat = (page, selector) => page.$eval(selector, node => node.innerText.replace(/\s+/g, ' ').trim());
/** Put the shared playhead on a recorded step, as a click on the timeline would. */
const scrub = (page, seq) => page.evaluate(async s => { const {setCursorSeq} = await import('/app/data.js'); setCursorSeq(s); }, seq);

for (const [name, width, scheme, mobile] of CONFIGS) {
  test(`every view renders cleanly: ${name} (${width}px)`, {timeout: 240000}, async () => {
    const page = await openPage(`${fx.url}#watch`, {width, height: name === 'narrow' ? 760 : mobile ? 800 : 900, scheme, mobile});
    try {
      await S.ready(page);
      for (const route of ROUTES) {
        await go(page, route);
        await S.settle(page, 900);
        const body = await page.$eval('#app', node => node.innerText);
        const panels = await page.$$eval('#app .panel', nodes => nodes.length);
        assert.ok(panels > 0, `${route} rendered no panels`);
        assert.doesNotMatch(body, /undefined|NaN|\[object|Loading/, `${route} shows a broken value: ${body.match(/.{0,30}(undefined|NaN|\[object|Loading).{0,30}/)}`);
        assert.doesNotMatch(body, /not yet measured|arrives in|\bbelief\b|\bstaleness\b|\{"/i, `${route} shows a placeholder or raw JSON`);
        assert.equal(await S.overflow(page), 0, `${route} scrolls horizontally at ${width}px`);
        assert.equal(await page.$('.curator-records'), null, 'unconfigured curator sources remain hidden');
        assert.deepEqual(page.problems, [], `${route} had problems`);
        await S.shot(page, `${route.replace(/[#/?=]/g, '_')}-${name}`);
      }
      const active = await page.$eval('html', el => getComputedStyle(el).colorScheme);
      assert.match(active, scheme === 'dark' ? /dark/ : /light/);
    } finally { await page.close(); }
  });
}

for (const width of [1440, 1160]) {
  test(`the navigation is four run tabs, and the Mission Control bar is one slim row: ${width}px`, {timeout: 45000}, async () => {
    const page = await openPage(fx.url, {width, height: 860});
    try {
      await S.ready(page);
      assert.deepEqual(await page.$$eval('nav.jobs a', links => links.map(a => a.textContent)), ['Watch', 'Memory', 'Curator', 'Diagnostics']);
      assert.equal(await page.$eval('nav.jobs a[aria-current="page"]', a => a.dataset.nav), 'watch', 'Watch is the default');
      await S.until(page, () => document.documentElement.dataset.watchStage === 'ok' && document.getElementById('pill-curator') && document.querySelector('#pill-curator .num'));
      const bar = await page.evaluate(() => {
        const header = document.querySelector('header.ctl'), tops = ['#runpick', '#all-runs-btn', '#pill-spend', '#pill-context', '#pill-curator', '#viewer', '#pause', '#statusline']
          .map(s => document.querySelector(s).getBoundingClientRect());
        return {height: header.offsetHeight, rows: new Set(tops.map(r => Math.round(r.top + r.height / 2) >> 3)).size,
          clipped: [...document.querySelectorAll('#viewer-facts > *')].some(n => n.getBoundingClientRect().right > document.getElementById('viewer-facts').getBoundingClientRect().right + 1)};
      });
      assert.ok(bar.height <= 60, `one row: ${bar.height} px`);
      assert.ok(bar.rows <= 2, 'every item sits on one line');
      assert.equal(bar.clipped, false, 'no pill is cut off');
      assert.equal(await page.$eval('#runpick', s => getComputedStyle(s).whiteSpace), 'nowrap');
      assert.deepEqual(await page.$$eval('#runpick optgroup', g => g.map(x => x.label)), ['Lineage reflection-aid', 'Lineage ceiling-line']);
      assert.match(await page.$eval('#pill-spend', n => n.title), /^Loop spend \$\d\.\d\d \(partial\)\. Player \$\d\.\d\d of a \$5\.00 limit\. Player: \$\d\.\d\d · Curator ingestion: \$0\.98 · Interleaved hygiene: \$0\.25 · Boundary grooming: unavailable$/);
      assert.match(await flat(page, '#pill-context'), /^35\.0k tok 5 cuts WAIT \d+s$/);
      assert.equal(await page.$eval('#wait-badge', n => getComputedStyle(n).animationName), 'pulse', 'a held wait pulses');
      assert.equal(await flat(page, '#pill-curator').then(t => t.replace(/^Head /, '')), 'v6 lag 20');
      assert.equal(await page.$eval('#pill-curator', a => a.getAttribute('href')), '#memory?version=v6');
      assert.match(await flat(page, '#viewer'), /^ok · eval #\d+\/\d+$/);
      // The bar follows the playhead: the latest prompt while live, the run's median in history and while the view is held.
      const prompt = words => S.until(page, w => document.getElementById('pill-context').innerText.replace(/\s+/g, ' ').startsWith(w), words);
      await page.click('#feed-hold'); await prompt('32.8k tok p50 · 5 cuts');
      await page.click('#feed-hold'); await prompt('35.0k tok 5 cuts');
      await page.click('#feed-back'); await prompt('32.8k tok p50 · 5 cuts');
      await page.click('#backlive'); await prompt('35.0k tok 5 cuts');
      await page.click('[data-nav="memory"]'); await prompt('35.0k tok 5 cuts');
      for (const [tab, name] of [['memory', 'Memory'], ['curator', 'Curator'], ['diagnostics', 'Diagnostics'], ['watch', 'Watch']]) {
        await page.click(`[data-nav="${tab}"]`);
        await S.until(page, n => document.querySelector('#app section[data-view]')?.getAttribute('aria-label') === n, name);
      }
      // All runs is the workspace above any run: its button is the current page there, and no tab is.
      await page.click('#all-runs-btn');
      await S.until(page, () => location.hash === '#runs/lineage' && document.getElementById('all-runs-btn').getAttribute('aria-current') === 'page');
      assert.equal(await page.$('nav.jobs a[aria-current="page"]'), null);
      assert.deepEqual(page.problems, []);
    } finally { await page.close(); }
  });
}

test('deep links: step, entry, version, curator session and the older #memory/<version>', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#watch?step=90`, {width: 1440});
  try {
    await S.until(page, () => /STEP #90 · HISTORY/.test(document.querySelector('.stagepill')?.textContent || ''), null, 15000);
    await go(page, `#watch?run=ceil09&step=40&entry=3950`);
    await S.until(page, () => document.getElementById('inspector') === null && /STEP #40/.test(document.querySelector('.stagepill').textContent));
    await go(page, '#watch?step=12&entry=1200');
    await S.until(page, () => /Step 12/.test(document.querySelector('#inspector h2')?.textContent || ''));
    await page.keyboard.press('Escape');
    await go(page, '#memory/v2');
    await S.until(page, () => document.querySelector('#versions [aria-current="true"] b')?.textContent === 'v2');
    await go(page, '#memory?version=v6');
    await S.until(page, () => document.querySelector('#versions [aria-current="true"] b')?.textContent === 'v6');
    await go(page, '#curator?csess=session-w-001-1-40');
    await S.until(page, () => /w-001-1-40/.test(document.querySelector('#cur-session-drawer h2')?.textContent || ''));
    await go(page, `#diagnostics?run=aidA1`);
    await S.until(page, session => document.getElementById('runpick').value === session, S.SESSIONS.aidA1);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Pause is calm until a Pause condition is met; the badge beside Pause opens the conditions; the button never changes', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1440});
  try {
    await S.ready(page);
    const look = () => page.$eval('#pause', b => [getComputedStyle(b).backgroundColor, b.disabled, b.firstChild.textContent]);
    const calm = await look();
    assert.equal(calm[0], 'rgba(0, 0, 0, 0)');
    assert.equal(await page.$('#pausealert'), null);
    await page.setRequestInterception(true);
    page.on('request', async request => {
      if (!/\/summary$/.test(new URL(request.url()).pathname)) return request.continue();
      const body = await (await fetch(request.url())).json();
      body.pause.conditions[0].met = true; body.pause.met = [body.pause.conditions[0].name]; body.pause.answer = 'yes';
      request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
    });
    await S.until(page, () => document.documentElement.dataset.pauseAlert === 'yes' && document.getElementById('pausealert'));
    assert.ok(await page.$eval('#pausealert', n => !!n.closest('.ctl-right') && n.closest('header.ctl') === document.getElementById('pause').closest('header.ctl')), 'beside Pause in the bar');
    assert.ok(await page.$eval('header.ctl', h => h.offsetHeight) <= 60);
    const alert = await look();
    assert.notEqual(alert[0], calm[0]);
    assert.deepEqual(alert.slice(1), calm.slice(1));
    await click(page, '#pausealert');
    await S.until(page, () => location.hash === '#diagnostics/pause' && document.querySelectorAll('#conds li').length === 5);
    assert.match(await text(page, '#pauseanswer'), /^Yes: /);
    assert.equal(await page.$eval('[data-view="diagnostics"] > *', n => n.classList.contains('pausebox')), true, 'Pause conditions come first');
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Continuity feed: steps, joined cut and briefing, the #1037 badge, coverage waits, deliveries, agenda and reads', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1440});
  try {
    await S.ready(page);
    const top = await text(page, '#story .card');
    assert.match(top, /look around before moving on\./);
    assert.match(top, /player claim/);
    assert.match(top, /#\d+ · \d+ ms · endpoint-a · \$0\.01\d\d/);
    assert.ok((await text(page, '#story')).includes('<img src=x onerror=window.storyExecuted=true>'), 'a hostile intent is text');
    assert.equal(await page.evaluate(() => window.storyExecuted), undefined);
    assert.deepEqual(await page.$$eval('.storyhead .seg button', b => b.map(x => x.id)), ['story-all', 'story-cuts', 'story-memory', 'story-agenda', 'story-alerts']);
    // Cuts & Waits: five applied cuts, each with its joined briefing where one was recorded, and two edge-computed waits.
    await page.click('#story-cuts');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 7);
    assert.match(await flat(page, '#story-count'), /^7 shown$/);
    assert.equal(await page.$$eval('#story [data-kind="coverage_wait"]', n => n.length), 2);
    const rescue = await flat(page, '#story [data-kind="context_cut"].uncovered');
    assert.match(rescue, /Context cut · rescue · v2 61\.4k → 24\.8k tokens \(−36\.6k\) 6 uncovered turns · #1037 20 turns cut/);
    assert.match(rescue, /Post-cut briefing 2\.5k tok · 4 sources/);
    assert.equal(await page.$$eval('#story .card .uncovered', n => n.length), 1, 'only the uncovered cut carries the #1037 badge');
    assert.match(await flat(page, '#story [data-kind="context_cut"]:not(.uncovered)'), /Context cut · best effort · v6/);
    assert.match(await flat(page, '[data-kind="context_cut"][data-entry="11950"]'), /No briefing joined to this cut/);
    const open = await flat(page, '#story [data-kind="coverage_wait"].active');
    assert.match(open, /Coverage wait · uncovered \d+ requests held · \d+ s · peak 63\.2k tok WAITING Open at the end of the trace: a restore may resume it\./);
    assert.match(await flat(page, '#story [data-kind="coverage_wait"]:not(.active)'), /3 requests held · \d+ s · peak 63\.2k tok closed by cut/);
    // A cut's Briefing points at its delivery, in the whole story.
    await page.click('[data-entry="7950"] [data-briefing]');
    await S.until(page, () => document.querySelector('#story-all').getAttribute('aria-pressed') === 'true' && document.querySelector('#story [data-focus="yes"]')?.dataset.entry === '7960');
    assert.match(await flat(page, '[data-entry="7960"]'), /Post-cut briefing v2/i);
    // Memory: every delivery kind, each badged as itself; the version opens in Memory.
    await page.click('#story-memory');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 10);
    assert.deepEqual(await page.$$eval('#story .card .dkind', n => [...new Set(n.map(x => x.textContent))].sort()),
      ['Adopted (empty-suppressed)', 'Live delta', 'Opening briefing', 'Post-cut briefing', 'Refused', 'Undelivered']);
    assert.match(await flat(page, '[data-entry="16960"]'), /Live delta v6 after v5 2 state changes · 1 flag changes · 2 added facts · 1 claim updates 2 state changes 1 flag changes 2 added facts 1 claim updates/i);
    await page.$eval('[data-entry="5960"] a[data-version="v2"]', a => a.click());
    await S.until(page, () => location.hash === '#memory?version=v2' && document.querySelector('#versions [aria-current="true"] b')?.textContent === 'v2');
    await page.click('[data-nav="watch"]');
    await S.until(page, () => document.querySelector('#story .card'));
    // Agenda & Reads: the agenda's changes, the knowledge reads, the source re-read and the handoff.
    await page.click('#story-agenda');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 12);
    assert.match(await flat(page, '#story [data-kind="agenda_change"]'), /Agenda · Completed threads cleared 2 threads · 2 active Secure the shelter \(active → paused\) · Find a water source \(cleared\)/);
    const source = await flat(page, '#story [data-entry="3010"]');
    assert.match(source, /Look at the earlier frame again\. player claim source re-read player saw as s01 non-clickable/);
    assert.equal(await page.$('#story [data-entry="3010"] a[href*="frame"]'), null, 'the alias the player saw is no link');
    assert.ok(await page.$('#story [data-kind="finding"].handoff'), 'the handoff is in continuity');
    // Alerts: findings, a failed call and the refused and undelivered deliveries; a handoff is not one.
    await page.click('#story-alerts');
    await S.until(page, () => [...document.querySelectorAll('#story .card')].some(c => c.dataset.kind === 'step'));
    assert.equal(await page.$$eval('#story .card.bad .state.alert', n => n.length), 1, 'a failed call is an alert');
    assert.equal(await page.$('#story .card.handoff'), null);
    await page.click('#story-all');
    await page.type('#story-search', 'Read the sign');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 1);
    assert.match(await text(page, '#story-count'), /1 found/);
    await page.$eval('#story-search', n => { n.value = ''; n.dispatchEvent(new Event('input', {bubbles: true})); });
    await S.until(page, () => document.querySelectorAll('#story .card').length > 20);
    await page.click('[data-entry="19950"] .cardmain');
    await S.until(page, () => /STEP #200 · HISTORY/.test(document.querySelector('.stagepill').textContent));
    assert.equal(await page.$eval('#story .card[aria-current="true"] .cardmain', b => b.dataset.jump), '200');
    const before = await page.$$eval('#story .card', n => n.length);
    await page.$eval('#story li.more:last-of-type button', b => b.click());
    await S.until(page, n => document.querySelectorAll('#story .card').length > n, before);
    await page.click('#backlive');
    await S.until(page, () => /LIVE/.test(document.querySelector('.stagepill').textContent));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('the timeline has four lanes, and an alert is the same thing on the timeline and in the story', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelectorAll('.mark-memory line.brief').length === 7);
    assert.deepEqual(await page.$$eval('.tlmarks > g', g => g.map(x => x.getAttribute('class'))), ['lane-bg', 'mark-actor', 'mark-context', 'mark-memory', 'mark-alert']);
    assert.equal(await page.$$eval('.mark-actor rect', n => n.length), 2, 'two actors');
    assert.equal(await page.$$eval('.mark-actor line.handoff', n => n.length), 1, 'one handoff divider');
    assert.deepEqual(await page.$$eval('.tlactors span', n => n.map(x => x.textContent)), ['001', '002']);
    assert.deepEqual(await page.$$eval('.mark-context line', n => n.map(x => x.getAttribute('class'))), ['covered', 'covered', 'covered', 'covered', 'uncovered']);
    assert.deepEqual(await page.$$eval('.mark-context rect.wait', n => n.map(x => x.classList.contains('active'))), [false, true]);
    assert.equal(await page.$$eval('.mark-memory line.quiet', n => n.length), 1, 'the empty-suppressed delivery is muted');
    assert.equal(await page.$$eval('.mark-memory line.dot', n => n.length), 7, 'reads and agenda calls are dots');
    assert.match(await flat(page, '#tl-legend'), /^Actors 2 Cuts 5 \(1 uncovered\) Waits 2 Memory 8 Reads 7 Alerts \d+$/);
    const shared = await page.evaluate(async () => {
      const {isAlertEntry} = await import('/app/continuity.js');
      const {store} = await import('/app/data.js');
      const found = store.feed.filter(isAlertEntry);
      return {total: found.length, failed: found.filter(e => e.entry_kind === 'step').map(e => e.seq),
        judged: [['step', 'error'], ['step', 'refused'], ['step', 'ok'], ['finding', null, 'stall'], ['finding', null, 'handoff'], ['context_cut'],
          ['knowledge_delivery', null, null, 'refused'], ['knowledge_delivery', null, null, 'update']]
          .map(([entry_kind, status, finding_kind, delivery_kind]) => isAlertEntry({entry_kind, status, finding_kind, delivery_kind}))};
    });
    assert.deepEqual(shared.failed, [12]);
    assert.deepEqual(shared.judged, [true, true, false, true, false, false, true, false]);
    const lane = await page.$$eval('.mark-alert line', n => n.length);
    assert.equal(lane, shared.total + 1, 'every alert of the story, and the spend reserve');
    assert.equal(Number(await page.$eval('#story-alerts .n', n => n.textContent)), shared.total);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Working state: the agenda as of the playhead, what a handoff carried, and the version held then', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1160, height: 860});
  try {
    await S.ready(page);
    // Above the fold at 1160 × 860: the stage, the timeline and the dock.
    assert.ok(await page.$eval('#agenda-dock', n => n.getBoundingClientRect().top < innerHeight), 'the dock is above the fold');
    assert.ok(await page.$eval('#story', n => n.getBoundingClientRect().left > document.querySelector('.player').getBoundingClientRect().right), 'two columns');
    const dock = () => flat(page, '#agenda-dock');
    await S.until(page, () => /PAUSED Secure the shelter/.test(document.getElementById('agenda-dock').innerText.replace(/\s+/g, ' ')));
    assert.match(await dock(), /as of step \d+ · last change #130 v6 → Memory ACTIVE Make a fire ring PAUSED Secure the shelter$/);
    await scrub(page, 10);
    await S.until(page, () => /Agenda empty/.test(document.getElementById('agenda-dock').innerText));
    assert.match(await dock(), /as of step 10 v1 → Memory Agenda empty \(0 threads · 0 cuts\)$/);
    await scrub(page, 60);
    await S.until(page, () => /last change #50/.test(document.getElementById('agenda-dock').innerText));
    assert.match(await dock(), /v2 → Memory ACTIVE Secure the shelter DONE Find a water source$/);
    await scrub(page, 80);
    await S.until(page, () => document.getElementById('dock-carried'));
    assert.match(await text(page, '#dock-carried'), /^carried at handoff #75 · 001 → 002$/);
    assert.equal(await page.$$eval('#agenda-threads .tag.carry', n => n.length), 2);
    await scrub(page, 95);
    await S.until(page, () => !document.getElementById('dock-carried') && /Make a fire ring/.test(document.getElementById('agenda-dock').innerText));
    await page.click('#dock-version');
    await S.until(page, () => location.hash === '#memory?version=v2');
    // A run whose player never used its agenda says so.
    await S.pick(page, 'aidA1');
    await go(page, '#watch');
    await S.until(page, () => /player_agenda unused/.test(document.getElementById('agenda-dock')?.innerText || ''), null, 15000);
    assert.match(await text(page, '#agenda-empty'), /^Agenda empty \(0 threads · 0 cuts\) — player_agenda unused$/);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Step Inspector: opens by button or key, sits below the bar, shows the agenda at the request, loads the context on request', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1440});
  try {
    await S.ready(page);
    assert.equal(await page.$('#inspector'), null);
    await page.click('#story .card.step .inspect');
    await S.until(page, () => document.activeElement?.classList.contains('drawerclose'));
    const body = await text(page, '#inspector');
    for (const value of ['player claim', 'computer_input', 'delivered', 'Operation completed; application effect is not certified', 'Uncached input', 'Cache read', 'Cache write', 'Output tokens', '$0.01', 'endpoint-', 'request-', 'call-', 'Source', 'Service tier'])
      assert.ok(body.toLowerCase().includes(value.toLowerCase()), value);
    assert.match(await flat(page, '#inspect-agenda'), /Agenda at this request player claim player_agenda paused Secure the shelter active Make a fire ring Last changed at step 130 \(clear completed\)\./i);
    assert.match(await text(page, '#inspect-arguments'), /"key": "ENTER"/);
    const asked = async () => (await fx.state()).view_requests.filter(r => /\/context\//.test(r)).length;
    const before = await asked();
    assert.equal(await page.$('[data-context]'), null, 'the context is fetched only on request');
    // The drawer covers the story only: the bar, Pause and the stage stay in view and usable.
    const clear = await page.evaluate(() => {
      const drawer = document.getElementById('inspector').getBoundingClientRect(), bar = document.querySelector('header.ctl').getBoundingClientRect(), stage = document.querySelector('.player').getBoundingClientRect();
      return drawer.top >= bar.bottom && drawer.left >= stage.right;
    });
    assert.ok(clear);
    await page.evaluate(() => scrollTo(0, 400));
    assert.ok(await page.evaluate(() => document.getElementById('inspector').getBoundingClientRect().top >= document.querySelector('header.ctl').getBoundingClientRect().bottom), 'still below the bar when scrolled');
    await page.click('#load-context');
    await S.until(page, () => document.querySelector('[data-context] .ctx-bar span'));
    assert.equal(await asked(), before + 1);
    assert.match(await text(page, '[data-context]'), /reconstructed|exact: replayed/);
    assert.ok(await page.$eval('[data-context] .ctx-bar span', n => n.style.width.endsWith('%')), 'widths set through the style object');
    await page.click('#inspector [aria-label="Previous entry"]');
    await S.until(page, () => !document.querySelector('[data-context]') && /HISTORY/.test(document.querySelector('.stagepill').textContent));
    await page.keyboard.press('Escape');
    await S.until(page, () => !document.getElementById('inspector'));
    await page.evaluate(() => document.activeElement && document.activeElement.blur());
    await page.keyboard.press('i');
    await S.until(page, () => document.getElementById('inspector'));
    await page.keyboard.press('Escape');
    await S.until(page, () => !document.getElementById('inspector'));
    // A source re-read names the real frame and the alias the player saw.
    await page.click('#story-agenda');
    await S.until(page, () => document.querySelector('[data-entry="3010"] .inspect'));
    await page.click('[data-entry="3010"] .inspect');
    await S.until(page, () => document.getElementById('inspect-source'));
    assert.match(await flat(page, '#inspect-source'), /Real frame 725598848e982c67bae7e80129b51f78-12 Player saw player saw as s01 Origin ancestor/);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Memory: a facts-only head opens on World State, with the full version chain and the recorded delivery', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#memory`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('#kb-state .stategroup'));
    assert.equal(await page.$eval('#app section[data-view]', n => n.getAttribute('aria-label')), 'Memory');
    assert.equal(await page.$eval('#kb-view-state', b => b.getAttribute('aria-pressed')), 'true', 'never opens on an empty view');
    assert.match(await flat(page, '#kb-view-articles'), /^Articles 0$/);
    assert.equal(await page.$eval('#kb-view-articles', b => b.disabled), false, 'Articles (0) stays selectable');
    // The chain: every version, as the files, the publications and the trace say.
    assert.deepEqual(await page.$$eval('#versions .vpill', n => n.map(v => [v.querySelector('b').textContent, v.querySelector('.vstat').textContent])), [
      ['v1', 'Delivered #2 · opening briefing'], ['v2', 'Delivered #60 · live delta'], ['v3', 'Adopted (empty-suppressed)'], ['v4', 'Refused'],
      ['v5', 'Superseded'], ['v6', 'Delivered #170 · live delta'], ['v7', 'Exported (not delivered)'], ['v8', 'Published only']]);
    assert.equal(await page.$eval('#versions [aria-current="true"] b', n => n.textContent), 'v7', 'the latest exported version by default');
    assert.match(await flat(page, '#delivery-diff'), /^UNDELIVERED v7 undelivered after v6 Jump to step #215 Delivery did not reach the player/i);
    // World state by key, with the readings that replaced one another, and the anchors.
    assert.deepEqual(await page.$$eval('#kb-state .stategroup', n => n.map(g => g.dataset.stateKey)), ['water-course', 'shelter-door', 'food-cache']);
    const water = await flat(page, '[data-state-key="water-course"]');
    assert.match(water, /water-course 2 readings current The stream is frozen over\. state When: while it is below zero Frame #150 also A stream runs past the east wall\./);
    assert.match(water, /Replaced: fact-water2@v5 \(changed\) → fact-water3/);
    assert.match(await flat(page, '#kb-anchors'), /Anchors East wall 3 facts water-course shelter-door Cellar 1 fact food-cache/);
    // A frame another admission recorded names that run and opens it at its step.
    assert.match(await flat(page, '[data-state-key="food-cache"] .fanchor.cross'), /ceil08 · step #12 Open in ceil08/);
    assert.ok(await page.$('[data-state-key="food-cache"] img.thumb'), 'a thumbnail of the cited frame');
    // Recorded quality, the statement kinds and a calm tag bar.
    assert.match(await flat(page, '#kb-quality'), /^8 facts · 3 state keys · when 25% · 0 stale · 0 contested · 0 unverified · 1 needs review$/);
    assert.deepEqual(await page.$$eval('[data-kind-pill]', b => b.map(x => x.textContent.replace(/\s+/g, ' ').trim())), ['state 4', 'observation 1', 'outcome 1', 'synthesis 1', 'inference 1']);
    assert.equal(await page.$$eval('#kb-tags > .factpill', n => n.length), 6);
    assert.match(await text(page, '#kb-tags .moretags summary'), /^\+3 tags$/);
    assert.ok(await page.$eval('#kb-tags', n => n.scrollHeight <= 32), 'the tag bar is one line');
    await page.click('[data-kind-pill="outcome"]');
    await S.until(page, () => document.querySelector('#kb-view-facts .n')?.textContent === '1');
    assert.ok((await fx.state()).view_requests.some(r => /delivered-knowledge\?.*&kind=outcome&/.test(r)), 'the kind is asked of the viewer');
    await page.click('[data-kind-pill="outcome"]');
    await page.click('#kb-scope-world');
    await S.until(page, () => document.querySelector('#kb-view-facts .n')?.textContent === '4');
    await page.click('#kb-scope-all');
    // The head delivery's recorded changes, never a diff made in the page.
    await go(page, '#memory?version=v6');
    await S.until(page, () => /Live delta/i.test(document.getElementById('delivery-diff')?.innerText || '') && document.querySelector('#delta-preview'));
    assert.deepEqual(await page.$$eval('#delta-counts .tag', n => n.map(t => t.dataset.bucket)), ['state_changes', 'flag_changes', 'added_facts', 'claim_updates']);
    await page.$eval('#delta-preview', d => { d.open = true; });
    assert.match(await flat(page, '#delta-preview'), /state changes The stream is frozen over\. water-course added facts An earlier admission cached food in the cellar\./);
    await page.click('#delivery-jump');
    await S.until(page, () => location.hash === '#watch' && /STEP #170/.test(document.querySelector('.stagepill')?.textContent || ''));
    await go(page, '#memory?version=v3');
    await S.until(page, () => /Adopted \(empty-suppressed\)/i.test(document.getElementById('delivery-diff')?.innerText || ''));
    assert.match(await flat(page, '#delivery-diff'), /No substantive changes/);
    await go(page, '#memory?version=v5');
    await S.until(page, () => /superseded before it was delivered/.test(document.getElementById('delivery-diff')?.innerText || ''));
    // The ancestor's frame opens that admission at its step.
    await go(page, '#memory?version=v6');
    await S.until(page, () => document.querySelector('[data-state-key="food-cache"] [data-open-run]'));
    await page.click('[data-state-key="food-cache"] [data-open-run]');
    await S.until(page, session => document.getElementById('runpick').value === session && location.hash === '#watch'
      && /STEP #12 · RECORDED/.test(document.querySelector('.stagepill')?.textContent || ''), S.SESSIONS.ceil08, 20000);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Memory: articles, facts, citations and a frame that opens Watch', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#memory?version=v2`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('#versions [aria-current="true"] b')?.textContent === 'v2' && document.querySelector('[data-reading]'));
    assert.equal(await page.$eval('#kb-view-articles', b => b.getAttribute('aria-pressed')), 'true', 'a version with articles opens on them');
    assert.match(await flat(page, '#delivery-diff'), /LIVE DELTA v2 delivered after v1 Jump to step #60 1 corrections · 2 state changes · 3 added facts · 1 article changes/i);
    assert.match(await text(page, '[data-reading="article-water"]'), /this world scope[\s\S]*#water[\s\S]*Finding water in one sentence\.[\s\S]*Last confirmed/);
    await page.$$eval('#kb-items .item', items => items[1].click());
    await S.until(page, () => document.querySelector('[data-reading="article-fire"] [data-links] .factpill'));
    await page.click('[data-reading="article-fire"] [data-links] .factpill');
    await S.until(page, () => document.activeElement?.dataset.reading === 'article-water');
    await page.$$eval('#kb-items .item', items => items[1].click());
    await S.until(page, () => document.querySelector('[data-reading="article-fire"] .refs .factpill'));
    await page.click('[data-reading="article-fire"] .refs .factpill');
    await S.until(page, () => document.activeElement?.dataset.reading === 'fact-fire');
    assert.ok((await text(page, '[data-reading]')).includes('<script>window.knowledgeExecuted=true</script>'));
    assert.equal(await page.evaluate(() => window.knowledgeExecuted), undefined);
    await page.click('#kb-view-facts');
    await S.until(page, () => document.querySelectorAll('#kb-items .item').length === 4);
    await page.$$eval('#kb-items .item', items => items[3].click());
    await S.until(page, () => document.querySelector('[data-reading="fact-old"]'));
    const old = await text(page, '[data-reading]');
    for (const pattern of [/contested/, /unverified branch/, /needs review/, /Contradicted by\s*fact-water/, /Stale citations: fact-gone/, /Frame unavailable/, /no cited frame of this run/,
      /When: while the passage is open/, /State key: shelter-state/, /Anchor: Stream/, /Replaces fact-shelter-before \(changed\)/, /08:45 \(2 steps earlier\)/])
      assert.match(old, pattern);
    await page.click('#kb-search');
    await page.type('#kb-search', 'lighter');
    await S.until(page, () => document.querySelectorAll('#kb-items .item').length === 1);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'kb-search');
    await S.until(page, () => document.querySelector('[data-reading="fact-fire"] [data-jump-seq]'));
    await page.click('[data-reading="fact-fire"] [data-jump-seq]');
    await S.until(page, () => location.hash === '#watch' && /STEP #90 · HISTORY/.test(document.querySelector('.stagepill')?.textContent || ''));
    await S.until(page, () => /^step 90 /.test(document.getElementById('feed-meta').textContent));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Memory: Usage & Claims shows reads, the source alias with the real run, hints, finishes and the carried agenda', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#memory/usage`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => [...(document.querySelector('[data-reader-actor]')?.options || [])].some(o => o.value === 'actor-1'));
    await page.select('[data-reader-actor]', 'actor-1');
    await S.until(page, () => document.querySelector('[data-call="player_source"]'));
    await page.evaluate(() => { for (const d of document.querySelectorAll('.knowledge-reader details')) d.open = true; });
    const source = await flat(page, '[data-call="player_source"]');
    assert.match(source, /player_source \(source re-read\) · finished · request-30 · player saw as s01/);
    assert.match(source, /Source re-read: 725598848e982c67bae7e80129b51f78-12 · player saw as s01 non-clickable/);
    assert.match(source, /Original frame \(ceil08\)/, 'the anchor names the real run');
    assert.ok(await page.$('[data-call="player_knowledge_query"]') && await page.$('[data-call="player_knowledge_read"]'));
    assert.match(await flat(page, '.knowledge-reader'), /Player finish claims \(unverified\)/);
    await S.until(page, () => document.querySelector('[data-carried-agenda]'));
    assert.match(await flat(page, '.handoff-detail'), /Handoff at step 75 .*Carried agenda player claim player_agenda done Find a water source active Secure the shelter/i);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('a run without a trace is an honest blank in Memory and Curator, and its bar shows only what it has', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#memory`, {width: 900});
  try {
    await S.ready(page);
    await S.pick(page, 'aidA1');
    await S.until(page, () => document.getElementById('knowledge-empty'));
    assert.match(await text(page, '#knowledge-empty'), /^No delivered knowledge for this run\.$/);
    // The bar shows a run's figures once its own summary has arrived, which Memory does not wait for.
    await S.until(page, () => /\$1\.64/.test(document.getElementById('pill-spend')?.innerText || ''));
    assert.equal(await page.$('#pill-curator, #pill-context'), null);
    assert.match(await flat(page, '#pill-spend'), /^(Spend )?\$1\.64 \*$/, 'the receipt\'s player figure, partial without curator and grooming');
    await page.click('[data-nav="curator"]');
    await S.until(page, () => document.getElementById('curator-empty'));
    assert.match(await text(page, '#curator-empty'), /^No curator data for this run\.$/);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Curator: operations, sessions with a detail drawer, honest limits and run-filtered verdicts', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#curator`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelectorAll('#cur-sessions tbody tr').length === 5);
    assert.equal(await page.$eval('#app section[data-view]', n => n.getAttribute('aria-label')), 'Curator');
    assert.match(await flat(page, '#cur-runner'), /Coverage & runner polling curator-runner-status\/2 Cadence 20 \/ 60 steps Lag 20 operations Backlog 20 steps Latest version v7 → Memory Confirmed v6 → Memory/);
    assert.match(await flat(page, '#cur-spend'), /\$1\.23 proxy-accounted · 4\/5 settled incomplete Ingestion \$0\.98 · 3 sessions Interleaved hygiene \$0\.25 · 2 sessions Hygiene share 20\.6% Tiers applied flex 4 · default 1 Flex 429 deferrals 1/);
    assert.match(await flat(page, '#cur-limits'), /^Run cap \$5\.00 Session cap \$1\.00 Service tier flex Deferral limit 3 Hygiene share cap 40%$/);
    assert.match(await flat(page, '#cur-hygiene'), /2 passes 1 consecutive failures · 1 failed in all Enabled yes Host wall watch 7 m 00 s Pass cap \$0\.20/);
    // The sessions table is above the fold.
    assert.ok(await page.$eval('#cur-sessions', n => n.getBoundingClientRect().top < innerHeight));
    const deferred = await flat(page, '[data-session="session-h-002-1"]');
    assert.match(deferred, /h-002-1 Hygiene text only 56 s \$0\.13 default 1 deferral 429 · 200 1 unchanged none flex-capacity-deferred \(failed\)/);
    await page.click('[data-session="session-h-002-1"] button.link');
    await S.until(page, () => location.hash === '#curator?csess=session-h-002-1' && document.querySelector('#cur-ledger table'));
    const drawer = await flat(page, '#cur-session-drawer');
    for (const pattern of [/Tokens prompt 36,000/, /Tool calls Calls 14 Failed 1/, /knowledge_query 6/, /Sandbox Stopped flex-capacity-deferred/, /HTTP 429 · 200/])
      assert.match(drawer, pattern);
    assert.match(await flat(page, '#cur-ledger'), /6 rows, 2 not shown\./);
    assert.ok(await page.evaluate(() => document.getElementById('cur-session-drawer').getBoundingClientRect().top >= document.querySelector('header.ctl').getBoundingClientRect().bottom), 'below the bar');
    await page.keyboard.press('Escape');
    await S.until(page, () => location.hash === '#curator' && !document.getElementById('cur-session-drawer'));
    // The run's own verdicts and drafts, labelled as filtered from the lineage.
    await page.click('#cur-gates > summary');
    await S.until(page, () => document.querySelector('#cur-gates .run-filtered'));
    assert.match(await flat(page, '#cur-gates'), /Gate verdicts Filtered to this run's sessions \(2 of 7 lineage total\)/);
    assert.match(await flat(page, '#cur-gates'), /Drafts Filtered to this run's sessions \(1 of 5 lineage total\)/);
    assert.equal(await page.$eval('#cur-gates a[href="#runs/archive"]', a => a.textContent), 'All runs → Archive');
    await page.click('#cur-wal > summary');
    await S.until(page, () => document.querySelector('#cur-wal dl'));
    assert.match(await flat(page, '#cur-wal'), /Hold 12 ms Transaction 34 ms Staging 210 ms/);
    await page.click('#cur-grooming > summary');
    await S.until(page, () => document.getElementById('cur-grooming-none'));
    // An archived runner status records no limits: none are shown, and the grooming receipt of that admission is.
    await S.pick(page, 'ceil08');
    await S.until(page, () => document.getElementById('cur-limits-none'));
    assert.match(await text(page, '#cur-limits-none'), /^No configured limits recorded \(curator-runner-status\/1\)\.$/);
    assert.equal(await page.$('#cur-limits'), null);
    assert.match(await flat(page, '#cur-hygiene'), /consecutive failures not recorded/);
    await page.click('#cur-grooming > summary');
    await S.until(page, () => /Stale records 3/.test(document.getElementById('cur-grooming')?.innerText.replace(/\s+/g, ' ') || ''));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Diagnostics: four cards, honest spend parts, the context chart, costliest requests and clean metrics', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#diagnostics`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('.ctxchart canvas') && document.querySelector('.spendchart canvas') && document.querySelectorAll('table.data tbody tr').length > 2);
    assert.equal(await page.$eval('#app section[data-view]', n => n.getAttribute('aria-label')), 'Diagnostics');
    assert.deepEqual(await page.$$eval('.kpi', n => n.map(x => x.id)), ['kpi-spend', 'kpi-context', 'kpi-routing', 'kpi-custody']);
    const spend = await flat(page, '#kpi-spend');
    assert.match(spend, /^Loop spend \$\d\.\d\d player \+ curator partial recorded host trace player open curator incomplete Player provider-reported \$\d\.\d\d of \$5\.00/);
    assert.match(spend, /Curator ingestion proxy-accounted \$0\.98 Interleaved hygiene proxy-accounted \$0\.25 Curator total \$1\.23 · 4\/5 settled Boundary grooming proxy-accounted recorded outside admission Configured-rate estimate \$3\.98/);
    assert.doesNotMatch(spend, /recall|\$0\.00/i, 'no recall row on a run that made no recall request, and no silent zero');
    assert.match(await page.$eval('#kpi-spend [data-exact]', n => n.dataset.exact), /^\d\.\d{4}$/, 'the exact provider text is kept');
    assert.match(await flat(page, '#kpi-context'), /32\.8k tok p50 prompt · max 49\.9k · latest 35\.0k .*Cache hit share 93\.1% Applied cuts 5 · 4 covered · 1 uncovered \(#1037\) · 1 rescue Held back 2 Coverage waits 2 · longest \d+ s · peak 63\.2k tok · 1 holding now Tail notices 2 Knowledge deliveries 11 · head v6/);
    assert.match(await flat(page, '#kpi-routing'), /endpoint-a most responses .*Player tier default \d+ · flex \d+ Curator tier flex 4 · default 1 Requests \d+ player input latency p50 433 · p95 1698 ms/);
    assert.match(await flat(page, '#kpi-custody'), /2\.11 game h censored \(budget\) derived live The custodian writes its receipt when the run ends\. Evaluator core 4/);
    assert.match(await flat(page, '#ctx-legend'), /^5 applied cuts \(1 uncovered\) · 2 coverage waits · 1 handoff$/);
    // The sawtooth draws holds as bands, covered cuts teal, uncovered ones amber, and handoffs as dividers.
    const option = await page.evaluate(async () => {
      const {contextOption, spendOption} = await import('/app/charts.js');
      const requests = [0, 1, 2, 3].map(index => ({index, request_id: `r${index}`, seq: index + 1, wall: 100 + index, prompt_tokens: 1000 * (index + 1), cache_read: 400, reported_cost_usd: '0.5', estimated_dollars: 9}));
      const o = contextOption(requests, [{index: 1, tokens_before: 61400, tokens_after: 24800, removed_turns: 20, uncovered_turns: 0}, {index: 2, tokens_before: 61400, tokens_after: 24800, removed_turns: 20, uncovered_turns: 6}, {index: null}],
        [{start_index: 0, end_index: 2, requests: 3, active: false}, {start_index: 3, end_index: null, requests: 1, active: true}], [{index: 2}]);
      const s = spendOption(requests, 5, [{started_wall: 101.5, session_kind: 'hygiene', cost_usd: '0.1'}]);
      return [o.series.map(x => [x.name, x.data]), o.series[1].markLine.data.map(d => [d.xAxis, d.name]), o.series[0].markArea.data.map(([a, b]) => [a.xAxis, b.xAxis]),
        o.series[0].markLine.data, s.series[0].data.map(p => p[1]), s.series[0].markPoint.data.map(p => p.name), o.tooltip.formatter([{dataIndex: 2}])];
    });
    assert.deepEqual(option[0], [['Cache read', [400, 400, 400, 400]], ['Not cached', [600, 1600, 2600, 3600]]]);
    assert.deepEqual(option[1], [[1, 'covered'], [2, 'uncovered']]);
    assert.deepEqual(option[2], [[0, 2], [3, 3]], 'a coverage wait is a band, an open one to the last request');
    assert.deepEqual(option[3], [{xAxis: 2}], 'a handoff divider');
    assert.deepEqual(option[4], [0.5, 1, 1.5, 2], 'the provider figure, not the estimate');
    assert.deepEqual(option[5], ['total', 'curator hygiene']);
    assert.match(option[6], /uncovered cut: 61\.4k → 24\.8k \(20 turns, 6 uncovered\)[\s\S]*coverage wait: 3 requests held/);
    await page.$eval('.panel details', d => { d.open = true; });
    const results = await page.$eval('.panel details table.data', table => {
      const col = name => [...table.querySelectorAll('th')].findIndex(th => th.textContent === name);
      return [...table.querySelectorAll('tbody tr')].map(row => [row.cells[col('Result')].textContent, row.cells[col('Uncovered')].textContent]);
    });
    assert.deepEqual(results, [['target', '0'], ['rescue', '6'], ['target', '0'], ['target', '0'], ['best effort', '0']]);
    // The costliest requests come from the viewer's ranking over every request.
    await page.click('#more-requests > summary');
    await S.until(page, () => document.querySelector('#top-costliest tbody tr'));
    assert.match(await flat(page, '#top-costliest tbody tr:first-child'), /^request-100 #100 .* \$0\.2500 recorded provider$/);
    assert.equal(await page.$$eval('#top-costliest tbody tr', n => n.length), 15);
    // Every metric reads as words: a recorded object is never raw JSON, and core=4 metrics are grouped.
    await page.click('#more-metrics > summary');
    await S.until(page, () => document.querySelector('#more-metrics .dbody'));
    const metrics = await flat(page, '#more-metrics');
    assert.doesNotMatch(metrics, /\{|\}|"excluded"|null/);
    for (const pattern of [/Knowledge deliveries/, /Context uncovered cuts/i, /Agenda calls/i, /Source reads ancestor reads/i, /retry share .*none \(aborts 0|retry share[^·]*none/i])
      assert.match(metrics, pattern);
    const tools = await page.evaluate(async () => (await import('/app/continuity.js')).TOOL_LABELS);
    for (const tool of ['computer_input', 'computer_observe', 'computer_result', 'player_knowledge_query', 'player_knowledge_read', 'player_source', 'player_agenda', 'player_hint', 'player_handoff', 'player_finish'])
      assert.ok(tools[tool], `${tool} has a label`);
    await S.pick(page, 'aidA2');
    await S.until(page, () => /no host trace for this run/.test(document.getElementById('kpi-context')?.innerText || ''));
    assert.match(await flat(page, '#kpi-spend'), /— no provider-reported cost.*Player provider-reported Unavailable.*no session recorded.*recorded outside admission/i);
    assert.doesNotMatch(await text(page, '#kpi-spend'), /Spend reserve/);
    assert.match(await text(page, '#kpi-routing'), /answering endpoint not recorded/);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Diagnostics: each part of the spend keeps its basis, and a combined figure is whole only when every part is closed', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#diagnostics`, {width: 1440});
  const closedPlayer = {reported_cost_usd: '3.6427473', spent_usd: '3.6427473', spend_complete: true, unpriced_requests: 0, unpriced_recall_requests: 0};
  const closedCurator = {sessions_total: 2, sessions_settled: 2, sessions_unsettled: 0, spent_usd: '1.5', unsettled_requests: 0, spend_complete: true,
    ingestion_usd: '1.2', hygiene_usd: '0.3', hygiene_share: 0.2, ingestion_sessions: 1, hygiene_sessions: 1, applied_tiers: {flex: 2}, deferrals: 0};
  const groomed = {source_status: 'available', status: 'completed', reason: null, spent_usd: '0.36140535', spend_complete: true, published_before: 'v31', published_after: 'v33', stale_records: 0};
  const absent = {source_status: 'not_configured', status: null, reason: null, spent_usd: null, spend_complete: null, published_before: null, published_after: null, stale_records: null};
  let player, curator, grooming;
  try {
    await S.ready(page);
    await page.setRequestInterception(true);
    page.on('request', async request => {
      if (!/\/summary$/.test(new URL(request.url()).pathname)) return request.continue();
      const body = await (await fetch(request.url())).json();
      if (player !== undefined) Object.assign(body, {host_telemetry: player && {...body.host_telemetry, ...player}, curator_spend: curator, boundary_grooming: grooming});
      request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
    });
    const shows = async (p, c, g, big, partial, pattern) => {
      [player, curator, grooming] = [p, c, g];
      const want = {big, partial, pattern};
      await S.until(page, ({big, partial, pattern}) => document.querySelector('#kpi-spend .big').textContent === big && !!document.getElementById('spend-partial') === partial
        && new RegExp(pattern, 'i').test(document.getElementById('kpi-spend').innerText.replace(/\s+/g, ' ')), want);
    };
    await shows(closedPlayer, closedCurator, groomed, '$5.50', false, 'player \\+ curator \\+ boundary grooming .*Curator ingestion proxy-accounted \\$1\\.20 Interleaved hygiene proxy-accounted \\$0\\.30 .*Boundary grooming proxy-accounted \\$0\\.36 · completed');
    await shows(closedPlayer, closedCurator, absent, '$5.14', true, 'Boundary grooming proxy-accounted recorded outside admission');
    await shows(closedPlayer, closedCurator, {...absent, source_status: 'other_run'}, '$5.14', true, 'recorded outside admission');
    await shows(closedPlayer, closedCurator, {...absent, source_status: 'malformed'}, '$5.14', true, 'receipt unreadable');
    await shows(closedPlayer, closedCurator, {...groomed, spent_usd: null, spend_complete: false, status: 'failed'}, '$5.14', true, 'unavailable · failed');
    await shows(closedPlayer, closedCurator, {...groomed, spend_complete: false}, '$5.50', true, '\\$0\\.36 · completed · unsettled');
    await shows(closedPlayer, {...closedCurator, spent_usd: null, ingestion_usd: null, hygiene_usd: null, spend_complete: false, sessions_settled: 0}, groomed, '$4.00', true, 'Curator ingestion proxy-accounted Unavailable .*Curator total Unavailable · 0/2 settled');
    await shows(closedPlayer, {...closedCurator, hygiene_usd: null, hygiene_sessions: 0}, groomed, '$5.50', false, 'Interleaved hygiene proxy-accounted none · no hygiene pass');
    await shows(closedPlayer, null, groomed, '$4.00', true, 'Curator ingestion proxy-accounted no session recorded');
    await shows({...closedPlayer, spend_complete: false, unpriced_requests: 1}, closedCurator, groomed, '$5.50', true, 'player open .*Player subtotal provider-reported \\$3\\.64 .*Unpriced or in flight 1 player · 0 recall');
    await shows({...closedPlayer, recall_requests: 3}, closedCurator, groomed, '$5.50', false, 'player \\+ recall \\+ curator .*Player \\+ recall provider-reported \\$3\\.64');
    await shows({...closedPlayer, reported_cost_usd: null}, closedCurator, groomed, '—', true, 'no combined figure .*Player provider-reported Unavailable .*\\$1\\.50 .*\\$0\\.36');
    assert.doesNotMatch(await text(page, '#kpi-spend'), /\$0\.00/);
    // The bar shows an unavailable curator figure as that, never as nothing spent.
    await shows(closedPlayer, {...closedCurator, spent_usd: null, spend_complete: false}, absent, '$3.64', true, 'Unavailable');
    assert.match(await page.$eval('#pill-spend', n => n.title), /Curator ingestion: \$1\.20/);
    assert.match(await flat(page, '#pill-spend'), /^Spend \$3\.64 \*/);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

for (const [name, width, scheme, mobile] of [CONFIGS[0], CONFIGS[3]]) {
  test(`Diagnostics shows the selected recorded custodian receipt: ${name}`, {timeout: 30000}, async () => {
    const page = await openPage(`${fx.url}#diagnostics`, {width, scheme, mobile});
    try {
      await S.ready(page);
      await S.until(page, live => document.querySelector('#runpick')?.value === live && document.querySelector('#evaluation-note'), S.SESSIONS.ceil09);
      assert.equal(await text(page, '#evaluation-note'), 'live');
      assert.equal(await page.$('.custodian-receipt dl'), null);
      const pause = () => page.$eval('#pause', b => [b.textContent, b.disabled]);
      const before = await pause();
      await S.pick(page, 'aidA1');
      await S.until(page, () => document.querySelector('.custodian-receipt dl'));
      assert.equal(await text(page, '#evaluation-note'), 'final record');
      const facts = await page.$$eval('.custodian-receipt dd', rows => rows.map(row => row.textContent));
      assert.deepEqual(facts, ['Player reported external stop complete (unassessed)', 'Yes', 'Yes', 'Unavailable', 'No']);
      assert.equal(await S.overflow(page), 0);
      await S.shot(page, `custodian-receipt-${name}`);
      await S.pick(page, 'aidA2');
      await S.until(page, () => /Receipt unavailable for this run/.test(document.querySelector('.custodian-receipt')?.textContent || ''));
      assert.equal(await page.$eval('#runpick', el => el.value), S.SESSIONS.aidA2);
      assert.deepEqual(await pause(), before);
      assert.deepEqual(page.problems, []);
    } finally { await page.close(); }
  });
}

test('recorded Diagnostics shows exact provider cost, unpriced attempts and unavailable accounting', {timeout: 30000}, async () => {
  await fx.viewer('nolive');
  const page = await openPage(`${fx.url}recorded/#diagnostics`, {width: 390, mobile: true});
  try {
    const amount = name => page.$$eval('#kpi-spend .kv dt', (terms, name) => terms.find(term => term.firstChild.textContent.trim() === name)?.nextElementSibling.textContent.trim(), name);
    const waitFor = (name, value) => S.until(page, ([name, value]) => Array.from(document.querySelectorAll('#kpi-spend .kv dt')).some(term => term.firstChild.textContent.trim() === name
      && term.nextElementSibling.textContent.trim().startsWith(value)), [name, value]);
    await S.until(page, () => document.querySelector('#runpick')?.value);
    await S.pick(page, 'aidA1');
    await waitFor('Player + recall subtotal', '$1.64');
    assert.equal(await page.$eval('#kpi-spend [data-exact]', n => n.dataset.exact), '1.64493095');
    assert.match(await text(page, '#kpi-spend'), /custodian receipt/);
    assert.equal(await amount('Unpriced attempts'), '1 player · 1 recall');
    assert.match(await amount('Configured-rate estimate'), /^\$\d/);
    await S.pick(page, 'aidA3');
    await waitFor('Player', '$0.00');
    assert.equal(await page.$eval('#kpi-spend [data-exact]', n => n.dataset.exact), '0');
    assert.equal(await amount('Unpriced attempts'), undefined);
    await S.pick(page, 'aidA4');
    await waitFor('Player', 'Unavailable');
    assert.ok(await page.$('.custodian-receipt dl'));
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); await fx.viewer('up'); }
});

test('recorded viewer opens Watch and follows findings without a control path', {timeout: 30000}, async () => {
  await fx.viewer('stale-recorded');
  const page = await openPage('about:blank', {width: 390, mobile: true});
  const requests = [];
  page.on('request', request => requests.push([request.method(), new URL(request.url()).pathname]));
  try {
    await page.goto(`${fx.url}recorded/`, {waitUntil: 'load'});
    await S.until(page, () => document.querySelector('[data-view="watch"] #story .card') && document.querySelector('#feed:not([hidden])')?.width > 0);
    const first = await page.$eval('#runpick', el => el.value);
    assert.equal(first, S.SESSIONS.aidA1);
    assert.equal(await page.$('#pause, #sheet, #statusline, #frame, .ctl-frame, .ctl-left, #pausealert, #viewer-alert'), null);
    assert.match(await text(page, '.stagepill'), /^STEP #\d+ · RECORDED$/);
    assert.match(await text(page, '#feed-meta'), /^recorded step \d+ at .* · viewer · original frame · sha-256 checked/);
    assert.match(await text(page, '#story-source'), /No host trace is available for this run/);
    assert.ok(await page.$$eval('#story .card .pv.claim', n => n.length) === 0, 'no intent is invented');
    await go(page, '#diagnostics');
    await S.until(page, () => document.querySelector('#findings button[data-jump]') && document.querySelector('.custodian-receipt dl'));
    assert.equal(await text(page, '#evaluation-note'), 'evaluation unfinished');
    assert.equal(await page.$('#conds'), null, 'nothing to pause');
    const step = await page.$eval('#findings button[data-jump]', el => el.dataset.jump);
    await click(page, '#findings button[data-jump]');
    await S.until(page, seq => location.hash === '#watch' && document.querySelector('#playinfo')?.textContent.startsWith(`Step ${seq}`), step);
    assert.equal(await page.$eval('#runpick', el => el.value), first);
    assert.equal(await page.$eval('#backlive', el => el.textContent), 'Latest step');
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
    assert.ok(requests.some(([, p]) => p.startsWith(`/api/view/run/${S.SESSIONS.aidA1}/frame/`)));
    assert.deepEqual(requests.filter(([method, p]) => method !== 'GET' || /^\/api\/(?:status|source|pause)\b|\/app\/control\.js/.test(p)), []);
  } finally { await page.close(); await fx.viewer('up'); }
});

test('All runs: the lineage, its admissions read on request, and the stores the viewer skipped', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#runs/lineage`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('[data-lineage="ceiling-line"]'));
    assert.equal(await page.$eval('#app section[data-view]', n => n.getAttribute('aria-label')), 'All runs');
    assert.deepEqual(await page.$$eval('#runs-nav a', n => n.map(a => a.dataset.sub)), ['lineage', 'compare', 'explore', 'changes', 'failures', 'archive']);
    assert.match(await text(page, '#runs-skipped'), /^2 run stores from an older evaluator core are not listed\.$/);
    assert.equal(await flat(page, '[data-lineage="ceiling-line"]'), 'a01 → a02 → a03');
    assert.match(await flat(page, '.lineage:has([data-lineage="ceiling-line"])'), /Lineage ceiling-line 3 admissions · one live .*Cumulative game hours 2\.75/);
    assert.match(await flat(page, '.lineage:has([data-lineage="reflection-aid"])'), /a01 → a02 → a03 → a04 → a05 → a06/);
    const before = (await fx.state()).view_requests.filter(r => r.endsWith('/summary')).length;
    await page.click('#lineage-ceiling-line > summary');
    await S.until(page, () => document.querySelectorAll('#lineage-ceiling-line .lineage-table tbody tr').length === 3 && !/…/.test(document.querySelector('#lineage-ceiling-line').innerText));
    assert.ok((await fx.state()).view_requests.filter(r => r.endsWith('/summary')).length >= before + 3, 'each admission\'s summary is read once opened');
    const rows = await page.$$eval('#lineage-ceiling-line tbody tr', n => n.map(r => r.innerText.replace(/\s+/g, ' ').trim()));
    assert.match(rows[0], /^a01 · ceil07 final 0\.61 0\.61 ~\$\d\.\d\d est — none$/);
    assert.match(rows[2], /^a03 · ceil09 live 2\.11 2\.75 \$\d\.\d\d v6 2 threads$/);
    await page.click('#lineage-ceiling-line tbody tr:nth-child(2) button.link');
    await S.until(page, session => location.hash === '#watch' && document.getElementById('runpick').value === session, S.SESSIONS.ceil08);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('an episode anchor opens Watch at its step, and a container opens its manifest', {timeout: 60000}, async () => {
  const page = await openPage(`${fx.url}#runs/archive/episodes`, {scheme: 'light'});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('[data-anchor="observed"] button.btn'));
    assert.match(await page.$eval('#app', n => n.innerText), /frame unavailable/i);   // the text-only anchor and the uncatalogued run
    await page.click('[data-anchor="observed"] button.btn');
    await S.until(page, () => location.hash === '#watch');
    await S.until(page, () => { const back = document.getElementById('feed-back'); return back && back.disabled; });   // the playhead is on the first step
    await go(page, '#runs/archive/containers');
    await S.until(page, () => document.querySelector('#app table.data button.link'));
    await click(page, '#app table.data button.link');
    await S.until(page, () => /container-manifest\/1/.test(document.getElementById('app').innerText));
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('theme button switches tokens and keeps the page clean', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {scheme: 'light'});
  try {
    await S.ready(page);
    const before = await page.$eval('body', el => getComputedStyle(el).backgroundColor);
    await page.click('#theme');
    await S.settle(page, 500);
    assert.notEqual(before, await page.$eval('body', el => getComputedStyle(el).backgroundColor));
    assert.equal(await page.$eval('html', el => el.dataset.theme), 'dark');
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

for (const scheme of ['light', 'dark']) {
  test(`text tokens keep at least 4.5:1 contrast on their surfaces: ${scheme}`, {timeout: 30000}, async () => {
    const page = await openPage(`${fx.url}#watch`, {scheme});
    try {
      const low = await page.evaluate(() => {
        const style = getComputedStyle(document.documentElement);
        const rgb = name => { const p = document.createElement('i'); p.style.color = style.getPropertyValue(name); document.body.append(p); const c = getComputedStyle(p).color.match(/[\d.]+/g).map(Number); p.remove(); return c; };
        const light = c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
        const ratio = (a, b) => { const [x, y] = [light(rgb(a)), light(rgb(b))].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
        const pairs = [['--fg', '--bg'], ['--fg', '--surface'], ['--fg', '--raised'], ['--fg', '--accent-soft'], ['--muted', '--bg'], ['--muted', '--surface'], ['--muted', '--sunk'], ['--muted', '--accent-soft'], ['--muted', '--teal-soft'], ['--muted', '--violet-soft'],
          ['--muted', '--watch-soft'], ['--muted', '--alert-soft'], ['--quiet', '--surface'], ['--accent', '--surface'], ['--accent', '--accent-soft'], ['--watch', '--watch-soft'], ['--alert', '--alert-soft'], ['--ok', '--ok-soft'], ['--teal', '--teal-soft'],
          ['--violet', '--violet-soft'], ['--surface', '--violet'], ...['rec', 'read', 'calc', 'claim', 'human', 'ex'].map(k => [`--p-${k}`, `--p-${k}-soft`])];
        return pairs.map(([a, b]) => [a, b, +ratio(a, b).toFixed(2)]).filter(r => r[2] < 4.5);
      });
      assert.deepEqual(low, []);
    } finally { await page.close(); }
  });
}

test('no network origin is used: every request stays on the page origin', {timeout: 30000}, async () => {
  const page = await browser.newPage();
  const foreign = [];
  page.on('request', r => { if (!r.url().startsWith(fx.origin) && !r.url().startsWith('blob:') && !r.url().startsWith('data:')) foreign.push(r.url()); });
  await page.goto(`${fx.url}#watch`, {waitUntil: 'load'});
  await S.settle(page, 1500);
  await page.close();
  assert.deepEqual(foreign, []);
});

test('every module under web/app is reachable from the page, and none writes an inline style attribute', () => {
  const root = path.join(__dirname, '../web/app');
  const entries = [...fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8').matchAll(/src="\/app\/([\w.-]+\.js)"/g)].map(m => m[1]);
  const seen = new Set();
  const walk = name => {
    if (seen.has(name)) return;
    seen.add(name);
    for (const m of fs.readFileSync(path.join(root, name), 'utf8').matchAll(/from '\.\/([\w.-]+\.js)'/g)) walk(m[1]);
  };
  entries.forEach(walk);
  const modules = fs.readdirSync(root).filter(n => n.endsWith('.js')).sort();
  assert.deepEqual(modules, [...seen].sort());
  for (const name of modules) assert.doesNotMatch(fs.readFileSync(path.join(root, name), 'utf8'), /\sstyle=|setAttribute\(\s*['"]style/, `${name} writes a style attribute`);
  assert.doesNotMatch(fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8'), /\sstyle=/);
});

test('current hints stay unverified text', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 390, height: 900, mobile: true});
  const hint = {id: 'hint-visible', actor_id: 'a'.repeat(32), text: '<script>window.hintExecuted=true</script> An uncertain report',
    intent: 'Report what needs checking', cites: ['fact-visible'], source_ids: ['source-unverified']};
  try {
    await S.ready(page);
    page.on('request', request => {
      const value = new URL(request.url()).pathname.endsWith('/memory') ? {schema: 'spectator-view/4', available: true, store_schema: 'player-journal/1', records: [], hints: [hint], hints_omitted: 0} : null;
      if (value) request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(value)});
      else request.continue();
    });
    await page.setRequestInterception(true);
    await go(page, '#runs/archive/player');
    await S.until(page, () => document.getElementById('app').innerText.includes('An uncertain report'));
    const body = await page.$eval('#app', node => node.innerText);
    for (const value of ['unverified player reports', hint.text, hint.intent, 'fact-visible', 'source-unverified']) assert.ok(body.includes(value), value);
    assert.doesNotMatch(body, /No memory records|0 written/);
    assert.equal(await page.evaluate(() => window.hintExecuted), undefined);
    assert.ok((await fx.state()).view_requests.length >= 0);
    await S.shot(page, 'current-hints-phone');
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('recorded reader keeps delivery, reports, operation and outcome distinct on a phone', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#memory/usage`, {width: 390, height: 900, mobile: true});
  try {
    await S.ready(page);
    await S.until(page, () => [...(document.querySelector('[data-reader-actor]')?.options || [])].some(o => o.value === 'actor-1'));
    await page.select('[data-reader-actor]', 'actor-1');
    await S.until(page, () => document.getElementById('app').innerText.toLowerCase().includes('public hints (unverified)'));
    await page.select('[data-reader-request]', 'request-1');
    await S.until(page, () => document.querySelector('[data-reader-request]')?.value === 'request-1');
    await page.evaluate(() => { for (const d of document.querySelectorAll('.knowledge-reader details')) d.open = true; });
    let body = await page.$eval('.knowledge-reader', n => n.innerText);
    for (const expected of ['knowledge-delivery', 'Move carefully', 'fact-visible', 'The visible passage may be blocked',
      'Receipt disposition: delivered', 'I believe I am done', 'Evaluator outcome', 'Original frame']) assert.ok(body.toLowerCase().includes(expected.toLowerCase()), expected);
    const hits = await text(page, '.query-hits');
    assert.match(hits, /fact-visible · fact · The passage · state · fuzzy · needs review/);
    assert.match(hits, /State key: passage-state[\s\S]*Anchor: Entry[\s\S]*When: when the gate is open[\s\S]*Depiction: c6c09be0b7d43fba2839147651a4f6a5-2/);
    assert.match(hits, /<img src=x onerror=window\.hitExecuted=true>/);
    assert.equal(await page.$('.query-hits img'), null);
    assert.deepEqual(await page.$eval('.query-hits', list => [...list.querySelectorAll('li > button')].map(b => b.textContent)), ['fact-visible', 'article-passage']);
    assert.match(body, /resolution: state key/);
    await page.focus('.query-hits li > button');
    await page.keyboard.press('Enter');
    await S.until(page, () => document.getElementById('app').innerText.includes('Entry fact-visible'));
    await S.until(page, () => document.activeElement?.matches('[data-reader-entry] > summary'));
    assert.equal(await page.evaluate(() => window.readerExecuted), undefined);
    assert.equal(await page.evaluate(() => window.hitExecuted), undefined);
    assert.equal(await page.$eval('#pause', button => button.disabled), false);
    const entry = await text(page, '[data-reader-entry]');
    for (const expected of [/Kind: state · scope: world \(ruleset: standard\) · state: active · needs review · tags: passage/,
      /Links: see_also fact-other · cited frames: c6c09be0b7d43fba2839147651a4f6a5-2/, /Anchor: Entry/, /When: when the gate is open/,
      /Replaces passage-before \(changed\)/, /09:20 \(1 step earlier\)/, /Depiction c6c09be0b7d43fba2839147651a4f6a5-2 · 09:20/])
      assert.match(entry, expected);
    assert.doesNotMatch(entry, /source IDs/, 'a current entry names its frames only as citations');
    assert.equal(await S.overflow(page), 0);
    await S.shot(page, 'recorded-reader-phone');
    await page.select('[data-reader-actor]', 'actor-2');
    await S.until(page, () => document.getElementById('app').innerText.includes('Public journal unavailable.'));
    body = await page.$eval('.knowledge-reader', n => n.innerText);
    assert.doesNotMatch(body, /Entry fact-visible/);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('recorded reader refreshes actors and public reports while staying on the page', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#memory/usage`, {width: 390, height: 900, mobile: true});
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/spectator/knowledge.json'), 'utf8'));
  let phase = 0, emptySeen = false;
  try {
    await page.setRequestInterception(true);
    page.on('request', r => {
      const url = new URL(r.url());
      if (!url.pathname.endsWith('/knowledge')) { r.continue(); return; }
      let body;
      if (!url.searchParams.get('actor')) {
        emptySeen ||= phase === 0;
        body = {schema: 'spectator-view/4', actors: phase ? fixture.actors : [], actors_omitted: 0, actor: null, request_id: null};
      } else {
        body = structuredClone(fixture);
        if (phase === 2) { body.hints[0].text = 'A later public hint'; body.requests.push('request-2'); }
      }
      r.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
    });
    await page.reload({waitUntil: 'load'});
    await S.ready(page);
    await S.until(page, () => !!document.querySelector('[data-reader-actor]'));
    assert.equal(emptySeen, true);
    assert.deepEqual(await page.$$eval('[data-reader-actor] option', ns => ns.map(n => n.value)), ['']);
    phase = 1;
    await S.until(page, () => [...(document.querySelector('[data-reader-actor]')?.options || [])].some(o => o.value === 'actor-1'));
    await page.select('[data-reader-actor]', 'actor-1');
    await S.until(page, () => document.getElementById('app').innerText.includes('The visible passage may be blocked'));
    phase = 2;
    await S.until(page, () => document.getElementById('app').innerText.includes('A later public hint'));
    assert.ok(await page.$$eval('[data-reader-request] option', ns => ns.some(n => n.value === 'request-2')));
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('All runs Archive opens configured draft manifests and gate results with the keyboard', {timeout: 30000}, async () => {
  const page = await S.open(browser, `${fx.url}#watch`, {width: 390, height: 900, mobile: true});
  const markup = '<img src=x onerror=window.curatorExecuted=true>';
  const active = {id: 'open-draft', bucket: 'active', state: 'open', untouched_sessions: 2,
    created_by_session: markup, last_touched_session: 'session-2', promoted_by_session: null,
    sessions: {items: ['session-1', 'session-2'], omitted: 0, values_omitted: 0}, max_bytes: 4096, retention_policy: 'retained'};
  const archived = {...active, id: 'promoted-draft', bucket: 'archived', state: 'promoted', promoted_by_session: 'session-3'};
  const gate = {index: 0, operation_id: 'b'.repeat(32), operation: 'submission', status: 'published', base_version: 'v1',
    restored_from: null, version: 'v2', submission: markup, session: 'session-3', from_drafts: [archived.id],
    from_drafts_omitted: 1, diagnostics: []};
  const schema = 'spectator-view/4';
  const sources = {schema, items: [{label: 'fixture'}], total: 1, next: null, limit: 500};
  let digest = 'a'.repeat(64);
  const pages = [];
  try {
    await S.ready(page);
    await page.evaluate(() => { window.curatorPauseButton = document.getElementById('pause'); });
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      const route = url.pathname.split('/').at(-1);
      let body, status = 200;
      if (route === 'draft-sources' || route === 'result-sources') body = sources;
      if (route === 'drafts') {
        const after = +url.searchParams.get('after'), snapshot = url.searchParams.get('snapshot');
        pages.push({after, snapshot});
        if (snapshot && snapshot !== digest) {
          status = 409;
          body = {schema, error: 'source_changed', detail: ''};
        } else {
          body = {schema, source: 'fixture', source_status: 'available', snapshot: {sha256: digest, bytes: 300},
            items: [after ? archived : active], total: 26, next: after ? null : 25, limit: 25};
        }
      }
      if (route === 'results') body = {schema, source: 'fixture', source_status: 'available', snapshot: {sha256: digest, bytes: 100},
        items: [gate], total: 1, next: null, limit: 25};
      if (body) return request.respond({status, contentType: 'application/json', body: JSON.stringify(body)});
      return request.continue();
    });
    await page.click('#all-runs-btn');
    await go(page, '#runs/archive');
    const nav = '#archive-nav';
    const drafts = '[data-curator-draft-source]';
    const row = '.curator-source-view button.link';
    const press = async selector => { await page.focus(selector); await page.keyboard.press('Enter'); };
    const button = async name => {
      await page.evaluate(n => Array.from(document.querySelectorAll('.curator-source-view button')).find(b => b.textContent === n).focus(), name);
      await page.keyboard.press('Enter');
    };
    await page.waitForSelector(`${nav} a[href="#runs/archive/curator-drafts"]`);
    assert.match(await text(page, '.curator-records'), /Operator curator sources cover the whole lineage/);
    assert.equal(await page.$(`${nav} a[href="#runs/archive/sessions"]`), null, 'an unconfigured source stays hidden');
    await press(`${nav} a[href="#runs/archive/curator-drafts"]`);
    await page.waitForSelector(drafts);
    await S.until(page, () => Array.from(document.querySelector('[data-curator-draft-source]')?.options || []).some(o => o.value === 'fixture'));
    await page.focus(drafts);
    await page.keyboard.press('ArrowDown');
    await S.until(page, () => document.querySelector('[data-curator-draft-status]')?.textContent.includes('available'));
    await S.until(page, () => document.querySelector('.curator-source-view button.link'));
    await press(row);
    await S.until(page, () => document.activeElement?.hasAttribute('data-curator-draft-detail'));
    assert.match(await text(page, '.curator-source-view table'), /open-draft\s+Active\s+open\s+2/);
    assert.match(await text(page, '.curator-source-view'), /Snapshot SHA-256: a{64} · 300 manifest bytes/);
    const detail = await text(page, '[data-curator-draft-detail]');
    assert.ok(detail.includes(markup) && detail.includes('session-2') && detail.includes('session-1, session-2'));
    assert.equal(await page.$('[data-curator-draft-detail] img'), null);
    digest = 'c'.repeat(64);
    await button('Next drafts');
    await S.until(page, () => document.querySelector('[data-curator-draft-error]')?.textContent.includes('Source changed'));
    assert.deepEqual(pages.at(-1), {after: 25, snapshot: 'a'.repeat(64)});
    assert.equal(await page.$('.curator-source-view table'), null);
    await button('Refresh drafts');
    await S.until(page, () => document.querySelector('.curator-source-view table'));
    assert.equal(await page.$eval(drafts, n => document.activeElement === n), true);
    await button('Next drafts');
    await S.until(page, () => document.querySelector('.curator-source-view table')?.textContent.includes('promoted-draft'));
    assert.deepEqual(pages.at(-1), {after: 25, snapshot: digest});
    await press(row);
    assert.match(await text(page, '.curator-source-view table'), /promoted-draft\s+Archived\s+promoted/);
    assert.match(await text(page, '[data-curator-draft-detail]'), /Promoted by session\s+session-3/);
    await press(`${nav} a[href="#runs/archive/results"]`);
    await page.waitForSelector('[data-curator-source]');
    await page.select('[data-curator-source]', 'fixture');
    await S.until(page, () => document.querySelector('.curator-source-view button.link'));
    await press(row);
    await S.until(page, () => document.activeElement?.hasAttribute('data-curator-detail'));
    assert.match(await text(page, '[data-curator-detail]'), /From drafts\s+promoted-draft · 1 more omitted/);
    assert.equal(await page.$('[data-curator-detail] img'), null);
    assert.equal(await page.evaluate(() => window.curatorExecuted), undefined);
    assert.equal(await S.overflow(page), 0);
    assert.equal(await page.$eval('#pause', n => n === window.curatorPauseButton && !n.disabled), true);
    assert.equal(await page.$eval('#frame', n => !n.hidden && n.naturalWidth > 0), true);
    await press('#pause');
    await S.until(page, () => !document.getElementById('sheet').hidden);
    await press('#sheetcancel');
    await S.until(page, () => document.getElementById('sheet').hidden);
    assert.deepEqual(page.problems.filter(p => p !== 'http 409: /api/view/curator-sources/drafts'), []);
  } finally { await page.close(); }
});

test('curator results select and show escaped recorded detail on a phone', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 390, height: 900, mobile: true});
  const digest = 'a'.repeat(64);
  const row = {index: 0, operation_id: 'b'.repeat(32), operation: 'submission', status: 'unknown', base_version: 'v1',
    restored_from: null, version: null, submission: '<img src=x onerror=window.curatorExecuted=true>', session: 'session',
    diagnostics: ['<b>recorded diagnostic'], diagnostics_omitted: 0};
  try {
    await S.ready(page);
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      const body = url.pathname.endsWith('/curator-sources/result-sources') ? {schema: 'spectator-view/4', items: [{label: 'fixture'}], total: 1, next: null, limit: 500}
        : url.pathname.endsWith('/curator-sources/results') ? {schema: 'spectator-view/4', source: 'fixture', source_status: 'available', snapshot: {sha256: digest, bytes: 123}, items: [row], total: 1, next: null, limit: 25} : null;
      if (body) request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
      else request.continue();
    });
    await go(page, '#runs/archive/results');
    await S.until(page, () => Array.from(document.querySelector('[data-curator-source]')?.options || []).some(o => o.value === 'fixture'));
    await page.select('[data-curator-source]', 'fixture');
    await S.until(page, () => document.querySelector('.curator-source-view table.data button.link'));
    await page.focus('.curator-source-view table.data button.link');
    await page.keyboard.press('Enter');
    await S.until(page, () => document.querySelector('[data-curator-detail]'));
    const body = await page.$eval('[data-curator-detail]', n => n.innerText);
    assert.match(body, /unknown/); assert.ok(body.includes(row.submission)); assert.ok(body.includes(row.diagnostics[0]));
    assert.equal(await page.evaluate(() => window.curatorExecuted), undefined);
    assert.equal(await S.overflow(page), 0);
    await S.until(page, () => document.activeElement?.hasAttribute('data-curator-detail'));
    await S.shot(page, 'curator-results-phone');
    await page.select('[data-curator-source]', '');
    await S.until(page, () => !document.querySelector('[data-curator-detail]'));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('curator runner status shows a present, a missing and a partly written file as such', {timeout: 60000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 390, height: 900, mobile: true});
  const place = (step, ordinal) => ({actor: 'actor-a', step, operation: `op-${step}`, ordinal});
  const walls = {began: 1700000000, ended: 1700000001};
  const stamp = {session: 'run', actor: 'actor-a', last_step: 25};
  const unknownRow = Object.fromEntries(['label', 'window', 'session_id', 'outcome', 'advanced', 'started_wall', 'ended_wall'].map(k => [k, 'unknown']));
  const status = {session: 'run', state: 'polling', updated_wall: 1700000002, stop_reason: null, look_error: null, status_schema: 'curator-runner-status/2',
    settings: {trigger_steps: 20, ceiling_steps: 60, poll_seconds: 5, watch_seconds: 600}, snapshot: 'unknown', limits: null,
    position: {...place(30, 30), read_wall: walls}, as_of: {...place(30, 30), read_wall: walls}, after_last_read: 'unknown',
    current: null, covered_prefix: {end: place(25, 25), restore: {version: 'v3', restored_from: 'v0', counted_through: 'v2'}},
    lag: 'unknown', stamp_distance: 'unknown', backlog: 5,
    last_confirmed: {version: 'v1', label: 'actor-a-1-25-x', window: {session: 'run', actor: 'actor-a', first: 1, last: 25}, coverage: stamp, baseline: false},
    latest_version: {version: 'v3', coverage: null, baseline: false}, failures: {sessions: 0, snapshots: 0, hygiene: 0, flex_deferrals: 0}, unconfirmed: 0,
    examined: {items: [{label: 'actor-a-1-25-x', window: {session: 'run', actor: 'actor-a', first: 1, last: 25}, session_id: 's',
      outcome: 'accepted', advanced: true, started_wall: 1699999990, ended_wall: 1e20}, unknownRow], total: 2, omitted: 0},
    unexamined: {items: null, total: null, omitted: null}};
  let state = 'available';
  const asked = [];
  try {
    await S.ready(page);
    await page.setRequestInterception(true);
    page.on('request', async request => {
      const url = new URL(request.url());
      if (!url.pathname.endsWith('/curator')) return request.continue();
      asked.push(url.pathname);
      const body = await (await fetch(request.url())).json();
      body.runner = {source_status: state, read_wall: 1700000003, snapshot: state === 'missing' ? null : {sha256: 'a'.repeat(64), bytes: state === 'available' ? 900 : 40},
        status: state === 'available' ? status : null};
      request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
    });
    await go(page, '#curator');
    await S.until(page, () => /Coverage & runner/.test(document.getElementById('cur-runner')?.innerText || '') && /polling/.test(document.getElementById('cur-runner').innerText));
    assert.ok(asked.every(p => p === `/api/view/run/${S.SESSIONS.ceil09}/curator`), 'the selected run\'s own curator is asked for');
    assert.match(await flat(page, '#cur-runner'), /Lag unknown operations Backlog 5 steps Latest version v3 → Memory Confirmed v1 → Memory/);
    assert.match(await text(page, '#cur-limits-none'), /No configured limits recorded/);
    await page.click('#cur-wal > summary');
    await S.until(page, () => document.querySelector('#cur-wal .runnerbox'));
    await page.$eval('#cur-wal .runnerbox', d => { d.open = true; });
    await S.until(page, () => document.querySelector('[data-runner-facts]'));
    const facts = await page.$$eval('[data-runner-facts] dt', dts => Object.fromEntries(dts.map(dt => [dt.textContent, dt.nextElementSibling.textContent])));
    assert.match(facts['Play has reached'], /actor actor-a · step 30 · operation op-30 · finished operation 30/);
    assert.match(facts['As of'], /2023-11-14T22:13:21Z/);
    assert.equal(facts['After the last read'], 'unknown');
    assert.match(facts['Covered prefix ends at'], /step 25 .*· unknown past the restore of v3 to v0 \(versions counted through v2\)/);
    assert.equal(facts['Lag (finished operations after the covered prefix)'], 'unknown');
    assert.equal(facts["Backlog (finished steps beyond the curator's cursor)"], '5');
    assert.equal(facts['Last confirmed version'], 'v1 · stamp: session run · actor actor-a · last step 25 · baseline: no');
    assert.equal(facts['Latest version seen'], 'v3 · stamp: no stamp · baseline: no');
    const table = await page.$eval('#cur-wal table.data', n => n.innerText);
    assert.match(table, /actor actor-a · steps 1–25\s+accepted\s+yes\s+2023-11-14T22:13:10Z\s+unknown/);
    assert.match(table, /unknown\s+unknown\s+unknown\s+unknown\s+unknown/);
    assert.equal(await S.overflow(page), 0);
    await S.shot(page, 'curator-runner-status-phone');
    // The card stays mounted; each later poll alone must clear the figures.
    await page.$eval('#cur-runner', n => { n.dataset.kept = 'yes'; });
    for (const [next, words] of [['missing', 'missing'], ['malformed', 'partly written']]) {
      state = next;
      await S.until(page, t => document.querySelector('#cur-runner [data-runner-status]')?.textContent.includes(t), words, 15000);
      assert.equal(await page.$eval('#cur-runner', n => n.dataset.kept), 'yes', 'the card was not remounted');
      assert.equal(await page.$('[data-runner-facts]'), null, `${next} shows no figures`);
      assert.doesNotMatch(await text(page, '#cur-runner'), /\bLag\b|Backlog|Latest version|Cadence/);
      await S.shot(page, `curator-runner-status-${next}`);
    }
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('curator paging and refresh keep empty, changed and failed sources distinct', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#watch`);
  const rows = '.curator-source-view table.data';
  let digest = 'a'.repeat(64), fail = true, failedRequests = 0;
  const labels = ['first', 'empty', 'missing', 'malformed', 'failed', ...Array.from({length: 495}, (_, i) => `extra-${i}`)];
  const row = {index: 0, operation_id: 'b'.repeat(32), operation: 'restore', status: 'unchanged', base_version: 'v2',
    restored_from: 'v0', version: 'v2', submission: null, session: null, diagnostics: [], diagnostics_omitted: 0};
  try {
    await S.ready(page);
    page.on('request', request => {
      const url = new URL(request.url());
      let body, status = 200;
      if (url.pathname.endsWith('/curator-sources/result-sources')) {
        const later = url.searchParams.get('after') === '500';
        body = {schema: 'spectator-view/4', items: (later ? ['last'] : labels).map(label => ({label})), total: 501, next: later ? null : 500, limit: 500};
      } else if (url.pathname.endsWith('/curator-sources/results')) {
        const source = url.searchParams.get('source'), old = url.searchParams.get('snapshot');
        if (source === 'failed' && fail) { failedRequests++; status = 503; body = {viewer: 'unavailable'}; }
        else if (old && old !== digest) { status = 409; body = {schema: 'spectator-view/4', error: 'source_changed'}; }
        else {
          const state = ['empty', 'missing', 'malformed'].includes(source) ? source : 'available';
          body = {schema: 'spectator-view/4', source, source_status: state, snapshot: ['missing'].includes(source) ? null : {sha256: digest, bytes: 123},
            items: state === 'available' ? [row] : [], total: state === 'available' ? 1 : 0, next: null, limit: 25};
        }
      }
      if (body) request.respond({status, contentType: 'application/json', body: JSON.stringify(body)});
      else request.continue();
    });
    await page.setRequestInterception(true);
    await go(page, '#runs/archive/results');
    await S.until(page, () => Array.from(document.querySelector('[data-curator-source]')?.options || []).some(o => o.value === 'first'));
    await page.select('[data-curator-source]', 'first');
    await S.until(page, s => document.querySelector(`${s} button.link`), rows);
    await click(page, `${rows} button.link`);
    await S.until(page, () => document.querySelector('[data-curator-detail]'));
    await S.shot(page, 'curator-results-desktop');
    digest = 'c'.repeat(64);
    await S.until(page, () => document.querySelector('[data-curator-error]')?.textContent.includes('Source changed'));
    assert.equal(await page.$('[data-curator-detail]'), null);
    assert.equal(await page.$(rows), null);
    const press = name => page.evaluate(n => Array.from(document.querySelectorAll('button')).find(b => b.textContent === n).click(), name);
    await press('Refresh results');
    await S.until(page, () => document.querySelector('[data-curator-status]')?.textContent.includes('available'));
    assert.equal(await page.$('[data-curator-detail]'), null);
    await page.select('[data-curator-source]', 'empty');
    await S.until(page, () => document.querySelector('[data-curator-status]')?.textContent.includes('contains no results'));
    for (const source of ['missing', 'malformed']) {
      await page.select('[data-curator-source]', source);
      await S.until(page, label => document.querySelector('[data-curator-status]')?.textContent.includes(label), source);
      assert.equal(await page.$(rows), null);
    }
    page.expect503 = true;
    await page.select('[data-curator-source]', 'failed');
    await S.until(page, () => document.querySelector('[data-curator-error]')?.textContent.includes('Viewer unavailable'));
    const before = failedRequests;
    fail = false;
    await press('Refresh results');
    await S.until(page, () => document.querySelector('[data-curator-status]')?.textContent.includes('available'), null, 2000);
    assert.equal(failedRequests, before);
    assert.equal(await page.evaluate(() => document.activeElement?.hasAttribute('data-curator-source')), true);
    page.expect503 = false;
    await page.select('[data-curator-source]', 'first');
    await S.until(page, s => document.querySelector(`${s} button.link`), rows);
    await click(page, `${rows} button.link`);
    await press('Next sources');
    await S.until(page, () => Array.from(document.querySelector('[data-curator-source]')?.options || []).some(o => o.value === 'last'));
    assert.equal(await page.$eval('[data-curator-source]', n => n.value), '');
    assert.equal(await page.$('[data-curator-detail]'), null);
    assert.equal(await page.$('[data-curator-status]'), null);
    assert.deepEqual(page.problems.filter(p => !p.startsWith('http 409: /api/view/curator-sources/results')), []);
  } finally { await page.close(); }
});

test('curator session selects a receipt and resets detail when its snapshot changes', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 390, height: 900, mobile: true});
  const digest = 'a'.repeat(64), rows = '.curator-source-view table.data';
  const row = {index: 0, operation_id: 'b'.repeat(32), operation: 'submission', status: 'unknown', base_version: 'v1',
    restored_from: null, version: null, submission: 's', session: 'session', diagnostics: [], diagnostics_omitted: 0};
  let changed = false;
  try {
    await S.ready(page);
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.pathname.endsWith('/curator-sources/session-sources')) return request.respond({status: 200, contentType: 'application/json', body: JSON.stringify({schema: 'spectator-view/4', items: [{label: 'receipt'}], total: 1, next: null, limit: 500})});
      if (url.pathname.endsWith('/curator-sources/session')) {
        if (changed && url.searchParams.has('snapshot')) return request.respond({status: 409, contentType: 'application/json', body: JSON.stringify({schema: 'spectator-view/4', error: 'source_changed'})});
        return request.respond({status: 200, contentType: 'application/json', body: JSON.stringify({schema: 'spectator-view/4', source: 'receipt', source_status: 'available', snapshot: {sha256: digest, bytes: 20}, header: {id: 's1', inputs: {session_kind: 'admission'}, pinned: {}, budgets: {cap_usd: '2'}, lifecycle: {state: 'sealed'}, resources: {}, published_after: 'v1'}, drafts: null, items: [row], total: 1, next: null, limit: 25})});
      }
      request.continue();
    });
    await go(page, '#runs/archive/sessions');
    await S.until(page, () => Array.from(document.querySelector('[data-session-source]')?.options || []).some(o => o.value === 'receipt'));
    await page.select('[data-session-source]', 'receipt');
    await S.until(page, s => document.querySelector(`${s} button.link`), rows);
    await page.focus(`${rows} button.link`); await page.keyboard.press('Enter');
    await S.until(page, () => document.activeElement?.hasAttribute('data-session-detail'));
    assert.match(await page.$eval('#app', n => n.innerText), /No collection report recorded/);
    assert.equal(await S.overflow(page), 0);
    await S.shot(page, 'curator-session-phone');
    changed = true;
    await S.until(page, () => Array.from(document.querySelectorAll('[role=alert]')).some(n => n.textContent.includes('Source changed')), null, 8000);
    assert.equal(await page.$('[data-session-detail]'), null);
    assert.deepEqual(page.problems.filter(p => !p.startsWith('http 409: /api/view/curator-sources/session')), []);
  } finally { await page.close(); }
});

test('Watch Fit mode never crops a 960x640 canvas, keeps stage badge off canvas, closes keys on Escape, and inerts story behind inspector (#1064)', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1280, height: 800});
  try {
    await S.ready(page);
    await S.until(page, () => document.getElementById('feed') && !document.getElementById('feed').hidden);
    // Simulate a real 960x640 CDDA frame on the canvas and verify Fit + Wide+Fit keep the canvas inside .player-view.
    const measure = () => page.evaluate(() => {
      const c = document.getElementById('feed'), v = document.querySelector('.player-view'), b = document.querySelector('.stagetop');
      c.width = 960; c.height = 640;
      const cr = c.getBoundingClientRect(), vr = v.getBoundingClientRect(), br = b.getBoundingClientRect();
      return {cw: cr.width, ch: cr.height, vw: vr.width, vh: vr.height, cTop: cr.top, cBottom: cr.bottom, vTop: vr.top, vBottom: vr.bottom, bTop: br.top, bBottom: br.bottom};
    });
    const fit = await measure();
    assert.ok(fit.ch <= fit.vh + 0.5 && fit.cw <= fit.vw + 0.5, `Fit canvas (${fit.cw}x${fit.ch}) must stay inside .player-view (${fit.vw}x${fit.vh})`);
    assert.ok(fit.cTop >= fit.vTop - 0.5 && fit.cBottom <= fit.vBottom + 0.5, 'Fit canvas must not crop vertically');
    assert.ok(fit.bTop >= fit.cBottom - 0.5, `.stagetop (top=${fit.bTop}) must not overlap canvas (bottom=${fit.cBottom})`);
    await page.click('#feed-wide');
    const wide = await measure();
    assert.ok(wide.ch <= wide.vh + 0.5 && wide.cw <= wide.vw + 0.5, `Wide+Fit canvas (${wide.cw}x${wide.ch}) must stay inside .player-view (${wide.vw}x${wide.vh})`);
    await page.click('#feed-wide');
    // Keyboard shortcuts popover closes on Escape.
    await page.click('details.keys > summary');
    await S.until(page, () => document.querySelector('details.keys')?.open === true);
    await page.keyboard.press('Escape');
    await S.until(page, () => document.querySelector('details.keys')?.open === false);
    // Opening Step Inspector inerts the underlying story list; closing restores it.
    await page.click('#story .inspect');
    await S.until(page, () => !!document.getElementById('inspector'));
    await S.until(page, () => document.querySelector('section.story')?.inert === true);
    await page.keyboard.press('Escape');
    await S.until(page, () => !document.getElementById('inspector'));
    await S.until(page, () => document.querySelector('section.story')?.inert === false);
    // Opening Source wraps the bar cleanly instead of clipping live pills inside .vfacts.
    await page.click('details.src-details > summary');
    await S.until(page, () => document.querySelector('details.src-details')?.open === true);
    const pillsOk = await page.evaluate(() => {
      const box = document.querySelector('#viewer-facts').getBoundingClientRect();
      return ['#pill-spend', '#pill-context', '#pill-curator'].every(sel => {
        const el = document.querySelector(sel);
        if (!el) return true;
        const r = el.getBoundingClientRect();
        return r.width > 0 && r.left >= box.left - 1 && r.right <= box.right + 1 && r.right <= window.innerWidth + 1;
      });
    });
    assert.equal(pillsOk, true, 'live header pills must not clip when Source is open');
    await page.click('details.src-details > summary');
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});
