// The spectator's frame (ADR 009 D18): a health strip over role views. Actor works on real sealed data and shows
// the forgetting episodes; Curator, Knowledge and Programs say which phase brings them; Containers is the inventory.
// Read-only: every value comes from /api/view/frame/* (spectator-frame/1); anchors open the existing per-run views.
import {html, useState, Panel, Pv, Waiting, Table, Insufficient, Callout, fmtMoney, trim, label} from './ui.js';
import {store, framePath, selectRun, set, useView} from './data.js';
import {SubNav} from './diagnose.js';

const SCHEMA = 'spectator-frame/1';
export const ROLES = [['actor', 'Actor'], ['curator', 'Curator'], ['knowledge', 'Knowledge'], ['programs', 'Programs'], ['containers', 'Containers']];

/* The shared viewer fetch (outage marking, timeouts) with the frame's own schema. */
const useFrame = (path, every = 15000) => useView(path, every, SCHEMA);

/* ---------------------------------------------------------------- frame */
export function Frame({section}) {
  const role = ROLES.some(r => r[0] === section) ? section : 'actor';
  const body = role === 'actor' ? html`<${Actor} />` : role === 'containers' ? html`<${Containers} />` : html`<${Placeholder} role=${role} />`;
  return html`<section class="grid" data-view="frame" aria-label="Spectator frame">
    <div class="s12"><${Health} /></div>
    <div class="s12"><${SubNav} tabs=${ROLES} base="frame" current=${role} label="Roles" /></div>${body}</section>`;
}

/* A phase is served as its hyphenated name ('curator-and-memory'); the page shows it as words. */
const phaseName = phase => `the ${phase.replaceAll('-', ' ')} phase`;

/* ---------------------------------------------------------------- health strip */
function Slot({slot}) {
  if (slot.state === 'not-yet-measured') {
    return html`<div class="hslot pending" data-slot=${slot.id}><span class="name">${slot.label}</span>
      <span class="val">not yet measured</span><span class="sub">arrives in ${phaseName(slot.phase)}</span></div>`;
  }
  if (slot.state === 'measured') {
    return html`<div class="hslot" data-slot=${slot.id}><span class="name">${slot.label}</span>
      <span class="val">${slot.decisions_per_game_hour === null ? '—' : trim(+slot.decisions_per_game_hour.toFixed(1))} decisions per game hour</span>
      <span class="sub">${trim(slot.steps)} steps (${slot.steps_per_game_hour === null ? '—' : trim(+slot.steps_per_game_hour.toFixed(1))} per game hour) · ${trim(slot.decisions)} decisions in ${trim(+slot.game_hours.toFixed(1))} game hours · ${slot.runs} sealed run${slot.runs === 1 ? '' : 's'} · ${fmtMoney(slot.dollars)}</span>
      <span><${Pv} source=${slot.source} /></span></div>`;
  }
  return html`<div class="hslot pending" data-slot=${slot.id}><span class="name">${slot.label}</span>
    <span class="val">no data</span><span class="sub">${slot.detail || 'nothing recorded'}</span></div>`;
}

function Health() {
  const {data, error} = useFrame('frame/health');
  if (!data) return html`<${Panel} title="Health" span="s12"><${Waiting} store=${store} what="the health strip" error=${error} /><//>`;
  return html`<${Panel} title="Health" note=${`${data.containers} containers · ${data.runs} of their runs in the catalog`} span="s12">
    <div class="hstrip" role="list" aria-label="Health strip">${data.slots.map(slot => html`<div role="listitem" class=${slot.state === 'measured' ? 'hitem wide' : 'hitem'}><${Slot} slot=${slot} /></div>`)}</div>
    <p class="note">Slots that need the curator, the gate, snapshots or programs show no number until the phase that delivers them.</p><//>`;
}

