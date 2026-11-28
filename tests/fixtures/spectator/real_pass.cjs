// Manual pass of every view against a REAL viewer (not part of `node --test`; needs a running viewer):
//   VIEWER=http://127.0.0.1:8765 SPECTATOR_SHOTS=/some/dir node tests/fixtures/spectator/real_pass.cjs
// The fixture server forwards /api/view/* to the viewer and still stubs the control path. Prints
// console errors, failed requests, horizontal overflow and text that looks broken, per view and
// configuration, and saves a full-page screenshot of each, and one of Watch with the Step Inspector open on a real step.
const {spawn} = require('node:child_process');
const path = require('node:path');
const S = require('./support.cjs');

const ROUTES = ['#watch', '#memory', '#memory/articles', '#memory/facts', '#memory/usage', '#curator', '#diagnostics', '#diagnostics/metrics',
  '#diagnostics/readers', '#runs/lineage', '#runs/compare', '#runs/explore', '#runs/changes', '#runs/failures', '#runs/archive', '#runs/archive/containers',
  '#runs/archive/player'];
const CONFIGS = [['light', 1280, 'light', false], ['dark', 1280, 'dark', false], ['phone', 390, 'light', true]];

function start(viewer) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.env.PYTHON || 'python3', ['-I', path.join(__dirname, 'server.py'), '--viewer', viewer], {stdio: ['ignore', 'pipe', 'inherit']});
    child.stdout.once('data', chunk => resolve({url: JSON.parse(String(chunk).split('\n')[0]).url, stop: () => child.kill()}));
    child.on('exit', code => reject(new Error(`server exited (${code})`)));
  });
}

(async () => {
  const viewer = process.env.VIEWER;
  if (!viewer) throw new Error('set VIEWER to a running viewer, e.g. http://127.0.0.1:8765');
  const label = process.env.LABEL || 'real';
  const fx = await start(viewer);
  const browser = await S.launch();
  let bad = 0;
  try {
    for (const [name, width, scheme, mobile] of CONFIGS) {
      const page = await S.open(browser, `${fx.url}#watch`, {width, height: mobile ? 800 : 900, scheme, mobile});
      await S.ready(page);
      const check = async (what, shot) => {
        const text = await page.$eval('#app', n => n.innerText);
        const broken = text.match(/.{0,30}(undefined|NaN|\[object|Loading).{0,30}/);
        const overflow = await S.overflow(page);
        const problems = page.problems.splice(0);
        if (broken || overflow || problems.length) bad++;
        console.log(`${label} ${name} ${what}`, JSON.stringify({overflow, problems, broken: broken && broken[0]}));
        await S.shot(page, `${label}-${shot}-${name}`);
      };
      for (const route of ROUTES) {
        await page.evaluate(h => { location.hash = h; }, route);
        await S.settle(page, 1500);
        await check(route, route.replace(/[#/]/g, '_'));
      }
      // The drawer over a step the run really took: the newest card that made one.
      await page.evaluate(() => { location.hash = '#watch'; });
      await S.settled(page);
      await page.$$eval('#story .card.step', cards => cards.find(c => !c.textContent.includes('(on screen)')).querySelector('.inspect').click());
      await S.until(page, () => document.querySelector('#inspector .drawerbody'));
      await S.settle(page, 1500);
      console.log(`${label} ${name} inspector:`, await page.$eval('#inspector header', n => n.innerText.replace(/\s+/g, ' ').slice(0, 60)));
      await check('#watch with the Step Inspector open', '_watch-inspector');
      await page.close();
    }
  } finally { await browser.close(); fx.stop(); }
  console.log(bad ? `${bad} view(s) with problems` : 'all views clean');
  process.exitCode = bad ? 1 : 0;
})().catch(error => { console.error(error); process.exit(1); });
