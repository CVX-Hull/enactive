// What the story feed says about the player's continuity: actors and handoffs, context cuts and coverage waits, memory
// deliveries, the player's own agenda and its reads. Pure functions over the feed, the summary and the handoffs; shared by
// Watch, the Step Inspector, Memory and Diagnostics so that each names a thing the same way.
import {label, actorNumber} from './ui.js';

export const TOOL_LABELS = {computer_input: 'input', computer_observe: 'observe', computer_result: 'collect result',
  player_knowledge_query: 'knowledge query', player_knowledge_read: 'knowledge read', player_source: 'source re-read',
  player_agenda: 'agenda', player_hint: 'hint', player_handoff: 'handoff', player_finish: 'finish',
  // archived runs only
  player_memory_append: 'memory write', player_memory_query: 'memory query', player_memory_read: 'memory read',
  player_memory_context: 'memory bundle', player_program_save: 'program save', player_program_run: 'program run'};
export const toolLabel = tool => TOOL_LABELS[tool] || label(tool || 'recorded step');
export const isKnowledgeTool = tool => tool === 'player_knowledge_query' || tool === 'player_knowledge_read';
export const isReadTool = tool => isKnowledgeTool(tool) || tool === 'player_source';

/** The buckets a delivery states its changes in, in the host's order; an older trace states only the first three. */
export const DELTA_BUCKETS = ['corrections', 'state_changes', 'flag_changes', 'added_facts', 'claim_updates', 'article_changes'];
export const LEGACY_BUCKETS = ['added', 'updated', 'removed'];
export const DELIVERY_KINDS = {opening_briefing: ['Opening briefing', 'brief'], post_cut_briefing: ['Post-cut briefing', 'brief'],
  update: ['Live delta', 'delta'], empty_suppressed: ['Adopted (empty-suppressed)', 'quiet'], refused: ['Refused', 'bad'],
  undelivered: ['Undelivered', 'bad']};
export const deliveryWord = kind => (DELIVERY_KINDS[kind] || [label(kind || 'delivery')])[0];
export const deliveryTone = kind => (DELIVERY_KINDS[kind] || [null, 'quiet'])[1];
/** A version's place in the chain, as the viewer states it from the files, the publications and the trace. */
export const CHAIN_STATUS = {delivered: 'Delivered', empty_suppressed: 'Adopted (empty-suppressed)', refused: 'Refused',
  exported_not_delivered: 'Exported (not delivered)', superseded: 'Superseded', published_only: 'Published only'};

/** A cut that left turns no briefing covered (#1037), or a rescue cut, is a cut the curator did not keep up with. */
export const uncoveredCut = e => (e.uncovered_turns || 0) > 0;
export const rescueCut = e => e.cut_result === 'rescue';
export const cutTone = e => (uncoveredCut(e) || rescueCut(e) ? 'uncovered' : 'covered');

/** What counts as an alert, on the timeline and in the story alike: a finding other than a handoff, a call that failed or
 *  was refused, and a delivery that was refused or never reached the player. */
export const isAlertEntry = e => (e.entry_kind === 'finding' && e.finding_kind !== 'handoff')
  || (e.entry_kind === 'step' && (e.status === 'error' || e.status === 'refused'))
  || (e.entry_kind === 'knowledge_delivery' && (e.delivery_kind === 'refused' || e.delivery_kind === 'undelivered'));

/** Actors in the order they first act: actor ID -> `001`, `002`. */
export function actorNumbers(feed, handoffs = []) {
  const out = new Map();
  for (const h of handoffs) if (h.actor && !out.has(h.actor)) out.set(h.actor, actorNumber(out.size));
  for (const e of feed) if (e.entry_kind === 'step' && e.actor && !out.has(e.actor)) out.set(e.actor, actorNumber(out.size));
  return out;
}

const before = (e, seq) => e.seq === null || e.seq === undefined || seq === null || e.seq <= seq;

/** The committed agenda as of a step: the run's starting agenda, then each `player_agenda` change up to the step. At a
 *  handoff with no change since, the next actor holds what was carried to it. Never a guess: absent is null. */
export function agendaAt(seq, feed, summary, handoffs = []) {
  let state = summary && summary.agenda ? summary.agenda.initial : null;
  let change = null;
  for (const e of feed) {
    if (e.entry_kind === 'agenda_change' && before(e, seq)) { state = e.agenda; change = e; }
  }
  const handoff = [...handoffs].filter(h => h.seq !== null && h.seq !== undefined && (seq === null || h.seq <= seq)).pop() || null;
  const carried = handoff && (!change || change.seq === null || change.seq < handoff.seq) ? handoff : null;
  if (carried && carried.carried_agenda) state = carried.carried_agenda;
  return {state, change, carried};
}

/** Each agenda change with what it changed against the state before it: threads added, closed or retitled. */
export function agendaDiffs(feed, summary) {
  const out = new Map();
  let prior = summary && summary.agenda && summary.agenda.initial ? summary.agenda.initial.threads : [];
  for (const e of feed) {
    if (e.entry_kind !== 'agenda_change') continue;
    const now = (e.agenda && e.agenda.threads) || [];
    const was = new Map(prior.map(t => [t.id, t]));
    const changed = now.filter(t => !was.has(t.id) || was.get(t.id).status !== t.status || was.get(t.id).title !== t.title)
      .map(t => ({id: t.id, title: t.title, status: t.status, change: was.has(t.id) ? (was.get(t.id).status !== t.status ? `${was.get(t.id).status} → ${t.status}` : 'retitled') : 'new'}));
    const gone = prior.filter(t => !now.some(n => n.id === t.id)).map(t => ({id: t.id, title: t.title, status: t.status, change: 'cleared'}));
    out.set(e.id, [...changed, ...gone]);
    prior = now;
  }
  return out;
}

/** The newest delivered knowledge version at a step, or null. */
export function versionAt(seq, feed) {
  let version = null;
  for (const e of feed) {
    if (e.entry_kind === 'knowledge_delivery' && e.outcome === 'delivered' && e.knowledge_version && before(e, seq)) version = e.knowledge_version;
  }
  return version;
}
export const cutsUpTo = (seq, feed) => feed.filter(e => e.entry_kind === 'context_cut' && before(e, seq)).length;

/** The non-zero buckets of a delivery's recorded counts, in the host's order. */
export function deltaChips(counts) {
  if (!counts) return [];
  const order = [...DELTA_BUCKETS, ...LEGACY_BUCKETS];
  return Object.entries(counts).filter(([, n]) => n).sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0])).map(([bucket, n]) => ({bucket, n, text: `${n} ${label(bucket)}`}));
}

/** A `player_source` read as the operator sees it: the real frame, and the alias the player saw it under. */
export function sourceReadText(read) {
  if (!read) return null;
  return read.player_alias ? `player saw as ${read.player_alias}` : read.origin === 'current' ? 'player saw this admission' : 'player alias unrecorded';
}
