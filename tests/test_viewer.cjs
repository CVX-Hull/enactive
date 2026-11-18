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

for (const [name, width, scheme, mobile] of [CONFIGS[0], CONFIGS[2]]) {
  test(`Overview shows the selected recorded custodian receipt: ${name}`, {timeout: 30000}, async () => {
    const page = await S.open(browser, `${fx.url}#run/overview`, {width, scheme, mobile});
    try {
      await S.ready(page);
      await S.until(page, () => document.querySelector('#runpick')?.value === 'ceil09' && document.querySelector('#app dl'));
      assert.equal(await page.$eval('[data-view="run"] .panel header .note', el => el.textContent), 'live');
      assert.equal(await page.$('.custodian-receipt'), null);
      const pause = () => page.$eval('#pause', b => [b.textContent, b.disabled]);
      const before = await pause();
      await page.select('#runpick', 'aidA1');
      await S.until(page, () => document.querySelector('.custodian-receipt dl'));
      assert.equal(await page.$eval('[data-view="run"] .panel header .note', el => el.textContent), 'final record');
      assert.equal(await page.$eval('#runpick', el => el.value), 'aidA1');
      assert.match(await page.$eval('.custodian-receipt', el => el.innerText), /recorded process and input state/);
      const facts = await page.$$eval('.custodian-receipt dd', rows => rows.map(row => row.textContent));
      assert.deepEqual(facts, ['Player reported external stop complete (unassessed)', 'Yes', 'Yes', 'Unavailable', 'No']);
      assert.equal(await S.overflow(page), 0);
      await S.shot(page, `custodian-receipt-${name}`);

      await page.focus('.src-details summary');
      await page.keyboard.press('Tab');
      assert.equal(await page.$eval('#runpick', el => el === document.activeElement), true);
      await page.select('#runpick', 'aidA2');
      await S.until(page, () => document.querySelector('.custodian-receipt p')?.textContent.includes('unavailable'));
      assert.equal(await page.$eval('#runpick', el => el.value), 'aidA2');
      assert.deepEqual(await pause(), before);
      assert.deepEqual(page.problems, []);
    } finally { await page.close(); }
  });
}

test('recorded Overview shows exact provider cost, unknown attempts and unavailable accounting', {timeout: 30000}, async () => {
  await fx.viewer('nolive');
  const page = await S.open(browser, `${fx.url}recorded/`, {width: 390, mobile: true});
  try {
    const amount = label => page.$$eval('#app .kv dt', (terms, label) =>
      terms.find(term => term.textContent === label)?.nextElementSibling.textContent.trim(), label);
    const waitForAmount = (label, value) => S.until(page, ([label, value]) =>
      Array.from(document.querySelectorAll('#app .kv dt')).some(term => term.textContent === label &&
        term.nextElementSibling.textContent.trim().startsWith(value)), [label, value]);
    await waitForAmount('Provider-reported subtotal', '$1.64493095');
    assert.match(await amount('Provider-reported subtotal'), /custodian receipt/);
    assert.equal(await amount('Counted toward run limit'), undefined);
    assert.equal(await amount('Unpriced attempts'), '1 player · 1 recall');
    assert.match(await amount('Estimated spend'), /configured rate/);

    await page.select('#runpick', 'aidA3');
    await waitForAmount('Provider-reported cost', '$0');
    assert.match(await amount('Provider-reported cost'), /^\$0\s.*custodian receipt/s);
    assert.equal(await amount('Counted toward run limit'), undefined);

    await page.select('#runpick', 'aidA4');
    await waitForAmount('Provider-reported cost', 'Unavailable');
    assert.equal(await amount('Provider-reported cost'), 'Unavailable');
    assert.ok(await page.$('.custodian-receipt dl'));
    await page.select('#runpick', 'aidA2');
    await S.until(page, () => document.querySelector('.custodian-receipt p')?.textContent.includes('unavailable'));
    assert.equal(await amount('Provider-reported cost'), 'Unavailable');
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); await fx.viewer('up'); }
});

