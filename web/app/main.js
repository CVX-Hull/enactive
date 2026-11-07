// Spectator page: the interpretive viewer UI. The control strip (Pause, status, frame and the
// operator check) is static markup driven by control.js and does not depend on this module.
import {html, render, useState, useEffect, Pv, fmtMoney, runName} from './ui.js';
import {store, useStore, startPolling, selectRun, liveRun, selectedRun} from './data.js';
import {Supervise} from './supervise.js';
import {Diagnose} from './diagnose.js';
import {Improve} from './improve.js';
import {Explore, Compare} from './crossrun.js';

const VIEWS = ['live', 'run', 'improve', 'explore', 'compare'];
function parse() {
  const [view, section] = (location.hash || '#live').slice(1).split('/');
  return {view: VIEWS.includes(view) ? view : 'live', section: section || ''};
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
    <span>Interpretive panels show the last data received, greyed, or wait for the viewer. The control strip, Pause and the operator check do not use the viewer and are unaffected.</span></div>`;
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
  }, [run && run.run, run && run.state, store.viewerOk]);
  const page = view === 'live' ? html`<${Supervise} />` : view === 'run' ? html`<${Diagnose} section=${section} />` :
    view === 'improve' ? html`<${Improve} section=${section} />` : view === 'explore' ? html`<${Explore} />` : html`<${Compare} />`;
  return html`<div data-viewer=${store.viewerOk ? 'ok' : 'down'}><${Banner} />${page}</div>`;
}

/** The viewer's part of the strip: availability, run facts and the run picker. Control facts stay in control.js. */
function StripViewer() {
  useStore();
  const runs = store.runs || [];
  const run = selectedRun();
  const s = store.summary;
  const facts = s && s.facts ? s.facts : null;
  const live = liveRun();
  return html`<div class="strip-viewer">
    <span class="viewer ${store.viewerOk ? '' : 'down'}" id="viewer" title="The viewer computes interpretive values; Pause and checks never depend on it" role="status">${store.viewerOk ? (store.viewerSeen ? 'viewer · connected' : 'viewer · connecting') : 'viewer unavailable'}</span>
    <label class="note">Run <select class="runpick" id="runpick" aria-label="Run to show" value=${store.runId || ''} disabled=${!runs.length} onChange=${e => selectRun(e.target.value)}>
      ${runs.length ? runs.map(r => html`<option value=${r.run} selected=${r.run === store.runId}>${runName(r)} · ${r.arm}${r.state === 'live' ? ' · live' : ''}${r.censor_reason === 'infrastructure' ? ' · lost' : ''}</option>`) : html`<option>no runs</option>`}</select></label>
    <div class="vfacts ${store.viewerOk ? '' : 'greyed'}" id="viewer-facts">${store.viewerOk && facts && run ? html`<span>${runName(run)} ${run.state === 'live' ? 'running' : 'final'} · decision ${facts.decisions}</span>
      <span>${fmtMoney(s.pause?.spent)}${facts.ceiling_dollars ? ` of ${fmtMoney(facts.ceiling_dollars)}` : ''} <${Pv} source="recorded" detail="declared ceiling" /></span>
      <span>${facts.arm} · ${facts.start} · ${String(facts.source_commit || '').slice(0, 7)}</span>${live && run.run !== live.run ? html`<span class="state watch">not the live run</span>` : null}` : null}</div></div>`;
}

document.getElementById('app').replaceChildren();
render(html`<${App} />`, document.getElementById('app'));
render(html`<${StripViewer} />`, document.getElementById('strip-viewer'));
startPolling();
