// Recorded sources: what one request selected and received and the player's public reports (Memory's Usage & Claims),
// handoffs, and the archive behind All runs: forgetting episodes, the container inventory, an archived run's pre-journal
// memory and the operator's configured curator sources for the whole lineage.
// Read-only: every value comes from the viewer's routes; anchors open Watch or the original frame.
import {html, useState, useEffect, Panel, Pv, Waiting, Table, Insufficient, Callout, SubNav, bytes, fmtMoney, pct, shortId, trim, label} from './ui.js';
import {store, framePath, runPath, selectRun, sessionOf, setCursorSeq, useStore, useView, API} from './data.js';
import {sourceReadText, toolLabel} from './continuity.js';

const CURATOR_SOURCES = [['curator-drafts', 'Curator drafts'], ['results', 'Gate results'], ['sessions', 'Curator sessions']];
const ARCHIVE_SOURCES = [['episodes', 'Forgetting episodes'], ['containers', 'Containers'], ['player', 'Archived player memory']];

/* A slower poll for files the operator configures; the same outage marking and timeouts as every viewer read. */
export const useFrame = (path, every = 15000, refresh = 0) => useView(path, every, API, refresh);

/** The archive and the lineage's operator sources (`#runs/archive/<section>`); unconfigured sources stay hidden. */
export function Archive({section}) {
  const drafts = useFrame('curator-sources/draft-sources?limit=1', 0);
  const results = useFrame('curator-sources/result-sources?limit=1', 0);
  const sessions = useFrame('curator-sources/session-sources?limit=1', 0);
  const configured = {'curator-drafts': drafts.data, results: results.data, sessions: sessions.data};
  const operator = CURATOR_SOURCES.filter(([id]) => configured[id]?.total > 0);
  const tabs = [...ARCHIVE_SOURCES, ...operator];
  const current = tabs.some(([id]) => id === section) ? section : 'episodes';
  const body = {episodes: Episodes, containers: Containers, player: PlayerRecords, 'curator-drafts': CuratorDrafts, results: Curator, sessions: CuratorSession}[current];
  return html`<div class="s12"><${SubNav} id="archive-nav" tabs=${tabs} base="runs/archive" current=${current} label="Archive and operator sources" /></div>
    ${operator.length ? html`<p class="note s12 curator-records">Operator curator sources cover the whole lineage, not one run.</p>` : null}<${body} />`;
}

/* ---------------------------------------------------------------- the player's own records */
const verdictText = labels => (labels.length ? labels.map(l => `${l.verdict}: ${label(l.code)}`).join('; ') : 'unchecked');
function PlayerRecords() {
  const {runId: run} = useStore();
  if (!run) return html`<${Panel} title="Archived player memory" span="s12"><${Insufficient}>Select a run to inspect its records.<//><//>`;
  return html`<${Memory} run=${run} key=${`memory-${run}`} />`;
}

function Hints({data}) {
  const hints = data.hints || [];
  return html`<${Panel} title="Public player hints" span="s12">
    <p class="note">Player-authored memory records are unavailable. These hints are unverified player reports, separate from curated knowledge.</p>
    ${hints.length ? hints.map(h => html`<article><h3>${shortId(h.id)} · actor ${shortId(h.actor_id)}</h3>
      <div><${Pv} source="player_claim" detail="unverified hint" /></div><p class="prewrap">${h.text}</p>
      <dl class="kv"><dt>Intent</dt><dd>${h.intent}</dd><dt>Cites</dt><dd>${(h.cites || []).join(', ') || 'none stated'}</dd>
        <dt>Source IDs</dt><dd>${(h.source_ids || []).join(', ') || 'none stated'}</dd></dl></article>`)
      : html`<${Insufficient}>No public hints recorded.<//>`}
    ${data.hints_omitted ? html`<p class="note">${data.hints_omitted} additional hints are omitted from this bounded view.</p>` : null}<//>`;
}

function Memory({run}) {
  const {data, error} = useView(`archive/${runPath(run, 'memory')}`, 0);
  const [sel, setSel] = useState(0);
  const [frame, setFrame] = useState(null);
  if (!data) return html`<${Panel} title="Player records" span="s12"><${Waiting} store=${store} what="player records" error=${error} /><//>`;
  if (!data.available && data.store_schema === 'player-journal/1') return html`<${Panel} title="Public player hints" span="s12"><${Insufficient}>Public player reports are unavailable for this run.<//><//>`;
  if (!data.available) return html`<${Panel} title="Player records" span="s12"><${Insufficient}>This run's player memory store is not available to the viewer.<//><//>`;
  if (data.store_schema === 'player-journal/1') return html`<${Hints} data=${data} />`;
  const records = data.records || [];
  const r = records[Math.min(sel, records.length - 1)];
  const reads = records.reduce((a, x) => a + (x.reads || []).length, 0);
  return html`<${Panel} title="Records" note=${`${records.length} written · read back ${reads} times`} span="s5">
      <${Table} columns=${[{title: 'Record', render: x => html`${shortId(x.id)}${x.supersedes ? ` ← ${shortId(x.supersedes)}` : ''}`}, {title: 'Kind', key: 'kind'}, {title: 'Read back', render: x => ((x.reads || []).length ? `${x.reads.length}×` : 'never')},
        {title: 'Carried', render: x => ((x.carried_by || []).length ? 'yes' : 'no')}, {title: 'Audit', render: x => html`${(x.labels || []).length ? x.labels[0].verdict : 'unchecked'} ${(x.labels || []).length ? html`<${Pv} source="human" />` : null}`}]}
        rows=${records} onPick=${i => { setSel(i); setFrame(null); }} selected=${sel} empty="No memory records." /><//>
    ${r ? html`<${Panel} title=${`${r.kind} ${shortId(r.id)}`} note=${`actor ${shortId(r.actor_id)}`} span="s7"><div><${Pv} source=${data.provenance || 'player_claim'} detail="fallible" /></div>
      <p class="prewrap">${r.text}</p>
      ${r.data && Object.keys(r.data).length ? html`<details><summary class="note">Structured data</summary><pre>${JSON.stringify(r.data, null, 1)}</pre></details>` : null}
      <dl class="kv"><dt>Supports</dt><dd>${(r.supports || []).map(shortId).join(', ') || 'none'}</dd><dt>Replaces</dt><dd>${r.supersedes ? shortId(r.supersedes) : 'nothing'}</dd><dt>Older versions</dt><dd>${(r.chain || []).length}</dd>
        <dt>Carried in a handoff</dt><dd>${(r.carried_by || []).length ? 'yes' : 'no'}</dd><dt>Audit</dt><dd>${verdictText(r.labels || [])}</dd></dl>
      ${(r.labels || []).filter(l => l.note).map(l => html`<${Callout}>${l.note} <${Pv} source="human" detail=${l.author} /><//>`)}
      <h3>Cited frames</h3>
      ${(r.sources || []).length ? html`<div class="chips">${r.sources.map(id => html`<button type="button" class="btn" aria-pressed=${frame === id} onClick=${() => setFrame(id)}>${id.split('-').pop()}</button>`)}</div>` : html`<p class="note">No cited frames.</p>`}
      ${frame ? html`<div class="frame small"><img src=${framePath(run, frame)} alt=${`Cited frame ${frame}`} /><span class="src">${frame.split('-').pop()} · viewer frame</span></div>` : null}
      <p class="note">Each cited frame opens beside the claim, so it can be checked against what the screen showed.</p><//>` : null}`;
}