/* ---------------------------------------------------------------- placeholders */
// What each role will show and when, from ADR 009 D18 and its phases. Nothing here is data.
const PLACEHOLDERS = {
  curator: ['curator-and-memory', 'Curator', 'A session timeline with lag; each session\'s brief, transcript summary, submissions and gate verdicts; submission diffs; open and stale drafts.'],
  knowledge: ['curator-and-memory', 'Knowledge', 'Facts with provenance frames, scope, belief and staleness; what each snapshot showed the actor and when. The ontology browser with versions and grooming history follows the ontology work.'],
  programs: ['programs-and-monitor', 'Programs', 'The program library with versions and statistics; live delegated runs with their progress; preemptions, yields, monitor flags and stops.'],
};
function Placeholder({role}) {
  const [phase, title, text] = PLACEHOLDERS[role];
  return html`<${Panel} title=${title} note=${`arrives in ${phaseName(phase)}`} span="s12">
    <${Insufficient}><b>Arrives in ${phaseName(phase)}.</b> There is no ${title.toLowerCase()} data yet, so this view shows none. ${text}<//><//>`;
}

/* ---------------------------------------------------------------- actor: the forgetting episodes */
const REASONS = {no_frame: 'no frame: stated in the actor\'s own text', run_not_in_catalog: 'its run is not in this viewer\'s catalog',
  unknown_frame: 'the run has no such frame', frame_unavailable: 'the frame file is missing', frame_digest_mismatch: 'the frame file fails its SHA-256 check',
  run_directory_unavailable: 'the run directory is not available', record_unavailable: 'the run\'s evaluation store cannot be read',
  ambiguous_run: 'two catalog runs share this run name; open it from the run list'};
const ANCHORS = [['observed', 'Observed'], ['needed', 'Needed'], ['acted_without', 'Acted without']];

/* One anchor opens at a time; navigating away or opening another cancels the pending one. */
let pending = null;

/** Select the run, wait for its steps to load, put the shared playhead on the step and open Live there. */
function openAnchor(anchor, setBusy, setFailed) {
  if (pending) pending.cancel();
  const from = location.hash;
  setBusy(anchor.source_id);
  setFailed(null);
  selectRun(anchor.run);
  const end = Date.now() + 90000;
  const timer = setInterval(() => {
    if (location.hash !== from) return finish();
    const step = store.runId === anchor.run ? store.steps.find(s => s.source_id === anchor.source_id) : null;
    if (step) {
      finish();
      set({cursor: step.seq});
      location.hash = '#live';
    } else if (Date.now() > end) {
      finish();
      setFailed(anchor.source_id);
    }
  }, 250);
  const finish = () => { clearInterval(timer); setBusy(null); if (pending && pending.timer === timer) pending = null; };
  pending = {timer, cancel: finish};
}

function Anchor({name, anchor, busy, setBusy, failed, setFailed}) {
  if (!anchor) return html`<div class="anchor"><b>${name}</b><span class="note">not recorded for this episode</span></div>`;
  const where = `${anchor.chunk}${anchor.run ? ` · run ${anchor.run}` : ''} · actor ${anchor.actor}`;
  return html`<div class="anchor" data-anchor=${name.toLowerCase()}><b>${name}</b><span class="mono wrapany">${where}</span>
    ${anchor.available ? html`<span class="acts">
        <button type="button" class="btn" disabled=${busy !== null} onClick=${() => openAnchor(anchor, setBusy, setFailed)}>${busy === anchor.source_id ? 'Opening…' : 'Open in Live view'}</button>
        <a href=${framePath(anchor.run, anchor.source_id)} target="_blank" rel="noopener">Original frame</a>
        <span class="note mono wrapany">${anchor.source_id}</span>
        ${failed === anchor.source_id ? html`<span class="state watch">the run's steps did not load in time; try again or open the original frame</span>` : null}</span>`
      : html`<span class="acts"><span class="state watch">frame unavailable</span><span class="note">${REASONS[anchor.reason] || label(anchor.reason || 'unknown')}</span></span>`}
    ${anchor.text ? html`<span class="note">${anchor.text}</span>` : null}</div>`;
}

function Episode({episode}) {
  const [busy, setBusy] = useState(null);
  const [failed, setFailed] = useState(null);
  return html`<${Panel} title=${episode.title} note=${`fact ${episode.fact}`} span="s6">
    <dl class="kv"><dt>Lost at</dt><dd>${episode.lost_at}</dd>
      <dt>Failing probe boundary</dt><dd>${episode.probe.boundary}</dd>
      <dt>Annotation layer</dt><dd>${episode.probe.annotation} <${Pv} source="human" /></dd></dl>
    <div class="anchors">${ANCHORS.map(([key, name]) => html`<${Anchor} name=${name} anchor=${episode[key]} busy=${busy} setBusy=${setBusy} failed=${failed} setFailed=${setFailed} />`)}</div><//>`;
}

