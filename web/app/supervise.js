// What the viewer reads off the game and says about pausing: Pause conditions, game readings and finding text.
// Shared by Watch and Diagnostics. The only place on the page that names the game's own vitals.
import {html, Panel, Pv, ReadChip, fmtMoney, gameClock, label, pct, trim} from './ui.js';

const CONDITION_TEXT = {
  feed_alive: v => (v === null ? 'no operation recorded yet' : `${trim(v)} s since the last operation`),
  custody_healthy: v => `${v.uncertain_receipts} uncertain receipts · ${v.custody_stops} custody stops`,
  not_looping: v => `out-of-play streak ${v.decisions_out_of_play}, game time ${v.game_time_advancing ? 'advancing' : 'not advancing'}`,
  spend_inside_allowance: v => `${fmtMoney(v.spent)} estimated from configured rates, on pace for ${fmtMoney(v.projected_one_hour)} in an hour${v.ceiling === null ? ', no limit declared' : ` (declared limit ${fmtMoney(v.ceiling)}, enforced on provider-reported cost, not this estimate)`}`,
  not_dead_and_spending: v => (v.died ? `death read, ${v.requests_after_death} requests since` : 'no death read'),
};
export const conditionText = c => (CONDITION_TEXT[c.id] ? CONDITION_TEXT[c.id](c.value) : String(c.value));
export const pauseMet = summary => !!(summary && summary.pause && summary.pause.met.length);

/** Shown only for the run the viewer evaluates live; nothing else can be paused. */
export function PauseConditions({summary}) {
  const pause = summary.pause;
  if (!pause) return null;
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

const VITALS = ['thirst', 'hunger', 'weariness', 'pain'];
const vitalText = v => (v.critical ? 'critical' : v.label || `level ${pct(v.level)}`);

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
  for (const key of VITALS) add(label(key).replace(/^./, c => c.toUpperCase()), `vital.${key}`, vitalText);
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

/** The vitals that were read and have something to say, for the line under the game screen. */
export function vitalBadges(state) {
  const readings = (state && state.readings) || {};
  const badges = [];
  for (const key of VITALS) {
    const r = readings[`vital.${key}`];
    if (r && !r.abstain && r.value && (r.value.critical || r.value.label)) badges.push({name: label(key), text: vitalText(r.value), critical: !!r.value.critical, reading: r});
  }
  const critical = Object.entries(readings).filter(([k, r]) => k.startsWith('vital.limb.') && !r.abstain && r.value && r.value.critical);
  if (critical.length) badges.push({name: 'limbs', text: `${critical.length} critical`, critical: true, reading: critical[0][1]});
  return badges;
}

export function GameState({summary, span = 's5'}) {
  const state = summary.game_state;
  const v = summary.versions || {};
  const rows = state ? readingRows(state) : [];
  return html`<${Panel} title="Game state" note=${`information only · binding ${v.binding_id || '?'} ${v.binding_version ?? ''}${state ? ` · as of step ${state.seq}` : ''}`} span=${span}>
    ${rows.length ? html`<div class="state-grid" id="gamestate">${rows.map(r => html`<div><span>${r.name}</span>${
      r.abstain ? html`<span class="note">abstained: ${r.abstain}</span>` : html`<span>${r.text} <${ReadChip} reading=${r.reading} /></span>`}</div>`)}</div>`
      : html`<div class="insuf" id="gamestate">No frame has been read yet.</div>`}<//>`;
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