/** Every handoff of the run: what carried over, the agenda the next actor started from, and how fast it resumed. */
export function Handoffs({run}) {
  const {data, error} = useView(runPath(run, 'handoffs'));
  const [sel, setSel] = useState(0);
  if (!data) return html`<${Panel} title="Handoffs" span="s12"><${Waiting} store=${store} what="handoffs" error=${error} /><//>`;
  const list = data.handoffs || [];
  if (!list.length) return html`<${Panel} title="Handoffs" span="s12"><${Insufficient}>No handoffs in this run.<//><//>`;
  const h = list[Math.min(sel, list.length - 1)];
  const threads = h.carried_agenda ? h.carried_agenda.threads : [];
  return html`<${Panel} title=${`${list.length} handoff${list.length === 1 ? '' : 's'} in this run`} note="how much carried over and how fast the next actor resumed" span="s7">
      <${Table} columns=${[{title: 'At step', num: true, render: x => `#${x.seq}`}, {title: 'Actor', render: x => shortId(x.actor)}, {title: 'Decisions to resume', num: true, render: x => x.decisions_to_resume ?? '—'},
        {title: 'Carry ratio', num: true, render: x => (x.carry_ratio === null || x.carry_ratio === undefined ? '—' : pct(x.carry_ratio, 1))}, {title: 'Carry', num: true, render: x => bytes(x.carry_bytes)},
        {title: 'Agenda', num: true, render: x => (x.carried_agenda ? `${x.carried_agenda.thread_count} threads` : 'none')},
        {title: 'Identity check', render: x => (x.identity_check.checked ? 'error confirmed' : 'none recorded')}]}
        rows=${list} onPick=${i => setSel(i)} selected=${sel} /><//>
    <${Panel} title=${`Handoff at step ${h.seq}`} span="s5" className="handoff-detail">
      <h3>Carry to the next actor <${Pv} source="recorded" detail="context file" /></h3><pre>${h.carry_text || '(none recorded)'}</pre>
      <p class="note">${(h.carried_ids || []).length} records carried · context ${shortId(h.context_id)}</p>
      <h3>Carried agenda <${Pv} source="player_claim" detail="player_agenda" /></h3>
      ${threads.length ? html`<ul class="threads compact" data-carried-agenda>${threads.map(t => html`<li data-status=${t.status}><span class="tstat">${t.status}</span><b>${t.title}</b></li>`)}</ul>`
        : html`<p class="note">No agenda was carried.</p>`}
      ${h.identity_check.errors.length ? h.identity_check.errors.map(e => html`<${Callout}>Identity check <${Pv} source="human" detail=${e.author} />: ${e.verdict} ${label(e.code)}. ${e.note}<//>`) : html`<p class="note">No identity or world error was labelled for this handoff.</p>`}<//>`;
}

/* ---------------------------------------------------------------- configured curator sources */
const RESULT_STATUS = {available:'Recorded data available.', empty:'The source is readable and empty.', missing:'The configured file is missing.', unreadable:'The configured source cannot be read as a regular file.', too_large:'The source exceeds the 16 MiB input limit.', unsupported:'The source contains unsupported records.', malformed:'The source contains malformed records.'};

function ResultRows({data, after, pick, setPick, setAfter, detailAttribute}) {
  const selected = data.items.find(row => row.index === pick);
  useEffect(() => { if (selected) document.querySelector(`[${detailAttribute}]`)?.focus(); }, [pick, Boolean(selected)]);
  const value = (v, key) => v === null || v === undefined ? (selected?.omitted_characters?.[key] ? 'omitted' : 'null') : v;
  return html`<${Table} columns=${[{title:'Recorded order', render:r => r.index}, {title:'Operation', key:'operation'}, {title:'Status', key:'status'}, {title:'Operation ID', render:r => value(r.operation_id), wrap:true}]} rows=${data.items} selected=${data.items.findIndex(r => r.index === pick)} onPick=${(i, row) => setPick(row.index)} />
    <p><button type="button" disabled=${after === 0} onClick=${() => {setPick(null); setAfter(Math.max(0, after - 25));}}>Previous results</button> <button type="button" disabled=${data.next === null} onClick=${() => {setPick(null); setAfter(data.next);}}>Next results</button></p>
    ${selected ? html`<section data-curator-detail=${detailAttribute === 'data-curator-detail' ? '' : null} data-session-detail=${detailAttribute === 'data-session-detail' ? '' : null} tabIndex=${-1}><h3>Recorded result</h3><dl class="kv wide">${['operation_id','operation','status','base_version','restored_from','version','submission','session'].map(key => html`<dt>${key}</dt><dd class="mono wrapany">${value(selected[key], key)}</dd>`)}
      ${selected.from_drafts?.length ? html`<dt>From drafts</dt><dd class="mono wrapany">${selected.from_drafts.join(', ')}${selected.from_drafts_omitted ? ` · ${selected.from_drafts_omitted} more omitted` : ''}</dd>` : null}</dl><h4>Diagnostics</h4>${selected.diagnostics.length ? selected.diagnostics.map(d => html`<p class="wrapany">${d}</p>`) : html`<p>${selected.path_details_omitted ? 'No diagnostic text displayed; path-like details are withheld.' : 'None recorded.'}</p>`}<${Omissions} value=${selected} /></section>` : null}`;
}

function Metadata({title, data, labels}) {
  const display = (value, key) => {
    if (data?.omitted_characters?.[key]) return 'omitted (path-like or too long)';
    if (value === undefined || value === null) return 'unavailable';
    if (Array.isArray(value)) return value.length ? value.map(item => display(item, '')).join(', ') : 'none recorded';
    if (typeof value === 'object') {
      if ('items' in value) return `${value.items.length ? value.items.map(item => display(item, '')).join(', ') : 'none recorded'}${value.omitted ? `; ${value.omitted} more omitted` : ''}${value.values_omitted ? `; ${value.values_omitted} values omitted` : ''}`;
      const entries = Object.entries(value).filter(([name]) => name !== 'omitted_characters');
      return entries.length ? entries.map(([name, item]) => `${name}: ${value.omitted_characters?.[name] ? 'omitted' : display(item, name)}`).join(' · ') : 'full window';
    }
    return String(value);
  };
  return html`<h4>${title}</h4><dl class="kv wide">${labels.map(([key, label]) => html`<dt>${label}</dt><dd class="mono wrapany">${display(data?.[key], key)}</dd>`)}</dl><${Omissions} value=${data} />`;
}

