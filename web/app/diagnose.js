// Diagnose: one run, every number drills down to its instances.
import {html, useState, useMemo, Panel, Pv, Unvalidated, Waiting, Table, Insufficient, Callout, fmtH, fmtMoney, pct, trim, bytes, mmss, shortId, scalar, label, compact} from './ui.js';
import {store, useView, runPath, framePath, runStart} from './data.js';
import {Chart, requestsOption, transitionsOption} from './charts.js';
import {findingText} from './supervise.js';

export const RUN_TABS = [['overview', 'Overview'], ['tools', 'Tools'], ['programs', 'Programs'], ['memory', 'Memory'], ['handoffs', 'Handoffs'], ['context', 'Requests and context']];
const TOOL_LABELS = {computer_input: 'input', computer_observe: 'observe', computer_result: 'collect result', player_source: 're-read frame',
  player_memory_append: 'memory write', player_memory_query: 'memory query', player_memory_read: 'memory read', player_memory_context: 'memory bundle',
  player_program_save: 'program save', player_program_run: 'program run', player_handoff: 'handoff', player_finish: 'finish'};
export const toolLabel = t => TOOL_LABELS[t] || t;
const GROUPS = {survival: 'Survival', custody: 'Custody', pace: 'Pace and game time', stall: 'Stalls', mode: 'Mode', host: 'Host and spend', input: 'Input', memory: 'Memory',
  handoff: 'Handoffs', programs: 'Programs', tools: 'Tool calls', needs: 'Needs', lineage: 'Lineage', run: 'Run losses'};

export function SubNav({tabs, base, current, label: aria}) {
  return html`<nav class="subnav" aria-label=${aria}>${tabs.map(([id, text]) => html`<a href=${`#${base}/${id}`} aria-current=${current === id ? 'page' : null}>${text}</a>`)}</nav>`;
}

export function Diagnose({section}) {
  const run = store.runId;
  const current = RUN_TABS.some(t => t[0] === section) ? section : 'overview';
  const body = !run ? html`<${Panel} title="Diagnose" span="s12"><${Waiting} store=${store} what="the run list" /><//>` :
    current === 'overview' ? html`<${Overview} />` : current === 'tools' ? html`<${Tools} run=${run} />` :
    current === 'programs' ? html`<${Programs} run=${run} />` : current === 'memory' ? html`<${Memory} run=${run} />` :
    current === 'handoffs' ? html`<${Handoffs} run=${run} />` : html`<${Context} run=${run} />`;
  return html`<section class="grid" data-view="run" aria-label="Diagnose a run">
    <div class="s12"><${SubNav} tabs=${RUN_TABS} base="run" current=${current} label="Run sections" /></div>${body}</section>`;
}

/* ---------------------------------------------------------------- overview */
const metricText = m => {
  if (m.value && typeof m.value === 'object' && typeof m.value.calls === 'number') return `${m.value.calls} calls, ${m.value.refused} refused, ${m.value.errors} errors`;
  const v = scalar(m.value);
  if (v === null) return m.value === null || (Array.isArray(m.value) && !m.value.length) ? 'none' : compact(m.value);
  return Math.abs(v) >= 100 ? String(Math.round(v)) : trim(+v.toFixed(3));
};
const metricNote = m => [m.count !== null && m.count !== undefined ? `n ${trim(m.count)}${m.denominator ? `/${trim(m.denominator)}` : ''}` : '', m.missing ? (typeof m.missing === 'number' ? `${trim(m.missing)} missing` : (/missing/i.test(label(m.missing)) ? label(m.missing) : `missing: ${label(m.missing)}`)) : ''].filter(Boolean).join(' · ');

