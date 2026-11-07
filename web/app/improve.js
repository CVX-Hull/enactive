// Improve: did a change work, what fails most, and how do components differ by arm.
import {html, useState, useMemo, Panel, Pv, Waiting, Table, Insufficient, Callout, Verdict, fmtMoney, pct, trim, median, quantile} from './ui.js';
import {store, useView, selectRun} from './data.js';
import {Chart, dotsOption} from './charts.js';
import {SubNav} from './diagnose.js';

export const IMPROVE_TABS = [['changes', 'Changes'], ['failures', 'Failure modes'], ['components', 'Components by arm']];

export function Improve({section}) {
  const current = IMPROVE_TABS.some(t => t[0] === section) ? section : 'changes';
  const body = current === 'changes' ? html`<${Changes} />` : current === 'failures' ? html`<${Failures} />` : html`<${Components} />`;
  return html`<section class="grid" data-view="improve" aria-label="Improve">
    <div class="s12"><${SubNav} tabs=${IMPROVE_TABS} base="improve" current=${current} label="Improve sections" /></div>${body}</section>`;
}

function Changes() {
  const {data, error} = useView('improve/changes');
  const [sel, setSel] = useState(null);
  const changes = data ? data.changes || [] : [];
  const c = changes.find(x => x.id === sel) || changes[0];
  const option = useMemo(() => (c && c.arms_values && c.arms_values.length ? dotsOption(c.arms_values, c.target_metric?.min_effect, c.target_metric?.name || 'target') : null), [c, store.themeEpoch]);
  if (!data) return html`<${Panel} title="Changes" span="s12"><${Waiting} store=${store} what="change records" error=${error} /><//>`;
  if (!c) return html`<${Panel} title="Changes" span="s12"><${Insufficient}>No change records.<//><//>`;
  const iv = c.interval;
  return html`<${Panel} title="Changes" note="each names a failure, a target metric, uptake and guards · records live in a git-tracked file" span="s12">
      <div class="cards">${changes.map(x => html`<button type="button" class="card" data-change=${x.id} aria-pressed=${x.id === c.id} onClick=${() => setSel(x.id)}>
        <div class="top"><b>${x.name}</b><${Verdict} verdict=${x.verdict} /></div><span class="note">Targets: ${x.target_failure}</span></button>`)}</div><//>
    <${Panel} title=${c.name} note=${c.hypothesis} span="s7"><div><${Verdict} verdict=${c.verdict} /> <${Pv} source=${c.source || 'human'} /></div>
      <dl class="kv wide"><dt>Failure targeted</dt><dd>${c.target_failure}</dd>
        <dt>Target metric</dt><dd>${c.target_metric?.name} (${c.target_metric?.direction} is better${c.target_metric?.min_effect !== null && c.target_metric?.min_effect !== undefined ? `; minimum effect ${c.target_metric.min_effect}` : ''})</dd>
        <dt>Uptake</dt><dd>${c.uptake?.text || c.uptake_metric}</dd><dt>Guards</dt><dd>${(c.guards || []).join(', ')}${c.guard_note ? ` · ${c.guard_note}` : ''}</dd>
        <dt>Arms · commits</dt><dd>${(c.arms || []).join(', ')} · ${(c.commits || []).join(', ')}</dd></dl>
      ${option ? html`<${Chart} option=${option} epoch=${store.themeEpoch} label=${`${c.target_metric?.name} per run, by arm`} className="dots" />` : html`<${Insufficient}>No per-run values: ${c.verdict === 'untested' ? 'untested, so there is nothing to plot' : 'none recorded'}.<//>`}
      ${iv ? html`<p class="note">Difference ${trim(iv.estimate)} (${pct(iv.level)} ${iv.method || 'bootstrap'} interval ${trim(iv.lo)} to ${trim(iv.hi)}; n = ${iv.n_a} and ${iv.n_b}). <${Pv} source=${c.source || 'derived'} /></p>` : null}
      <${Callout}>${c.notes}<//><//>
    <${Panel} title="How a verdict is reached" span="s5"><ul class="note plain"><li><b>Untested</b> when uptake is zero or not measurable.</li>
      <li><b>Moved</b> or <b>moved the wrong way</b> when the target metric's interval excludes zero.</li><li><b>No effect detected</b> otherwise, stated with n.</li>
      <li>Guards report any harm to survival, cost or setup.</li><li>A pre-registered rule, where one exists, decides adoption; this page explains why.</li></ul><//>`;
}

