// Supervise: should I Pause, what is on screen, and where is the playhead.
import {html, useMemo, useRef, Panel, Pv, ReadChip, Waiting, fmtMoney, mmss, bytes} from './ui.js';
import {store, runPath, framePath, selectedRun, setCursorIndex, cursorIndex, goLive, isLive} from './data.js';
import {Chart, timelineOption, legendItems, nearestStep} from './charts.js';

export function PauseConditions({summary}) {
  const pause = summary.pause || {conditions: []};
  const met = pause.conditions.filter(c => c.met);
  const answer = met.length
    ? `Yes: ${met.map(c => c.name.toLowerCase()).join('; ')}.`
    : `No. Waiting costs about ${fmtMoney(pause.continuing_cost_per_minute)} a minute, which is the run working as intended.`;
  return html`<${Panel} title="Pause?" note="only conditions where continuing wastes money or invalidates evidence" span="s7" className="pausebox">
    <p class="answer" id="pauseanswer">${answer}</p>
    <ul class="conds" id="conds">${pause.conditions.map(c => html`<li class=${c.met ? 'met' : ''}>
      <span>${c.name}</span><span class="val">${c.value} · ${c.threshold} <${Pv} source=${c.source} /></span>
      ${c.met ? html`<span class="state alert">Pause</span>` : html`<span class="state clear">clear</span>`}</li>`)}</ul>
    <p class="note">Game danger is never on this list: survival is the player's job, and pausing at a dangerous moment would bias survival data.</p><//>`;
}

export function GameState({summary}) {
  const state = summary.game_state || {readings: []};
  return html`<${Panel} title="Game state" note=${`information only · binding: ${state.binding || 'unknown'}`} span="s5">
    <div class="state-grid" id="gamestate">${state.readings.map(r => html`<div><span>${r.label}</span>${
      r.abstain ? html`<span class="note">abstained: ${r.abstain}</span>` : html`<span>${r.value ?? '—'} <${ReadChip} reading=${r} /></span>`}</div>`)}</div><//>`;
}

function PlayheadFrame({run, step}) {
  const following = store.cursor === null && selectedRun()?.state === 'live';
  const live = store.control.frameUrl;
  const src = following ? live : step ? framePath(run, step.source_id) : null;
  return html`<div class="s7 frame-col"><div class="frame">${src ? html`<img src=${src} alt=${following ? 'Latest game screen from the control path' : `Game screen at step ${step.seq}`} />` : html`<span class="frame-empty">No frame</span>`}
    <span class="src">${following ? 'control path · /api/source · live' : `viewer · /api/view frame · step ${step ? step.seq : '—'} · sha-256 checked`}</span></div></div>`;
}

export function Findings({summary}) {
  const findings = [...(summary.findings || [])].sort((a, b) => b.wall - a.wall);
  const t0 = summary.facts?.started_wall ?? 0;
  const jump = f => {
    const i = store.steps.findIndex(s => s.seq >= f.seq);
    if (i >= 0) setCursorIndex(i);
    if (location.hash !== '#live') location.hash = '#live';
  };
  return html`<${Panel} title="Findings" note="recorded automatically for later analysis · no action needed" span="s5">
    ${findings.length ? html`<ul class="feed" id="findings">${findings.map(f => html`<li><button type="button" data-jump=${f.seq} onClick=${() => jump(f)}>
      <span class="t">${mmss(f.wall - t0)}</span><span>${f.text}</span><${Pv} source=${f.source} /></button></li>`)}</ul>` : html`<div class="insuf">No findings recorded yet.</div>`}<//>`;
}

export function Timeline({summary}) {
  const t0 = summary.facts?.started_wall ?? (store.steps[0] ? store.steps[0].wall : 0);
  const steps = store.steps;
  const cursorSeq = store.cursor;
  const option = useMemo(() => (steps.length ? timelineOption({steps, requests: store.requests, markers: store.markers, t0, cursorSeq}) : null),
    [steps, store.requests, store.markers, t0, cursorSeq, store.themeEpoch]);
  const chartRef = useRef(null);
  const index = cursorIndex();
  const step = steps[index];
  const live = isLive();
  const move = delta => setCursorIndex(index + delta);
  const onKeyDown = e => {
    if (e.key === 'ArrowLeft') { e.preventDefault(); move(e.shiftKey ? -10 : -1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); move(e.shiftKey ? 10 : 1); }
    else if (e.key === 'End') { e.preventDefault(); goLive(); }
    else if (e.key === 'Home') { e.preventDefault(); setCursorIndex(0); }
  };
  const onReady = chart => {
    chartRef.current = chart;
    chart.getZr().on('click', e => {
      const i = nearestStep(chart, store.steps, t0, e.offsetX, e.offsetY);
      if (i !== null) setCursorIndex(i);
    });
  };
  const legend = useMemo(() => legendItems(), [store.themeEpoch]);
  return html`<${Panel} title="Timeline" note="viewer · click or use ← → to move the playhead; checks re-enable when you return to live" span="s12">
    <div class="legend" id="tl-legend">${legend.map(([n, c]) => html`<span><i style=${{background: c}}></i>${n}</span>`)}</div>
    ${option ? html`<${Chart} option=${option} epoch=${store.themeEpoch} onReady=${onReady} onKeyDown=${onKeyDown} tabindex="0" className="tl" role="slider"
      label="Timeline of game clock, mode, cache writes with evictions, findings and spend. Left and right arrows move the playhead, End returns to live."
      extra=${{id: 'tl', 'aria-valuemin': 0, 'aria-valuemax': Math.max(0, steps.length - 1), 'aria-valuenow': Math.max(0, index), 'aria-valuetext': step ? `Step ${step.seq}${live ? ', live' : ''}` : 'no steps'}} />`
      : html`<${Waiting} store=${store} what="the timeline" />`}
    <div class="note" id="playinfo" role="status">${step ? html`Playhead at step ${step.seq}${live ? ' (live)' : ''} · ${step.mode === 'in_play' ? 'in play' : 'out of play'} · keys ${step.keys || '(observe)'}${live ? '' : html` · <button type="button" class="link" id="backlive" onClick=${goLive}>return to live</button>`}` : 'No steps yet.'}</div><//>`;
}

export function Supervise() {
  const s = store.summary, run = store.runId;
  if (!s) return html`<section class="grid" data-view="live" aria-label="Supervise"><${Panel} title="Supervise" span="s12"><${Waiting} store=${store} what="the run" /><//></section>`;
  const step = store.steps[cursorIndex()];
  return html`<section class="grid" data-view="live" aria-label="Supervise">
    <${PauseConditions} summary=${s} /><${GameState} summary=${s} />
    <${PlayheadFrame} run=${run} step=${step} /><${Findings} summary=${s} />
    <${Timeline} summary=${s} /></section>`;
}
