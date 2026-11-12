// Graphical lane for the redesigned spectator (#383). Not part of `node --test`.
// Starts tests/spectator_lane_fixture.py (real control path + real viewer over a replayed run),
// drives the page in a real browser, kills the viewer, checks that the page reports the outage
// while the control strip and Pause keep working, and pauses with a reason.
// Usage: node tests/spectator_lane.cjs <fixture dir under .runtime> <archived run> <runs dir> <records> <shots dir>
'use strict';
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const puppeteer = require('puppeteer');

const [dir, source, runs, records, shots] = process.argv.slice(2);
const root = path.resolve(__dirname, '..');
const python = path.join(root, '.venv/bin/python');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = [];
const note = (k, v) => { log.push({ step: k, value: v, at: new Date().toISOString() }); console.log(k, JSON.stringify(v)); };

(async () => {
  fs.mkdirSync(shots, { recursive: true });
  const fixture = spawn(python, ['-m', 'tests.spectator_lane_fixture', '--directory', dir, '--source', source,
    '--runs', runs, '--records', records, '--instant-until', '1200', '--seconds', '420'], { cwd: root, stdio: ['ignore', 'pipe', 'inherit'] });
  const ready = await new Promise((resolve, reject) => {
    let buf = ''; fixture.stdout.on('data', d => { buf += d; const line = buf.split('\n').find(l => l.startsWith('{')); if (line) resolve(JSON.parse(line)); });
    fixture.on('exit', c => reject(new Error('fixture exited ' + c)));
  });
  note('fixture-ready', ready);
  const browser = await puppeteer.launch({ headless: true });
  const errors = [];
  const shoot = async (page, name) => { await page.screenshot({ path: path.join(shots, name + '.png'), fullPage: true }); };
  // The owner's page follows live; nothing on it has to be clicked for the run to continue.
  const owner = await browser.newPage();
  owner.on('console', m => { if (m.type() === 'error') errors.push(`owner: ${m.text()}`); });
  await owner.setViewport({ width: 1440, height: 900 });
  await owner.goto(ready.url + '#live', { waitUntil: 'networkidle2' });
  const strip = () => owner.evaluate(() => { const f = document.getElementById('frame');
    return { connection: document.getElementById('connection').dataset.state, frame: !!f && !f.hidden && f.complete && f.naturalWidth > 0,
      pause: !document.getElementById('pause').disabled }; });
  for (let i = 0; i < 60; i++) {   // poll: waitForFunction proved unreliable here
    const s = await strip();
    if (s.connection === 'ok' && s.frame) break;
    await sleep(500);
  }
  note('strip-first', await strip());
  try {
    for (const [name, vw, dark] of [['desktop-light', 1440, false], ['desktop-dark', 1440, true], ['phone', 390, false]]) {
      const page = await browser.newPage();
      page.on('console', m => { if (m.type() === 'error') errors.push(`${name}: ${m.text()}`); });
      page.on('pageerror', e => errors.push(`${name}: ${e.message}`));
      await page.setViewport({ width: vw, height: 900 });
      await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: dark ? 'dark' : 'light' }]);
      const views = name === 'desktop-light' ? ['live', 'run/overview', 'run/tools', 'run/programs', 'run/memory', 'run/handoffs', 'run/context',
        'improve/changes', 'improve/failures', 'improve/components', 'explore', 'compare'] : ['live'];
      for (const v of views) {
        await page.goto(ready.url + '#' + v, { waitUntil: 'networkidle2' });
        await sleep(2500);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        if (overflow > 0) errors.push(`${name}/${v}: horizontal overflow ${overflow}px`);
        await shoot(page, `${name}-${v.replace('/', '-')}`);
      }
      await page.close();
    }
    // Replay progress: the viewer's decision count grows while it is alive.
    const decisions = async () => owner.evaluate(async () => (await (await fetch('/api/view/runs')).json()).items.find(r => r.state === 'live')?.decisions);
    const first = await decisions(); await sleep(20000);
    note('live-decisions-over-20s', { before: first, after: await decisions() });
    await shoot(owner, 'owner-live-before-kill');
    // Kill the viewer; the page must say so, and the control strip and Pause must still work.
    process.kill(ready.viewer_pid, 'SIGKILL'); note('viewer-killed', ready.viewer_pid);
    await sleep(8000);
    note('strip-viewer-after-kill', await owner.$eval('#strip-viewer', e => e.textContent));
    await shoot(owner, 'owner-after-viewer-kill');
    note('strip-after-kill', await strip());
    // Pause with a reason through the confirmation sheet.
    await owner.focus('#pause'); await owner.keyboard.press('Enter'); await sleep(600);
    await shoot(owner, 'owner-pause-sheet');
    await owner.click('#reasons input[value="other"]');
    await owner.click('#sheetsubmit'); await sleep(3000);
    note('pause-result', await owner.$eval('#pause-result', e => e.textContent).catch(() => null));
    await shoot(owner, 'owner-after-pause');
  } finally {
    await browser.close();
    const code = await new Promise(r => { const t = setTimeout(() => { fs.writeFileSync(path.join(dir, 'finish-fixture'), ''); }, 20000); fixture.on('exit', c => { clearTimeout(t); r(c); }); });
    const result = JSON.parse(fs.readFileSync(path.join(dir, 'fixture-result.json'), 'utf8'));
    note('fixture-exit', code);
    note('fixture-result', { reason: result.reason, pause_reason: result.pause_reason,
      viewer_alive_at_end: result.viewer_alive_at_end, synthetic_channel_stopped: result.synthetic_channel_stopped });
    note('console-errors', errors);
    fs.writeFileSync(path.join(shots, 'lane-result.json'), JSON.stringify({ log, errors, result }, null, 1));
  }
})().catch(e => { console.error(e); process.exit(1); });