function Actor() {
  const {data, error} = useFrame('frame/episodes');
  if (!data) return html`<${Panel} title="Actor" span="s12"><${Waiting} store=${store} what="the forgetting episodes" error=${error} /><//>`;
  if (!data.lineages.length) return html`<${Panel} title="Actor" span="s12"><${Insufficient}>No episodes are tracked.<//><//>`;
  return html`<${Panel} title="Actor" note="sealed traces · read-only" span="s12">
      <${Callout}><b>What this shows.</b> Facts the actor knew and then lost at a handoff, each anchored in the sealed frames where it was observed, needed and acted on without. Open an anchor to see the actor's decision at that frame. The live frame is on <a href="#live">Live</a>; intent, expectation and outcome side by side, citations, hints and the snapshot in use arrive in ${phaseName('curator-and-memory')} with required emissions.<//><//>
    ${data.lineages.map(lineage => html`<${Panel} title=${`Lineage ${lineage.lineage}`} note=${`study ${lineage.study}`} span="s12">
      <p class="note">${lineage.note}</p><//>
      ${lineage.episodes.map(episode => html`<${Episode} episode=${episode} />`)}`)}`;
}

/* ---------------------------------------------------------------- containers */
const detailPath = id => `frame/containers/${id.split('/').map(encodeURIComponent).join('/')}`;

function ContainerDetail({id}) {
  const {data, error} = useFrame(detailPath(id), 0);
  if (!data) return html`<${Panel} title=${id} span="s12"><${Waiting} store=${store} what="the manifest" error=${error} /><//>`;
  const c = data.container;
  return html`<${Panel} title=${c.id} note=${`${c.kind} · ${c.lifecycle.state}`} span="s12" className="detail">
    <dl class="kv wide"><dt>Owner role</dt><dd>${c.owner_role}</dd><dt>Retention</dt><dd>${c.retention.policy}${c.retention.note ? ` · ${c.retention.note}` : ''}</dd>
      <dt>Evidence study</dt><dd>${c.provenance.evidence_study || '—'}</dd><dt>Path</dt><dd class="mono wrapany">${c.provenance.path || '—'}</dd>
      <dt>Session</dt><dd class="mono wrapany">${c.inputs.session_id || '—'}</dd>
      <dt>Source commit</dt><dd class="mono">${String(c.pinned.source_commit || '').slice(0, 12) || '—'}</dd></dl>
    <details><summary>Whole manifest (container-manifest/1)</summary><pre>${JSON.stringify(c, null, 1)}</pre></details><//>`;
}

function Containers() {
  const {data, error} = useFrame('frame/containers?limit=500');
  const [pick, setPick] = useState(null);
  if (!data) return html`<${Panel} title="Containers" span="s12"><${Waiting} store=${store} what="the container inventory" error=${error} /><//>`;
  const kinds = Object.entries(data.kinds || {}).map(([k, n]) => `${n} ${k}`).join(' · ');
  const shown = data.next === null ? `${data.total} listed` : `first ${data.items.length} of ${data.total} listed`;
  return html`<${Panel} title="Containers" note=${`${shown}${kinds ? ` · ${kinds}` : ''}`} span="s12">
      <${Table} columns=${[{title: 'Container', render: c => c.id}, {title: 'Kind', key: 'kind'}, {title: 'Owner role', key: 'owner_role'}, {title: 'State', key: 'lifecycle_state'},
        {title: 'Retention', key: 'retention_policy'}, {title: 'Evidence study', render: c => c.evidence_study || '—'}]}
        rows=${data.items} onPick=${(i, row) => setPick(row.id)} selected=${data.items.findIndex(c => c.id === pick)} empty="No containers are indexed." />
      <p class="note">Sealed sessions are described by sidecar manifests beside their evidence; the evidence is never rewritten. Age is not shown: a sealed manifest records no creation time.</p><//>
    ${pick ? html`<${ContainerDetail} id=${pick} key=${pick} />` : null}`;
}
