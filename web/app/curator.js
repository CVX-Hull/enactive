// Curator: what the live curator did for this run. Its runner's cadence and coverage, what it spent by kind of session
// and tier, the health of its interleaved hygiene, every session it ran with a drawer for one, and the run's own gate
// verdicts and drafts. Limits are shown only where the runner recorded them: an archived status has none.
import {html, useEffect, useRef, Panel, Pv, Waiting, Insufficient, Disclosure, Table, count, label, plural, pct, secs, usd2, bytes, plainValue} from './ui.js';
import {store, runPath, useView} from './data.js';
import {RunnerDetail, RUNNER_STATES, RUNNER_STATUS, known} from './records.js';

const KINDS = {admission: 'Window', ingestion: 'Window', hygiene: 'Hygiene', grooming: 'Grooming'};
const isNumber = v => typeof v === 'number' && Number.isFinite(v);
const ms = v => (isNumber(v) ? `${Math.round(v * 1000)} ms` : known({v}, 'v'));
const wall = v => (isNumber(v) ? new Date(v * 1000).toISOString().replace('.000Z', 'Z') : 'unknown');
const versionLink = v => (v && v !== 'unknown' ? html`<a href=${`#memory?version=${encodeURIComponent(v)}`}>${v} → Memory</a>` : html`<span>${v === null ? 'none' : 'unknown'}</span>`);

function Stat({name, children, id}) {
  return html`<div class="stat" id=${id}><span class="name">${name}</span><span class="val num">${children}</span></div>`;
}

/** Card 1: the runner's state and cadence, how far its coverage lags play, and the versions it has confirmed. */
function RunnerCard({runner}) {
  const s = runner.status;
  if (!s) return html`<section class="kpi panel interp" id="cur-runner" aria-label="Coverage and runner"><h3>Coverage & runner</h3><div class="big">—</div>
    <p class="note" data-runner-status>Status file: ${RUNNER_STATUS[runner.source_status] || 'state unknown.'}</p></section>`;
  const set = s.settings && s.settings !== 'unknown' ? s.settings : {};
  const latest = s.latest_version && s.latest_version !== 'unknown' ? s.latest_version.version : s.latest_version;
  const confirmed = s.last_confirmed === null ? null : s.last_confirmed && s.last_confirmed !== 'unknown' ? s.last_confirmed.version : 'unknown';
  return html`<section class="kpi panel interp" id="cur-runner" aria-label="Coverage and runner"><h3>Coverage & runner</h3>
    <div class="big">${RUNNER_STATES[s.state] || 'state unknown'}</div><div class="sub">${s.current && s.current !== 'unknown' ? `in a ${(KINDS[s.current.session_kind] || 'session').toLowerCase()} session` : s.status_schema}</div>
    <dl class="kv"><dt>Cadence</dt><dd>${known(set, 'trigger_steps')} / ${known(set, 'ceiling_steps')} steps</dd>
      <dt>Lag</dt><dd>${known(s, 'lag')} operations</dd><dt>Backlog</dt><dd>${known(s, 'backlog')} steps</dd>
      <dt>Latest version</dt><dd>${versionLink(latest)}</dd><dt>Confirmed</dt><dd>${versionLink(confirmed)}</dd></dl></section>`;
}

/** Card 2: ingestion against interleaved hygiene, the tiers sessions ran at, and flex deferrals; limits when recorded. */
function SpendCard({spend, runner}) {
  const limits = runner.status ? runner.status.limits : null;
  const tiers = spend ? Object.entries(spend.applied_tiers || {}) : [];
  return html`<section class="kpi panel interp" id="cur-spend" aria-label="Spend and tier"><h3>Spend & tier</h3>
    <div class="big num">${spend ? usd2(spend.spent_usd) : '—'}</div><div class="sub">${spend ? `proxy-accounted · ${spend.sessions_settled}/${spend.sessions_total} settled` : 'no curator session recorded'}</div>
    ${spend ? html`<div class="chips">${spend.spend_complete ? html`<${Pv} source="recorded" detail="proxy" />` : html`<span class="state watch">incomplete</span>`}</div>
    <dl class="kv"><dt>Ingestion</dt><dd>${usd2(spend.ingestion_usd)} · ${plural(spend.ingestion_sessions, 'session')}</dd>
      <dt>Interleaved hygiene</dt><dd>${usd2(spend.hygiene_usd)} · ${plural(spend.hygiene_sessions, 'session')}</dd>
      <dt>Hygiene share</dt><dd id="cur-hygiene-share">${spend.hygiene_share === null ? '—' : pct(spend.hygiene_share, 1)}</dd>
      <dt>Tiers applied</dt><dd>${tiers.length ? tiers.map(([t, n]) => `${t} ${n}`).join(' · ') : 'none recorded'}</dd>
      <dt>Flex 429 deferrals</dt><dd>${count(spend.deferrals)}</dd></dl>` : null}
    ${limits && limits !== 'unknown' ? html`<dl class="kv limits" id="cur-limits"><dt>Run cap</dt><dd>${usd2(limits.cap_usd)}</dd><dt>Session cap</dt><dd>${usd2(limits.session_cap_usd)}</dd>
      <dt>Service tier</dt><dd>${known(limits, 'service_tier')}</dd><dt>Deferral limit</dt><dd>${known(limits, 'flex_deferral_limit')}</dd>
      ${limits.hygiene && limits.hygiene !== 'unknown' ? html`<dt>Hygiene share cap</dt><dd>${isNumber(Number(limits.hygiene.max_spend_share)) ? pct(Number(limits.hygiene.max_spend_share)) : 'unknown'}</dd>` : null}</dl>`
      : html`<p class="note" id="cur-limits-none">No configured limits recorded${runner.status ? ` (${runner.status.status_schema})` : ''}.</p>`}</section>`;
}

/** Card 3: interleaved hygiene passes, their failures, and their per-pass watch where the runner recorded one. */
function HygieneCard({spend, sessions, runner}) {
  const s = runner.status;
  const passes = sessions.filter(r => r.session_kind === 'hygiene');
  const failed = passes.filter(r => (r.host_end && r.host_end.ok === false) || r.session_state === 'failed').length;
  const hygiene = s && s.limits && s.limits !== 'unknown' && s.limits.hygiene && s.limits.hygiene !== 'unknown' ? s.limits.hygiene : null;
  const failures = s && s.failures && s.failures !== 'unknown' ? s.failures : null;
  return html`<section class="kpi panel interp" id="cur-hygiene" aria-label="Hygiene health"><h3>Hygiene health</h3>
    <div class="big num" id="cur-hygiene-passes">${(n => `${count(n)} ${n === 1 ? 'pass' : 'passes'}`)(spend ? spend.hygiene_sessions : passes.length)}</div>
    <div class="sub">${failures && failures.hygiene !== null ? `${known(failures, 'hygiene')} consecutive failures` : 'consecutive failures not recorded'} · ${failed} failed in all</div>
    <dl class="kv">${hygiene ? html`<dt>Enabled</dt><dd>${hygiene.enabled === true ? 'yes' : hygiene.enabled === false ? 'no' : 'unknown'}</dd><dt>Host wall watch</dt><dd>${isNumber(hygiene.host_wall_seconds) ? secs(hygiene.host_wall_seconds) : 'unknown'}</dd>
        <dt>Pass cap</dt><dd>${usd2(hygiene.pass_cap_usd)}</dd><dt>Failure limit</dt><dd>${known(hygiene, 'max_consecutive_failures')}</dd>` : html`<dt>Watch</dt><dd>not recorded</dd>`}
      <dt>Session failures</dt><dd>${failures ? known(failures, 'sessions') : 'unknown'}</dd><dt>Snapshot failures</dt><dd>${failures ? known(failures, 'snapshots') : 'unknown'}</dd></dl></section>`;
}

const windowText = r => (r.window && r.window !== 'unknown' ? `actor ${String(r.window.actor || '—').slice(0, 8)} · steps ${r.window.first ?? '—'}–${r.window.last ?? '—'}` : 'text only');
const verdictText = v => (v && v.total ? [v.published && `${v.published} published`, v.rejected && `${v.rejected} rejected`, v.unchanged && `${v.unchanged} unchanged`].filter(Boolean).join(' · ') : 'none');
const draftText = d => (d ? [d.created && `${d.created} new`, d.renewed && `${d.renewed} renewed`, d.refused && `${d.refused} refused`].filter(Boolean).join(' · ') || 'none' : '—');
const outcomeText = r => (r.host_end ? `${label(r.host_end.reason || 'ended')}${r.host_end.ok === false ? ' (failed)' : ''}` : r.session_state ? label(r.session_state) : '—');
const statusText = r => (r.model_status || []).length ? [...new Set(r.model_status)].join(' · ') : '—';

function SessionsTable({sessions, selected, open, omitted}) {
  if (!sessions.length) return html`<${Insufficient}>No curator session was recorded for this run.<//>`;
  return html`<div class="scroll"><table class="data" id="cur-sessions"><thead><tr><th>Session</th><th>Kind</th><th>Window</th><th class="num">Duration</th><th class="num">Cost</th><th>Tier</th><th>HTTP</th><th>Verdicts</th><th>Drafts</th><th>Outcome</th></tr></thead>
    <tbody>${sessions.map(r => html`<tr class=${selected === r.id ? 'sel' : ''} data-session=${r.id}>
      <td><button type="button" class="link" aria-pressed=${selected === r.id} onClick=${() => open(r.id)}>${r.label || r.id}</button></td>
      <td><span class=${`kindbadge ${r.session_kind || 'unknown'}`}>${KINDS[r.session_kind] || 'unknown'}</span></td><td>${windowText(r)}</td>
      <td class="num">${secs(r.wall_seconds)}</td><td class="num">${usd2(r.cost_usd)}${r.settled ? '' : html` <span class="state watch">open</span>`}</td>
      <td>${(r.applied_service_tiers || []).join(', ') || r.requested_service_tier || '—'}${r.deferrals ? html` <span class="tag defer">${plural(r.deferrals, 'deferral')}</span>` : null}</td>
      <td class="num">${statusText(r)}</td><td>${verdictText(r.verdicts_summary)}</td><td>${draftText(r.drafts_summary)}</td><td>${outcomeText(r)}</td></tr>`)}</tbody></table></div>
    ${omitted ? html`<p class="note">${count(omitted)} earlier sessions are not listed.</p>` : null}`;
}

/** One session's recorded figures and its bounded proxy ledger, fetched when it is opened. */
function SessionDrawer({run, id, close}) {
  const box = useRef(null);
  const {data, error} = useView(runPath(run, `curator/session/${encodeURIComponent(id)}`), 0);
  useEffect(() => { if (box.current) box.current.querySelector('.drawerclose').focus(); }, [id]);
  useEffect(() => {
    const onKey = event => { const sheet = document.getElementById('sheet'); if (event.key === 'Escape' && !event.defaultPrevented && !(sheet && !sheet.hidden)) { event.preventDefault(); close(); } };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [close]);
  const s = data && data.session;
  return html`<aside class="drawer curdrawer" id="cur-session-drawer" ref=${box} role="dialog" aria-modal="false" aria-label="Curator session">
    <header><h2>${s ? s.label || s.id : id}</h2><span class="note">${s ? KINDS[s.session_kind] || 'session' : ''}</span><span class="gap"></span>
      <button type="button" class="btn drawerclose" aria-label="Close the session" onClick=${close}>Close</button></header>
    <div class="drawerbody">${!s ? html`<${Waiting} store=${store} what="the session" error=${error} />` : html`
      <section><h3>Session <${Pv} source="recorded" detail="summary.json" /></h3><dl class="kv wide"><dt>Session ID</dt><dd class="mono wrapany">${s.session_id || '—'}</dd>
        <dt>Window</dt><dd>${windowText(s)}</dd><dt>Started</dt><dd>${wall(s.started_wall)}</dd><dt>Duration</dt><dd>${secs(s.wall_seconds)}</dd>
        <dt>Cost</dt><dd>${usd2(s.cost_usd)}${s.cap_usd ? ` of a ${usd2(s.cap_usd)} cap` : ''}</dd><dt>Settled</dt><dd>${s.settled ? 'yes' : `no · ${s.unsettled_requests} open`}</dd>
        <dt>Published</dt><dd>${s.published_before || '—'} → ${s.published_after || '—'}</dd><dt>HTTP</dt><dd>${statusText(s)}</dd><dt>Outcome</dt><dd>${outcomeText(s)}</dd></dl></section>
      <section id="cur-session-tokens"><h3>Tokens</h3><dl class="kv">${Object.entries(s.tokens || {}).map(([k, v]) => html`<dt>${label(k)}</dt><dd>${count(v)}</dd>`)}</dl></section>
      <section><h3>Tool calls</h3><dl class="kv"><dt>Calls</dt><dd>${count(s.tool_calls.count)}</dd><dt>Failed</dt><dd>${count(s.tool_calls.failed)}</dd><dt>Result bytes</dt><dd>${bytes(s.tool_calls.bytes)}</dd>
        ${Object.entries(s.tool_calls.by_name || {}).map(([n, c]) => html`<dt class="mono">${n}</dt><dd>${count(c)}</dd>`)}</dl></section>
      <section><h3>Sandbox</h3><dl class="kv"><dt>Stopped</dt><dd>${label(s.sandbox.stopped || 'unrecorded')}</dd><dt>Seconds</dt><dd>${secs(s.sandbox.seconds)}</dd>
        <dt>Peak memory</dt><dd>${bytes(s.sandbox.peak_memory_bytes)}</dd><dt>Return code</dt><dd>${s.sandbox.returncode ?? '—'}</dd><dt>Survivors</dt><dd>${s.sandbox.survivors ? s.sandbox.survivors.length : '—'}</dd></dl></section>
      <section><h3>Verdicts</h3>${s.verdicts.length ? html`<ul class="plain">${s.verdicts.map(v => html`<li><b>${label(v.status || 'unknown')}</b> ${v.operation || ''} ${v.version ? `→ ${v.version}` : ''}${v.diagnostics.length ? html` <span class="note">${v.diagnostics.join('; ')}</span>` : null}</li>`)}</ul>` : html`<p class="note">No verdicts.</p>`}</section>
      <section><h3>Drafts</h3><p class="note">${['created', 'renewed', 'refused'].map(k => `${(s.drafts[k] || []).length} ${k}`).join(' · ')}</p></section>
      <section><h3>Proxy</h3><p class="note wrapany">${plainValue(s.proxy)}</p></section>
      <section id="cur-ledger"><h3>Proxy ledger <${Pv} source="recorded" detail="proxy-ledger.jsonl" /></h3>
        <${Table} columns=${[{title: 'Model', render: r => r.model || '—'}, {title: 'HTTP', num: true, render: r => r.status ?? '—'}, {title: 'Charged', num: true, render: r => usd2(r.charged)},
          {title: 'Tier', render: r => r.applied_service_tier || r.service_tier || '—'}, {title: 'ms', num: true, render: r => (isNumber(r.latency_ms) ? Math.round(r.latency_ms) : '—')}]} rows=${data.ledger} empty="No ledger rows recorded." />
        <p class="note">${count(data.ledger_total)} rows${data.ledger_omitted ? `, ${count(data.ledger_omitted)} not shown` : ''}.</p></section>`}</div></aside>`;
}

function GateRows({gates, drafts}) {
  return html`<${Panel} title="Gate verdicts" note=${`Filtered to this run's sessions (${count(gates.total)} of ${count(gates.total_lineage)} lineage total)`} span="s7" className="run-filtered">
      ${gates.items.length ? html`<${Table} columns=${[{title: 'Operation', key: 'operation'}, {title: 'Status', key: 'status'}, {title: 'Version', render: r => r.version || '—'}, {title: 'Session', render: r => r.session || '—'}]} rows=${gates.items} />`
        : html`<${Insufficient}>${gates.source_status === 'not_configured' ? 'No gate result source is configured.' : 'No gate verdict names a session of this run.'}<//>`}
      <p class="note">The full lineage's operator sources are in <a href="#runs/archive">All runs → Archive</a>.</p><//>
    <${Panel} title="Drafts" note=${`Filtered to this run's sessions (${count(drafts.total)} of ${count(drafts.total_lineage)} lineage total)`} span="s5" className="run-filtered">
      ${drafts.items.length ? html`<${Table} columns=${[{title: 'Draft', key: 'id', wrap: true}, {title: 'State', key: 'state'}, {title: 'Bucket', key: 'bucket'}]} rows=${drafts.items} />`
        : html`<${Insufficient}>${drafts.source_status === 'not_configured' ? 'No draft source is configured.' : 'No draft names a session of this run.'}<//>`}<//>`;
}

export function CuratorTab({csess}) {
  const run = store.runId, s = store.summary;
  const live = !!(s && s.live);
  const {data, error} = useView(run ? runPath(run, 'curator') : null, live ? 5000 : 0);
  const open = id => { location.hash = `#curator?csess=${encodeURIComponent(id)}`; };
  const close = () => { location.hash = '#curator'; };
  if (!run || !data) return html`<section class="grid" data-view="curator" aria-label="Curator"><${Panel} title="Curator" span="s12"><${Waiting} store=${store} what="the curator" error=${error} /><//></section>`;
  const runner = data.runner, status = runner.status;
  const empty = !data.sessions.length && !status;
  const snapshot = status && status.snapshot && status.snapshot !== 'unknown' ? status.snapshot : null;
  const unexamined = status && status.unexamined && Array.isArray(status.unexamined.items) ? status.unexamined.items : null;
  const g = data.grooming;
  return html`<section class="grid" data-view="curator" aria-label="Curator">
    ${empty ? html`<${Panel} title="Curator" span="s12"><div class="insuf" id="curator-empty" role="status">No curator data for this run.</div><span hidden data-runner-status>${runner.source_status}</span><//>` : html`
    <div class="kpis three s12"><${RunnerCard} runner=${runner} /><${SpendCard} spend=${data.spend} runner=${runner} /><${HygieneCard} spend=${data.spend} sessions=${data.sessions} runner=${runner} /></div>
    <${Panel} title="Sessions" note=${`${plural(data.sessions.length, 'session')} · window, hygiene and grooming · open one for its ledger`} span="s12" className="sessions">
      <div class="sessionswrap"><${SessionsTable} sessions=${data.sessions} selected=${csess} open=${open} omitted=${data.sessions_omitted} />
        ${csess ? html`<${SessionDrawer} run=${run} id=${csess} close=${close} key=${csess} />` : null}</div><//>`}
    <${Disclosure} id="cur-wal" title="Snapshot timings and unexamined ranges" note="how long each WAL snapshot held the store">${() => html`<${Panel} span="s12">
      ${snapshot ? html`<dl class="kv"><dt>Hold</dt><dd>${ms(snapshot.hold_seconds)}</dd><dt>Transaction</dt><dd>${ms(snapshot.transaction_seconds)}</dd><dt>Staging</dt><dd>${ms(snapshot.staging_seconds)}</dd>
        <dt>Read</dt><dd>${snapshot.read_wall && snapshot.read_wall !== 'unknown' ? wall(snapshot.read_wall.ended) : 'unknown'}</dd></dl>` : html`<p class="note">No snapshot timings recorded.</p>`}
      <h3>Left unexamined</h3>${unexamined === null ? html`<p class="note">Written only once the runner stops or ends.</p>` : unexamined.length ? html`<ul class="plain">${unexamined.map(r => html`<li>actor ${known(r, 'actor')} · steps ${known(r, 'first')}–${known(r, 'last')}</li>`)}</ul>` : html`<p class="note">None.</p>`}
      <details class="runnerbox"><summary>Every runner status figure</summary><${RunnerDetail} data=${runner} /></details><//>`}<//>
    <${Disclosure} id="cur-grooming" title="Boundary grooming receipt" note="after the admission ends, outside its package">${() => html`<${Panel} span="s12">
      ${g.source_status === 'available' ? html`<dl class="kv"><dt>Status</dt><dd>${g.status}${g.reason ? ` · ${label(g.reason)}` : ''}</dd><dt>Published</dt><dd>${g.published_before || '—'} → ${g.published_after || '—'}</dd>
        <dt>Spent</dt><dd>${usd2(g.spent_usd)}${g.spend_complete ? '' : ' · unsettled'}</dd><dt>Stale records</dt><dd>${g.stale_records === null ? 'not recorded' : count(g.stale_records)}</dd></dl>`
        : html`<p class="note" id="cur-grooming-none">${g.source_status === 'not_configured' || g.source_status === 'other_run' ? 'No receipt for this run is attached: grooming is recorded outside the admission.' : `Receipt ${label(g.source_status)}.`}</p>`}<//>`}<//>
    <${Disclosure} id="cur-gates" title="Gate verdicts and drafts" note=${`filtered to this run's sessions · ${count(data.gate_verdicts.total)} verdicts · ${count(data.drafts.total)} drafts`}>${() => html`<${GateRows} gates=${data.gate_verdicts} drafts=${data.drafts} />`}<//></section>`;
}
