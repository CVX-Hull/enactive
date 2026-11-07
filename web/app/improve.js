// Improve: did a change work, what fails most, and how do components differ by arm.
import {html, useState, useMemo, Panel, Pv, Waiting, Table, Insufficient, Callout, Verdict, fmtMoney, pct, trim, median, quantile, label} from './ui.js';
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

const metricName = m => (m ? `${m.name}${m.key ? ` · ${m.key}` : ''}` : '—');
const groupText = g => (g && g.n ? `${trim(+g.mean.toFixed(3))} mean, ${trim(+g.median.toFixed(3))} median (n ${g.n})` : 'no values');

function Changes() {
  const {data, error} = useView('improve/changes');
  const [sel, setSel] = useState(null);
  const changes = data ? data.changes || [] : [];
  const c = changes.find(x => x.id === sel) || changes[0];
  const option = useMemo(() => {
    if (!c || !c.target || !(c.target.arm.n || c.target.baseline.n)) return null;
    const pick = g => g.runs.filter(r => r.value !== null).map(r => ({run: r.run, target: r.value}));
    return dotsOption([{arm: 'Changed arms', runs: pick(c.target.arm)}, {arm: 'Baseline', runs: pick(c.target.baseline)}], null, c.target.metric.name);
  }, [c, store.themeEpoch]);
  if (!data) return html`<${Panel} title="Changes" span="s12"><${Waiting} store=${store} what="change records" error=${error} /><//>`;
  if (!c) return html`<${Panel} title="Changes" span="s12"><${Insufficient}>No change records.<//><//>`;
  const diff = c.target.difference, up = c.uptake;
  return html`<${Panel} title="Changes" note="each names a failure, a target metric, uptake and guards · records live in a git-tracked file" span="s12">
      <div class="cards">${changes.map(x => html`<button type="button" class="card" data-change=${x.id} aria-pressed=${x.id === c.id} onClick=${() => setSel(x.id)}>
        <div class="top"><b>${x.name}</b><${Verdict} verdict=${x.computed_verdict} /></div><span class="note">Targets: ${label(x.target_failure)}</span></button>`)}</div><//>
    <${Panel} title=${c.name} note=${c.hypothesis} span="s7">
      <div class="chips"><span>Computed <${Verdict} verdict=${c.computed_verdict} /> <${Pv} source="derived" /></span><span>Recorded <${Verdict} verdict=${c.verdict} /> <${Pv} source="human" /></span></div>
      <dl class="kv wide"><dt>Failure targeted</dt><dd>${label(c.target_failure)}</dd>
        <dt>Target metric</dt><dd>${metricName(c.target.metric)} (${c.target.metric.direction} is better; minimum effect ${c.target.metric.min_effect ?? 'unset'})</dd>
        <dt>Changed arms</dt><dd>${groupText(c.target.arm)}</dd><dt>Baseline</dt><dd>${groupText(c.target.baseline)}</dd>
        <dt>Uptake</dt><dd>${up ? `${up.with_uptake} of ${up.n} runs used it (${trim(up.total)} in all) · ${metricName(up.metric)}` : 'no uptake metric recorded'}</dd>
        <dt>Excluded (lost)</dt><dd>${c.target.excluded.join(', ') || 'none'}</dd>
        <dt>Commits</dt><dd>${(c.commits || []).join(', ') || 'not recorded'}</dd></dl>
      ${option ? html`<${Chart} option=${option} epoch=${store.themeEpoch} label=${`${c.target.metric.name} per run, changed arms against baseline`} className="dots" />` : html`<${Insufficient}>No per-run values to plot.<//>`}
      ${diff && diff.difference !== null ? html`<p class="note">Difference ${trim(+diff.difference.toFixed(3))} (95% bootstrap interval ${trim(+diff.low.toFixed(3))} to ${trim(+diff.high.toFixed(3))}; n = ${c.target.arm.n} and ${c.target.baseline.n}; ${diff.resamples} resamples). <${Pv} source="derived" /></p>` : html`<p class="note">No difference can be computed: a group has no values.</p>`}
      ${(c.guard_values || []).length ? html`<h3>Guards</h3><${Table} columns=${[{title: 'Guard', render: g => metricName(g.metric)}, {title: 'Changed arms', render: g => groupText(g.arm)}, {title: 'Baseline', render: g => groupText(g.baseline)}]} rows=${c.guard_values} />` : null}
      <${Callout}>${c.notes}<//><//>
    <${Panel} title="How a verdict is reached" span="s5"><ul class="note plain"><li><b>Untested</b> when uptake is zero or not measurable.</li>
      <li><b>Moved</b> or <b>moved the wrong way</b> when the target metric's interval excludes zero.</li><li><b>No effect detected</b> otherwise, stated with n.</li>
      <li>The computed verdict is the viewer's; the recorded verdict is the owner's, from the git-tracked change file. They can differ.</li>
      <li>Guards report any harm to survival, cost or setup. A pre-registered rule, where one exists, decides adoption.</li></ul><//>`;
}

