// Spectator page: the interpretive viewer in four run tabs (Watch, Memory, Curator, Diagnostics) and the All runs
// workspace. The control strip (Pause, status and frame) is static markup driven by control.js and does not depend on
// this module.
import {html, render, useState, useEffect, useLayoutEffect, useRef, kilo, plural, runName, usd2} from './ui.js';
import {store, set, useStore, useView, startPolling, selectRun, sessionOf, setCursorSeq, liveRun, selectedRun, followingLive,
  recordedPage, runPath} from './data.js';
import {pauseMet} from './supervise.js';
import {Watch} from './watch.js';
import {MemoryTab} from './memory.js';
import {CuratorTab} from './curator.js';
import {Diagnostics, spendParts} from './diagnostics.js';
import {AllRuns, RUNS_SECTIONS} from './allruns.js';

const TABS = {watch: Watch, memory: MemoryTab, curator: CuratorTab, diagnostics: Diagnostics};
const VERSION = /^(?:v\d+|initial)$/;

/** `#<tab>/<section>?run=&step=&entry=&version=&csess=`, `#runs/<section>`, and the older `#memory/<version>`. */
export function parseRoute(hash = location.hash) {
  const raw = hash.replace(/^#/, '');
  const at = raw.indexOf('?');
  const path = at < 0 ? raw : raw.slice(0, at);
  const params = new URLSearchParams(at < 0 ? '' : raw.slice(at + 1));
  const [head, ...rest] = path.split('/');
  let section = rest.join('/');
  try { section = decodeURIComponent(section); } catch { /* not an encoded name */ }
  if (head === 'runs') {
    const [first, ...deeper] = section.split('/');
    return {view: 'runs', section: RUNS_SECTIONS.some(([id]) => id === first) ? first : 'lineage', sub: deeper.join('/'), params, version: '', csess: '', key: raw};
  }
  const view = Object.hasOwn(TABS, head) ? head : 'watch';
  const version = params.get('version') || (view === 'memory' && VERSION.test(section) ? section : '');
  return {view, section: view === 'memory' && VERSION.test(section) ? '' : section, params, version, csess: params.get('csess') || '', key: raw};
}
function useRoute() {
  const [route, setRoute] = useState(parseRoute());
  useEffect(() => {
    const f = () => setRoute(parseRoute());
    addEventListener('hashchange', f);
    return () => removeEventListener('hashchange', f);
  }, []);
  return route;
}

/** A deep link's run, step and entry, applied once each as the data they name arrives; later owner choices stand. */
function useDeepLink(route) {
  const done = useRef({key: null});
  useEffect(() => {
    const d = done.current;
    if (d.key !== route.key) Object.assign(d, {key: route.key, run: false, step: false, entry: false});
    const run = route.params.get('run'), step = route.params.get('step'), entry = route.params.get('entry');
    if (!d.run) {
      if (!run) d.run = true;
      else if (store.runs) {
        const session = sessionOf(run);
        d.run = true;
        if (session && session !== store.runId) { selectRun(session); return; }
      }
    }
    if (!d.run) return;
    if (step && !d.step && store.steps.length && Number.isFinite(Number(step))) { d.step = true; setCursorSeq(Number(step)); }
    if (entry && !d.entry && store.feedMeta && route.view === 'watch') {
      const found = store.feed.find(e => String(e.id) === entry);
      d.entry = true;
      // The inspector is a step's; any other entry is placed on the playhead only.
      if (found) set({...(found.entry_kind === 'step' ? {inspect: found.id} : {}), ...(found.seq === null || step ? {} : {cursor: found.seq})});
    }
  });
}

function Banner() {
  if (store.viewerOk) return null;
  return html`<div class="banner down" role="status"><span class="state alert">viewer unavailable</span>
    <span>Interpretive panels show the last data received, greyed, or wait for the viewer.${recordedPage ? '' : ' The control strip and Pause do not use the viewer and are unaffected.'}</span></div>`;
}

function App() {
  useStore();
  const route = useRoute();
  const {view} = route;
  useDeepLink(route);
  useEffect(() => {
    for (const link of document.querySelectorAll('nav.jobs [data-nav]')) {
      if (link.dataset.nav === view) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    }
  }, [view]);
  const run = selectedRun();
  useEffect(() => {
    const name = run ? `${runName(run)} · ${run.state} — Enactive Spectator` : 'Enactive Spectator';
    document.title = store.viewerOk ? name : 'viewer unavailable — Enactive Spectator';
  }, [run && run.session, run && run.state, store.viewerOk]);
  // Page-wide states, as attributes the stylesheet reads. Without this module, or with the viewer down, none of them is
  // set and the control strip shows its own frame in full. `watchStage` is set only while Watch has painted the same
  // capture, so the strip's copy is a duplicate; `pauseAlert` only marks the Pause button, which works the same either way.
  const stage = store.viewerOk && view === 'watch' && store.stageLive;
  const alert = store.viewerOk && pauseMet(store.summary);
  useLayoutEffect(() => {   // before the browser paints: the strip's frame never misses the moment it is the only one
    const flags = document.documentElement.dataset;
    flags.viewer = store.viewerOk ? 'ok' : 'down';
    if (stage) flags.watchStage = 'ok'; else delete flags.watchStage;
    if (alert) flags.pauseAlert = 'yes'; else delete flags.pauseAlert;
  }, [store.viewerOk, stage, alert]);
  const body = view === 'runs' ? html`<${AllRuns} section=${route.section} sub=${route.sub} />` : html`<${TABS[view]} section=${route.section} version=${route.version} csess=${route.csess} />`;
  return html`<div class="app" data-viewer=${store.viewerOk ? 'ok' : 'down'} data-route=${view}><${Banner} />${body}</div>`;
}

/* ---------------------------------------------------------------- the viewer's part of the strip */
const limitOf = s => (s.facts && typeof s.facts.spend_allowance_usd === 'number' ? s.facts.spend_allowance_usd : null);

/** The loop's spend: every part that is recorded, summed; the player's part against its limit; each part in the title. */
function SpendPill({s}) {
  const p = spendParts(s);
  const limit = limitOf(s);
  const player = p.player.usd === null ? null : Number(p.player.usd);
  const total = p.sum !== null ? p.sum : player;
  const estimate = total === null && typeof s.dollars === 'number' ? s.dollars : null;
  if (total === null && estimate === null) return null;
  const parts = [[p.playerName, p.player.usd], ['Curator ingestion', p.ingestion.usd], ['Interleaved hygiene', p.hygiene.usd], ['Boundary grooming', p.boundary.usd]];
  const title = `${total !== null ? `Loop spend ${usd2(total)}${p.partial ? ' (partial)' : ''}` : `Configured-rate estimate ${usd2(estimate)}; no provider cost is recorded`}`
    + `${limit === null ? '' : `. Player ${usd2(player)} of a ${usd2(limit)} limit`}. ${parts.map(([n, v]) => `${n}: ${v === null || v === undefined ? 'unavailable' : usd2(v)}`).join(' · ')}`;
  return html`<a class="spill spend" id="pill-spend" href="#diagnostics" title=${title}><span class="sub">Spend</span>
    <b class="num">${total !== null ? usd2(total) : `~${usd2(estimate)}`}</b>${total !== null && p.partial ? html`<span class="sub">*</span>` : estimate !== null ? html`<span class="sub">est</span>` : null}
    ${limit && player !== null ? html`<progress max=${limit} value=${Math.min(player, limit)} aria-label="Player spend against its limit"></progress>` : null}</a>`;
}

/** The latest prompt while the playhead follows live, else the run's median; cuts; and a held wait for coverage. */
function ContextPill({s, live}) {
  const host = s.host_telemetry;
  if (!host) return null;
  const t = host.token_summary, waits = host.coverage_waits || {count: 0, active_count: 0};
  const shown = live ? t.latest_prompt_tokens : t.p50_prompt_tokens;
  if (shown === null) return null;
  const active = waits.active_count > 0;
  const held = active && waits.latest && waits.latest.active ? waits.latest.duration_seconds : null;
  const title = `Prompt tokens: latest ${kilo(t.latest_prompt_tokens)}, p50 ${kilo(t.p50_prompt_tokens)}, max ${kilo(t.max_prompt_tokens)}. ${plural(host.context_cuts.applied, 'context cut')} applied, `
    + `${plural(waits.count, 'coverage wait')}${active ? `, ${waits.active_count} still holding requests` : ''}`;
  return html`<a class="spill" id="pill-context" href="#watch" title=${title}><b class="num">${kilo(shown)} tok</b><span class="sub num">${live ? '' : 'p50 · '}${plural(host.context_cuts.applied, 'cut')}</span>
    ${active ? html`<span class="waitbadge" id="wait-badge">WAIT${held === null ? '' : ` ${Math.round(held)}s`}</span>` : null}</a>`;
}

/** The knowledge version the player holds now, and how far the curator's coverage lags play, when its runner says. */
function HeadPill({s, run, live}) {
  const host = s.host_telemetry;
  const version = host ? (host.knowledge_deliveries && host.knowledge_deliveries.latest_version) || host.knowledge_updates.latest_version : null;
  const curator = useView(version && run ? runPath(run, 'curator') : null, live ? 10000 : 0);
  if (!version) return null;
  const status = curator.data && curator.data.runner && curator.data.runner.status;
  const lag = status && typeof status.lag === 'number' ? status.lag : null;
  return html`<a class="spill" id="pill-curator" href=${`#memory?version=${encodeURIComponent(version)}`} title=${`Head knowledge version the player holds: ${version}${lag === null ? '' : `; curator coverage lags play by ${plural(lag, 'operation')}`}`}>
    <span class="sub">Head</span><b class="num">${version}</b>${lag ? html`<span class="sub num">lag ${lag}</span>` : null}</a>`;
}

/** Availability and, for a run evaluated live, how far the evaluator has read. */
function ViewerStatus({s}) {
  const ok = store.viewerOk;
  const fresh = s && s.evaluator_freshness;
  const latest = s ? s.latest_step_seq : null;
  const behind = fresh && typeof fresh.last_seq === 'number' && typeof latest === 'number' && latest - fresh.last_seq > 10;
  const title = recordedPage ? 'Reads existing evaluation records' : `The viewer computes interpretive values; Pause and checks never depend on it${fresh ? `. Live evaluator: ${fresh.passes} passes, last evaluated step ${fresh.last_seq} of ${latest}${fresh.error ? `, error ${fresh.error}` : ''}` : ''}`;
  return html`<span class="viewer ${ok ? '' : 'down'} ${behind ? 'behind' : ''}" id="viewer" title=${title} role="status">${ok
    ? html`${store.viewerSeen ? 'ok' : 'connecting'}${fresh && fresh.last_seq !== null && fresh.last_seq !== undefined ? html`<span class="evalf num"> · eval #${fresh.last_seq}/${latest ?? '—'}</span>` : null}`
    : 'viewer unavailable'}</span>`;
}

function runOption(r) {
  const admission = r.labels && r.labels.admission !== null && r.labels.admission !== undefined ? ` · a${String(r.labels.admission).padStart(2, '0')}` : '';
  return `${runName(r)} · ${r.labels.arm || 'no arm'}${admission}${r.state === 'live' ? ' · live' : r.state === 'unfinished' ? ' · not finalized' : ''}${r.outcome.lost ? ' · lost' : ''}`;
}
/** Runs grouped by lineage, in the order the viewer lists them; runs of no lineage stand alone. */
function RunPicker({runs}) {
  const groups = [];
  for (const r of runs) {
    const name = r.labels && r.labels.lineage ? r.labels.lineage : null;
    const last = groups[groups.length - 1];
    const found = name === null ? null : groups.find(g => g.name === name);
    if (found) found.runs.push(r);
    else if (name === null && last && last.name === null) last.runs.push(r);
    else groups.push({name, runs: [r]});
  }
  const option = r => html`<option key=${r.session} value=${r.session} selected=${r.session === store.runId}>${runOption(r)}</option>`;
  return html`<select class="runpick" id="runpick" aria-label="Run to show" title=${selectedRun() ? runOption(selectedRun()) : 'Run to show'} value=${store.runId || ''} disabled=${!runs.length} onChange=${e => selectRun(e.target.value)}>
    ${runs.length ? groups.map(g => (g.name === null ? g.runs.map(option) : html`<optgroup label=${`Lineage ${g.name}`}>${g.runs.map(option)}</optgroup>`)) : html`<option>no runs</option>`}</select>`;
}

function StripViewer() {
  useStore();
  const route = useRoute();
  const runs = store.runs || [];
  const run = selectedRun();
  const s = store.summary;
  const live = liveRun();
  const ok = store.viewerOk;
  const mine = ok && s && run && s.session === run.session;
  return html`<div class="strip-viewer">
    <span class="runbox"><${RunPicker} runs=${runs} /><a class="spill allruns" id="all-runs-btn" href="#runs/lineage" aria-current=${route.view === 'runs' ? 'page' : null}>All runs</a></span>
    <span class="vfacts ${ok ? '' : 'greyed'}" id="viewer-facts">${mine ? html`${run.state === 'live' ? null : html`<span class="spill plain">${run.state === 'unfinished' ? 'ended, not finalized' : 'final'}</span>`}
      ${live && run.session !== live.session ? html`<span class="state watch">not the live run</span>` : null}
      <${SpendPill} s=${s} /><${ContextPill} s=${s} live=${followingLive()} /><${HeadPill} s=${s} run=${store.runId} live=${!!s.live} key=${store.runId} />` : null}</span>
    <${ViewerStatus} s=${mine ? s : null} /></div>`;
}

/** Beside Pause, the viewer's own reading that a Pause condition is met; it opens the conditions. Pause is unchanged. */
function PauseBadge() {
  useStore();
  const s = store.summary;
  if (!store.viewerOk || !pauseMet(s)) return null;
  return html`<a class="pausealert" id="pausealert" href="#diagnostics/pause" title=${`Pause condition met: ${s.pause.met.join('; ')}. Open the conditions.`}><span aria-hidden="true">◆</span> Pause? <span class="why">${s.pause.met[0]}</span></a>`;
}

/* ---------------------------------------------------------------- start */
if (recordedPage) {
  document.body.dataset.recorded = '';
  document.getElementById('watch').closest('header').setAttribute('aria-label', 'Recorded spectator');
}
// Panels that stick below the bar read its height; the bar wraps on narrow screens, so it is measured, not assumed.
const header = document.querySelector('header.ctl');
const measure = () => document.documentElement.style.setProperty('--header-h', `${Math.ceil(header.getBoundingClientRect().height)}px`);
measure();
if (typeof ResizeObserver === 'function') new ResizeObserver(measure).observe(header);
document.getElementById('app').replaceChildren();
render(html`<${App} />`, document.getElementById('app'));
render(html`<${StripViewer} />`, document.getElementById('strip-viewer'));
const slot = document.getElementById('viewer-alert');
if (slot) render(html`<${PauseBadge} />`, slot);
startPolling();
