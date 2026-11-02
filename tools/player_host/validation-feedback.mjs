const RECEIVED_LIMIT = 120;
export const FIX_LINE = 'Fix the call and resend it; abstaining is not the remedy for a fixable call.';

/** A minimal valid argument value for a flat portable schema: first enum value, smallest bound, placeholder text. */
export function exampleValue(schema, name = 'value') {
  if (Array.isArray(schema.enum)) return schema.enum[0];
  switch (schema.type) {
    case 'string': {
      // An optional-length string is shown empty; a required one as a visible placeholder within its bound.
      if ((schema.minLength ?? 0) === 0) return '';
      const placeholder = `<${name}>`;
      return placeholder.slice(0, Math.max(schema.minLength, schema.maxLength ?? placeholder.length));
    }
    case 'number': case 'integer': return schema.minimum ?? 0;
    case 'boolean': return false;
    case 'array': return (schema.minItems ?? 0) > 0 ? [exampleValue(schema.items ?? {}, name)] : [];
    case 'object': return Object.fromEntries((schema.required ?? []).filter(key => schema.properties?.[key])
      .map(key => [key, exampleValue(schema.properties[key], key)]));
    default: return null;
  }
}

const at = (value, parts) => parts.reduce((current, part) =>
  current !== null && typeof current === 'object' ? current[part] : undefined, value);
/** The schema node of a dotted path (array indexes descend into `items`), or undefined. */
function nodeAt(schema, parts) {
  let node = schema;
  for (const part of parts) {
    if (node === undefined) return undefined;
    node = node.type === 'array' ? node.items : node.properties?.[part];
  }
  return node;
}

/** The received value at a path, shown within a fixed width. */
function received(args, parts) {
  const value = at(args, parts);
  if (value === undefined) return 'nothing';
  const text = JSON.stringify(value) ?? String(value);
  return text.length > RECEIVED_LIMIT ? `${text.slice(0, RECEIVED_LIMIT)}...(${text.length - RECEIVED_LIMIT} more characters)` : text;
}

const LIMITS = ['minLength', 'maxLength', 'minItems', 'maxItems', 'minimum', 'maximum'];
/** One failing field per line: its path, the rule, the expected value or allowed set (read from the schema) and what was received. */
function describe(path, message, schema, args) {
  const root = path === 'root';
  const parts = root ? [] : path.split('.');
  if (message === 'schema is false') return []; // The sibling additionalProperties refusal names the properties.
  const missing = /^must have required propert(?:y|ies) (.+)$/.exec(message);
  if (missing) {
    // The SDK names the first missing property in the path; the message lists all of them.
    const base = parts.slice(0, -1).join('.');
    return missing[1].split(', ').map(name => `- ${base ? `${base}.` : ''}${name}: required property is missing`);
  }
  const node = nodeAt(schema, parts);
  if (message === 'must not have additional properties') {
    const unknown = Object.keys(at(args, parts) ?? {}).filter(key => !(node?.properties && key in node.properties));
    return [`- ${root ? 'arguments' : path}: unknown properties ${unknown.map(name => JSON.stringify(name)).join(', ')} are not allowed; remove them`];
  }
  let rule = message;
  if (Array.isArray(node?.enum)) rule = `must be one of ${node.enum.map(value => JSON.stringify(value)).join(', ')}`;
  else if (node) {
    const limits = LIMITS.filter(key => node[key] !== undefined).map(key => `${key} ${node[key]}`);
    if (limits.length) rule = `${message} (${limits.join(', ')})`;
  }
  return [`- ${root ? 'arguments' : path}: ${rule}; received ${received(args, parts)}`];
}

/** Request-only diagnostics for the pinned SDK's validation refusals of the named tools.
 * `names` selects the tools covered; `terminal` the subset whose refusals also say a fixable call is not abstained;
 * `notes` maps a tool to one line shown after its example, for what a minimal example cannot show. */
export function createValidationFeedback(tools, report, {names = [], terminal = [], notes = {}} = {}) {
  const covered = new Map(tools.filter(tool => names.includes(tool.name)).map(tool => [tool.name, tool]));
  const cache = new WeakMap();

  function diagnostic(call, result) {
    const tool = covered.get(call.name);
    if (!tool) return null;
    const original = result.content;
    const header = `Validation failed for tool "${call.name}":\n`;
    // Pinned Pi supplies durationMs whenever execute ran, including exceptions
    // and zero-duration calls. Immediate parser/blocked errors have other headers.
    if (!(result.isError === true && !Object.hasOwn(result, 'durationMs')
        && !Object.hasOwn(call, 'argumentsError') && result.toolName === call.name
        && original?.length === 1 && original[0].type === 'text'
        && original[0].text.startsWith(header))) return null;
    const memo = cache.get(result);
    if (memo?.call === call) return memo.text;
    let text = null;
    try {
      // The SDK's own refusal names each failing path and rule; the tool's schema supplies the expected values.
      const body = original[0].text.slice(header.length).split('\n\nReceived arguments:')[0];
      const lines = body.split('\n').flatMap(line => {
        const match = /^ {2}- ([^:]+): (.*)$/.exec(line);
        return match ? describe(match[1], match[2], tool.parameters, call.arguments) : [];
      });
      if (lines.length) {
        text = `${header.trimEnd()}\n${lines.join('\n')}\n`
          + `Valid example call: ${call.name} ${JSON.stringify(exampleValue(tool.parameters))}`
          + (notes[call.name] ? `\n${notes[call.name]}` : '')
          + (terminal.includes(call.name) ? `\n${FIX_LINE}` : '');
      }
    } catch { text = null; }
    cache.set(result, {call, text});
    if (text !== null) report({tool_call_id:call.id, tool:call.name, original_result:result, projected_text:text});
    return text;
  }

  return messages => {
    if (!covered.size) return messages;
    let output = messages;
    let calls = [], results = [];
    function completeBatch() {
      // Recheck pairing on every build, outside the memoized diagnostic. Never
      // reinterpret ambiguous, partial or unpaired SDK history as a refusal.
      const byId = new Map(calls.map(call => [call.id, call]));
      if (!calls.length || byId.size !== calls.length || results.length !== calls.length
          || new Set(results.map(({message}) => message.toolCallId)).size !== results.length
          || results.some(({message}) => !byId.has(message.toolCallId))) return;
      for (const {message, index} of results) {
        const text = diagnostic(byId.get(message.toolCallId), message);
        if (text === null) continue;
        if (output === messages) output = [...messages];
        output[index] = {...message, content:[{type:'text', text}]};
      }
    }
    for (const [index, message] of messages.entries()) {
      if (message.role === 'assistant') {
        completeBatch();
        calls = (message.content ?? []).filter(part => part.type === 'toolCall');
        results = [];
      } else if (message.role === 'toolResult') results.push({message, index});
    }
    completeBatch();
    return output;
  };
}
