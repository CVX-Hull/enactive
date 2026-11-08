// Supervise: should I Pause, what is on screen, and where is the playhead.
import {html, useEffect, useMemo, useRef, useState, Panel, Pv, ReadChip, Waiting, fmtMoney, mmss, gameClock, label, pct, trim} from './ui.js';
import {store, framePath, selectedRun, setCursorIndex, cursorIndex, goLive, isLive, runStart} from './data.js';
import {Chart, timelineOption, legendItems, nearestStep} from './charts.js';

const CONDITION_TEXT = {
  feed_alive: (v, c) => (v === null ? 'no operation recorded yet' : `${trim(v)} s since the last operation`),
  custody_healthy: v => `${v.uncertain_receipts} uncertain receipts · ${v.custody_stops} custody stops`,
  not_looping: v => `out-of-play streak ${v.decisions_out_of_play}, game time ${v.game_time_advancing ? 'advancing' : 'not advancing'}`,
  spend_inside_allowance: v => `${fmtMoney(v.spent)} spent, on pace for ${fmtMoney(v.projected_one_hour)} in an hour${v.ceiling === null ? ', no ceiling declared' : ` (ceiling ${fmtMoney(v.ceiling)})`}`,
  not_dead_and_spending: v => (v.died ? `death read, ${v.requests_after_death} requests since` : 'no death read'),
};
export const conditionText = c => (CONDITION_TEXT[c.id] ? CONDITION_TEXT[c.id](c.value, c) : String(c.value));

export function PauseConditions({summary}) {
  const pause = summary.pause;
  if (!pause) {
    return html`<${Panel} title="Pause?" note="the viewer computes these for the live run only" span="s7" className="pausebox">
      <p class="answer" id="pauseanswer">This run is not live, so there is nothing to pause.</p>
      <div class="insuf">Pause conditions (feed alive, custody, looping, spend, death with spending) appear while the viewer evaluates a live run.</div><//>`;
  }
  const answer = pause.met.length
    ? `Yes: ${pause.met.map(n => n.toLowerCase()).join('; ')}.`
    : `No. Waiting costs about ${fmtMoney(pause.dollars_per_minute)} a minute, which is the run working as intended.`;
  return html`<${Panel} title="Pause?" note="only conditions where continuing wastes money or invalidates evidence" span="s7" className="pausebox">
    <p class="answer" id="pauseanswer">${answer}</p>
    <ul class="conds" id="conds">${pause.conditions.map(c => html`<li class=${c.met ? 'met' : ''}>
      <span>${c.name}</span><span class="val">${conditionText(c)} · ${c.threshold} <${Pv} source="derived" /></span>
      ${c.met ? html`<span class="state alert">Pause</span>` : html`<span class="state clear">clear</span>`}</li>`)}</ul>
    <p class="note">Game danger is never on this list: survival is the player's job, and pausing at a dangerous moment would bias survival data.</p><//>`;
}

/** Readings in display order: mode, clock, vitals, limbs, threat, identity, death. Each keeps its own confidence and validation. */
export function readingRows(state) {
  const readings = state.readings || {};
  const rows = [];
  const add = (name, key, text) => {
    const r = readings[key];
    if (!r) return;
    rows.push(r.abstain ? {name, abstain: label(r.abstain)} : {name, text: text(r.value, r), reading: r});
  };
  add('Mode', 'mode', v => label(v));
  add('Game clock', 'game_time', v => gameClock(v));
  for (const key of ['thirst', 'hunger', 'weariness', 'pain']) {
    add(label(key).replace(/^./, c => c.toUpperCase()), `vital.${key}`, v => (v.critical ? 'critical' : v.label || `level ${pct(v.level)}`));
  }
  const limbs = Object.entries(readings).filter(([k]) => k.startsWith('vital.limb.'));
  if (limbs.length) {
    const usable = limbs.filter(([, r]) => !r.abstain);
    const critical = usable.filter(([, r]) => r.value && r.value.critical).length;
    rows.push(usable.length ? {name: 'Limbs', text: critical ? `${critical} critical` : 'none critical', reading: usable[0][1]} : {name: 'Limbs', abstain: 'not read'});
  }
  add('Creatures listed', 'threat', v => `${v.count} (${v.bucket})`);
  add('Identity', 'identity', v => v);
  add('Death screen', 'death', v => (v ? 'yes' : 'no'));
  return rows;
}

export function GameState({summary}) {
  const state = summary.game_state;
  const v = summary.versions || {};
  const rows = state ? readingRows(state) : [];
  return html`<${Panel} title="Game state" note=${`information only · binding ${v.binding_id || '?'} ${v.binding_version ?? ''}${state ? ` · as of step ${state.seq}` : ''}`} span="s5">
    ${rows.length ? html`<div class="state-grid" id="gamestate">${rows.map(r => html`<div><span>${r.name}</span>${
      r.abstain ? html`<span class="note">abstained: ${r.abstain}</span>` : html`<span>${r.text} <${ReadChip} reading=${r.reading} /></span>`}</div>`)}</div>`
      : html`<div class="insuf" id="gamestate">No frame has been read yet.</div>`}<//>`;
}