/* ---------------------------------------------------------------- the curator runner's status
   What the curator has done since the version the player started with: the selected run's status file
   (curator-runner-status/2, or an archived /1), read by the viewer at each request. Delivered versions are Memory's; the two
   are not merged. */
export const RUNNER_STATUS = {available:'read.', not_configured:'no curator runner status file is known for this run.',
  missing:'missing: the runner has not written it, or no runner was started.', unreadable:'unreadable: it cannot be read as a regular file.',
  too_large:'unreadable: it exceeds the 16 MiB input limit.', empty:'unreadable: the file is empty.',
  malformed:'unreadable: it is not complete JSON (partly written); the next read tries again.',
  unsupported:'unreadable: it is not curator-runner-status/2 or an archived /1.'};
export const RUNNER_STATES = {polling:'polling', 'in-session':'in a session', stopped:'stopped for the rest of the admission', ended:'ended'};

/* An absent or `unknown` value is unknown, never zero; a recorded null is none; a withheld string says so. */
export function known(obj, key, none = 'none') {
  if (obj === null) return none;
  if (!obj || obj === 'unknown') return 'unknown';
  if (obj.omitted_characters?.[key]) return 'withheld (path-like or too long)';
  const value = obj[key];
  return value === undefined || value === 'unknown' ? 'unknown' : value === null ? none : String(value);
}
/* A wall time in seconds; a number the browser cannot place as a date (non-finite, out of range) is unknown. */
function wallText(value) {
  if (value === null) return 'none';
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'unknown';
  const date = new Date(value * 1000);
  return Number.isNaN(date.getTime()) ? 'unknown' : date.toISOString().replace('.000Z', 'Z');
}
function placeText(place, none = 'none') {
  if (place === null) return none;
  if (!place || place === 'unknown') return 'unknown';
  if (place.step === 0) return 'no finished step yet';
  return `actor ${known(place, 'actor')} · step ${known(place, 'step')} · operation ${known(place, 'operation')} · finished operation ${known(place, 'ordinal')} of the admission`;
}
const stampText = stamp => stamp === null ? 'no stamp' : !stamp || stamp === 'unknown' ? 'unknown'
  : `session ${known(stamp, 'session')} · actor ${known(stamp, 'actor')} · last step ${known(stamp, 'last_step')}`;
/* A version, its coverage stamp and the runner's own `baseline` flag for it, each as recorded. */
const versionText = v => `${known(v, 'version')} · stamp: ${stampText(v.coverage)} · baseline: ${v.baseline === true ? 'yes' : v.baseline === false ? 'no' : 'unknown'}`;
const windowText = w => !w || w === 'unknown' ? 'unknown' : `actor ${known(w, 'actor')} · steps ${known(w, 'first')}–${known(w, 'last')}`;

/* The recorded end of the covered prefix and, after a restore, that the prefix is unknown past it. */
function prefixText(prefix) {
  if (!prefix || prefix === 'unknown') return 'unknown';
  const end = placeText(prefix.end, 'no step covered yet');
  if (prefix.restore === 'unknown') return `${end} · whether a restore applies is unknown`;
  if (!prefix.restore) return end;
  return `${end} · unknown past the restore of ${known(prefix.restore, 'version')} to ${known(prefix.restore, 'restored_from')} (versions counted through ${known(prefix.restore, 'counted_through')})`;
}

/** Every figure of the status file. `data` is the one response the Memory tab's curator strip also shows. */
export function RunnerDetail({data, error}) {
  const s = data?.status;
  const confirmed = s && s.last_confirmed;
  const latest = s && s.latest_version;
  const failures = s && s.failures;
  const examined = s && s.examined;
  const rows = examined && Array.isArray(examined.items) ? examined.items : [];
  const unexamined = s && s.unexamined;
  return html`<div class="runner-detail">
    <p class="note">What the curator has done during this run. Read from the curator runner's status file at each request, without a lock; nothing is sent to the curator. Lag, backlog and unexamined steps count only what the runner's last successful read saw (as of); steps finished after it are unknown.</p>
    ${!data ? html`<${Waiting} store=${store} what="the curator runner status" error=${error} />` : html`<p data-runner-status>Status file: ${RUNNER_STATUS[data.source_status] || 'state unknown.'}</p>
      ${s ? html`<dl class="kv wide" data-runner-facts>
        <dt>Runner</dt><dd>${RUNNER_STATES[s.state] || 'unknown'}</dd>
        <dt>Play has reached</dt><dd class="wrapany">${placeText(s.position)}</dd>
        <dt>As of</dt><dd class="wrapany">${s.as_of && s.as_of !== 'unknown' ? `the read that ended ${wallText(s.as_of.read_wall?.ended)}` : 'unknown'}</dd>
        <dt>After the last read</dt><dd>${known(s, 'after_last_read')}</dd>
        <dt>Covered prefix ends at</dt><dd class="wrapany">${prefixText(s.covered_prefix)}</dd>
        <dt>Lag (finished operations after the covered prefix)</dt><dd>${known(s, 'lag')}</dd>
        <dt>Distance from the latest stamp</dt><dd>${known(s, 'stamp_distance')}</dd>
        <dt>Backlog (finished steps beyond the curator's cursor)</dt><dd>${known(s, 'backlog')}</dd>
        <dt>Last confirmed version</dt><dd class="wrapany">${confirmed === null ? 'none confirmed yet' : !confirmed || confirmed === 'unknown' ? 'unknown' : versionText(confirmed)}</dd>
        <dt>Latest version seen</dt><dd class="wrapany">${!latest || latest === 'unknown' ? 'unknown' : versionText(latest)}</dd>
        <dt>Unconfirmed publications</dt><dd>${known(s, 'unconfirmed')}</dd>
        <dt>Session in flight</dt><dd class="wrapany">${s.current === null ? 'none' : !s.current || s.current === 'unknown' ? 'unknown' : `${windowText(s.current.window)} · started ${wallText(s.current.started_wall)}`}</dd>
        <dt>Consecutive failures</dt><dd>${!failures || failures === 'unknown' ? 'unknown' : `${known(failures, 'sessions')} sessions · ${known(failures, 'snapshots')} snapshots`}</dd>
        <dt>Stop reason</dt><dd class="wrapany">${known(s, 'stop_reason')}</dd>
        <dt>Status written</dt><dd>${wallText(s.updated_wall)} · read by the viewer ${wallText(data.read_wall)}</dd></dl>
      <h3>Examined ranges</h3>${!examined || examined.items === 'unknown' ? html`<p>Examined ranges unknown.</p>` : examined.items === null ? html`<p>No examined ranges recorded.</p>` : html`<${Table} columns=${[{title:'Range', render:r => windowText(r.window)}, {title:'Outcome', render:r => known(r, 'outcome')}, {title:'Cursor advanced', render:r => r.advanced === true ? 'yes' : r.advanced === false ? 'no' : 'unknown'}, {title:'Started', render:r => wallText(r.started_wall)}, {title:'Ended', render:r => wallText(r.ended_wall)}]} rows=${rows} empty="No range examined yet." />${examined.omitted ? html`<p class="note">The ${examined.omitted} earliest of ${examined.total} ranges are not shown.</p>` : null}`}
      ${unexamined && unexamined.items === 'unknown' ? html`<h3>Left unexamined</h3><p>Unknown.</p>` : unexamined && Array.isArray(unexamined.items) ? html`<h3>Left unexamined</h3>${unexamined.items.length ? unexamined.items.map(r => html`<p class="wrapany">actor ${known(r, 'actor')} · steps ${known(r, 'first')}–${known(r, 'last')}</p>`) : html`<p>None as of the last read.</p>`}` : null}
      <${Omissions} value=${s} />` : null}`}</div>`;
}

