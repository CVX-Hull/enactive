// Spectator page: the three tabs render in light, dark, narrow and phone widths without console errors, failed requests
// or horizontal overflow, and each tab does its job. Browser behavior against the fixture server only: no game, no
// provider, and no claim about the real viewer's data.
const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const S = require('./fixtures/spectator/support.cjs');

const ROUTES = ['#watch', '#memory', '#memory/v2', '#memory/requests', '#memory/player', '#memory/curator-drafts', '#memory/results', '#memory/sessions', '#memory/containers', '#memory/episodes',
  '#diagnostics', '#diagnostics/metrics', '#diagnostics/readers', '#diagnostics/compare', '#diagnostics/explore', '#diagnostics/changes', '#diagnostics/failures', '#diagnostics/components'];
const CONFIGS = [['light', 1440, 'light', false], ['dark', 1440, 'dark', false], ['narrow', 900, 'light', false], ['phone', 390, 'light', true]];
let fx, browser;
before(async () => { fx = await S.startFixture(); browser = await S.launch(); });
after(async () => { if (browser) await browser.close(); if (fx) fx.stop(); });

const openPage = (url, options) => S.open(browser, url, options);

const go = async (page, hash) => { await page.evaluate(h => { location.hash = h; }, hash); await S.settle(page, 100); };
const text = (page, selector) => page.$eval(selector, node => node.innerText);
const click = (page, selector) => page.$eval(selector, node => node.click());

for (const [name, width, scheme, mobile] of CONFIGS) {
  test(`every view renders cleanly: ${name} (${width}px)`, {timeout: 180000}, async () => {
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
        assert.doesNotMatch(body, /not yet measured|arrives in|\bbelief\b|\bstaleness\b/i, `${route} shows a placeholder`);
        assert.equal(await S.overflow(page), 0, `${route} scrolls horizontally at ${width}px`);
        assert.equal(await page.$('.curator-records'), null, 'unconfigured curator sources remain hidden');
        assert.deepEqual(page.problems, [], `${route} had problems`);
        await S.shot(page, `${route.replace(/[#/]/g, '_')}-${name}`);
      }
      const active = await page.$eval('html', el => getComputedStyle(el).colorScheme);
      assert.match(active, scheme === 'dark' ? /dark/ : /light/);
    } finally { await page.close(); }
  });
}

