// Player-authored working state. The host only validates, stamps, and carries it.
export const AGENDA_SCHEMA = 'player-agenda-continuation/1';
export const AGENDA_MAX_BYTES = 3072;
export const AGENDA_MAX_ACTIVE = 8;
export const AGENDA_MAX_THREADS = 16;
export const AGENDA_MAX_SUB_ITEMS = 6;
export const AGENDA_MAX_REFS = 8;
export const AGENDA_TOMBSTONE_CUTS = 2;

const idPattern = '^[a-z0-9][a-z0-9-]{0,31}(?![\\s\\S])';
const idMatches = new RegExp(idPattern);
const statuses = ['active', 'paused', 'done', 'dropped'];
const string = maxLength => ({type:'string', minLength:1, maxLength});
const subItem = {type:'object', additionalProperties:false, required:['text', 'done'],
  properties:{text:string(100), done:{type:'boolean'}}};
const fields = {
  id:{type:'string', pattern:idPattern}, title:string(120), status:{type:'string', enum:statuses},
  notes:string(240), stop_when:string(160), drop_reason:string(160),
  sub_items:{type:'array', maxItems:AGENDA_MAX_SUB_ITEMS, items:subItem},
  refs:{type:'array', maxItems:AGENDA_MAX_REFS, uniqueItems:true, items:string(128)},
};
const operationFields = {
  read:[], upsert:Object.keys(fields), set_status:['id', 'status', 'drop_reason', 'notes', 'sub_items'], clear_completed:[],
};

export const agendaToolParameters = {
  type:'object', additionalProperties:false, required:['intent', 'op'],
  properties:{intent:string(512), op:{type:'string', enum:Object.keys(operationFields)}, ...fields},
};

const closed = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).every(key => keys.includes(key));
const natural = value => Number.isSafeInteger(value) && value >= 0;
const nonblank = (value, max) => typeof value === 'string' && value.isWellFormed()
  && [...value].length <= max
  && [...value].some(character => character === '\ufeff' || !/[\s\x1c-\x1f\x85]/u.test(character));
const working = thread => thread.status === 'active' || thread.status === 'paused';
const invalid = detail => { throw new Error(`invalid-agenda: ${detail}`); };

export function emptyAgenda() {
  return {schema:AGENDA_SCHEMA, cut_count:0, threads:[]};
}

export function validateAgenda(value) {
  if (!closed(value, ['schema', 'cut_count', 'threads']) || value.schema !== AGENDA_SCHEMA
      || !natural(value.cut_count) || !Array.isArray(value.threads)) invalid('continuation shape');
  if (value.threads.length > AGENDA_MAX_THREADS) invalid('too many threads');
  const ids = new Set();
  for (const thread of value.threads) {
    if (!closed(thread, [...Object.keys(fields), 'created_at_cut', 'updated_at_cut'])
        || typeof thread.id !== 'string' || !idMatches.test(thread.id) || ids.has(thread.id)
        || !nonblank(thread.title, 120) || !statuses.includes(thread.status)
        || !natural(thread.created_at_cut) || !natural(thread.updated_at_cut)
        || thread.updated_at_cut < thread.created_at_cut || thread.updated_at_cut > value.cut_count) invalid('thread shape or stamps');
    ids.add(thread.id);
    for (const key of ['notes', 'stop_when', 'drop_reason']) {
      if ((Object.hasOwn(thread, key) || key === 'drop_reason' && thread.status === 'dropped')
          && !nonblank(thread[key], fields[key].maxLength)) invalid(key);
    }
    if (Object.hasOwn(thread, 'sub_items') && (!Array.isArray(thread.sub_items)
        || thread.sub_items.length > AGENDA_MAX_SUB_ITEMS || [...thread.sub_items].some(item =>
          !closed(item, ['text', 'done']) || !nonblank(item.text, 100) || typeof item.done !== 'boolean'))) invalid('sub_items');
    if (Object.hasOwn(thread, 'refs') && (!Array.isArray(thread.refs) || thread.refs.length > AGENDA_MAX_REFS
        || [...thread.refs].some(ref => !nonblank(ref, 128))
        || new Set(thread.refs).size !== thread.refs.length)) invalid('refs');
  }
  if (value.threads.filter(working).length > AGENDA_MAX_ACTIVE) invalid('too many active or paused threads');
  if (Buffer.byteLength(JSON.stringify(value)) > AGENDA_MAX_BYTES) invalid('exceeds 3072 UTF-8 bytes');
  return value;
}

export function advanceAgendaCut(agenda) {
  const cut_count = agenda.cut_count + 1;
  return validateAgenda({...agenda, cut_count, threads:agenda.threads.filter(thread =>
    working(thread) || cut_count - thread.updated_at_cut < AGENDA_TOMBSTONE_CUTS)});
}

export const agendaRefSet = agenda => new Set(agenda.threads.filter(working).flatMap(thread => thread.refs ?? []));
export const agendaQueryText = agenda => agenda.threads.filter(working)
  .flatMap(thread => [thread.title, thread.notes ?? '']).join(' ');
export const agendaForPrompt = agenda => ({cut_count:agenda.cut_count, threads:agenda.threads.map(
  ({created_at_cut, updated_at_cut, ...thread}) => thread)});

export function applyAgendaTool(agenda, args, earnedRefs) {
  const allowed = args && Object.hasOwn(operationFields, args.op) ? operationFields[args.op] : null;
  if (!allowed || !closed(args, ['op', 'intent', ...allowed])) invalid('tool operation arguments');
  let threads = agenda.threads;
  if (args.op === 'clear_completed') threads = threads.filter(working);
  if (args.op === 'upsert' || args.op === 'set_status') {
    const index = threads.findIndex(thread => thread.id === args.id);
    const old = threads[index];
    if (args.op === 'set_status' && (!old || !statuses.includes(args.status))) invalid('set_status requires an existing id and status');
    const patch = Object.fromEntries(allowed.filter(key => Object.hasOwn(args, key)).map(key => [key, args[key]]));
    const thread = {...old, ...structuredClone(patch), created_at_cut:old?.created_at_cut ?? agenda.cut_count,
      updated_at_cut:agenda.cut_count};
    if (thread.status !== 'dropped' && !Object.hasOwn(patch, 'drop_reason')) delete thread.drop_reason;
    threads = [...threads];
    if (old) threads[index] = thread;
    else threads.push(thread);
  }
  const next = validateAgenda({...agenda, threads});
  if (args.op === 'upsert') {
    for (const ref of args.refs ?? []) {
      if (!earnedRefs.has(ref)) invalid(`unearned ref ${JSON.stringify(ref)}`);
    }
  }
  const changed = JSON.stringify(threads) !== JSON.stringify(agenda.threads);
  return {agenda:changed ? next : agenda, changed, summary:{op:args.op, changed, ...agendaForPrompt(next)}};
}
