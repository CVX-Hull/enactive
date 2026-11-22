// Spectator page: the interpretive viewer UI in three tabs. The control strip (Pause, status and frame)
// is static markup driven by control.js and does not depend on this module.
import {html, render, useState, useEffect, useLayoutEffect, count, kilo, plural, runName} from './ui.js';
import {store, useStore, startPolling, selectRun, liveRun, selectedRun, followingLive, recordedPage} from './data.js';
import {pauseMet} from './supervise.js';
import {Watch} from './watch.js';
import {MemoryTab} from './memory.js';
import {Diagnostics} from './diagnostics.js';

const VIEWS = {watch: Watch, memory: MemoryTab, diagnostics: Diagnostics};
function parse() {
  const [view, section] = location.hash.slice(1).split('/');
  let name = section || '';
  try { name = decodeURIComponent(name); } catch { /* not an encoded name */ }
  return {view: Object.hasOwn(VIEWS, view) ? view : 'watch', section: name};
}
function useRoute() {
  const [route, setRoute] = useState(parse());
  useEffect(() => {
    const f = () => setRoute(parse());
    addEventListener('hashchange', f);
    return () => removeEventListener('hashchange', f);
  }, []);
  return route;
}

function Banner() {
  if (store.viewerOk) return null;
  return html`<div class="banner down" role="status"><span class="state alert">viewer unavailable</span>
    <span>Interpretive panels show the last data received, greyed, or wait for the viewer.${recordedPage ? '' : ' The control strip and Pause do not use the viewer and are unaffected.'}</span></div>`;
}

function App() {
  useStore();
  const {view, section} = useRoute();
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
  const View = VIEWS[view];
  return html`<div class="app" data-viewer=${store.viewerOk ? 'ok' : 'down'}><${Banner} /><${View} section=${section} /></div>`;
}

/* ---------------------------------------------------------------- the viewer's part of the strip */
const dollars = text => `$${Number(text).toFixed(2)}`;

function SpendPill({s}) {
  const host = s.host_telemetry, curator = s.curator_spend;
  const limit = s.facts && typeof s.facts.spend_allowance_usd === 'number' ? s.facts.spend_allowance_usd : null;
  const reported = host ? host.reported_cost_usd : null;
  const value = reported !== null ? Number(reported) : s.dollars;
  if (typeof value !== 'number') return null;
  const curated = curator ? curator.spent_usd : null;
  const title = `${reported !== null ? `Provider-reported player and recall spend $${reported}${host.spend_complete === true ? '' : ' (partial)'}` : 'Configured-rate estimate; no provider cost is recorded'}${limit === null ? '' : `, limit $${limit.toFixed(2)}`}`
    + `${curator ? `. Live curator, proxy-accounted: ${curated === null ? 'unavailable' : `$${curated}`}, ${curator.sessions_settled} of ${curator.sessions_total} sessions settled` : ''}. Boundary grooming is not in these figures`;
  return html`<span class="spill spend" id="pill-spend" title=${title}><b class="num">${reported !== null ? dollars(reported) : `~${dollars(value)} est`}${limit === null ? '' : html`<span class="of"> / ${dollars(limit)}</span>`}</b>
    ${limit ? html`<progress max=${limit} value=${Math.min(value, limit)} aria-label="Player spend against its limit"></progress>` : null}
    ${curator ? html`<span class="sub num">+ ${curated === null ? 'unavailable' : dollars(curated)} curator${curator.spend_complete ? '' : '*'}</span>` : null}</span>`;
}
/** The latest prompt while the playhead follows live; the run's median while it is in history, held or on a recorded run. */
function ContextPill({s, live}) {
  const host = s.host_telemetry;
  if (!host) return null;
  const t = host.token_summary;
  const shown = live ? t.latest_prompt_tokens : t.p50_prompt_tokens;
  if (shown === null) return null;
  return html`<span class="spill" id="pill-context" title=${`Prompt tokens: latest ${kilo(t.latest_prompt_tokens)}, p50 ${kilo(t.p50_prompt_tokens)}, max ${kilo(t.max_prompt_tokens)}. ${plural(host.context_cuts.applied, 'context cut')} applied, ${host.context_cuts.held_back} held back`}>
    <b class="num">${kilo(shown)} tok</b><span class="sub num">${live ? '' : 'p50 · '}${plural(host.context_cuts.applied, 'cut')}</span></span>`;
}
/** The endpoint that answered last. How often each answered is in its title. */
function EndpointPill({s}) {
  const host = s.host_telemetry;
  const ends = host ? Object.entries(host.response_by_endpoint) : [];
  if (!ends.length) return null;
  const others = ends.filter(([name]) => name !== host.latest_provider).length;
  return html`<span class="spill" id="pill-endpoint" title=${`Last answering endpoint: ${host.latest_provider ?? 'unknown'}. Responses: ${ends.map(([n, c]) => `${n} ${count(c)}`).join(', ')}`}><b>${host.latest_provider ?? 'unknown'}</b>${others ? html`<span class="sub">+${others}</span>` : null}</span>`;
}

/** Availability, the run picker and the run's figures. Control facts stay in control.js. */
function StripViewer() {
  useStore();
  const runs = store.runs || [];
  const run = selectedRun();
  const s = store.summary;
  const live = liveRun();
  const ok = store.viewerOk;
  const version = s && s.host_telemetry ? s.host_telemetry.knowledge_updates.latest_version : null;
  const viewerTitle = recordedPage ? 'Reads existing evaluation records' : 'The viewer computes interpretive values; Pause and checks never depend on it';
  return html`<div class="strip-viewer">
    <select class="runpick" id="runpick" aria-label="Run to show" value=${store.runId || ''} disabled=${!runs.length} onChange=${e => selectRun(e.target.value)}>
      ${runs.length ? runs.map(r => html`<option key=${r.session} value=${r.session} selected=${r.session === store.runId}>${runName(r)} · ${r.labels.arm || 'no arm'}${r.state === 'live' ? ' · live' : r.state === 'unfinished' ? ' · not finalized' : ''}${r.outcome.lost ? ' · lost' : ''}</option>`) : html`<option>no runs</option>`}</select>
    <span class="vfacts ${ok ? '' : 'greyed'}" id="viewer-facts">${ok && s && run ? html`${run.state === 'live' ? null : html`<span class="spill plain">${run.state === 'unfinished' ? 'ended, not finalized' : 'final'}</span>`}
      ${live && run.session !== live.session ? html`<span class="state watch">not the live run</span>` : null}
      <${SpendPill} s=${s} /><${ContextPill} s=${s} live=${followingLive()} />
      ${version ? html`<a class="spill" id="pill-curator" href=${`#memory/${encodeURIComponent(version)}`} title="The knowledge version the player holds"><span class="sub">Curator</span><b class="num">${version}</b></a>` : null}
      <${EndpointPill} s=${s} />` : null}</span>
    <span class="viewer ${ok ? '' : 'down'}" id="viewer" title=${viewerTitle} role="status">${ok ? (store.viewerSeen ? 'viewer ok' : 'viewer connecting') : 'viewer unavailable'}</span></div>`;
}

if (recordedPage) {
  document.body.dataset.recorded = '';
  document.getElementById('watch').closest('header').setAttribute('aria-label', 'Recorded spectator');
}
document.getElementById('app').replaceChildren();
render(html`<${App} />`, document.getElementById('app'));
render(html`<${StripViewer} />`, document.getElementById('strip-viewer'));
startPolling();