test('recorded viewer opens Overview and follows findings without a control path', {timeout: 30000}, async () => {
  await fx.viewer('stale-recorded');
  const page = await S.open(browser, 'about:blank', {width: 390, mobile: true});
  const requests = [];
  page.on('request', request => requests.push([request.method(), new URL(request.url()).pathname]));
  try {
    await page.goto(`${fx.url}recorded/`, {waitUntil: 'load'});
    await S.until(page, () => document.querySelector('[data-view="run"] .custodian-receipt dl'));
    assert.equal(await page.$eval('[data-view="run"] .panel header .note', el => el.textContent), 'evaluation unfinished');
    const first = await page.$eval('#runpick', el => el.value);
    assert.equal(first, 'aidA1');
    assert.equal(await page.$('#pause, #sheet, #statusline, #frame'), null);
    const playback = '[data-nav="live"]';
    assert.equal(await page.$eval(playback, el => el.textContent), 'Recorded playback');
    await page.click(playback);
    await S.until(page, () => document.querySelector('#findings button[data-jump]'));
    const step = await page.$eval('#findings button[data-jump]', el => el.dataset.jump);
    await page.click('#findings button[data-jump]');
    await S.until(page, seq => document.querySelector('#playinfo')?.textContent.includes(`Playhead at step ${seq} ·`), step);
    await S.until(page, () => document.querySelector('#feed:not([hidden])')?.width > 0);
    assert.equal(await page.$eval('#runpick', el => el.value), first);
    assert.equal(await page.$('#feed-live, .pausebox'), null);
    assert.equal(await page.$eval('#backlive', el => el.textContent), 'return to latest recorded step');
    assert.equal(await S.overflow(page), 0);
    assert.deepEqual(page.problems, []);
    assert.ok(requests.some(([,path]) => path.startsWith('/api/view/run/aidA1/frame/')));
    assert.deepEqual(requests.filter(([method,path]) => method !== 'GET' || /^\/api\/(?:status|source|pause)\b|\/app\/control\.js/.test(path)), []);
  } finally { await page.close(); await fx.viewer('up'); }
});

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
      const value = path.endsWith('/memory') ? {schema:'spectator-view/2',available:true,store_schema:'player-journal/1',records:[],hints:[hint],hints_omitted:0}
        : path.endsWith('/programs') ? {schema:'spectator-view/2',capability:'retired',store_schema:'player-journal/1',programs:[],runs:[],saves:[]} : null;
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