function Overview() {
  const s = store.summary;
  if (!s) return html`<${Panel} title="Overview" span="s12"><${Waiting} store=${store} what="the run summary" /><//>`;
  const out = s.outcome || {}, facts = s.facts || {}, labels = s.labels || {};
  const groups = new Map();
  for (const m of s.metrics || []) {
    const prefix = m.name.split('.')[0];
    if (m.name === 'reader.coverage' || m.name === 'ladder.reached') continue;
    const title = GROUPS[prefix] || label(prefix);
    if (!groups.has(title)) groups.set(title, []);
    groups.get(title).push(m);
  }
  const t0 = runStart();
  const listed = (s.findings || []).filter(f => f.kind !== 'context_eviction');
  const evictions = (s.findings || []).length - listed.length;
  const verdict = out.lost ? 'lost' : out.died ? 'died' : out.censor_reason ? `censored (${label(out.censor_reason)})` : s.live ? 'running' : 'ended';
  return html`<${Panel} title=${`${shortId(s.run)} · ${verdict}`} note=${s.live ? 'live' : 'final record'} span="s4">
      <dl class="kv"><dt>Survival</dt><dd>${fmtH(out.hours)} game h <${Pv} source="derived" /></dd>
        <dt>Episodes</dt><dd>${out.episodes ?? '—'}</dd>
        <dt>Decisions</dt><dd>${s.decisions ?? '—'} <${Pv} source="recorded" /></dd>
        <dt>Spend</dt><dd>${fmtMoney(s.dollars)} <${Pv} source="recorded" detail="configured rate" /></dd>
        <dt>Arm · start</dt><dd>${labels.arm || '—'} · ${labels.start || '—'} <${Pv} source="recorded" detail="assignment" /></dd>
        <dt>Scenario</dt><dd>${labels.scenario || '—'}</dd>
        <dt>Source commit</dt><dd>${String(facts.source_commit || '').slice(0, 7) || '—'}</dd>
        <dt>Model · effort</dt><dd>${facts.model || '—'} · ${facts.effort || '—'}</dd>
        <dt>Evaluator</dt><dd>core ${s.versions?.core_version} · ${s.versions?.binding_id} ${s.versions?.binding_version}</dd></dl><//>
    ${[...groups.entries()].map(([name, list]) => html`<${Panel} title=${name} span="s4"><dl class="kv">${list.map(m => html`<dt>${label(m.name.split('.').slice(1).join('.'))}${m.key ? ` · ${m.key}` : ''} <${Pv} source=${m.source} /><${Unvalidated} metric=${m} /></dt>
      <dd title=${metricNote(m)}>${metricText(m)} <span class="note sub">${metricNote(m)}</span></dd>`)}</dl><//>`)}
    <${Panel} title="Findings in this run" note="every row opens its evidence on Supervise · newest first, up to 100" span="s12">
      ${listed.length ? html`<${Table} columns=${[{title: 'Finding', render: f => findingText(f)}, {title: 'When', render: f => (f.wall === null ? '—' : mmss(f.wall - t0))}, {title: 'Step', num: true, render: f => f.seq_start}, {title: 'Source', render: f => html`<${Pv} source=${f.source} />`}]} rows=${listed} />`
        : html`<${Insufficient}>No findings recorded for this run.<//>`}
      ${evictions ? html`<p class="note">${evictions} routine image evictions among the newest findings are not listed; they are the dotted lines on the Requests chart.</p>` : null}<//>
    <${Panel} title="Reader coverage" note="how often each reader produced a value, and its held-out validation; values from a reader below its floor are provisional" span="s7">
      <${Table} columns=${[{title: 'Reader', key: 'reader'}, {title: 'Coverage', num: true, render: r => pct(r.coverage, 1)}, {title: 'Frames', num: true, render: r => `${trim(r.count)}/${trim(r.denominator)}`},
        {title: 'Held-out', num: true, render: r => (r.validation ? `${pct(r.validation.accuracy, 1)} of ${r.validation.n} · floor ${pct(r.validation.floor, 1)}` : '—')},
        {title: 'Status', render: r => (r.validation ? html`<span class="state ${r.validation.pass === true ? 'clear' : 'watch'}">${r.validation.pass === true ? 'passes' : r.validation.pass === false ? 'below floor' : 'unmeasured'}</span>` : html`<span class="note">not validated</span>`)}]} rows=${s.reader_coverage || []} empty="No reader coverage recorded." /><//>
    <${Panel} title="Milestone ladder" note=${s.ladder ? `highest reached: ${label(s.ladder.highest || 'none')}` : ''} span="s5">
      <${Table} columns=${[{title: 'Milestone', render: r => label(r.id)}, {title: 'Status', render: r => label(r.status)}, {title: 'Evidence', render: r => html`<${Pv} source=${r.evidence} />`},
        {title: 'At decision', num: true, render: r => (r.clocks ? r.clocks.decision : '—')}, {title: '$', num: true, render: r => (r.clocks ? fmtMoney(r.clocks.dollars) : '—')}]}
        rows=${s.ladder ? s.ladder.rungs || [] : []} empty="No ladder recorded." /><//>`;
}