function Failures() {
  const {data, error} = useView('improve/failures');
  const [sel, setSel] = useState(null);
  if (!data) return html`<${Panel} title="Failure modes" span="s12"><${Waiting} store=${store} what="failure modes" error=${error} /><//>`;
  const modes = [...(data.modes || [])].sort((a, b) => (b.code === 'death') - (a.code === 'death') || (b.dollars || 0) - (a.dollars || 0));
  const m = modes.find(x => x.code === sel) || modes[0];
  const open = item => { selectRun(item.run); location.hash = '#run/overview'; };
  return html`<${Panel} title="Failure modes ranked by impact" note=${`deaths first, then money spent inside the failure · taxonomy version ${data.taxonomy_version ?? '?'}`} span="s12">
      <${Table} columns=${[{title: 'Failure mode', render: x => x.name}, {title: 'Occurrences', num: true, key: 'occurrences'}, {title: 'Runs', num: true, key: 'runs'},
        {title: 'Decisions inside', num: true, render: x => x.decisions || '—'}, {title: '$ inside', num: true, render: x => (x.dollars ? fmtMoney(x.dollars) : '—')}, {title: 'Source', render: x => html`<${Pv} source=${x.source} />`}]}
        rows=${modes} onPick=${(i, x) => setSel(x.code)} selected=${m ? modes.indexOf(m) : -1} empty="No failure modes recorded." /><//>
    ${m ? html`<${Panel} title=${`${m.name}: every occurrence`} note="open a row in Diagnose to see its frames" span="s12">
      <${Table} columns=${[{title: 'Run', render: x => x.label || x.run}, {title: 'Steps', num: true, render: x => `${x.seq_start}–${x.seq_end}`}, {title: 'Decisions', num: true, render: x => x.decisions || '—'}, {title: '$', num: true, render: x => (x.dollars ? x.dollars.toFixed(2) : '—')}]}
        rows=${m.items || []} onPick=${(i, x) => open(x)} empty="No occurrences listed." /><//>` : null}`;
}

const COMPONENT_METRICS = [['Routine pace (game s / decision)', 'pace'], ['Out-of-play share', 'oop', 'pct'], ['Longest stall', 'stall_longest'], ['Setup decisions', 'setup'],
  ['Memory writes', 'mem_w'], ['Memory reads', 'mem_r'], ['Handoffs', 'handoffs'], ['Tool refusals', 'refused'], ['$ per decision', 'per_dec', 'money'], ['Large-rewrite share of spend', 'rewrite', 'pct']];
function Components() {
  const runs = store.runs;
  if (!runs) return html`<${Panel} title="Components by arm" span="s12"><${Waiting} store=${store} what="runs" /><//>`;
  const scored = runs.filter(r => r.censor_reason !== 'infrastructure');
  const arms = [...new Set(scored.map(r => r.arm))];
  const fmt = (v, kind) => (v === null || v === undefined ? '—' : kind === 'pct' ? pct(v) : kind === 'money' ? `$${v.toFixed(4)}` : trim(Math.round(v * 10) / 10));
  const lost = runs.filter(r => r.censor_reason === 'infrastructure').map(r => r.label || r.run);
  return html`<${Panel} title="Components by arm" note="median [interquartile range] · n = scored runs · lost runs excluded and listed · no thresholds until each has a stated source" span="s12">
    <div class="scroll"><table class="data"><thead><tr><th>Metric</th>${arms.map(a => html`<th class="num">${a}<br /><span class="note">n = ${scored.filter(r => r.arm === a).length}</span></th>`)}</tr></thead>
      <tbody>${COMPONENT_METRICS.map(([name, key, kind]) => html`<tr><td>${name}</td>${arms.map(a => { const v = scored.filter(r => r.arm === a).map(r => r.metrics?.[key]);
        return html`<td class="num">${fmt(median(v), kind)} <span class="note">[${fmt(quantile(v, 0.25), kind)}–${fmt(quantile(v, 0.75), kind)}]</span></td>`; })}</tr>`)}</tbody></table></div>
    <p class="note"><${Pv} source="derived" detail="computed in this page from per-run headline metrics" /> Arms ran one after another, so differences mix the arm with run order, code fixes and provider drift. Read this table as exploratory unless a change page pre-registered the metric. Excluded: ${lost.join(', ') || 'none'}.</p><//>`;
}