test('recorded reader keeps delivery, reports, operation and outcome distinct on a phone', {timeout: 30000}, async () => {
  const page = await S.open(browser, `${fx.url}#frame/actor`, {width:390,height:900,mobile:true});
  try {
    await S.ready(page);
    await S.until(page, () => [...(document.querySelector('[data-reader-actor]')?.options || [])].some(o => o.value === 'actor-1'));
    await page.select('[data-reader-actor]', 'actor-1');
    await S.until(page, () => document.getElementById('app').innerText.toLowerCase().includes('public hints (unverified)'));
    await page.select('[data-reader-request]', 'request-1');
    await S.until(page, () => document.querySelector('[data-reader-request]')?.value === 'request-1');
    await page.evaluate(() => { for (const d of document.querySelectorAll('#app details')) d.open = true; });
    let text = await page.$eval('#app', n => n.innerText);
    for (const expected of ['knowledge-delivery', 'Move carefully', 'fact-visible', 'The visible passage may be blocked',
      'Receipt disposition: delivered', 'I believe I am done', 'Evaluator outcome', 'Original frame']) assert.ok(text.toLowerCase().includes(expected.toLowerCase()), expected);
    const buttons = await page.$$('button');
    const fact = await Promise.all(buttons.map(b => b.evaluate(el => el.textContent)));
    await buttons[fact.indexOf('fact-visible')].focus();
    await page.keyboard.press('Enter');
    await S.until(page, () => document.getElementById('app').innerText.includes('Entry fact-visible'));
    await S.until(page, () => document.activeElement?.matches('[data-reader-entry] > summary'));
    assert.equal(await page.evaluate(() => window.readerExecuted), undefined);
    assert.equal(await S.overflow(page), 0);
    await S.shot(page, 'recorded-reader-phone');
    await page.select('[data-reader-actor]', 'actor-2');
    await S.until(page, () => document.getElementById('app').innerText.includes('Public journal unavailable.'));
    text = await page.$eval('#app', n => n.innerText);
    assert.doesNotMatch(text, /Entry fact-visible/);
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});


test('recorded reader refreshes actors and public reports while staying on the page', {timeout:30000}, async () => {
  const page = await S.open(browser, `${fx.url}#frame/actor`, {width:390,height:900,mobile:true});
  const fixture = JSON.parse(require('node:fs').readFileSync(require('node:path').join(__dirname,'fixtures/spectator/knowledge.json'),'utf8'));
  let phase=0, emptySeen=false;
  try {
    await page.setRequestInterception(true);
    page.on('request', r => {
      const url=new URL(r.url());
      if (!url.pathname.endsWith('/knowledge')) { r.continue(); return; }
      let body;
      if (!url.searchParams.get('actor')) {
        emptySeen ||= phase===0;
        body={schema:'spectator-view/2',actors:phase ? fixture.actors : [],actors_omitted:0,actor:null,request_id:null};
      } else {
        body=structuredClone(fixture);
        if (phase===2) { body.hints[0].text='A later public hint'; body.requests.push('request-2'); }
      }
      r.respond({status:200,contentType:'application/json',body:JSON.stringify(body)});
    });
    await page.reload({waitUntil:'load'});
    await S.ready(page);
    await S.until(page, () => !!document.querySelector('[data-reader-actor]'));
    assert.equal(emptySeen,true);
    assert.deepEqual(await page.$$eval('[data-reader-actor] option', ns=>ns.map(n=>n.value)),['']);
    phase=1;
    await S.until(page, () => [...(document.querySelector('[data-reader-actor]')?.options || [])].some(o=>o.value==='actor-1'));
    await page.select('[data-reader-actor]','actor-1');
    await S.until(page, () => document.getElementById('app').innerText.includes('The visible passage may be blocked'));
    phase=2;
    await S.until(page, () => document.getElementById('app').innerText.includes('A later public hint'));
    assert.ok(await page.$$eval('[data-reader-request] option', ns=>ns.some(n=>n.value==='request-2')));
    assert.equal(await S.overflow(page),0);
    assert.deepEqual(page.problems,[]);
  } finally { await page.close(); }
});

test('curator results select and show escaped recorded detail on a phone', {timeout: 30000}, async () => {
  const page = await S.open(browser, `${fx.url}#live`, {width:390,height:900,mobile:true});
  const digest = 'a'.repeat(64);
  const row = {index:0,operation_id:'b'.repeat(32),operation:'submission',status:'unknown',base_version:'v1',
    restored_from:null,version:null,submission:'<img src=x onerror=window.curatorExecuted=true>',session:'session',
    diagnostics:['<b>recorded diagnostic'],diagnostics_omitted:0};
  try {
    await S.ready(page);
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      const body = url.pathname.endsWith('/frame/curator-sources') ? {schema:'spectator-frame/1',items:[{label:'fixture'}],total:1,next:null,limit:500}
        : url.pathname.endsWith('/frame/curator-results') ? {schema:'spectator-frame/1',source:'fixture',source_status:'available',snapshot:{sha256:digest,bytes:123},items:[row],total:1,next:null,limit:25} : null;
      if (body) request.respond({status:200,contentType:'application/json',body:JSON.stringify(body)});
      else request.continue();
    });
    await page.evaluate(() => { location.hash='#frame/curator'; });
    await S.until(page, () => Array.from(document.querySelector('[data-curator-source]')?.options || []).some(o => o.value === 'fixture'));
    await page.select('[data-curator-source]', 'fixture');
    await S.until(page, () => document.querySelector('table.data button.link'));
    await page.focus('table.data button.link');
    await page.keyboard.press('Enter');
    await S.until(page, () => document.querySelector('[data-curator-detail]'));
    const text = await page.$eval('[data-curator-detail]', n => n.innerText);
    assert.match(text, /unknown/); assert.ok(text.includes(row.submission)); assert.ok(text.includes(row.diagnostics[0]));
    assert.equal(await page.evaluate(() => window.curatorExecuted), undefined);
    assert.equal(await S.overflow(page), 0);
    await S.until(page, () => document.activeElement?.hasAttribute('data-curator-detail'));
    await S.shot(page, 'curator-results-phone');
    await page.select('[data-curator-source]', '');
    await S.until(page, () => !document.querySelector('[data-curator-detail]'));
    assert.deepEqual(page.problems, []);
  } finally { await page.close(); }
});