/* ---------------------------------------------------------------- tools */
function Tools({run}) {
  const {data, error} = useView(runPath(run, 'tools'));
  const [tool, setTool] = useState('');
  const [status, setStatus] = useState('');
  const [pick, setPick] = useState(null);
  const query = `${runPath(run, 'calls')}?tool=${encodeURIComponent(tool)}&status=${encodeURIComponent(status)}&limit=100`;
  const calls = useView(query);
  const option = useMemo(() => (data ? transitionsOption(data.tools || [], data.transitions || [], toolLabel) : null), [data, store.themeEpoch]);
  if (!data) return html`<${Panel} title="Tools" span="s12"><${Waiting} store=${store} what="tool statistics" error=${error} /><//>`;
  const rows = [...(data.tools || [])].sort((a, b) => b.calls - a.calls);
  const total = rows.reduce((a, t) => a + t.calls, 0);
  const input = rows.find(t => t.tool === 'computer_input');
  const list = calls.data ? calls.data.items || [] : [];
  const chosen = pick === null ? null : list[pick];
  return html`<${Panel} title="Every tool in this run" note="volume, speed, failures and how much text each adds to the player's context" span="s12">
      <${Table} columns=${[{title: 'Tool', render: t => toolLabel(t.tool)}, {title: 'Calls', num: true, key: 'calls'}, {title: 'Share', num: true, render: t => pct(total ? t.calls / total : 0)},
        {title: 'p50 ms', num: true, render: t => (t.p50_ms === null ? '—' : Math.round(t.p50_ms))}, {title: 'p95 ms', num: true, render: t => (t.p95_ms === null ? '—' : Math.round(t.p95_ms))}, {title: 'Refused', num: true, key: 'refused'},
        {title: 'Errors', num: true, key: 'errors'}, {title: 'Result text', num: true, render: t => bytes(t.result_bytes)}, {title: 'Per call', num: true, render: t => (t.calls ? bytes(t.result_bytes / t.calls) : '—')},
        {title: 'Source', render: () => html`<${Pv} source="recorded" />`}]} rows=${rows} />
      ${input ? html`<${Callout}><b>What this says.</b> Input is ${pct(input.calls / total)} of calls and carries ${bytes(input.result_bytes)} of receipt text into context, about ${bytes(input.result_bytes / input.calls)} per call.<//>` : null}<//>
    <${Panel} title="What follows what" note="tool transitions within each actor · diagonal = repeats" span="s7">
      ${option && (data.transitions || []).length ? html`<${Chart} option=${option} epoch=${store.themeEpoch} label="Tool transition matrix" className="trans" />` : html`<${Insufficient}>No transitions recorded.<//>`}<//>
    <${Panel} title="Calls" note="open a call to see the frame it produced" span="s5">
      <div class="filters"><label>Tool <select aria-label="Tool filter" value=${tool} onChange=${e => { setTool(e.target.value); setPick(null); }}><option value="">all</option>${rows.map(t => html`<option value=${t.tool}>${toolLabel(t.tool)}</option>`)}</select></label>
        <label>Status <select aria-label="Status filter" value=${status} onChange=${e => { setStatus(e.target.value); setPick(null); }}><option value="">all</option><option value="ok">ok</option><option value="error">error</option><option value="refused">refused</option></select></label></div>
      ${calls.data ? html`<div class="tall"><${Table} columns=${[{title: 'Decision', num: true, key: 'decision'}, {title: 'Tool', render: c => toolLabel(c.tool)}, {title: 'Status', key: 'status'}, {title: 'ms', num: true, render: c => (c.latency_ms === null ? '—' : Math.round(c.latency_ms))}, {title: 'Result', num: true, render: c => bytes(c.result_bytes)}]}
        rows=${list} onPick=${i => setPick(i)} selected=${pick} empty="No calls match." /></div>` : html`<${Waiting} store=${store} what="calls" error=${calls.error} />`}
      ${chosen && chosen.step && chosen.step.source_id ? html`<div class="frame small"><img src=${framePath(run, chosen.step.source_id)} alt=${`Frame produced by decision ${chosen.decision}`} /><span class="src">step ${chosen.step.seq} · viewer frame</span></div>` : chosen ? html`<${Insufficient}>This call produced no step.<//>` : null}<//>`;
}

