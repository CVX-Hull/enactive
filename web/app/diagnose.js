// Diagnose: one run, every number drills down to its instances.
import {html, useState, useMemo, Panel, Pv, Waiting, Table, Insufficient, Callout, fmtH, fmtMoney, pct, trim, bytes, median, quantile, mmss, shortId} from './ui.js';
import {store, useView, runPath, framePath} from './data.js';
import {Chart, requestsOption, transitionsOption} from './charts.js';

export const RUN_TABS = [['overview', 'Overview'], ['tools', 'Tools'], ['programs', 'Programs'], ['memory', 'Memory'], ['handoffs', 'Handoffs'], ['context', 'Requests and context']];
const TOOL_LABELS = {computer_input: 'input', computer_observe: 'observe', computer_result: 'collect result', player_source: 're-read frame',
  player_memory_append: 'memory write', player_memory_query: 'memory query', player_memory_read: 'memory read', player_memory_context: 'memory bundle',
  player_program_save: 'program save', player_program_run: 'program run', player_handoff: 'handoff', player_finish: 'finish'};
export const toolLabel = t => TOOL_LABELS[t] || t;

export function SubNav({tabs, base, current, label}) {
  return html`<nav class="subnav" aria-label=${label}>${tabs.map(([id, text]) => html`<a href=${`#${base}/${id}`} aria-current=${current === id ? 'page' : null}>${text}</a>`)}</nav>`;
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
function Overview() {
  const s = store.summary;
  if (!s) return html`<${Panel} title="Overview" span="s12"><${Waiting} store=${store} what="the run summary" /><//>`;
  const out = s.outcome || {}, facts = s.facts || {};
  const groups = new Map();
  for (const m of s.metrics || []) { const g = m.group || 'Metrics'; if (!groups.has(g)) groups.set(g, []); groups.get(g).push(m); }
  const t0 = facts.started_wall ?? 0;
  return html`<${Panel} title=${`${facts.label || shortId(store.runId)} · ${out.died ? 'died' : out.censor_reason ? `censored (${out.censor_reason})` : 'running'}`} span="s4">
      <dl class="kv"><dt>Survival</dt><dd>${fmtH(out.hours)} game h <${Pv} source=${out.source || 'derived'} /></dd>
        <dt>Decisions</dt><dd>${out.decisions ?? '—'} <${Pv} source="recorded" /></dd>
        <dt>Spend</dt><dd>${fmtMoney(out.dollars)} <${Pv} source="recorded" detail="configured rate" /></dd>
        <dt>Arm · start</dt><dd>${facts.arm} · ${facts.start} <${Pv} source="recorded" detail="assignment" /></dd>
        <dt>Source commit</dt><dd>${String(facts.source_commit || '').slice(0, 7)}</dd>
        <dt>Model · effort</dt><dd>${facts.model} · ${facts.effort}</dd></dl><//>
    ${[...groups.entries()].map(([name, list]) => html`<${Panel} title=${name} span="s4"><dl class="kv">${list.map(m => html`<dt>${m.name} <${Pv} source=${m.source} /></dt>
      <dd title=${`n=${m.count ?? '?'} of ${m.denominator ?? '?'}; missing ${m.missing ?? 0}`}>${typeof m.value === 'number' && m.unit === 'share of spend' ? pct(m.value) : trim(m.value)} <span class="note">${m.unit || ''}${m.count !== undefined ? ` · n ${m.count}/${m.denominator}` : ''}${m.missing ? ` · ${m.missing} missing` : ''}</span></dd>`)}</dl><//>`)}
    <${Panel} title="Findings in this run" note="every row opens its evidence on Supervise" span="s12">
      ${(s.findings || []).length ? html`<${Table} columns=${[{title: 'Finding', key: 'text'}, {title: 'When', render: f => mmss(f.wall - t0)}, {title: 'Step', num: true, key: 'seq'}, {title: 'Source', render: f => html`<${Pv} source=${f.source} />`}]} rows=${s.findings} />`
        : html`<${Insufficient}>No findings recorded for this run.<//>`}<//>
    <${Panel} title="Reader coverage" note="held-out validation of each screen reader; values from a reader below its floor are provisional" span="s7">
      <${Table} columns=${[{title: 'Reader', key: 'name'}, {title: 'Accuracy', num: true, render: r => pct(r.accuracy, 1)}, {title: 'Floor', num: true, render: r => pct(r.floor, 1)},
        {title: 'Held-out n', num: true, key: 'n'}, {title: 'Status', render: r => html`<span class="state ${r.status === 'passes' ? 'clear' : 'watch'}">${r.status === 'passes' ? 'passes' : r.status === 'below_floor' ? 'below floor' : 'fails floor'}</span>`}]} rows=${s.readers || []} empty="No reader validation recorded." /><//>
    <${Panel} title="Milestone ladder" span="s5"><${Table} columns=${[{title: 'Milestone', key: 'name'}, {title: 'Reached', render: l => (l.reached ? 'yes' : 'no')}, {title: 'At game h', num: true, render: l => fmtH(l.at_hours)}]} rows=${s.ladder || []} empty="No ladder recorded." /><//>`;
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
  const list = calls.data ? calls.data.calls || [] : [];
  const chosen = pick === null ? null : list[pick];
  return html`<${Panel} title=${`Every tool, ${data.scope || 'this run'}`} note="volume, speed, failures and how much text each adds to the player's context" span="s12">
      <${Table} columns=${[{title: 'Tool', render: t => toolLabel(t.tool)}, {title: 'Calls', num: true, key: 'calls'}, {title: 'Share', num: true, render: t => pct(t.calls / total)},
        {title: 'p50 ms', num: true, render: t => t.p50_ms ?? '—'}, {title: 'p95 ms', num: true, render: t => t.p95_ms ?? '—'}, {title: 'Refused', num: true, key: 'refused'},
        {title: 'Errors', num: true, key: 'errors'}, {title: 'Result text', num: true, render: t => bytes(t.result_bytes)}, {title: 'Per call', num: true, render: t => (t.calls ? bytes(t.result_bytes / t.calls) : '—')},
        {title: 'Source', render: () => html`<${Pv} source="recorded" />`}]} rows=${rows} />
      ${input ? html`<${Callout}><b>What this says.</b> Input is ${pct(input.calls / total)} of calls and carries ${bytes(input.result_bytes)} of receipt text into context, about ${bytes(input.result_bytes / input.calls)} per call.<//>` : null}<//>
    <${Panel} title="What follows what" note="tool transitions · diagonal = repeats" span="s7">
      ${option ? html`<${Chart} option=${option} epoch=${store.themeEpoch} label="Tool transition matrix" className="trans" />` : null}<//>
    <${Panel} title="Calls" note="open a call to see the frame it produced" span="s5">
      <div class="filters"><label>Tool <select aria-label="Tool filter" value=${tool} onChange=${e => { setTool(e.target.value); setPick(null); }}><option value="">all</option>${rows.map(t => html`<option value=${t.tool}>${toolLabel(t.tool)}</option>`)}</select></label>
        <label>Status <select aria-label="Status filter" value=${status} onChange=${e => { setStatus(e.target.value); setPick(null); }}><option value="">all</option><option value="ok">ok</option><option value="error">error</option><option value="refused">refused</option></select></label></div>
      ${calls.data ? html`<div class="tall"><${Table} columns=${[{title: 'Decision', num: true, key: 'decision'}, {title: 'Tool', render: c => toolLabel(c.tool)}, {title: 'Keys', wrap: true, render: c => c.keys || '—'}, {title: 'Status', key: 'status'}, {title: 'ms', num: true, key: 'latency_ms'}]}
        rows=${list} onPick=${i => setPick(i)} selected=${pick} empty="No calls match." /></div>` : html`<${Waiting} store=${store} what="calls" error=${calls.error} />`}
      ${chosen && chosen.step ? html`<div class="frame small"><img src=${framePath(run, chosen.step.source_id)} alt=${`Frame produced by decision ${chosen.decision}`} /><span class="src">step ${chosen.step.seq} · viewer frame</span></div>` : chosen ? html`<${Insufficient}>This call produced no step.<//>` : null}<//>`;
}

/* ---------------------------------------------------------------- programs */
function Programs({run}) {
  const {data, error} = useView(runPath(run, 'programs'));
  if (!data) return html`<${Panel} title="Programs" span="s12"><${Waiting} store=${store} what="programs" error=${error} /><//>`;
  const programs = data.programs || [], min = data.summary?.min_sample ?? 5;
  return html`${programs.length < min ? html`<${Panel} span="s12"><${Insufficient}><b>Insufficient sample.</b> ${programs.length} program${programs.length === 1 ? ' was' : 's were'} saved in this run. Rates are not shown until there are at least ${min} programs.<//><//>` : null}
    ${programs.map(p => html`<${Panel} title=${`Program ${p.id}`} note=${`actor ${p.actor} · ${p.parent ? `parent ${p.parent}` : 'no parent'}`} span="s6"><${Pv} source=${p.source || 'player_claim'} detail="authored by the player" />
        <pre>${JSON.stringify(p.doc, null, 1)}</pre><//>
      <${Panel} title="Runs" note="status, steps and elapsed time" span="s6">
        <${Table} columns=${[{title: 'Run', render: (_, i) => i + 1}, {title: 'Status', render: r => html`${r.status} <${Pv} source="recorded" />`}, {title: 'Steps', num: true, key: 'steps'},
          {title: 'Seconds', num: true, render: r => (r.elapsed_seconds ?? 0).toFixed(1)}, {title: 'Reason given', wrap: true, render: r => r.reason || ''}]} rows=${p.runs || []} empty="Never run." /><//>`)}
    ${!programs.length ? html`<${Panel} span="s12"><${Insufficient}>No program was saved in this run.<//><//>` : null}`;
}

/* ---------------------------------------------------------------- memory */
function Memory({run}) {
  const {data, error} = useView(runPath(run, 'memory'));
  const [sel, setSel] = useState(0);
  const [frame, setFrame] = useState(null);
  if (!data) return html`<${Panel} title="Memory" span="s12"><${Waiting} store=${store} what="memory records" error=${error} /><//>`;
  const records = data.records || [];
  const r = records[Math.min(sel, records.length - 1)];
  const sum = data.summary || {};
  return html`<${Panel} title="Records" note=${`${sum.written ?? records.length} written · ${sum.queries ?? 0} queries · ${sum.returned ?? 0} returned a record`} span="s5">
      <${Table} columns=${[{title: 'Record', render: x => html`${x.id}${x.supersedes ? ` ← ${x.supersedes}` : ''}`}, {title: 'Kind', key: 'kind'}, {title: 'Read back', render: x => ((x.reads || []).length ? 'yes' : 'never')},
        {title: 'Audit', render: x => html`${x.audit ? x.audit.verdict : 'unchecked'} ${x.audit ? html`<${Pv} source="human" />` : null}`}]} rows=${records} onPick=${i => { setSel(i); setFrame(null); }} selected=${sel} empty="No memory records." /><//>
    ${r ? html`<${Panel} title=${`${r.kind} ${r.id}`} note=${`actor ${r.actor} · chain ${r.chain || '—'}`} span="s7"><div><${Pv} source=${r.source || 'player_claim'} detail="fallible" /></div>
      <p class="prewrap">${r.text}</p>
      <dl class="kv"><dt>Supports</dt><dd>${(r.supports || []).join(', ') || 'none'}</dd><dt>Replaces</dt><dd>${r.supersedes || 'nothing'}</dd><dt>Carried in a handoff</dt><dd>${r.handoff_carry ? 'yes' : 'no'}</dd>
        <dt>Audit</dt><dd>${r.audit ? r.audit.verdict : 'unchecked'}</dd></dl>
      ${r.audit && r.audit.note ? html`<${Callout}>${r.audit.note}<//>` : null}
      <h3>Cited frames</h3>
      ${(r.sources || []).length ? html`<div class="chips">${r.sources.map(id => html`<button type="button" class="btn" aria-pressed=${frame === id} onClick=${() => setFrame(id)}>${id.slice(-6)}</button>`)}</div>` : html`<p class="note">No cited frames.</p>`}
      ${frame ? html`<div class="frame small"><img src=${framePath(run, frame)} alt=${`Cited frame ${frame}`} /><span class="src">${frame.slice(-12)} · viewer frame</span></div>` : null}
      <p class="note">Each cited frame opens beside the claim, so it can be checked against what the screen showed.</p><//>` : null}`;
}

/* ---------------------------------------------------------------- handoffs */
function Handoffs({run}) {
  const {data, error} = useView(runPath(run, 'handoffs'));
  const [sel, setSel] = useState(0);
  if (!data) return html`<${Panel} title="Handoffs" span="s12"><${Waiting} store=${store} what="handoffs" error=${error} /><//>`;
  const list = data.handoffs || [];
  const h = list[Math.min(sel, list.length - 1)];
  const sum = data.summary || {};
  const resume = list.map(x => x.decisions_to_resume).filter(x => x !== null && x !== undefined);
  return html`<${Panel} title=${`All ${list.length} handoffs`} note=${resume.length ? `median ${trim(sum.median_resume ?? median(resume))} decisions to resume (IQR ${trim(sum.q1 ?? quantile(resume, 0.25))}–${trim(sum.q3 ?? quantile(resume, 0.75))})` : 'no resume measurements'} span="s7">
      <${Table} columns=${[{title: 'Run', render: x => x.label || x.run}, {title: 'Arm', render: x => x.arm || '—'}, {title: 'At decision', num: true, key: 'at_decision'},
        {title: 'Decisions to resume', num: true, render: x => x.decisions_to_resume ?? '—'}, {title: 'Carry ratio', num: true, render: x => (x.carry_ratio === null || x.carry_ratio === undefined ? '—' : pct(x.carry_ratio, 1))}]}
        rows=${list} onPick=${i => setSel(i)} selected=${sel} empty="No handoffs." /><//>
    ${h ? html`<${Panel} title=${`${h.label || h.run}'s handoff, side by side`} span="s5">
      <h3>Predecessor's last note <${Pv} source="player_claim" /></h3><pre>${h.predecessor_note || '(none recorded)'}</pre>
      <h3>Carry to the next actor <${Pv} source="recorded" detail="context" /></h3><pre>${h.carry_text || '(none recorded)'}</pre>
      ${h.identity_check ? html`<${Callout}>Identity check <${Pv} source=${h.identity_check.source || 'human'} />: ${h.identity_check.verdict}. ${h.identity_check.note}<//>` : html`<p class="note">No identity check recorded.</p>`}<//>` : null}`;
}

/* ---------------------------------------------------------------- requests and context */
const PART_COLOURS = ['--p-rec', '--p-claim', '--accent', '--watch', '--quiet', '--sunk'];
function Context({run}) {
  const requests = store.requests, markers = store.markers;
  const t0 = store.summary?.facts?.started_wall ?? (requests[0] ? requests[0].wall : 0);
  const [sel, setSel] = useState(null);
  const pick = sel || (requests.length ? requests[requests.length - 1].request_id : null);
  const ctx = useView(pick ? runPath(run, `context/${encodeURIComponent(pick)}`) : null, 0);
  const option = useMemo(() => (requests.length ? requestsOption(requests, markers, t0) : null), [requests, markers, t0, store.themeEpoch]);
  if (!requests.length) return html`<${Panel} title="Requests and context" span="s12"><${Waiting} store=${store} what="requests" /><//>`;
  const top = [...requests].sort((a, b) => b.dollars - a.dollars).slice(0, 6);
  const total = requests.reduce((a, r) => a + r.dollars, 0);
  const heavy = requests.filter(r => r.cache_write > 30000).reduce((a, r) => a + r.dollars, 0);
  const c = ctx.data;
  const kinds = c ? [...new Map((c.parts || []).map(p => [p.kind, 0])).keys()] : [];
  const sizes = c ? kinds.map((k, i) => [k, c.parts.filter(p => p.kind === k).reduce((a, p) => a + p.bytes, 0), `var(${PART_COLOURS[i % PART_COLOURS.length]})`]) : [];
  const sum = sizes.reduce((a, s) => a + s[1], 0) || 1;
  return html`<${Panel} title="Every request" note="tokens per request, cache writes, image evictions (dotted) and the handoff" span="s12">
      <${Chart} option=${option} epoch=${store.themeEpoch} label="Per-request tokens and cache writes" className="reqchart" />
      <${Callout}><b>Where the rewrite money goes.</b> Spikes in cache writes follow image evictions: each eviction changes the cached prefix, and the next request rewrites it. ${pct(total ? heavy / total : 0)} of this run's spend was in requests that wrote over 30,000 cache tokens. <${Pv} source="derived" /><//><//>
    <${Panel} title="Costliest requests" note="open one to replay its context" span="s5">
      <${Table} columns=${[{title: 'Request', render: r => r.request_id}, {title: 'Actor', key: 'actor'}, {title: 'Tokens', num: true, render: r => `${Math.round(r.input_tokens / 1000)}k`},
        {title: 'Cache write', num: true, render: r => `${Math.round(r.cache_write / 1000)}k`}, {title: '$', num: true, render: r => r.dollars.toFixed(3)}]}
        rows=${top} onPick=${(i, r) => setSel(r.request_id)} selected=${top.findIndex(r => r.request_id === pick)} /><//>
    <${Panel} title=${`What actor ${c ? c.actor : '—'} sent in ${pick}`} note=${c ? (c.exact ? 'exact: replayed from the recorded manifest' : 'reconstructed: frozen inputs plus recorded tool results') : ''} span="s7">
      ${c ? html`<div><${Pv} source=${c.exact ? 'recorded' : 'derived'} detail=${c.exact ? 'manifest' : 'reconstruction'} /></div>
        <div class="ctx-bar" role="img" aria-label="Context composition">${sizes.map(([n, b, col]) => html`<span title=${n} style=${{width: `${(b / sum * 100).toFixed(2)}%`, background: col}}></span>`)}</div>
        <dl class="kv">${sizes.map(([n, b, col]) => html`<dt><i class="swatch" style=${{background: col}}></i>${n}</dt><dd>${bytes(b)}</dd>`)}
          <dt>Images</dt><dd>${c.totals?.images_kept ?? 0} kept · ${c.totals?.images_omitted ?? 0} omitted</dd><dt>Input tokens · cache read</dt><dd>${c.totals?.input_tokens ?? '—'} · ${c.totals?.cache_read ?? '—'}</dd></dl>
        ${c.note ? html`<p class="note">${c.note}</p>` : null}` : html`<${Waiting} store=${store} what="the request context" error=${ctx.error} />`}<//>`;
}