test('curator paging and refresh keep empty, changed and failed sources distinct', {timeout: 30000}, async () => {
  const page = await S.open(browser, `${fx.url}#live`);
  let digest = 'a'.repeat(64), fail = true, failedRequests = 0;
  const labels = ['first','empty','missing','malformed','failed', ...Array.from({length:495},(_,i)=>`extra-${i}`)];
  const row = {index:0,operation_id:'b'.repeat(32),operation:'restore',status:'unchanged',base_version:'v2',
    restored_from:'v0',version:'v2',submission:null,session:null,diagnostics:[],diagnostics_omitted:0};
  try {
    await S.ready(page);
    page.on('request', request => {
      const url = new URL(request.url());
      let body, status=200;
      if (url.pathname.endsWith('/frame/curator-sources')) {
        const later = url.searchParams.get('after') === '500';
        body={schema:'spectator-frame/1',items:(later?['last']:labels).map(label=>({label})),total:501,next:later?null:500,limit:500};
      } else if (url.pathname.endsWith('/frame/curator-results')) {
        const source=url.searchParams.get('source'), old=url.searchParams.get('snapshot');
        if (source==='failed' && fail) { failedRequests++; status=503; body={viewer:'unavailable'}; }
        else if (old && old!==digest) { status=409; body={schema:'spectator-view/2',error:'source_changed'}; }
        else { const state=['empty','missing','malformed'].includes(source)?source:'available';
          body={schema:'spectator-frame/1',source,source_status:state,snapshot:['missing'].includes(source)?null:{sha256:digest,bytes:123},
            items:state==='available'?[row]:[],total:state==='available'?1:0,next:null,limit:25}; }
      }
      if (body) request.respond({status,contentType:'application/json',body:JSON.stringify(body)});
      else request.continue();
    });
    await page.setRequestInterception(true);
    await page.evaluate(()=>{location.hash='#frame/curator';});
    await S.until(page,()=>Array.from(document.querySelector('[data-curator-source]')?.options||[]).some(o=>o.value==='first'));
    await page.select('[data-curator-source]','first');
    await S.until(page,()=>document.querySelector('table.data button.link'));
    await page.click('table.data button.link');
    await S.until(page,()=>document.querySelector('[data-curator-detail]'));
    await S.shot(page,'curator-results-desktop');
    digest='c'.repeat(64);
    await S.until(page,()=>document.querySelector('[data-curator-error]')?.textContent.includes('Source changed'));
    assert.equal(await page.$('[data-curator-detail]'),null);
    assert.equal(await page.$('table.data'),null);
    await S.shot(page,'curator-source-changed');
    await page.evaluate(()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Refresh results').click());
    await S.until(page,()=>document.querySelector('[data-curator-status]')?.textContent.includes('available'));
    assert.equal(await page.$('[data-curator-detail]'),null);
    await page.select('[data-curator-source]','empty');
    await S.until(page,()=>document.querySelector('[data-curator-status]')?.textContent.includes('contains no results'));
    await S.shot(page,'curator-source-empty');
    for (const source of ['missing','malformed']) {
      await page.select('[data-curator-source]',source);
      await S.until(page,label=>document.querySelector('[data-curator-status]')?.textContent.includes(label),source);
      assert.equal(await page.$('table.data'),null);
    }
    page.expect503=true;
    await page.select('[data-curator-source]','failed');
    await S.until(page,()=>document.querySelector('[data-curator-error]')?.textContent.includes('Viewer unavailable'));
    const before=failedRequests;
    fail=false;
    await page.evaluate(()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Refresh results').click());
    await S.until(page,()=>document.querySelector('[data-curator-status]')?.textContent.includes('available'),null,2000);
    assert.equal(failedRequests,before);
    assert.equal(await page.evaluate(()=>document.activeElement?.hasAttribute('data-curator-source')),true);
    page.expect503=false;
    await page.select('[data-curator-source]','first');
    await S.until(page,()=>document.querySelector('table.data button.link'));
    await page.click('table.data button.link');
    await page.evaluate(()=>Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Next sources').click());
    await S.until(page,()=>Array.from(document.querySelector('[data-curator-source]')?.options||[]).some(o=>o.value==='last'));
    assert.equal(await page.$eval('[data-curator-source]',n=>n.value),'');
    assert.equal(await page.$('[data-curator-detail]'),null);
    assert.equal(await page.$('[data-curator-status]'),null);
    assert.deepEqual(page.problems.filter(p=>!p.startsWith('http 409: /api/view/frame/curator-results')),[]);
  } finally { await page.close(); }
});

test('curator session selects a receipt and resets detail when its snapshot changes', {timeout: 30000}, async () => {
  const page = await S.open(browser, `${fx.url}#live`, {width:390,height:900,mobile:true});
  const digest = 'a'.repeat(64);
  const row = {index:0,operation_id:'b'.repeat(32),operation:'submission',status:'unknown',base_version:'v1',
    restored_from:null,version:null,submission:'s',session:'session',diagnostics:[],diagnostics_omitted:0};
  let changed = false;
  try {
    await S.ready(page);
    await page.setRequestInterception(true);
    page.on('request', request => {
      const url = new URL(request.url());
      if (url.pathname.endsWith('/frame/curator-session-sources')) return request.respond({status:200,contentType:'application/json',body:JSON.stringify({schema:'spectator-frame/1',items:[{label:'receipt'}],total:1,next:null,limit:500})});
      if (url.pathname.endsWith('/frame/curator-session')) {
        if (changed && url.searchParams.has('snapshot')) return request.respond({status:409,contentType:'application/json',body:JSON.stringify({schema:'spectator-view/2',error:'source_changed'})});
        return request.respond({status:200,contentType:'application/json',body:JSON.stringify({schema:'spectator-frame/1',source:'receipt',source_status:'available',snapshot:{sha256:digest,bytes:20},header:{id:'s1',inputs:{session_kind:'admission'},pinned:{},budgets:{cap_usd:'2'},lifecycle:{state:'sealed'},resources:{},published_after:'v1'},drafts:null,items:[row],total:1,next:null,limit:25})});
      }
      request.continue();
    });
    await page.evaluate(() => { location.hash='#frame/curator'; });
    await S.until(page, () => Array.from(document.querySelector('[data-session-source]')?.options || []).some(o => o.value === 'receipt'));
    await page.select('[data-session-source]', 'receipt');
    await S.until(page, () => document.querySelector('table.data button.link'));
    await page.focus('table.data button.link'); await page.keyboard.press('Enter');
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