const SCALE_KEY = 'feed-scale';
function savedScale() {
  try { return localStorage.getItem(SCALE_KEY) === 'fit' ? 'fit' : 'native'; } catch { return 'native'; }
}

/** The game feed (#435). Each frame is decoded before it replaces the last one and is drawn at its own pixel size,
 *  so the picture never blanks or rescales as frames arrive. Hold freezes this view only: it sends nothing to the
 *  run and is unrelated to the custody Pause above. The step buttons move the shared playhead. */
const clockTime = ms => new Date(ms).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});

export function FeedPlayer({run, step}) {
  const liveRunSelected = selectedRun()?.state === 'live';
  const following = store.cursor === null && liveRunSelected;
  const src = following ? store.control.frameUrl : step && step.source_id ? framePath(run, step.source_id) : null;
  const canvas = useRef(null), shell = useRef(null);
  const [held, setHeld] = useState(false);
  const [scale, setScale] = useState(savedScale);
  const [shown, setShown] = useState(null);
  useEffect(() => {
    if (!src || held) return undefined;
    // What this frame is, fixed now: a newer frame arriving during the decode must not relabel it.
    const label = following
      ? {following: true, source: store.control.frameSource || null}
      : {following: false, seq: step ? step.seq : null, wall: step ? step.wall : null};
    let cancelled = false;
    const image = new Image();
    image.src = src;
    image.decode().then(() => {
      const target = canvas.current;
      if (cancelled || !target) return;
      if (target.width !== image.naturalWidth || target.height !== image.naturalHeight) {
        target.width = image.naturalWidth; target.height = image.naturalHeight;
      }
      target.getContext('2d').drawImage(image, 0, 0);
      setShown({...label, width: image.naturalWidth, height: image.naturalHeight});
    }).catch(() => { /* a frame that fails to decode leaves the last good one in place */ });
    return () => { cancelled = true; };
  }, [src, held]);
  const choose = value => { setScale(value); try { localStorage.setItem(SCALE_KEY, value); } catch { /* no storage */ } };
  const expand = () => { const el = shell.current; if (el && el.requestFullscreen) el.requestFullscreen().catch(() => {}); };
  // Stepping always shows the step it moves to, so it releases a held view.
  const stepTo = target => { setHeld(false); setCursorIndex(target); };
  const where = !shown ? 'waiting for the first frame'
    : shown.following ? `live · control path${shown.source ? ` · capture ${shown.source.capture_id} at ${clockTime(shown.source.presented_ms)}` : ''}`
    : `step ${shown.seq}${typeof shown.wall === 'number' ? ` at ${clockTime(shown.wall * 1000)}` : ''} · viewer · original frame · sha-256 checked`;
  const missing = !following && step && !step.source_id ? ` · no frame at step ${step.seq}` : '';
  const index = cursorIndex();
  const canExpand = typeof document !== 'undefined' && document.fullscreenEnabled;
  return html`<div class="s7 frame-col"><div class="player" ref=${shell} data-scale=${scale} data-held=${held ? 'yes' : 'no'}>
    <div class="player-bar" role="toolbar" aria-label="Feed player (view only; never pauses the run)">
      <button type="button" id="feed-back" aria-label="Previous recorded frame" title="Previous recorded frame" disabled=${index <= 0} onClick=${() => stepTo(index - 1)}>◀</button>
      <button type="button" id="feed-hold" aria-pressed=${held} title="Freeze this view; the run keeps going" onClick=${() => setHeld(!held)}>Hold view</button>
      <button type="button" id="feed-forward" aria-label="Next recorded frame" title="Next recorded frame" disabled=${index < 0 || index >= store.steps.length - 1} onClick=${() => stepTo(index + 1)}>▶</button>
      <button type="button" id="feed-live" title=${liveRunSelected ? 'Follow the live frame' : 'This run is not live'} disabled=${!liveRunSelected || (following && !held)} onClick=${() => { setHeld(false); goLive(); }}>Live</button>
      <span class="player-gap"></span>
      <button type="button" id="feed-scale" aria-pressed=${scale === 'fit'} title="Off: pixel for pixel (1:1). On: scaled to the column"
        onClick=${() => choose(scale === 'fit' ? 'native' : 'fit')}>Fit</button>
      ${canExpand ? html`<button type="button" id="feed-expand" title="Full screen" onClick=${expand}>Expand</button>` : null}
    </div>
    <div class="player-view">${src || shown ? null : html`<span class="frame-empty">No frame</span>`}
      <canvas ref=${canvas} id="feed" role="img" hidden=${!shown}
        aria-label=${shown ? `Game screen, ${where}` : 'Game screen not yet shown'}></canvas></div>
    <div class="player-meta" id="feed-meta" aria-live="off">${held ? 'held · ' : ''}${where}${shown ? ` · ${shown.width} × ${shown.height} · ${scale === 'fit' ? 'fit' : '1:1'}` : ''}${missing}</div>
  </div></div>`;
}

