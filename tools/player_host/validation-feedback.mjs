import { Type, validateToolArguments } from '@earendil-works/pi-ai';

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

/** Request-only diagnostics for Pi1.4.0's misleading memory anyOf errors. */
export function createValidationFeedback(tools, report) {
  const variants = new Map();
  const cache = new WeakMap();
  for (const tool of tools) {
    const intent = tool.parameters.properties?.intent;
    if (!Array.isArray(intent?.anyOf)) continue;
    const selected = new Map();
    for (const branch of intent.anyOf) {
      const kind = branch.properties?.entry_type?.const;
      if (typeof kind !== 'string') continue;
      // An ambiguous discriminator cannot select a diagnostic branch.
      selected.set(kind, selected.has(kind) ? null : {name:tool.name,
        parameters:Type.Unsafe({...tool.parameters,
          properties:{...tool.parameters.properties, intent:{...intent, anyOf:[branch]}}})});
    }
    variants.set(tool.name, selected);
  }

  function diagnostic(call, result) {
    let text = null;
    const original = result.content;
    const header = `Validation failed for tool "${call.name}":\n`;
    // Pinned Pi supplies durationMs whenever execute ran, including exceptions
    // and zero-duration calls. Immediate parser/blocked errors have other headers.
    if (!(result.isError === true && !Object.hasOwn(result, 'durationMs')
        && !Object.hasOwn(call, 'argumentsError') && result.toolName === call.name
        && original?.length === 1 && original[0].type === 'text'
        && original[0].text.startsWith(header) && object(call.arguments?.intent))) return null;
    const kind = call.arguments.intent.entry_type;
    const narrowed = variants.get(call.name)?.get(kind);
    if (!narrowed) return null;
    const memo = cache.get(result);
    if (memo?.call === call) return memo.text;
    try { validateToolArguments(narrowed, call); }
    catch (error) {
      if (error instanceof Error && error.message.startsWith(header)) {
        text = `Selected intent.entry_type=${JSON.stringify(kind)}.\n${error.message}`;
      }
    }
    cache.set(result, {call, text});
    if (text !== null) report({tool_call_id:call.id, tool:call.name,
      entry_type:call.arguments.intent.entry_type, original_result:result, projected_text:text});
    return text;
  }

  return messages => {
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