function CuratorSession() {
  const [sourceAfter, setSourceAfter] = useState(0);
  const sources = useFrame(`curator-sources/session-sources?limit=500&after=${sourceAfter}`, 5000);
  const [source, setSource] = useState('');
  const [after, setAfter] = useState(0);
  const [snapshot, setSnapshot] = useState(null);
  const [pick, setPick] = useState(null);
  const [refresh, setRefresh] = useState(0);
  const path = source ? `curator-sources/session?source=${encodeURIComponent(source)}&after=${after}&limit=25${snapshot ? `&snapshot=${snapshot}` : ''}` : null;
  const result = useFrame(path, 5000, refresh);
  const data = result.error ? null : result.data;
  useEffect(() => { if (data?.snapshot && !snapshot) setSnapshot(data.snapshot.sha256); }, [data, snapshot]);
  const reset = () => { setAfter(0); setSnapshot(null); setPick(null); setRefresh(n => n + 1); };
  return html`<${Panel} title="Recorded curator session" span="s12" className="curator-source-view">
    <p class="note">Operator-supplied aliases identify configured receipts, not a verified fork or association with a run or result journal. These are historical records, not live custody. Wall time is not game time; the USD cap is a limit, not measured spend.</p>
    ${!sources.data ? html`<${Waiting} store=${store} what="session sources" error=${sources.error} />` : !sources.data.items.length ? html`<p>No curator session sources configured.</p>` : html`<label>Session receipt <select data-session-source value=${source} onChange=${e => {setSource(e.target.value); reset();}}><option value="">Choose a source</option>${sources.data.items.map(item => html`<option value=${item.label}>${item.label}</option>`)}</select></label>${sourceAfter || sources.data.next !== null ? html`<p><button type="button" disabled=${sourceAfter === 0} onClick=${() => {setSourceAfter(Math.max(0, sourceAfter - 500)); setSource(''); reset();}}>Previous sources</button> <button type="button" disabled=${sources.data.next === null} onClick=${() => {setSourceAfter(sources.data.next); setSource(''); reset();}}>Next sources</button></p>` : null}`}
    ${source && result.error ? html`<p role="alert">${result.error.message === 'source_changed' ? 'Source changed; refresh for a fresh snapshot.' : result.error.message}</p><button type="button" onClick=${() => {reset(); document.querySelector('[data-session-source]')?.focus();}}>Refresh session</button>` : null}
    ${source && !data && !result.error ? html`<${Waiting} store=${store} what="session receipt" />` : null}
    ${data ? html`<p data-session-status>Source ${data.source}: ${RESULT_STATUS[data.source_status] || 'Source state unavailable.'}</p>${data.snapshot ? html`<p class="mono wrapany">Snapshot SHA-256: ${data.snapshot.sha256} · ${data.snapshot.bytes} bytes</p>` : null}
      ${data.header ? html`<h3>Recorded session metadata</h3>
      <${Metadata} title="Identity" data=${data.header} labels=${[['id','Session ID'], ['published_after','Published after']]} />
      <${Metadata} title="Recorded inputs" data=${data.header.inputs} labels=${[['session_kind','Session kind'],['trace_sessions','Trace sessions'],['window','Window'],['coverage','Coverage'],['window_frames','Frame count'],['drafts','Input draft IDs']]} />
      <${Metadata} title="Pinned versions and digests" data=${data.header.pinned} labels=${[['knowledge_version','Knowledge version'],['trace_manifest_sha256','Trace digest'],['brief_sha256','Brief digest'],['grooming_sha256','Grooming digest']]} />
      <${Metadata} title="Configured limits" data=${data.header.budgets} labels=${[['wall_seconds','Wall seconds'],['memory_bytes','Memory bytes'],['disk_bytes','Disk bytes'],['cap_usd','USD cap']]} />
      <${Metadata} title="Terminal lifecycle" data=${data.header.lifecycle} labels=${[['state','State'],['started_wall','Started wall timestamp'],['ended_wall','Ended wall timestamp'],['stopped','Stop reason'],['returncode','Return code'],['survivor_count','Survivor count'],['errors','Errors'],['refused','Refusals']]} />
      <${Metadata} title="Recorded resources" data=${data.header.resources} labels=${[['seconds','Resource seconds'],['peak_memory_bytes','Peak memory bytes'],['peak_disk_bytes','Peak disk bytes']]} />
      <h3>Historical draft collection events</h3>${data.drafts === null ? html`<p>No collection report recorded.</p>` : html`<${Metadata} title="Collection report" data=${data.drafts} labels=${[['created','Created'],['renewed','Renewed'],['aged','Aged'],['stale','Stale'],['abandoned','Abandoned'],['refused','Refused']]} />`}<p class="note">Collection events are not current draft states or a complete promotion history.</p>
      <h3>Recorded gate results</h3>${data.total === 0 ? html`<p>No results recorded; this does not establish publications or acceptance.</p>` : html`<${ResultRows} data=${data} after=${after} pick=${pick} setPick=${setPick} setAfter=${setAfter} detailAttribute="data-session-detail" />`}` : null}` : null}<//>`;
}

const DRAFT_STATUS = {available: 'Draft manifests available.', empty: 'The source is readable and contains no draft manifests.',
  missing: 'The configured directory is missing.', unreadable: 'The directory or a draft manifest cannot be read safely.',
  too_large: 'A manifest exceeds the 16 MiB input limit.', malformed: 'The source contains malformed manifests.', unsupported: 'The source contains unsupported draft manifests.'};