/** One line of text for a recorded finding. */
export function findingText(f) {
  const p = f.payload || {};
  switch (f.kind) {
    case 'stall': return `Out of play ${p.decisions} decisions${p.setup ? ' (setup)' : ''}${p.ongoing ? ', ongoing' : ''}`;
    case 'long_activity': return `Long activity: ${(p.seconds / 3600).toFixed(2)} game h in ${p.decisions} decisions`;
    case 'ineffective_repeat': return `Ineffective repeated input: ${p.key} × ${p.inputs}`;
    case 'handoff': return 'Handoff to the next actor';
    case 'death': return `Death read (cause ${p.cause || 'unknown'})`;
    case 'run_end': return `Run ended: ${label(p.reason || 'unknown')}`;
    case 'custody_stop': return `Custody stop: ${p.reason || label(p.cause || 'unknown')}`;
    case 'tool_refused': return `Tool refused: ${p.tool} (${p.reason})`;
    case 'memory_write': return `Memory write: ${p.record_kind} (cites ${p.sources} frames)`;
    case 'program_save': return 'Program saved';
    case 'context_eviction': return `Images evicted: ${p.omitted_images} omitted, ${p.retained_images} kept`;
    default: return label(f.kind);
  }
}

export function Findings({summary}) {
  // Image evictions are many and routine; they are the dotted lines on the timeline, not a feed row.
  const findings = (summary.findings || []).filter(f => f.kind !== 'context_eviction' && f.wall !== null);
  const t0 = runStart();
  const jump = f => {
    const i = store.steps.findIndex(s => s.seq >= f.seq_start);
    if (i >= 0) setCursorIndex(i);
    if (location.hash !== '#live') location.hash = '#live';
  };
  return html`<${Panel} title="Findings" note="recorded automatically for later analysis · image evictions are on the timeline" span="s5">
    ${findings.length ? html`<ul class="feed" id="findings">${findings.slice(0, 30).map(f => html`<li><button type="button" data-jump=${f.seq_start} onClick=${() => jump(f)}>
      <span class="t">${mmss(f.wall - t0)}</span><span>${findingText(f)}</span><${Pv} source=${f.source} detail=${f.confidence ? pct(f.confidence) : ''} /></button></li>`)}</ul>` : html`<div class="insuf" id="findings">No findings recorded yet.</div>`}<//>`;
}

export function Timeline({summary}) {
  const t0 = runStart();
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
      const i = nearestStep(chart, store.steps, runStart(), e.offsetX, e.offsetY);
      if (i !== null) setCursorIndex(i);
    });
  };
  const legend = useMemo(() => legendItems(), [store.themeEpoch]);
  const keys = step && step.keys && step.keys.length ? step.keys.join(' ') : '(observe)';
  const mode = step ? label(step.mode || 'unknown') : '';
  return html`<${Panel} title="Timeline" note="viewer · click or use ← → to move the playhead; checks re-enable when you return to live" span="s12">
    <div class="legend" id="tl-legend">${legend.map(([n, c]) => html`<span><i style=${{background: c}}></i>${n}</span>`)}</div>
    ${option ? html`<${Chart} option=${option} epoch=${store.themeEpoch} onReady=${onReady} onKeyDown=${onKeyDown} tabindex="0" className="tl" role="slider"
      label="Timeline of game clock, mode, cache writes with evictions, findings and spend. Left and right arrows move the playhead, End returns to live."
      extra=${{id: 'tl', 'aria-valuemin': 0, 'aria-valuemax': Math.max(0, steps.length - 1), 'aria-valuenow': Math.max(0, index), 'aria-valuetext': step ? `Step ${step.seq}${live ? ', live' : ''}` : 'no steps'}} />`
      : html`<${Waiting} store=${store} what="the timeline" />`}
    <div class="note" id="playinfo" role="status">${step ? html`Playhead at step ${step.seq}${live ? ' (live)' : ''} · ${mode} · keys ${keys}${live ? '' : html` · <button type="button" class="link" id="backlive" onClick=${goLive}>return to live</button>`}` : 'No steps yet.'}</div><//>`;
}

export function Supervise() {
  const s = store.summary, run = store.runId;
  if (!s) return html`<section class="grid" data-view="live" aria-label="Supervise"><${Panel} title="Supervise" span="s12"><${Waiting} store=${store} what="the run" /><//></section>`;
  const step = store.steps[cursorIndex()];
  return html`<section class="grid" data-view="live" aria-label="Supervise">
    <${PauseConditions} summary=${s} /><${GameState} summary=${s} />
    <${FeedPlayer} run=${run} step=${step} /><${Findings} summary=${s} />
    <${Timeline} summary=${s} /></section>`;
}
