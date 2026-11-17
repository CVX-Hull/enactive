// Spectator page: every view renders in light, dark and a 390 px phone without console errors,
// failed requests or horizontal overflow. Browser behavior against the fixture server only:
// no game, no provider, and no claim about the real viewer's data.
const {test, before, after} = require('node:test');
const assert = require('node:assert/strict');
const S = require('./fixtures/spectator/support.cjs');

const ROUTES = ['#live', '#run/overview', '#run/tools', '#run/programs', '#run/memory', '#run/handoffs', '#run/context',
  '#improve/changes', '#improve/failures', '#improve/components', '#explore', '#compare',
  '#frame/actor', '#frame/curator', '#frame/knowledge', '#frame/programs', '#frame/containers'];
const CONFIGS = [['light', 1280, 'light', false], ['dark', 1280, 'dark', false], ['phone', 390, 'light', true]];
let fx, browser;
before(async () => { fx = await S.startFixture(); browser = await S.launch(); });
after(async () => { if (browser) await browser.close(); if (fx) fx.stop(); });

for (const [name, width, scheme, mobile] of CONFIGS) {
  test(`every view renders cleanly: ${name} (${width}px)`, {timeout: 120000}, async () => {
    const page = await S.open(browser, `${fx.url}#live`, {width, height: mobile ? 800 : 900, scheme, mobile});
    try {
      await S.ready(page);
      for (const route of ROUTES) {
        await page.evaluate(h => { location.hash = h; }, route);
        await S.settle(page, 900);
        const text = await page.$eval('#app', node => node.innerText);
        const panels = await page.$$eval('#app .panel', nodes => nodes.length);
        assert.ok(panels > 0, `${route} rendered no panels`);
        assert.doesNotMatch(text, /undefined|NaN|\[object|Loading/, `${route} shows a broken value: ${text.match(/.{0,30}(undefined|NaN|\[object|Loading).{0,30}/)}`);
        assert.equal(await S.overflow(page), 0, `${route} scrolls horizontally at ${width}px`);
        assert.deepEqual(page.problems, [], `${route} had problems`);
        await S.shot(page, `${route.replace(/[#/]/g, '_')}-${name}`);
      }
      const active = await page.$eval('html', el => getComputedStyle(el).colorScheme);
      assert.match(active, scheme === 'dark' ? /dark/ : /light/);
    } finally { await page.close(); }
  });
}

test('frame: an episode anchor opens the live view at its step, and a container opens its manifest', {timeout: 60000}, async () => {
  const page = await S.open(browser, `${fx.url}#frame/actor`, {scheme: 'light'});
  try {
    await S.ready(page);
    await S.until(page, () => document.querySelector('[data-anchor="observed"] button.btn'));
    const slots = await page.$$eval('[data-slot]', nodes => nodes.map(n => [n.dataset.slot, n.className.includes('pending')]));
    assert.deepEqual(slots.map(s => s[0]), ['actor_cadence', 'curator_lag', 'gate_pass_rate', 'snapshot_freshness',
      'program_delegation_share', 'monitor_alerts', 'spend_against_cap']);
    assert.deepEqual(slots.slice(1).map(s => s[1]), [true, true, true, true, true, true]);
    const arrives = await page.$$eval('[data-slot] .sub', nodes => nodes.slice(1).map(n => n.textContent));
    assert.deepEqual(arrives, [1, 1, 1, 0, 0, 1].map(curator => `arrives in the ${curator ? 'curator and memory' : 'programs and monitor'} phase`));
    assert.match(await page.$eval('#app', n => n.innerText), /frame unavailable/i);   // the text-only anchor and the uncatalogued run
    await page.click('[data-anchor="observed"] button.btn');
    await S.until(page, () => location.hash === '#live');
    await S.until(page, () => { const back = document.getElementById('feed-back'); return back && back.disabled; });   // the playhead is on the first step
    await page.evaluate(h => { location.hash = h; }, '#frame/containers');
    await S.until(page, () => document.querySelector('#app table.data button.link'));
    await page.click('#app table.data button.link');
    await S.until(page, () => /container-manifest\/1/.test(document.getElementById('app').innerText));
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('theme button switches tokens and keeps the page clean', {timeout: 30000}, async () => {
  const page = await S.open(browser, `${fx.url}#live`, {scheme: 'light'});
  try {
    await S.ready(page);
    const before = await page.$eval('body', el => getComputedStyle(el).backgroundColor);
    await page.click('#theme');
    await S.settle(page, 500);
    const dark = await page.$eval('body', el => getComputedStyle(el).backgroundColor);
    assert.notEqual(before, dark);
    assert.equal(await page.$eval('html', el => el.dataset.theme), 'dark');
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('no network origin is used: every request stays on the page origin', {timeout: 30000}, async () => {
  const page = await browser.newPage();
  const foreign = [];
  page.on('request', r => { if (!r.url().startsWith(fx.origin) && !r.url().startsWith('blob:') && !r.url().startsWith('data:')) foreign.push(r.url()); });
  await page.goto(`${fx.url}#live`, {waitUntil: 'load'});
  await S.settle(page, 1500);
  await page.close();
  assert.deepEqual(foreign, []);
});

test('current hints stay unverified text and retired programs are explicit', {timeout: 30000}, async () => {
  const page = await S.open(browser, `${fx.url}#live`, {width:390,height:900,mobile:true});
  const hint = {id:'hint-visible',actor_id:'a'.repeat(32),text:'<script>window.hintExecuted=true</script> An uncertain report',
    intent:'Report what needs checking',cites:['fact-visible'],source_ids:['source-unverified']};
  try {
    await S.ready(page);
    page.on('request', request => {
      const path = new URL(request.url()).pathname;
      const value = path.endsWith('/memory') ? {schema:'spectator-view/1',available:true,store_schema:'player-journal/1',records:[],hints:[hint],hints_omitted:0}
        : path.endsWith('/programs') ? {schema:'spectator-view/1',capability:'retired',store_schema:'player-journal/1',programs:[],runs:[],saves:[]} : null;
      if (value) request.respond({status:200,contentType:'application/json',body:JSON.stringify(value)});
      else request.continue();
    });
    await page.setRequestInterception(true);
    await page.evaluate(() => { location.hash='#run/memory'; });
    await S.until(page, () => document.getElementById('app').innerText.includes('An uncertain report'));
    const text = await page.$eval('#app', node => node.innerText);
    for (const value of ['unverified player reports',hint.text,hint.intent,'fact-visible','source-unverified']) assert.ok(text.includes(value),value);
    assert.doesNotMatch(text,/No memory records|0 written/);
    assert.equal(await page.evaluate(() => window.hintExecuted),undefined);
    await S.shot(page,'current-hints-phone');
    assert.equal(await S.overflow(page),0);
    await page.evaluate(() => { location.hash='#run/programs'; });
    await S.until(page, () => document.getElementById('app').innerText.includes('Programs are unavailable for this run'));
    assert.doesNotMatch(await page.$eval('#app', node => node.innerText),/Insufficient sample/);
    assert.deepEqual(page.problems,[]);
  } finally { await page.close(); }
});