const DRAFT_COLUMNS = [{title: 'Draft ID', key: 'id', wrap: true}, {title: 'Bucket', render: row => row.bucket === 'active' ? 'Active' : 'Archived'},
  {title: 'State', key: 'state'}, {title: 'Untouched sessions', key: 'untouched_sessions', num: true}];

function CuratorDrafts() {
  const [sourceAfter, setSourceAfter] = useState(0);
  const sources = useFrame(`curator-sources/draft-sources?limit=500&after=${sourceAfter}`, 0);
  const [source, setSource] = useState('');
  const [after, setAfter] = useState(0);
  const [snapshot, setSnapshot] = useState(null);
  const [pick, setPick] = useState(null);
  const [refresh, setRefresh] = useState(0);
  const path = source ? `curator-sources/drafts?source=${encodeURIComponent(source)}&after=${after}&limit=25${snapshot ? `&snapshot=${snapshot}` : ''}` : null;
  const result = useFrame(path, 5000, refresh);
  const data = result.error ? null : result.data;
  const selected = data?.items[pick];
  useEffect(() => { if (data?.snapshot && !snapshot) setSnapshot(data.snapshot.sha256); }, [data, snapshot]);
  useEffect(() => { if (selected) document.querySelector('[data-curator-draft-detail]')?.focus(); }, [pick, Boolean(selected)]);
  const reset = () => { setAfter(0); setSnapshot(null); setPick(null); setRefresh(n => n + 1); };
  const sourcePage = index => { setSourceAfter(index); setSource(''); reset(); };
  const manifestPage = index => {
    setSnapshot(data.snapshot.sha256);
    setAfter(index);
    setPick(null);
    document.querySelector('[data-curator-draft-source]')?.focus();
  };
  return html`<${Panel} title="Curator drafts" span="s12" className="curator-source-view">
    ${!sources.data ? html`<${Waiting} store=${store} what="draft sources" error=${sources.error} />` : html`
      <label>Draft source <select data-curator-draft-source value=${source} onChange=${e => {setSource(e.target.value); reset();}}><option value="">Choose a source</option>${sources.data.items.map(item => html`<option value=${item.label}>${item.label}</option>`)}</select></label>
      ${sourceAfter || sources.data.next !== null ? html`<p><button type="button" disabled=${sourceAfter === 0} onClick=${() => sourcePage(Math.max(0, sourceAfter - 500))}>Previous sources</button> <button type="button" disabled=${sources.data.next === null} onClick=${() => sourcePage(sources.data.next)}>Next sources</button></p>` : null}`}
    ${source && result.error ? html`<p role="alert" data-curator-draft-error>${result.error.message === 'source_changed' ? 'Source changed; refresh to restart paging.' : result.error.message}</p>` : null}
    ${source ? html`<button type="button" onClick=${() => {reset(); document.querySelector('[data-curator-draft-source]')?.focus();}}>Refresh drafts</button>` : null}
    ${source && !data && !result.error ? html`<${Waiting} store=${store} what="curator drafts" />` : null}
    ${data ? html`<p data-curator-draft-status role="status">Source ${data.source}: ${DRAFT_STATUS[data.source_status] || 'Source state unavailable.'}</p>
      ${data.snapshot ? html`<p class="mono wrapany">Snapshot SHA-256: ${data.snapshot.sha256} · ${data.snapshot.bytes} manifest bytes</p>` : null}
      ${data.source_status === 'available' ? html`<${Table} columns=${DRAFT_COLUMNS} rows=${data.items} selected=${pick} onPick=${setPick} />
        <p><button type="button" disabled=${after === 0} onClick=${() => manifestPage(Math.max(0, after - 25))}>Previous drafts</button> <button type="button" disabled=${data.next === null} onClick=${() => manifestPage(data.next)}>Next drafts</button></p>
        ${selected ? html`<section data-curator-draft-detail tabIndex=${-1}><h3 class="wrapany">${selected.id}</h3><${Metadata} title="Draft manifest" data=${selected}
          labels=${[['created_by_session','Created by session'], ['last_touched_session','Last touched by session'], ['promoted_by_session','Promoted by session'], ['sessions','Recorded sessions'], ['max_bytes','Byte limit'], ['retention_policy','Retention policy']]} /></section>` : null}` : null}` : null}<//>`;
}

/* Recorded results belong to an operator-selected source, independent of any run. */
function Curator() {
  const [sourceAfter, setSourceAfter] = useState(0);
  const sources = useFrame(`curator-sources/result-sources?limit=500&after=${sourceAfter}`, 5000);
  const [source, setSource] = useState('');
  const [after, setAfter] = useState(0);
  const [snapshot, setSnapshot] = useState(null);
  const [pick, setPick] = useState(null);
  const [refresh, setRefresh] = useState(0);
  const path = source ? `curator-sources/results?source=${encodeURIComponent(source)}&after=${after}&limit=25${snapshot ? `&snapshot=${snapshot}` : ''}` : null;
  const result = useFrame(path, 5000, refresh);
  const data = result.error ? null : result.data;
  useEffect(() => { if (data && data.snapshot && !snapshot) setSnapshot(data.snapshot.sha256); }, [data, snapshot]);
  const reset = () => { setAfter(0); setSnapshot(null); setPick(null); setRefresh(n => n + 1); };
  const sourcePage = index => { setSourceAfter(index); setSource(''); reset(); };
  const messages = {available:'Recorded results available.', empty:'The source is readable and contains no results.', missing:'The configured result file is missing.', unreadable:'The configured source cannot be read as a regular file.', too_large:'The result source exceeds the 16 MiB input limit.', unsupported:'The source contains unsupported or mixed result records.', malformed:'The source contains malformed or incomplete records.'};
  return html`<${Panel} title="Curator results" span="s12" className="curator-source-view">
    <p class="note">Recorded publication reports in journal order. A source label does not establish a run association or the repository's current head.</p>
    ${!sources.data ? html`<${Waiting} store=${store} what="curator sources" error=${sources.error} />` : !sources.data.items.length ? html`<p>No curator result sources configured.</p>` : html`<label>Result source <select data-curator-source value=${source} onChange=${e => {setSource(e.target.value); reset();}}><option value="">Choose a source</option>${sources.data.items.map(item => html`<option value=${item.label}>${item.label}</option>`)}</select></label>${sourceAfter || sources.data.next !== null ? html`<p><button type="button" disabled=${sourceAfter === 0} onClick=${() => sourcePage(Math.max(0, sourceAfter - 500))}>Previous sources</button> <button type="button" disabled=${sources.data.next === null} onClick=${() => sourcePage(sources.data.next)}>Next sources</button></p>` : null}`}
    ${source && result.error ? html`<p role="alert" data-curator-error>${result.error.message === 'source_changed' ? 'Source changed; refresh to restart paging.' : result.error.message}</p><button type="button" onClick=${() => {reset(); document.querySelector('[data-curator-source]')?.focus();}}>Refresh results</button>` : null}
    ${source && !data && !result.error ? html`<${Waiting} store=${store} what="curator results" />` : null}
    ${data ? html`<p data-curator-status>Source ${data.source}: ${messages[data.source_status] || 'Source state unavailable.'}</p>${data.snapshot ? html`<p class="mono wrapany">Snapshot SHA-256: ${data.snapshot.sha256} · ${data.snapshot.bytes} bytes</p>` : null}
      ${data.source_status === 'available' ? html`<${ResultRows} data=${data} after=${after} pick=${pick} setPick=${setPick} setAfter=${setAfter} detailAttribute="data-curator-detail" />` : null}` : null}
    <p class="note">These are publication reports only: no submission text, draft contents or current draft states are read.</p><//>`;
}