function Failures() {
  const {data, error} = useView('improve/failures');
  const [sel, setSel] = useState(null);
  if (!data) return html`<${Panel} title="Failure modes" span="s12"><${Waiting} store=${store} what="failure modes" error=${error} /><//>`;
  const modes = data.failures || [];
  const m = modes.find(x => x.code === sel) || modes[0];
  const open = item => { selectRun(item.run); location.hash = '#run/overview'; };
  return html`<${Panel} title="Failure modes ranked by impact" note=${`deaths first, then money spent inside the failure · taxonomy version ${data.taxonomy_version ?? '?'}`} span="s12">
      <${Table} columns=${[{title: 'Failure mode', render: x => x.name}, {title: 'Occurrences', num: true, key: 'occurrences'}, {title: 'Runs', num: true, key: 'runs'},
        {title: 'Decisions inside', num: true, render: x => x.decisions || '—'}, {title: '$ inside', num: true, render: x => (x.dollars ? fmtMoney(x.dollars) : '—')},
        {title: 'Source', render: x => (x.sources.length ? x.sources.map(s => html`<${Pv} source=${s} /> `) : html`<span class="note">none yet</span>`)}]}
        rows=${modes} onPick=${(i, x) => setSel(x.code)} selected=${m ? modes.indexOf(m) : -1} empty="No failure modes recorded." /><//>
    ${m ? html`<${Panel} title=${`${m.name}: every occurrence`} note="open a row in Diagnose to see its run" span="s12">
      <p class="note">${m.definition}</p>
      <${Table} columns=${[{title: 'Run', key: 'run'}, {title: 'Decisions', num: true, render: x => (x.decision_from === null ? '—' : `${x.decision_from}–${x.decision_to}`)}, {title: 'Length', num: true, render: x => x.decisions || '—'},
        {title: '$', num: true, render: x => (x.dollars ? x.dollars.toFixed(2) : '—')}, {title: 'Source', render: x => html`<${Pv} source=${x.source} />`}, {title: 'Note', wrap: true, render: x => x.note || x.reason || ''}]}
        rows=${m.items || []} onPick=${(i, x) => open(x)} empty="No occurrences recorded." /><//>` : null}`;
}

const COMPONENT_METRICS = [['Routine pace (game s / decision)', 'pace.routine_seconds_per_decision'], ['Out-of-play share', 'mode.out_of_play_share', 'pct'],
  ['Longest stall', 'stall.longest'], ['Stalls', 'stall.count'], ['$ per decision', 'host.dollars_per_decision', 'money'],
  ['Large-rewrite share of spend', 'host.large_rewrite_share', 'pct'], ['Survival (game h)', 'survival.game_hours']];
function Components() {
  const runs = store.runs;
  if (!runs) return html`<${Panel} title="Components by arm" span="s12"><${Waiting} store=${store} what="runs" /><//>`;
  const scored = runs.filter(r => !r.outcome.lost);
  const arms = [...new Set(scored.map(r => r.labels.arm || 'unlabelled'))];
  const inArm = a => scored.filter(r => (r.labels.arm || 'unlabelled') === a);
  const fmt = (v, kind) => (v === null || v === undefined ? '—' : kind === 'pct' ? pct(v) : kind === 'money' ? `$${v.toFixed(4)}` : trim(Math.round(v * 100) / 100));
  const lost = runs.filter(r => r.outcome.lost).map(r => r.run);
  return html`<${Panel} title="Components by arm" note="median [interquartile range] · n = scored runs · lost runs excluded and listed · no thresholds until each has a stated source" span="s12">
    <div class="scroll"><table class="data"><thead><tr><th>Metric</th>${arms.map(a => html`<th class="num">${a}<br /><span class="note">n = ${inArm(a).length}</span></th>`)}</tr></thead>
      <tbody>${COMPONENT_METRICS.map(([name, key, kind]) => html`<tr><td>${name}</td>${arms.map(a => { const v = inArm(a).map(r => r.headline[key]);
        return html`<td class="num">${fmt(median(v), kind)} <span class="note">[${fmt(quantile(v, 0.25), kind)}–${fmt(quantile(v, 0.75), kind)}]</span></td>`; })}</tr>`)}</tbody></table></div>
    <p class="note"><${Pv} source="derived" detail="computed in this page from the viewer's per-run headline metrics" /> Arms ran one after another, so differences mix the arm with run order, code fixes and provider drift. Read this table as exploratory unless a change page pre-registered the metric. Excluded: ${lost.join(', ') || 'none'}.</p><//>`;
}