test('the navigation is three tabs, and the Mission Control bar is one slim row at desktop width', {timeout: 30000}, async () => {
  const page = await openPage(fx.url, {width: 1440});
  try {
    await S.ready(page);
    assert.deepEqual(await page.$$eval('nav.jobs a', links => links.map(a => a.textContent)), ['Watch', 'Memory & Curator', 'Diagnostics']);
    assert.equal(await page.$eval('nav.jobs a[aria-current="page"]', a => a.dataset.nav), 'watch', 'Watch is the default');
    await S.until(page, () => document.documentElement.dataset.watchStage === 'ok' && document.getElementById('pill-endpoint'));
    assert.ok(await page.$eval('header.ctl', h => h.offsetHeight) <= 60, 'one row');
    assert.match(await text(page, '#pill-spend'), /^\$2\.\d\d \/ \$5\.00\s+\+ \$1\.23 curator\*$/);
    assert.match(await text(page, '#pill-context'), /^35\.0k tok\s*5 cuts$/);
    assert.match(await text(page, '#pill-curator'), /Curator\s*v3/);
    assert.match(await text(page, '#pill-endpoint'), /^endpoint-b\s*\+1$/, 'the endpoint that answered last, not the most frequent');
    assert.match(await page.$eval('#pill-endpoint', n => n.title), /^Last answering endpoint: endpoint-b\. Responses: endpoint-a \d+, endpoint-b 4$/);
    // The bar follows the playhead: the latest prompt while live, the run's median in history and while the view is held.
    const prompt = words => S.until(page, w => document.getElementById('pill-context').innerText.replace(/\s+/g, ' ') === w, words);
    await page.click('#feed-hold'); await prompt('32.8k tok p50 · 5 cuts');
    await page.click('#feed-hold'); await prompt('35.0k tok 5 cuts');
    await page.click('#feed-back'); await prompt('32.8k tok p50 · 5 cuts');
    await page.click('#backlive'); await prompt('35.0k tok 5 cuts');
    await page.click('#feed-hold'); await prompt('32.8k tok p50 · 5 cuts');
    await page.click('[data-nav="memory"]'); await prompt('35.0k tok 5 cuts');   // a view that is gone holds nothing
    await page.click('[data-nav="watch"]');
    await S.until(page, () => document.documentElement.dataset.watchStage === 'ok');
    for (const [tab, name] of [['memory', 'Memory and curator'], ['diagnostics', 'Diagnostics'], ['watch', 'Watch']]) {
      await page.click(`[data-nav="${tab}"]`);
      await S.until(page, n => document.querySelector('#app section[data-view]')?.getAttribute('aria-label') === n, name);
    }
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Pause is calm until a Pause condition is met, and the same button either way', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`);
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
    const alert = await look();
    assert.notEqual(alert[0], calm[0]);
    assert.deepEqual(alert.slice(1), calm.slice(1));
    await click(page, '#pausealert');
    await S.until(page, () => document.querySelectorAll('#conds li').length === 5);
    assert.match(await text(page, '#pauseanswer'), /^Yes: /);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Story feed: cards, filters, search and the step they select', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1440});
  try {
    await S.ready(page);
    const top = await text(page, '#story .card');
    assert.match(top, /look around before moving on\./);
    assert.match(top, /player claim/);
    assert.match(top, /#\d+ · \d+ ms · endpoint-a · \$0\.0125/);
    assert.ok((await text(page, '#story')).includes('<img src=x onerror=window.storyExecuted=true>'), 'a hostile intent is text');
    assert.equal(await page.evaluate(() => window.storyExecuted), undefined);
    assert.equal(await page.$('#story [data-kind="context_cut"].held'), null, 'a cut that was held back is not in the whole story');
    await page.click('#story-cuts');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 9);
    assert.equal(await page.$$eval('#story .card.held', n => n.length), 4);
    assert.match(await text(page, '#story .card.cut:not(.held)'), /Context cut · best effort · v3[\s\S]*61\.4k → 24\.8k tokens \(−36\.6k\)[\s\S]*39 → 19 imgs · 20 turns cut/);
    assert.match(await text(page, '#story-count'), /4 held back/);
    await page.type('#story-search', 'best effort');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 1);
    assert.match(await text(page, '#story .card'), /Context cut · best effort/);
    await page.$eval('#story-search', n => { n.value = ''; n.dispatchEvent(new Event('input', {bubbles: true})); });
    await S.until(page, () => document.querySelectorAll('#story .card').length === 9);
    await page.click('#story .card.cut:not(.held) .cardmain');
    await S.until(page, () => /STEP #200 · HISTORY/.test(document.querySelector('.stagepill').textContent));
    assert.match(await text(page, '#playinfo'), /^Step 200/);
    await page.click('#story-memory');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 3);
    assert.match(await text(page, '#story .card'), /Memory updated · v3[\s\S]*\+1 fact · ~1 updated · −1 removed/);
    await page.click('#story-alerts');
    await S.until(page, () => [...document.querySelectorAll('#story .card')].some(c => c.dataset.kind === 'step') && [...document.querySelectorAll('#story .card')].some(c => c.dataset.kind === 'finding'));
    assert.ok(await page.$$eval('#story .card.bad .state.alert', n => n.length) === 1, 'a failed call is an alert');
    await page.click('#story-all');
    await page.type('#story-search', 'Read the sign');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 1);
    assert.match(await text(page, '#story-count'), /1 found/);
    await page.$eval('#story-search', n => { n.value = ''; n.dispatchEvent(new Event('input', {bubbles: true})); });
    await S.until(page, () => document.querySelectorAll('#story .card').length > 20);
    // Older entries than the window are a click away; the active card is the playhead's step.
    assert.equal(await page.$eval('#story .card[aria-current="true"] .cardmain', b => b.dataset.jump), '200');
    const before = await page.$$eval('#story .card', n => n.length);
    await page.$eval('#story li.more:last-of-type button', b => b.click());
    await S.until(page, n => document.querySelectorAll('#story .card').length > n, before);
    await page.click('#backlive');
    await S.until(page, () => /LIVE/.test(document.querySelector('.stagepill').textContent));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Story feed: a delivered version opens in Memory, and the timeline marks each kind in its own lane', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelectorAll('.mark-memory line').length === 3);
    assert.deepEqual(await page.$$eval('.tlmarks g', groups => groups.map(g => [g.getAttribute('class'), g.children.length > 0])), [['mark-cut', true], ['mark-memory', true], ['mark-alert', true]]);
    assert.match(await text(page, '#tl-legend'), /Context cut 5\s*Memory update 3\s*Alert \d+/);
    // A call that failed or was refused is an alert in the story and on the timeline alike.
    const alerts = async () => page.evaluate(() => ({lane: document.querySelectorAll('.mark-alert line').length, legend: Number(document.querySelector('#tl-legend .lg-alert b').textContent),
      story: Number(document.querySelector('#story-alerts .n').textContent)}));
    const shared = await page.evaluate(async () => {
      const {isAlertEntry} = await import('/app/watch.js');
      const {store} = await import('/app/data.js');
      const found = store.feed.filter(isAlertEntry);
      return {total: found.length, failed: found.filter(e => e.entry_kind === 'step').map(e => e.seq),
        judged: [['step', 'error'], ['step', 'refused'], ['step', 'ok'], ['step', 'pending'], ['finding'], ['context_cut'], ['knowledge_update']].map(([entry_kind, status]) => isAlertEntry({entry_kind, status}))};
    });
    assert.deepEqual(shared.failed, [12]);
    assert.deepEqual(shared.judged, [true, true, false, false, true, false, false]);
    assert.deepEqual(await alerts(), {lane: shared.total, legend: shared.total, story: shared.total});
    await page.evaluate(async () => {   // a refused call, as a later poll would bring it
      const {store, set} = await import('/app/data.js');
      set({feed: store.feed.map(e => (e.entry_kind === 'step' && e.seq === 20 ? {...e, status: 'refused'} : e))});
    });
    await S.until(page, n => document.querySelectorAll('.mark-alert line').length === n && Number(document.querySelector('#story-alerts .n').textContent) === n, shared.total + 1);
    await page.click('#story-memory');
    await S.until(page, () => document.querySelectorAll('#story .card').length === 3);
    await page.$eval('#story .card:nth-child(2) a.inspect', a => a.click());
    await S.until(page, () => location.hash === '#memory/v2' && document.querySelector('#versions [aria-current="true"]')?.textContent.startsWith('v2'));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Step Inspector: opens by button or key, shows the mechanics, loads the context on request, closes with Escape', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 1440});
  try {
    await S.ready(page);
    assert.equal(await page.$('#inspector'), null);
    await page.click('#story .card.step .inspect');
    await S.until(page, () => document.activeElement?.classList.contains('drawerclose'));
    const body = await text(page, '#inspector');
    for (const value of ['player claim', 'computer_input', 'delivered', 'Operation completed; application effect is not certified', 'Uncached input', 'Cache read', 'Cache write', 'Output tokens', '$0.0125', 'endpoint-', 'request-', 'call-', 'Source'])
      assert.ok(body.toLowerCase().includes(value.toLowerCase()), value);
    assert.match(await text(page, '#inspect-arguments'), /"key": "ENTER"/);
    const asked = async () => (await fx.state()).view_requests.filter(r => /\/context\//.test(r)).length;
    const before = await asked();
    assert.equal(await page.$('[data-context]'), null, 'the context is fetched only on request');
    // The drawer covers the story only: Pause and the stage stay usable.
    const clear = await page.evaluate(() => {
      const drawer = document.getElementById('inspector').getBoundingClientRect(), pause = document.getElementById('pause').getBoundingClientRect(), stage = document.querySelector('.player').getBoundingClientRect();
      return drawer.top >= pause.bottom && drawer.left >= stage.right;
    });
    assert.ok(clear);
    await page.click('#load-context');
    await S.until(page, () => document.querySelector('[data-context] .ctx-bar'));
    assert.equal(await asked(), before + 1);
    assert.match(await text(page, '[data-context]'), /reconstructed|exact: replayed/);
    await page.click('#inspector [aria-label="Previous entry"]');
    await S.until(page, () => !document.querySelector('[data-context]') && /HISTORY/.test(document.querySelector('.stagepill').textContent));
    await page.keyboard.press('Escape');
    await S.until(page, () => !document.getElementById('inspector'));
    await page.evaluate(() => document.activeElement && document.activeElement.blur());
    await page.keyboard.press('i');
    await S.until(page, () => document.getElementById('inspector'));
    await page.keyboard.press('Escape');
    await S.until(page, () => !document.getElementById('inspector'));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Memory: curator strip, version rail, delivery diff, reader, and a citation that opens Watch at its frame', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#memory`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('[data-reading]') && document.getElementById('curator-spend'));
    assert.match(await text(page, '.curator-strip'), /Latest version\s*v3[\s\S]*Covers through\s*step 160[\s\S]*Lag\s*20[\s\S]*Backlog\s*20/);
    assert.match(await text(page, '#curator-spend'), /\$1\.23\s*proxy-accounted · 3\/4 settled\s*incomplete/i);
    // A version is said to be delivered only where the trace records it.
    assert.match(await text(page, '.browser header'), /v3 · Exported snapshot · confirmed delivered at step 170 · fallible/);
    assert.deepEqual(await page.$$eval('.browserbar .seg button', n => n.map(b => b.innerText.trim())), ['Articles 2', 'World facts 2', 'Game facts 2', 'All facts 4']);
    assert.equal(await page.$('#kb-scope'), null, 'every fact of a delivered-knowledge/3 version records its scope');
    // The tag and claim-kind view, counted from the delivered records.
    assert.match(await text(page, '#kb-summary'), /instance state\s*2[\s\S]*mechanic\s*1[\s\S]*strategy\s*1[\s\S]*#fire\s*2[\s\S]*#water\s*2/);
    assert.deepEqual(await page.$$eval('#versions .vpill b', n => n.map(x => x.textContent)), ['v1', 'v2', 'v3']);
    assert.equal(await page.$eval('#versions [aria-current="true"] b', n => n.textContent), 'v3', 'the latest version by default');
    await page.$eval('#versions .vpill:nth-child(2)', a => a.click());
    await S.until(page, () => document.querySelector('#versions [aria-current="true"] b').textContent === 'v2' && document.querySelector('#delivery-diff details'));
    assert.match(await text(page, '#delivery-diff'), /Delivered at step 110\s*\+1 article · \+2 facts\s*after v1/);
    await page.$eval('#delivery-diff details', d => { d.open = true; });
    assert.match(await text(page, '#delivery-diff .difflist'), /added Making fire Making fire in one sentence\./);
    // Articles: a cited fact and a typed link open on the reading side by their exact IDs.
    assert.match(await text(page, '[data-reading="article-water"]'), /this world scope[\s\S]*#water[\s\S]*Finding water in one sentence\.[\s\S]*Last confirmed/);
    await page.$$eval('#kb-items .item', items => items[1].click());
    await S.until(page, () => document.querySelector('[data-reading="article-fire"] [data-links] .factpill'));
    assert.match(await text(page, '[data-reading="article-fire"] [data-links]'), /see also article-water/);
    await page.click('[data-reading="article-fire"] [data-links] .factpill');
    await S.until(page, () => document.activeElement?.dataset.reading === 'article-water');
    await page.$$eval('#kb-items .item', items => items[1].click());
    await S.until(page, () => document.querySelector('[data-reading="article-fire"] .refs .factpill'));
    await page.click('[data-reading="article-fire"] .refs .factpill');
    await S.until(page, () => document.activeElement?.dataset.reading === 'fact-fire');
    assert.ok((await text(page, '[data-reading]')).includes('<script>window.knowledgeExecuted=true</script>'));
    assert.match(await text(page, '[data-reading]'), /game-wide scope[\s\S]*ruleset: standard[\s\S]*mechanic[\s\S]*observed[\s\S]*depends on fact-water/);
    assert.equal(await page.evaluate(() => window.knowledgeExecuted), undefined);
    // Facts, with the scope class, kind and flags they record, and their cited frames.
    await page.click('#kb-all');
    await S.until(page, () => document.querySelectorAll('#kb-items .item').length === 4 && document.querySelector('[data-reading="fact-water"]'));
    assert.match(await text(page, '[data-reading]'), /this world scope[\s\S]*instance state[\s\S]*session s01 · actor 001 · step 20/);
    assert.ok(await page.$('[data-reading="fact-water"] [data-citation-seq="20"]'), 'a frame of this run is clickable');
    await page.$$eval('#kb-items .item', items => items[3].click());
    await S.until(page, () => document.querySelector('[data-reading="fact-old"]'));
    assert.equal(await page.$('[data-reading="fact-old"] [data-jump-seq], [data-reading="fact-old"] [data-citation-seq]'), null, 'another session\'s frame is not a frame of this run');
    const old = await text(page, '[data-reading]');
    for (const pattern of [/contested/, /unverified branch/, /needs review/, /Contradicted by\s*fact-water/, /Stale citations: fact-gone/, /Frame unavailable/, /no cited frame of this run/])
      assert.match(old, pattern);
    await page.click('#kb-world');
    await S.until(page, () => document.querySelectorAll('#kb-items .item').length === 2);
    assert.deepEqual(await page.$$eval('#kb-items .item b', n => n.map(b => b.textContent)), ['Subject of fact-water', 'Subject of fact-old']);
    await page.click('#kb-all');
    await S.until(page, () => document.querySelectorAll('#kb-items .item').length === 4);
    // A tag searches the version.
    await page.click('#kb-summary [data-tag-count="fire"]');
    await S.until(page, () => document.getElementById('kb-search').value === 'fire' && document.querySelectorAll('#kb-items .item').length === 1);
    await page.$eval('#kb-search', input => { input.value = ''; input.dispatchEvent(new Event('input', {bubbles: true})); });
    await S.until(page, () => document.querySelectorAll('#kb-items .item').length === 4);
    // Search keeps its focus while it fetches.
    await page.type('#kb-search', 'lighter');
    await S.until(page, () => document.querySelectorAll('#kb-items .item').length === 1);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'kb-search');
    await S.until(page, () => document.querySelector('[data-reading="fact-fire"] [data-jump-seq]'));
    await page.click('[data-jump-seq]');
    await S.until(page, () => location.hash === '#watch' && /STEP #90 · HISTORY/.test(document.querySelector('.stagepill')?.textContent || ''));
    await S.until(page, () => /^step 90 /.test(document.getElementById('feed-meta').textContent));
    assert.equal(await page.$eval('#story .card[aria-current="true"] .cardmain', b => b.dataset.jump), '90');
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Memory: an exported version nobody recorded as delivered says so, a fact without a recorded scope is counted, and a run without any is an honest blank', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#memory`, {width: 900});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('[data-reading]'));
    assert.deepEqual(await page.$$eval('.browserbar .seg button', n => n.map(b => b.dataset.value)), ['articles', 'world', 'game', 'all']);
    let scoped = false;
    await page.setRequestInterception(true);
    page.on('request', async request => {
      const url = new URL(request.url());
      const knowledge = url.pathname.endsWith('/delivered-knowledge'), feed = url.pathname.endsWith('/feed');
      if ((!knowledge && !feed) || url.pathname.includes(S.SESSIONS.aidA1)) return request.continue();
      const body = await (await fetch(request.url())).json();
      if (feed) body.items = body.items.map(e => (e.knowledge_version === 'v3' && e.entry_kind === 'knowledge_update' ? {...e, outcome: 'refused'} : e.knowledge_version === 'v2' && e.entry_kind === 'knowledge_update' ? {...e, outcome: 'undelivered'} : e));
      // A listing that counts a fact with no readable scope says so.
      if (knowledge && scoped) body.scope_counts = {...body.scope_counts, unrecorded: 1};
      request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
    });
    await page.reload({waitUntil: 'load'});
    await S.until(page, () => /v3 · Exported snapshot · no delivery recorded/.test(document.querySelector('.browser header')?.innerText || ''), null, 15000);
    assert.match(await text(page, '#delivery-diff'), /No delivery of v3 to the player is recorded in this run\./);
    assert.doesNotMatch(await text(page, '#app'), /as delivered to the player|confirmed delivered/);
    await go(page, '#memory/v2');   // neither refused nor delivered: only a delivery is one
    await S.until(page, () => /v2 · Exported snapshot · no delivery recorded/.test(document.querySelector('.browser header')?.innerText || ''));
    await go(page, '#memory/v1');
    await S.until(page, () => /v1 · Exported snapshot · confirmed delivered at step 60/.test(document.querySelector('.browser header')?.innerText || ''));
    scoped = true;
    await S.until(page, () => /^1 fact without a recorded scope\.$/.test(document.getElementById('kb-scope')?.textContent || ''));
    scoped = false;
    await S.until(page, () => !document.getElementById('kb-scope'));
    await S.pick(page, 'aidA1');
    await S.until(page, () => document.getElementById('curator-empty') && document.getElementById('knowledge-empty'));
    assert.match(await text(page, '#curator-empty'), /^No curator data for this run\.$/);
    assert.match(await text(page, '#knowledge-empty'), /^No delivered knowledge for this run\.$/);
    assert.equal(await page.$('#pill-curator, #pill-context, #pill-endpoint'), null);
    assert.match(await text(page, '#pill-spend'), /^~\$3\.98 est/);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Diagnostics: four cards, the context sawtooth, spend, tools, and no figure where none is recorded', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#diagnostics`, {width: 1440});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('.ctxchart canvas') && document.querySelector('.spendchart canvas') && document.querySelectorAll('table.data tbody tr').length > 2);
    assert.deepEqual(await page.$$eval('.kpi', n => n.map(x => x.id)), ['kpi-spend', 'kpi-context', 'kpi-routing', 'kpi-custody']);
    assert.match(await text(page, '#kpi-spend'), /\$4\.\d\d\s*player \+ recall \+ live curator\s*partial[\s\S]*recorded\s+host trace[\s\S]*player open[\s\S]*curator incomplete[\s\S]*provider-reported\s*\$2\.\d\d of \$5\.00[\s\S]*Live curator\s*proxy-accounted\s*\$1\.23 · 3\/4 settled[\s\S]*Boundary grooming\s*proxy-accounted\s*recorded outside admission[\s\S]*Configured-rate estimate\s*\$3\.98/i);
    assert.doesNotMatch(await text(page, '#kpi-spend'), /\$0\.00|provider-reported, player \+ recall \+ live curator/i, 'no part is a silent zero, and no basis covers them all');
    assert.match(await page.$eval('#kpi-spend [data-exact]', n => n.dataset.exact), /^2\.\d{4}$/, 'the exact provider text is kept');
    assert.match(await text(page, '#kpi-context'), /32\.8k tok[\s\S]*max 49\.9k[\s\S]*93\.1%[\s\S]*5 applied · 4 held back/);
    assert.match(await text(page, '#kpi-context'), /Cut results\s*2 target · 1 rescue · 1 best effort[\s\S]*Tail notices\s*2/);
    assert.match(await text(page, '#kpi-spend'), /Spend reserve\s*Reached 1 time · latest \$2\.50 spent of \$5\.00 · \$2\.50 finish reserve/);
    assert.match(await text(page, '#kpi-routing'), /endpoint-a:\s*\d+\s*endpoint-b:\s*4/);
    assert.match(await text(page, '#kpi-custody'), /live[\s\S]*writes its receipt when the run ends/);
    // The sawtooth's option draws both series and one dashed line for each applied cut.
    const option = await page.evaluate(async () => {
      const {contextOption, spendOption} = await import('/app/charts.js');
      const requests = [0, 1, 2].map(index => ({index, request_id: `r${index}`, seq: index + 1, prompt_tokens: 1000 * (index + 1), cache_read: 400, reported_cost_usd: '0.5', estimated_dollars: 9}));
      const o = contextOption(requests, [{index: 2, tokens_before: 61400, tokens_after: 24800, removed_turns: 20}, {index: null}]);
      const s = spendOption(requests, 5);
      return [o.series.map(x => [x.name, x.data]), o.series[1].markLine.data, s.series[0].data.map(p => p[1]), o.tooltip.formatter([{dataIndex: 2}])];
    });
    assert.deepEqual(option[0], [['Cache read', [400, 400, 400]], ['Not cached', [600, 1600, 2600]]]);
    assert.deepEqual(option[1], [{xAxis: 2}]);
    assert.deepEqual(option[2], [0.5, 1, 1.5], 'the provider figure, not the estimate');
    assert.match(option[3], /cut: 61\.4k → 24\.8k \(20 turns\)/);
    const cuts = await page.$$eval('.panel details table.data tbody tr', n => n.length);
    assert.equal(cuts, 5, 'the cuts are also a table');
    const results = await page.$eval('.panel details table.data', table => {
      const col = [...table.querySelectorAll('th')].findIndex(th => th.textContent === 'Result');
      return [...table.querySelectorAll('tbody tr')].map(row => row.cells[col]?.textContent);
    });
    assert.deepEqual(results, ['—', 'target', 'rescue', 'target', 'best effort']);
    await S.pick(page, 'aidA2');
    await S.until(page, () => /no host trace for this run/.test(document.getElementById('kpi-context')?.innerText || ''));
    assert.match(await text(page, '#kpi-spend'), /—\s*no provider-reported cost[\s\S]*Player \+ recall\s*provider-reported\s*Unavailable[\s\S]*no session recorded[\s\S]*recorded outside admission/i);
    assert.doesNotMatch(await text(page, '#kpi-spend'), /Spend reserve/);
    assert.match(await text(page, '#kpi-routing'), /answering endpoint not recorded/);
    await S.until(page, () => /configured-rate estimate: no provider cost is recorded/.test(document.getElementById('app').innerText));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('Diagnostics: each part of the spend keeps its basis, and a combined figure is whole only when every part is closed', {timeout: 45000}, async () => {
  const page = await openPage(`${fx.url}#diagnostics`, {width: 1440});
  const closedPlayer = {reported_cost_usd: '3.6427473', spent_usd: '3.6427473', spend_complete: true, unpriced_requests: 0, unpriced_recall_requests: 0};
  const closedCurator = {sessions_total: 2, sessions_settled: 2, sessions_unsettled: 0, spent_usd: '1.5', unsettled_requests: 0, spend_complete: true};
  const groomed = {source_status: 'available', status: 'completed', reason: null, spent_usd: '0.36140535', spend_complete: true, published_before: 'v31', published_after: 'v33'};
  const absent = {source_status: 'not_configured', status: null, reason: null, spent_usd: null, spend_complete: null, published_before: null, published_after: null};
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
    await shows(closedPlayer, closedCurator, groomed, '$5.50', false, 'player \\+ recall \\+ live curator \\+ boundary grooming .*Boundary grooming proxy-accounted \\$0\\.36 · completed');
    await shows(closedPlayer, closedCurator, absent, '$5.14', true, 'Boundary grooming proxy-accounted recorded outside admission');
    await shows(closedPlayer, closedCurator, {...absent, source_status: 'other_run'}, '$5.14', true, 'recorded outside admission');
    await shows(closedPlayer, closedCurator, {...absent, source_status: 'malformed'}, '$5.14', true, 'receipt unreadable');
    await shows(closedPlayer, closedCurator, {...groomed, spent_usd: null, spend_complete: false, status: 'failed'}, '$5.14', true, 'unavailable · failed');
    await shows(closedPlayer, closedCurator, {...groomed, spend_complete: false}, '$5.50', true, '\\$0\\.36 · completed · unsettled');
    await shows(closedPlayer, {...closedCurator, spent_usd: null, spend_complete: false, sessions_settled: 0}, groomed, '$4.00', true, 'Live curator proxy-accounted Unavailable · 0/2 settled');
    await shows(closedPlayer, null, groomed, '$4.00', true, 'Live curator proxy-accounted no session recorded');
    await shows({...closedPlayer, spend_complete: false, unpriced_requests: 1}, closedCurator, groomed, '$5.50', true, 'player open .*subtotal provider-reported \\$3\\.64 .*Unpriced or in flight 1 player · 0 recall');
    await shows({...closedPlayer, reported_cost_usd: null}, closedCurator, groomed, '—', true, 'no combined figure .*Player \\+ recall provider-reported Unavailable .*\\$1\\.50 .*\\$0\\.36');
    assert.doesNotMatch(await text(page, '#kpi-spend'), /\$0\.00/);
    // The bar and the curator strip show an unavailable curator figure as that, never as nothing spent.
    await shows(closedPlayer, {...closedCurator, spent_usd: null, spend_complete: false}, absent, '$3.64', true, 'Unavailable');
    assert.match(await text(page, '#pill-spend'), /\+ unavailable curator\*/);
    await go(page, '#memory');
    await S.until(page, () => /Unavailable/.test(document.getElementById('curator-spend')?.innerText || ''));
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
    await waitFor('Player + recall subtotal', '$1.64');
    assert.equal(await page.$eval('#kpi-spend [data-exact]', n => n.dataset.exact), '1.64493095');
    assert.match(await text(page, '#kpi-spend'), /custodian receipt/);
    assert.equal(await amount('Unpriced attempts'), '1 player · 1 recall');
    assert.match(await amount('Configured-rate estimate'), /^\$\d/);
    await S.pick(page, 'aidA3');
    await waitFor('Player + recall', '$0.00');
    assert.equal(await page.$eval('#kpi-spend [data-exact]', n => n.dataset.exact), '0');
    assert.equal(await amount('Unpriced attempts'), undefined);
    await S.pick(page, 'aidA4');
    await waitFor('Player + recall', 'Unavailable');
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
    assert.equal(await page.$('#pause, #sheet, #statusline, #frame, .ctl-frame, .ctl-left'), null);
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

test('an episode anchor opens Watch at its step, and a container opens its manifest', {timeout: 60000}, async () => {
  const page = await openPage(`${fx.url}#memory/episodes`, {scheme: 'light'});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('[data-anchor="observed"] button.btn'));
    assert.match(await page.$eval('#app', n => n.innerText), /frame unavailable/i);   // the text-only anchor and the uncatalogued run
    await page.click('[data-anchor="observed"] button.btn');
    await S.until(page, () => location.hash === '#watch');
    await S.until(page, () => { const back = document.getElementById('feed-back'); return back && back.disabled; });   // the playhead is on the first step
    await go(page, '#memory/containers');
    await S.until(page, () => document.querySelector('#more-sources table.data button.link'));
    await click(page, '#more-sources table.data button.link');
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
        const pairs = [['--fg', '--bg'], ['--fg', '--surface'], ['--fg', '--accent-soft'], ['--muted', '--bg'], ['--muted', '--surface'], ['--muted', '--sunk'], ['--muted', '--accent-soft'], ['--muted', '--teal-soft'], ['--muted', '--violet-soft'],
          ['--muted', '--watch-soft'], ['--muted', '--alert-soft'], ['--quiet', '--surface'], ['--accent', '--surface'], ['--accent', '--accent-soft'], ['--watch', '--watch-soft'], ['--alert', '--alert-soft'], ['--ok', '--ok-soft'], ['--teal', '--teal-soft'],
          ['--violet', '--violet-soft'], ...['rec', 'read', 'calc', 'claim', 'human', 'ex'].map(k => [`--p-${k}`, `--p-${k}-soft`])];
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

test('every module under web/app is reachable from the page', () => {
  const root = path.join(__dirname, '../web/app');
  const entries = [...fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8').matchAll(/src="\/app\/([\w.-]+\.js)"/g)].map(m => m[1]);
  const seen = new Set();
  const walk = name => {
    if (seen.has(name)) return;
    seen.add(name);
    for (const m of fs.readFileSync(path.join(root, name), 'utf8').matchAll(/from '\.\/([\w.-]+\.js)'/g)) walk(m[1]);
  };
  entries.forEach(walk);
  assert.deepEqual(fs.readdirSync(root).filter(n => n.endsWith('.js')).sort(), [...seen].sort());
});

test('current hints stay unverified text', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#watch`, {width: 390, height: 900, mobile: true});
  const hint = {id: 'hint-visible', actor_id: 'a'.repeat(32), text: '<script>window.hintExecuted=true</script> An uncertain report',
    intent: 'Report what needs checking', cites: ['fact-visible'], source_ids: ['source-unverified']};
  try {
    await S.ready(page);
    page.on('request', request => {
      const value = new URL(request.url()).pathname.endsWith('/memory') ? {schema: 'spectator-view/3', available: true, store_schema: 'player-journal/1', records: [], hints: [hint], hints_omitted: 0} : null;
      if (value) request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(value)});
      else request.continue();
    });
    await page.setRequestInterception(true);
    await go(page, '#memory/player');
    await S.until(page, () => document.getElementById('app').innerText.includes('An uncertain report'));
    const body = await page.$eval('#app', node => node.innerText);
    for (const value of ['unverified player reports', hint.text, hint.intent, 'fact-visible', 'source-unverified']) assert.ok(body.includes(value), value);
    assert.doesNotMatch(body, /No memory records|0 written/);
    assert.equal(await page.evaluate(() => window.hintExecuted), undefined);
    await S.shot(page, 'current-hints-phone');
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('recorded reader keeps delivery, reports, operation and outcome distinct on a phone', {timeout: 30000}, async () => {
  const page = await openPage(`${fx.url}#memory/requests`, {width: 390, height: 900, mobile: true});
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
    assert.match(hits, /fact-visible · fact · The passage · match · needs review/);
    assert.match(hits, /<img src=x onerror=window\.hitExecuted=true>/);
    assert.equal(await page.$('.query-hits img'), null);
    assert.deepEqual(await page.$$eval('.query-hits button', buttons => buttons.map(b => b.textContent)), ['fact-visible', 'article-passage']);
    await page.focus('.query-hits li > button');
    await page.keyboard.press('Enter');
    await S.until(page, () => document.getElementById('app').innerText.includes('Entry fact-visible'));
    await S.until(page, () => document.activeElement?.matches('[data-reader-entry] > summary'));
    assert.equal(await page.evaluate(() => window.readerExecuted), undefined);
    assert.equal(await page.evaluate(() => window.hitExecuted), undefined);
    assert.equal(await page.$eval('#pause', button => button.disabled), false);
    // The frozen snapshot entry's delivered state: kind, evidence, scope class and axes, flags, tags, typed links and cited frames.
    const entry = await text(page, '[data-reader-entry]');
    for (const expected of [/Kind: entity property · evidence: observed · scope: world \(ruleset: standard\) · state: active · needs review · tags: passage/,
      /Links: see_also fact-other · cited frames: c6c09be0b7d43fba2839147651a4f6a5-2/]) assert.match(entry, expected);
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
  const page = await openPage(`${fx.url}#memory/requests`, {width: 390, height: 900, mobile: true});
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
        body = {schema: 'spectator-view/3', actors: phase ? fixture.actors : [], actors_omitted: 0, actor: null, request_id: null};
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

test('Memory & Curator opens configured draft manifests and gate results with the keyboard', {timeout: 30000}, async () => {
  const page = await S.open(browser, `${fx.url}#watch`, {width: 390, height: 900, mobile: true});
  const markup = '<img src=x onerror=window.curatorExecuted=true>';
  const active = {id: 'open-draft', bucket: 'active', state: 'open', untouched_sessions: 2,
    created_by_session: markup, last_touched_session: 'session-2', promoted_by_session: null,
    sessions: {items: ['session-1', 'session-2'], omitted: 0, values_omitted: 0}, max_bytes: 4096, retention_policy: 'retained'};
  const archived = {...active, id: 'promoted-draft', bucket: 'archived', state: 'promoted', promoted_by_session: 'session-3'};
  const gate = {index: 0, operation_id: 'b'.repeat(32), operation: 'submission', status: 'published', base_version: 'v1',
    restored_from: null, version: 'v2', submission: markup, session: 'session-3', from_drafts: [archived.id],
    from_drafts_omitted: 1, diagnostics: []};
  const schema = 'spectator-frame/1';
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
      if (route === 'curator-draft-sources' || route === 'curator-sources') body = sources;
      if (route === 'curator-drafts') {
        const after = +url.searchParams.get('after'), snapshot = url.searchParams.get('snapshot');
        pages.push({after, snapshot});
        if (snapshot && snapshot !== digest) {
          status = 409;
          body = {schema: 'spectator-view/3', error: 'source_changed', detail: ''};
        } else {
          body = {schema, source: 'fixture', source_status: 'available', snapshot: {sha256: digest, bytes: 300},
            items: [after ? archived : active], total: 26, next: after ? null : 25, limit: 25};
        }
      }
      if (route === 'curator-results') body = {schema, source: 'fixture', source_status: 'available', snapshot: {sha256: digest, bytes: 100},
        items: [gate], total: 1, next: null, limit: 25};
      if (body) return request.respond({status, contentType: 'application/json', body: JSON.stringify(body)});
      return request.continue();
    });
    await page.click('[data-nav="memory"]');
    const nav = 'nav[aria-label="Curator records"]';
    const drafts = '[data-curator-draft-source]';
    const row = '.curator-source-view button.link';
    const press = async selector => { await page.focus(selector); await page.keyboard.press('Enter'); };
    const button = async name => {
      await page.evaluate(n => Array.from(document.querySelectorAll('.curator-source-view button')).find(b => b.textContent === n).focus(), name);
      await page.keyboard.press('Enter');
    };
    await page.waitForSelector(`${nav} a[href="#memory/curator-drafts"]`);
    assert.match(await text(page, '.curator-records'), /Curator drafts & gate results/);
    assert.equal(await page.$('#more-sources [href="#memory/results"]'), null);
    assert.equal(await page.$eval('#more-sources', node => node.open), false);
    await press(`${nav} a[href="#memory/curator-drafts"]`);
    await page.waitForSelector(drafts);
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

    await press(`${nav} a[href="#memory/results"]`);
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
    assert.deepEqual(page.problems.filter(p => p !== 'http 409: /api/view/frame/curator-drafts'), []);
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
      const body = url.pathname.endsWith('/frame/curator-sources') ? {schema: 'spectator-frame/1', items: [{label: 'fixture'}], total: 1, next: null, limit: 500}
        : url.pathname.endsWith('/frame/curator-results') ? {schema: 'spectator-frame/1', source: 'fixture', source_status: 'available', snapshot: {sha256: digest, bytes: 123}, items: [row], total: 1, next: null, limit: 25} : null;
      if (body) request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
      else request.continue();
    });
    await go(page, '#memory/results');
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
  const status = {session: 'run', state: 'polling', updated_wall: 1700000002, stop_reason: null, look_error: null,
    position: {...place(30, 30), read_wall: walls}, as_of: {...place(30, 30), read_wall: walls}, after_last_read: 'unknown',
    current: null, covered_prefix: {end: place(25, 25), restore: {version: 'v3', restored_from: 'v0', counted_through: 'v2'}},
    lag: 'unknown', stamp_distance: 'unknown', backlog: 5,
    last_confirmed: {version: 'v1', label: 'actor-a-1-25-x', window: {session: 'run', actor: 'actor-a', first: 1, last: 25}, coverage: stamp, baseline: false},
    latest_version: {version: 'v3', coverage: null, baseline: false}, failures: {sessions: 0, snapshots: 0}, unconfirmed: 0,
    examined: {items: [{label: 'actor-a-1-25-x', window: {session: 'run', actor: 'actor-a', first: 1, last: 25}, session_id: 's',
      outcome: 'accepted', advanced: true, started_wall: 1699999990, ended_wall: 1e20}, unknownRow], total: 2, omitted: 0},
    unexamined: {items: null, total: null, omitted: null}};
  let state = 'available';
  const asked = [];
  try {
    await S.ready(page);
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      if (!url.pathname.endsWith('/frame/curator-runner')) return request.continue();
      asked.push(url.searchParams.get('run'));
      const body = {schema: 'spectator-frame/1', source_status: state, read_wall: 1700000003,
        snapshot: state === 'missing' ? null : {sha256: 'a'.repeat(64), bytes: state === 'available' ? 900 : 40},
        status: state === 'available' ? status : null};
      request.respond({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
    });
    await go(page, '#memory');
    await S.until(page, () => document.querySelector('[data-runner-facts]'));
    assert.ok(asked.every(run => run === S.SESSIONS.ceil09), 'the selected run\'s own runner is asked for');
    await page.$eval('.runnerbox', d => { d.open = true; });
    const facts = await page.$$eval('[data-runner-facts] dt', dts => Object.fromEntries(dts.map(dt => [dt.textContent, dt.nextElementSibling.textContent])));
    assert.match(facts['Play has reached'], /actor actor-a · step 30 · operation op-30 · finished operation 30/);
    assert.match(facts['As of'], /2023-11-14T22:13:21Z/);
    assert.equal(facts['After the last read'], 'unknown');
    // The recorded end and, past the restore, unknown.
    assert.match(facts['Covered prefix ends at'], /step 25 .*· unknown past the restore of v3 to v0 \(versions counted through v2\)/);
    assert.equal(facts['Lag (finished operations after the covered prefix)'], 'unknown');
    assert.equal(facts['Distance from the latest stamp'], 'unknown');
    assert.equal(facts["Backlog (finished steps beyond the curator's cursor)"], '5');
    assert.equal(facts['Last confirmed version'], 'v1 · stamp: session run · actor actor-a · last step 25 · baseline: no');
    assert.equal(facts['Latest version seen'], 'v3 · stamp: no stamp · baseline: no');
    assert.match(await text(page, '.curator-strip .stats'), /Covers through\s*step 25\s*unknown past a restore\s*Lag\s*unknown[\s\S]*Backlog\s*5/);
    const table = await page.$eval('.curator-strip table.data', n => n.innerText);
    assert.match(table, /actor actor-a · steps 1–25\s+accepted\s+yes\s+2023-11-14T22:13:10Z\s+unknown/);
    assert.match(table, /unknown\s+unknown\s+unknown\s+unknown\s+unknown/);
    assert.equal(await S.overflow(page), 0);
    await S.shot(page, 'curator-runner-status-phone');
    // The panel stays mounted; each later poll alone must clear the figures.
    await page.$eval('.curator-strip', n => { n.dataset.kept = 'yes'; });
    for (const [next, words] of [['missing', 'missing'], ['malformed', 'partly written']]) {
      state = next;
      await S.until(page, t => document.querySelector('[data-runner-status]')?.textContent.includes(t), words, 15000);
      assert.equal(await page.$eval('.curator-strip', n => n.dataset.kept), 'yes', 'the panel was not remounted');
      assert.equal(await page.$('[data-runner-facts]'), null, `${next} shows no figures`);
      assert.doesNotMatch(await text(page, '.curator-strip .stats'), /\bLag\b|Backlog|Latest version|Covers through/);
      assert.doesNotMatch(await text(page, '.curator-strip'), /Play has reached|Examined ranges/);
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
      if (url.pathname.endsWith('/frame/curator-sources')) {
        const later = url.searchParams.get('after') === '500';
        body = {schema: 'spectator-frame/1', items: (later ? ['last'] : labels).map(label => ({label})), total: 501, next: later ? null : 500, limit: 500};
      } else if (url.pathname.endsWith('/frame/curator-results')) {
        const source = url.searchParams.get('source'), old = url.searchParams.get('snapshot');
        if (source === 'failed' && fail) { failedRequests++; status = 503; body = {viewer: 'unavailable'}; }
        else if (old && old !== digest) { status = 409; body = {schema: 'spectator-view/3', error: 'source_changed'}; }
        else {
          const state = ['empty', 'missing', 'malformed'].includes(source) ? source : 'available';
          body = {schema: 'spectator-frame/1', source, source_status: state, snapshot: ['missing'].includes(source) ? null : {sha256: digest, bytes: 123},
            items: state === 'available' ? [row] : [], total: state === 'available' ? 1 : 0, next: null, limit: 25};
        }
      }
      if (body) request.respond({status, contentType: 'application/json', body: JSON.stringify(body)});
      else request.continue();
    });
    await page.setRequestInterception(true);
    await go(page, '#memory/results');
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
    await S.shot(page, 'curator-source-changed');
    const press = name => page.evaluate(n => Array.from(document.querySelectorAll('button')).find(b => b.textContent === n).click(), name);
    await press('Refresh results');
    await S.until(page, () => document.querySelector('[data-curator-status]')?.textContent.includes('available'));
    assert.equal(await page.$('[data-curator-detail]'), null);
    await page.select('[data-curator-source]', 'empty');
    await S.until(page, () => document.querySelector('[data-curator-status]')?.textContent.includes('contains no results'));
    await S.shot(page, 'curator-source-empty');
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
    assert.deepEqual(page.problems.filter(p => !p.startsWith('http 409: /api/view/frame/curator-results')), []);
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
      if (url.pathname.endsWith('/frame/curator-session-sources')) return request.respond({status: 200, contentType: 'application/json', body: JSON.stringify({schema: 'spectator-frame/1', items: [{label: 'receipt'}], total: 1, next: null, limit: 500})});
      if (url.pathname.endsWith('/frame/curator-session')) {
        if (changed && url.searchParams.has('snapshot')) return request.respond({status: 409, contentType: 'application/json', body: JSON.stringify({schema: 'spectator-view/3', error: 'source_changed'})});
        return request.respond({status: 200, contentType: 'application/json', body: JSON.stringify({schema: 'spectator-frame/1', source: 'receipt', source_status: 'available', snapshot: {sha256: digest, bytes: 20}, header: {id: 's1', inputs: {session_kind: 'admission'}, pinned: {}, budgets: {cap_usd: '2'}, lifecycle: {state: 'sealed'}, resources: {}, published_after: 'v1'}, drafts: null, items: [row], total: 1, next: null, limit: 25})});
      }
      request.continue();
    });
    await go(page, '#memory/sessions');
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
    await S.shot(page, 'curator-session-changed');
    assert.deepEqual(page.problems.filter(p => !p.startsWith('http 409: /api/view/frame/curator-session')), []);
  } finally { await page.close(); }
});