/* ---------------------------------------------------------------- actor: the forgetting episodes */
const REASONS = {no_frame: 'no frame: stated in the actor\'s own text', run_not_in_catalog: 'its run is not in this viewer\'s catalog',
  unknown_frame: 'the run has no such frame', frame_unavailable: 'the frame file is missing', frame_digest_mismatch: 'the frame file fails its SHA-256 check',
  run_directory_unavailable: 'the run directory is not available', record_unavailable: 'the run\'s evaluation store cannot be read',
  ambiguous_run: 'two catalog runs share this run name; open it from the run list'};
const ANCHORS = [['observed', 'Observed'], ['needed', 'Needed'], ['acted_without', 'Acted without']];

/* One anchor opens at a time; navigating away or opening another cancels the pending one. */
let pending = null;

/** Select the run, wait for its steps to load, put the shared playhead on the step and open Watch there. */
export function openAnchor(anchor, setBusy, setFailed) {
  if (pending) pending.cancel();
  const from = location.hash;
  setBusy(anchor.source_id);
  setFailed(null);
  const session = (anchor.session && sessionOf(anchor.session)) || sessionOf(anchor.run);
  if (session === null) { setBusy(null); setFailed(anchor.source_id); return; }
  selectRun(session);
  const end = Date.now() + 90000;
  const timer = setInterval(() => {
    if (location.hash !== from) return finish();
    const step = store.runId === session ? store.steps.find(s => s.source_id === anchor.source_id) : null;
    if (step) {
      finish();
      setCursorSeq(step.seq);
      location.hash = '#watch';
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
        <button type="button" class="btn" disabled=${busy !== null} onClick=${() => openAnchor(anchor, setBusy, setFailed)}>${busy === anchor.source_id ? 'Opening…' : 'Open in Watch'}</button>
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

function Omissions({value}) {
  const found = [];
  function visit(node, path = '') {
    if (!node || typeof node !== 'object') return;
    for (const [key, item] of Object.entries(node)) {
      const name = path ? `${path}.${key}` : key;
      if (key.endsWith('_omitted') && item) found.push(`${name}: ${item}`);
      else if ((key === 'omitted_characters' || key === 'order_omitted_characters') && Object.keys(item || {}).length) found.push(`${name}: ${JSON.stringify(item)}`);
      else if (Array.isArray(item)) item.forEach((child, i) => visit(child, `${name}[${i}]`));
      else if (item && typeof item === 'object') visit(item, name);
    }
  }
  visit(value);
  return found.length ? html`<p class="note wrapany">Omitted: ${found.join(' · ')}</p>` : null;
}

function SourceAnchors({anchors, clocks, depiction}) {
  return (anchors || []).map(anchor => html`<p class="note wrapany">${anchor.source_id === depiction ? 'Depiction' : 'Source'} ${anchor.source_id}${clocks?.[anchor.source_id] ? ` · ${clocks[anchor.source_id]}` : ''}: ${anchor.available
    ? html`<a href=${framePath(anchor.run, anchor.source_id)} target="_blank" rel="noopener">Original frame (${anchor.run})</a>`
    : `unavailable (${anchor.reason || 'unknown'})`}</p>`);
}

export function clockText(position) {
  const prior = position?.prior_clock;
  if (position?.clock_label) return ` · ${position.clock_label}`;
  return prior ? ` · ${prior.label} (${prior.step_offset} ${prior.step_offset === 1 ? 'step' : 'steps'} earlier)` : '';
}

export function conditionText(when) {
  if (typeof when === 'string') return when;
  if (!when) return '';
  return [when.note, ...Object.entries(when.requires || {}).map(([k, v]) => `${label(k)}: ${v}`)].filter(Boolean).join(' · ');
}

export function Replacements({history, id}) {
  const rows = Object.entries(history?.replaced || {}).filter(([, row]) => row.by.includes(id));
  return rows.length ? html`<p class="note wrapany">Replaces ${rows.map(([from, row]) => `${from} (${label(row.reason)})`).join(', ')}</p>` : null;
}

function RecordedMarker({value}) {
  if (!value) return 'unavailable';
  return html`<span>session ${value.session ?? 'unavailable'} · actor ${value.actor ?? 'unavailable'} · step ${value.step ?? value.last_step ?? 'unavailable'}${value.order?.length ? ` · order ${value.order.join(', ')}` : ''}${clockText(value)}</span>`;
}

function RecordedOutcome({value}) {
  if (!value) return 'Unavailable';
  const hours = typeof value.hours === 'number' ? `${value.hours.toFixed(2)} h` : 'unavailable';
  const death = value.died === true ? 'yes' : value.died === false ? 'no' : 'unavailable';
  return html`<span>Elapsed game time: ${hours} · death reading: ${death} · ending: ${label(value.outcome || 'unavailable')} · censor reason: ${label(value.censor_reason || 'unavailable')} · infrastructure loss: ${value.lost === true ? 'yes' : value.lost === false ? 'no' : 'unavailable'}</span>`;
}

/** A snapshot entry's delivered state: kind, evidence, scope class, lifecycle, flags, tags and links. An archived
 *  entry names plain link IDs; a current one types each link. */
function EntryState({item, choose}) {
  const link = (l, end) => (typeof l === 'string' ? l : `${l.rel} ${l[end]}`);
  const flags = ['needs_review', 'unverified_branch', 'condition_unverified'].filter(name => item[name]);
  return html`<p class="wrapany" data-entry-state>Kind: ${label(item.statement_kind || item.claim_kind || item.type || item.kind)}${item.evidence_basis ? ` · evidence: ${item.evidence_basis}` : ''} · scope: ${item.scope || 'unrecorded'}${Object.entries(item.scope_axes || {}).map(([k, v]) => ` (${k}: ${v})`).join('')} · state: ${item.lifecycle_state || 'unrecorded'}${flags.length ? ` · ${flags.map(label).join(', ')}` : ''} · tags: ${(item.tags || []).join(', ') || 'none'}</p>
    <${FactDetails} item=${item} choose=${choose} showDepiction=${!item.anchors?.some(anchor => anchor.source_id === item.depiction_source_id)} />
    <p class="wrapany">Links: ${(item.links || []).map(l => link(l, 'target')).join(', ') || 'none'}${(item.backlinks || []).length ? ` · linked from: ${item.backlinks.map(l => link(l, 'source')).join(', ')}` : ''} · cited frames: ${(item.citation_source_ids || []).join(', ') || 'none recorded'}</p>`;
}

function FactDetails({item, choose, showDepiction = false}) {
  const when = conditionText(item.when);
  return html`${item.state_key ? html`<p class="note wrapany">State key: ${item.state_key}</p>` : null}
    ${item.anchor ? html`<p class="note wrapany">Anchor: <button type="button" onClick=${() => choose(item.anchor)}>${item.anchor_display || item.anchor}</button></p>` : null}
    ${when ? html`<p class="note wrapany">When: ${when}</p>` : null}
    ${showDepiction && item.depiction_source_id ? html`<p class="note wrapany">Depiction: ${item.depiction_source_id}</p>` : null}`;
}

function EntryButtons({ids, choose}) {
  return ids.length ? ids.map(id => html`<button type="button" class="wrapany" onClick=${() => choose(id)}>${id}</button>`) : 'none recorded';
}

function QueryHits({hits, choose}) {
  return html`<ul class="query-hits">${hits.map(h => {
    const metadata = [h.kind, h.title || h.subject, label(h.statement_kind || h.claim_kind || ''), h.via, ...(h.status || []).map(label)].filter(Boolean);
    return html`<li class="wrapany">${h.id ? html`<button type="button" class="wrapany" onClick=${() => choose(h.id)}>${h.id}</button>` : 'ID unavailable'}
      ${metadata.length ? ` · ${metadata.join(' · ')}` : ''}${h.snippet ? html`<p>${h.snippet}</p>` : null}
      <${FactDetails} item=${h} choose=${choose} showDepiction=${true} />
      ${h.cited_by_articles?.length ? html`<p>Cited by <${EntryButtons} ids=${h.cited_by_articles} choose=${choose} /></p>` : null}</li>`;
  })}</ul>`;
}

/** A `player_source` call names the real frame and the alias the player saw; the alias is never a link. */
function SourceRead({call}) {
  if (call.tool !== 'player_source') return null;
  return html`<p class="wrapany" data-source-read>Source re-read: ${call.source_id || 'frame unavailable'} · <span class="tag alias">${sourceReadText(call)}</span> <span class="tag quiet">non-clickable</span></p>`;
}

export function RecordedKnowledge() {
  const {runId} = useStore();
  const [actor, setActor] = useState('');
  const [request, setRequest] = useState('');
  const [after, setAfter] = useState(0);
  const [entry, setEntry] = useState('');
  const [focusEntry, setFocusEntry] = useState(false);
  useEffect(() => { setActor(''); setRequest(''); setAfter(0); setEntry(''); }, [runId]);
  const path = runId ? runPath(runId, `knowledge?actor=${encodeURIComponent(actor)}&request=${encodeURIComponent(request)}&entry=${encodeURIComponent(entry)}&after=${after}&limit=25`) : null;
  const {data, error} = useView(path);
  const choose = id => {setEntry(id); setAfter(0); setFocusEntry(!!id);};
  useEffect(() => {
    if (focusEntry && data && data.snapshot && data.snapshot.entry_id === entry) {
      const target = document.querySelector('[data-reader-entry] > summary') || document.querySelector('[data-reader-snapshot]');
      if (target) target.focus();
      setFocusEntry(false);
    }
  }, [focusEntry, data, entry]);
  if (!runId) return html`<${Panel} title="Recorded knowledge" span="s12"><${Insufficient}>Select a run to inspect its records.<//><//>`;
  if (!data) return html`<${Panel} title="Recorded knowledge" span="s12"><${Waiting} store=${store} what="recorded knowledge" error=${error} /><//>`;
  return html`<${Panel} title="Recorded knowledge and public reports" note="Recorded data · reports are unverified" span="s12" className="knowledge-reader">
    <p class="note">Selection, delivery, explicit reads, public reports and game effects are separate records. An absent ID or link is unavailable; it does not establish attention, use or withholding.</p>
    <label>Actor <select data-reader-actor value=${actor} onChange=${e => {setActor(e.target.value); setRequest(''); setEntry(''); setAfter(0);}}><option value="">Choose an actor</option>${data.actors.map(a => html`<option value=${a}>${a}</option>`)}</select></label>
    ${actor ? html`<label> Request <select data-reader-request value=${request} onChange=${e => {setRequest(e.target.value); setAfter(0);}}><option value="">All recorded requests</option>${(data.requests || []).map(r => html`<option value=${r}>${r}</option>`)}</select></label>` : null}
    <${Omissions} value=${{actors_omitted:data.actors_omitted,requests_omitted:data.requests_omitted}} />
    ${actor ? html`<p class="note">Context: ${data.context ? (data.context.exact ? 'recorded manifest' : 'reconstructed or unavailable') : 'select a request'}.</p>
      <h3>Selection and delivery</h3>${data.events.length ? data.events.map(e => html`<details><summary>${e.type} · ${e.kind || 'unknown'} · ${e.status || e.outcome || 'recorded'} · line ${e.line}</summary>
        <p class="wrapany">Recall request: ${e.recall_request_id || e.request_id || 'unavailable'} · receiving request: ${e.receiving_player_request_id || 'unavailable'} · version: ${e.version || 'unavailable'}</p>
        ${e.kind === 'update' ? html`<p class="wrapany">Newer version during play · previous version: ${e.previous_version || 'none'} · coverage: <${RecordedMarker} value=${e.coverage} />${e.reason ? ` · reason: ${e.reason}` : ''}</p>` : null}
        ${e.delivery_text_unavailable ? html`<p>Delivered text unavailable.</p>` : null}
        ${(e.leads || []).map(v => html`<p class="wrapany">${e.outcome === 'undelivered' ? 'Attempted lead' : 'Delivered lead'}: ${v.title || v.id}: ${v.lead}</p>`)}${(e.index || []).map(v => html`<p class="wrapany">${e.outcome === 'undelivered' ? 'Attempted index' : 'Delivered index'}: ${v.title || v.id}: ${v.index}</p>`)}
        ${(e.added || []).map(v => html`<p class="wrapany">Added: ${v.title || v.id}: ${v.lead}</p>`)}${(e.updated || []).map(v => html`<p class="wrapany">Updated: ${v.title || v.id}: ${v.lead}</p>`)}${(e.removed || []).map(v => html`<p class="wrapany">Removed: ${v.title || v.id}</p>`)}
        <p>Articles: <${EntryButtons} ids=${e.article_ids} choose=${choose} /><br />Facts: <${EntryButtons} ids=${e.fact_ids} choose=${choose} /><br />Index: <${EntryButtons} ids=${e.index_ids} choose=${choose} /></p><${Omissions} value=${e} /></details>`) : html`<p>No matching selection or delivery recorded.</p>`}<${Omissions} value=${{events_omitted:data.events_omitted}} />
      <h3 data-reader-snapshot tabIndex="-1">Frozen delivered snapshot</h3>${entry ? html`<p class="wrapany">Entry ${entry} <button type="button" onClick=${() => choose('')}>Show all entries</button></p>` : null}${data.snapshot ? html`<p class="wrapany">Digest verified · version: ${data.snapshot.version || 'unavailable'} · coverage: <${RecordedMarker} value=${data.snapshot.coverage} /> · ${data.snapshot.total} entries. Citation source and absolute age are unavailable unless recorded.</p>
        <${Omissions} value=${{coverage:data.snapshot.coverage,omitted_characters:data.snapshot.omitted_characters}} />
        ${entry && !data.snapshot.items.length ? html`<p>Entry unavailable in this snapshot.</p>` : null}${data.snapshot.items.map(item => html`<details data-reader-entry open=${!!entry}><summary class="wrapany">${item.kind}: ${item.title || item.subject || item.id || 'ID unavailable'}</summary><p class="mono wrapany">${item.id || 'ID unavailable'}</p><p class="wrapany">${item.lead || item.text || ''}</p>${item.body.map(part => html`<p class="wrapany">${part.text} · facts: ${part.facts.join(', ') || 'unavailable'}</p>`)}<${EntryState} item=${item} choose=${choose} /><${Replacements} history=${data.snapshot.history} id=${item.id} /><p class="wrapany">Seen: <${RecordedMarker} value=${item.seen} /> · last confirmed: <${RecordedMarker} value=${item.last_confirmed} />${item.source_ids.length ? ` · source IDs: ${item.source_ids.join(', ')}` : ''}</p><${SourceAnchors} anchors=${item.anchors} clocks=${data.snapshot.frame_clocks} depiction=${item.depiction_source_id} /><${Omissions} value=${item} /></details>`)}
        <p><button type="button" disabled=${after === 0} onClick=${() => setAfter(Math.max(0, after-25))}>Previous entries</button> <button type="button" disabled=${data.snapshot.next === null} onClick=${() => setAfter(data.snapshot.next)}>Next entries</button></p>` : html`<p>Frozen delivered snapshot unavailable (${data.snapshot_status || 'unavailable'}).</p>`}
      <h3>Recorded calls and results</h3>${data.calls.length ? data.calls.map(c => html`<details data-call=${c.tool}><summary class="wrapany">${c.tool} (${toolLabel(c.tool)}) · ${c.status} · ${c.request_id || 'request unavailable'}${c.player_alias ? ` · player saw as ${c.player_alias}` : ''}</summary>
        <${SourceRead} call=${c} />
        <p class="wrapany">Call: ${c.tool_call_id || 'unavailable'} · intent (unverified): ${c.intent || 'unavailable'} · cites: ${c.cites.join(', ') || 'none recorded'}</p>
        <p class="wrapany">Query: ${c.query || 'unavailable'} · returned IDs: <${EntryButtons} ids=${c.returned_ids} choose=${choose} />${c.result.resolution ? ` · resolution: ${label(c.result.resolution)}${c.result.resolved_from ? ` (${c.result.resolved_from})` : ''}` : ''} · operation: ${c.operation_id || 'unavailable'}</p>
        ${c.returned_hits?.length ? html`<${QueryHits} hits=${c.returned_hits} choose=${choose} />` : null}
        <p class="wrapany">Tool result status: ${c.result.status || 'unavailable'} · reason: ${c.result.reason || 'unavailable'} · delivered: ${c.result.delivered ?? 'unavailable'}</p>
        <p class="wrapany">Operation status: ${c.operation ? c.operation.status : 'unavailable'} · reason: ${c.operation && c.operation.reason || 'unavailable'}</p>
        ${c.operation ? c.operation.receipts.map(r => html`<p class="wrapany">Receipt disposition: ${r.disposition || 'unavailable'} · status: ${r.status || 'unavailable'} · reason: ${r.reason || 'unavailable'}</p>`) : null}
        <${SourceAnchors} anchors=${c.anchors} /><${Omissions} value=${c} /></details>`) : html`<p>No matching calls recorded.</p>`}<${Omissions} value=${{calls_omitted:data.calls_omitted}} />
      <h3>Public hints (unverified)</h3><p class="note">Hints and finish claims cover this actor; they are not attributed to the selected request.</p>${!data.journal_available ? html`<p>Public journal unavailable.</p>` : data.hints.length ? data.hints.map(h => html`<div><p class="wrapany">${h.text} · intent: ${h.intent || 'unavailable'} · cites: ${h.cites.join(', ') || 'none recorded'}</p><${SourceAnchors} anchors=${h.anchors} /><${Omissions} value=${h} /></div>`) : html`<p>No public hints recorded.</p>`}<${Omissions} value=${{hints_omitted:data.hints_omitted}} />
      <h3>Player finish claims (unverified)</h3>${data.finishes.length ? data.finishes.map(f => html`<div><p class="wrapany">${f.disposition || 'unavailable'} · ${f.report || 'unavailable'} · cites: ${f.cites.join(', ') || 'none recorded'}</p><${SourceAnchors} anchors=${f.anchors} /><${Omissions} value=${f} /></div>`) : html`<p>No finish claim recorded.</p>`}<${Omissions} value=${{finishes_omitted:data.finishes_omitted}} /><h3>Evaluator outcome</h3><p class="wrapany"><${RecordedOutcome} value=${data.outcome} /></p>` : null}<//>`;
}

function Episodes() {
  const {data, error} = useFrame('archive/episodes');
  return html`${!data ? html`<${Panel} title="Forgetting episodes" span="s12"><${Waiting} store=${store} what="the forgetting episodes" error=${error} /><//>` :
      !data.lineages.length ? html`<${Panel} title="Forgetting episodes" span="s12"><${Insufficient}>No episodes are tracked.<//><//>` :
      data.lineages.map(lineage => html`<${Panel} title=${`Lineage ${lineage.lineage}`} note=${`study ${lineage.study}`} span="s12"><p class="note">${lineage.note}</p><//>${lineage.episodes.map(episode => html`<${Episode} episode=${episode} />`)}`)}`;
}

/* ---------------------------------------------------------------- containers */
const detailPath = id => `archive/containers/${id.split('/').map(encodeURIComponent).join('/')}`;

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
  const {data, error} = useFrame('archive/containers?limit=500');
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