/* ---------------------------------------------------------------- programs */
const MIN_PROGRAMS = 5;
function Programs({run}) {
  const {data, error} = useView(runPath(run, 'programs'));
  if (!data) return html`<${Panel} title="Programs" span="s12"><${Waiting} store=${store} what="programs" error=${error} /><//>`;
  const programs = data.programs || [], runs = data.runs || [];
  const saved = new Set([...programs.map(p => p.id), ...(data.saves || []).map(x => x.program_id)]);
  return html`${programs.length < MIN_PROGRAMS ? html`<${Panel} span="s12"><${Insufficient}><b>Insufficient sample.</b> ${saved.size} program${saved.size === 1 ? ' was' : 's were'} saved and ${runs.length} program run${runs.length === 1 ? '' : 's'} recorded in this run. Rates are not shown until there are at least ${MIN_PROGRAMS} programs.<//><//>` : null}
    ${programs.map(p => html`<${Panel} title=${`Program ${shortId(p.id)}${p.name ? ` · ${p.name}` : ''}`} note=${`actor ${shortId(p.actor_id)} · ${p.parent_id ? `parent ${shortId(p.parent_id)}` : 'no parent'}`} span="s6"><div><${Pv} source="player_claim" detail="authored by the player" /></div>
        <pre>${JSON.stringify(p.document, null, 1)}</pre><//>`)}
    ${runs.length ? html`<${Panel} title="Program runs" note=${programs.length ? 'status, steps and elapsed time' : 'the program documents are not in the store the viewer reads, so only their runs are shown'} span="s12">
        <${Table} columns=${[{title: 'Program', render: r => shortId(r.program_id)}, {title: 'Status', render: r => html`${r.status} <${Pv} source="recorded" />`}, {title: 'Steps', num: true, key: 'steps'},
          {title: 'Seconds', num: true, render: r => (r.elapsed_seconds ?? 0).toFixed(1)}, {title: 'Reason given', wrap: true, render: r => html`${r.reason || ''} <${Pv} source="player_claim" />`}]} rows=${runs} /><//>` : null}
    ${!programs.length && !runs.length ? html`<${Panel} span="s12"><${Insufficient}>No program was saved or run in this run.<//><//>` : null}`;
}

/* ---------------------------------------------------------------- memory */
const verdictText = labels => (labels.length ? labels.map(l => `${l.verdict}: ${label(l.code)}`).join('; ') : 'unchecked');
function Memory({run}) {
  const {data, error} = useView(runPath(run, 'memory'));
  const [sel, setSel] = useState(0);
  const [frame, setFrame] = useState(null);
  if (!data) return html`<${Panel} title="Memory" span="s12"><${Waiting} store=${store} what="memory records" error=${error} /><//>`;
  if (!data.available) return html`<${Panel} title="Memory" span="s12"><${Insufficient}>This run's player memory store is not available to the viewer.<//><//>`;
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

/* ---------------------------------------------------------------- handoffs */
function Handoffs({run}) {
  const {data, error} = useView(runPath(run, 'handoffs'));
  const [sel, setSel] = useState(0);
  if (!data) return html`<${Panel} title="Handoffs" span="s12"><${Waiting} store=${store} what="handoffs" error=${error} /><//>`;
  const list = data.handoffs || [];
  const h = list[Math.min(sel, list.length - 1)];
  return html`<${Panel} title=${`${list.length} handoff${list.length === 1 ? '' : 's'} in this run`} note="how much carried over and how fast the next actor resumed" span="s7">
      <${Table} columns=${[{title: 'At decision', num: true, key: 'decision'}, {title: 'Actor', render: x => shortId(x.actor)}, {title: 'Decisions to resume', num: true, render: x => x.decisions_to_resume ?? '—'},
        {title: 'Carry ratio', num: true, render: x => (x.carry_ratio === null || x.carry_ratio === undefined ? '—' : pct(x.carry_ratio, 1))}, {title: 'Carry', num: true, render: x => bytes(x.carry_bytes)},
        {title: 'Identity check', render: x => (x.identity_check.checked ? 'error confirmed' : 'none recorded')}]}
        rows=${list} onPick=${i => setSel(i)} selected=${sel} empty="No handoffs." /><//>
    ${h ? html`<${Panel} title=${`Handoff at decision ${h.decision}`} span="s5">
      <h3>Carry to the next actor <${Pv} source="recorded" detail="context file" /></h3><pre>${h.carry_text || '(none recorded)'}</pre>
      <p class="note">${(h.carried_ids || []).length} memory records and programs carried · context ${shortId(h.context_id)}</p>
      ${h.identity_check.errors.length ? h.identity_check.errors.map(e => html`<${Callout}>Identity check <${Pv} source="human" detail=${e.author} />: ${e.verdict} ${label(e.code)}. ${e.note}<//>`) : html`<p class="note">No identity or world error was labelled for this handoff.</p>`}<//>` : null}`;
}

/* ---------------------------------------------------------------- requests and context */
const PART_COLOURS = ['--p-rec', '--p-claim', '--accent', '--watch', '--quiet', '--p-calc', '--sunk'];
function Context({run}) {
  const requests = store.requests, markers = store.markers;
  const t0 = runStart();
  const [sel, setSel] = useState(null);
  const row = requests.find(r => r.id === sel) || requests[requests.length - 1];
  const ctx = useView(row ? `${runPath(run, `context/${encodeURIComponent(row.request_id)}`)}?actor=${encodeURIComponent(row.actor)}` : null, 0);
  const option = useMemo(() => (requests.length ? requestsOption(requests, markers, t0) : null), [requests, markers, t0, store.themeEpoch]);
  if (!requests.length) return html`<${Panel} title="Requests and context" span="s12"><${Waiting} store=${store} what="requests" /><//>`;
  const top = [...requests].sort((a, b) => b.dollars - a.dollars).slice(0, 6);
  const total = requests.reduce((a, r) => a + (r.dollars || 0), 0);
  const heavy = requests.filter(r => r.cache_write > 30000).reduce((a, r) => a + (r.dollars || 0), 0);
  const c = ctx.data;
  const kinds = c ? Object.entries(c.bytes_by_kind || {}) : [];
  const sum = kinds.reduce((a, k) => a + k[1], 0) || 1;
  const images = c ? (c.parts || []).filter(p => p.kind === 'image') : [];
  return html`<${Panel} title="Every request" note="tokens per request, cache writes, image evictions (dotted) and handoffs" span="s12">
      <${Chart} option=${option} epoch=${store.themeEpoch} label="Per-request tokens and cache writes" className="reqchart" />
      <${Callout}><b>Where the rewrite money goes.</b> Spikes in cache writes follow image evictions: each eviction changes the cached prefix, and the next request rewrites it. ${pct(total ? heavy / total : 0)} of this run's spend was in requests that wrote over 30,000 cache tokens. <${Pv} source="derived" /><//><//>
    <${Panel} title="Costliest requests" note="open one to replay its context" span="s5">
      <${Table} columns=${[{title: 'Request', render: r => r.request_id}, {title: 'Actor', render: r => shortId(r.actor)}, {title: 'Input tokens', num: true, render: r => `${Math.round((r.input_tokens + r.cache_read + r.cache_write) / 1000)}k`},
        {title: 'Cache write', num: true, render: r => `${Math.round(r.cache_write / 1000)}k`}, {title: '$', num: true, render: r => (r.dollars === null ? '—' : r.dollars.toFixed(3))}]}
        rows=${top} onPick=${(i, r) => setSel(r.id)} selected=${top.findIndex(r => r.id === (row && row.id))} /><//>
    <${Panel} title=${`What actor ${c ? shortId(c.actor) : '—'} sent in ${row ? row.request_id : '—'}`} note=${c ? (c.exact ? 'exact: replayed from the recorded manifest' : 'reconstructed: frozen inputs plus recorded tool results') : ''} span="s7">
      ${c ? html`<div><${Pv} source=${c.exact ? 'recorded' : 'derived'} detail=${c.exact ? 'manifest' : 'reconstruction'} /></div>
        <div class="ctx-bar" role="img" aria-label="Context composition">${kinds.map(([n, b], i) => html`<span title=${n} style=${{width: `${(b / sum * 100).toFixed(2)}%`, background: `var(${PART_COLOURS[i % PART_COLOURS.length]})`}}></span>`)}</div>
        <dl class="kv">${kinds.map(([n, b], i) => html`<dt><i class="swatch" style=${{background: `var(${PART_COLOURS[i % PART_COLOURS.length]})`}}></i>${label(n)}</dt><dd>${bytes(b)}</dd>`)}
          <dt>Parts</dt><dd>${c.part_count}</dd><dt>Images</dt><dd>${images.filter(p => p.state !== 'omitted').length} kept · ${images.filter(p => p.state === 'omitted').length} omitted</dd></dl>
        ${(c.missing || []).length ? html`<p class="note">Not recorded: ${c.missing.map(label).join(', ')}.</p>` : null}
        ${c.omissions_capped ? html`<p class="note">The omitted-image list is capped by the viewer.</p>` : null}` : html`<${Waiting} store=${store} what="the request context" error=${ctx.error} />`}<//>`;
}
