import { Type, validateToolArguments } from '@earendil-works/pi-ai';

const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

/** The discriminated unions of one tool's top-level arguments: an anyOf whose branches each carry a string `const` on one common key. */
function discriminatedUnions(tool) {
  const unions = [];
  for (const [property, schema] of Object.entries(tool.parameters.properties ?? {})) {
    if (!Array.isArray(schema?.anyOf) || !schema.anyOf.length || !schema.anyOf.every(branch => object(branch.properties))) continue;
    // Keys that every branch pins; a shared constant (a schema version) discriminates nothing, so prefer distinct values.
    const keys = Object.keys(schema.anyOf[0].properties).filter(candidate =>
      schema.anyOf.every(branch => typeof branch.properties[candidate]?.const === 'string'));
    const key = keys.find(candidate => new Set(schema.anyOf.map(branch => branch.properties[candidate].const)).size === schema.anyOf.length) ?? keys[0];
    if (key === undefined) continue;
    const selected = new Map();
    for (const branch of schema.anyOf) {
      const kind = branch.properties[key].const;
      // An ambiguous discriminator cannot select a diagnostic branch.
      selected.set(kind, selected.has(kind) ? null : {name:tool.name, branch,
        parameters:Type.Unsafe({...tool.parameters,
          properties:{...tool.parameters.properties, [property]:{...schema, anyOf:[branch]}}})});
    }
    const shape = branch => `${branch.properties[key].const} {${(branch.required ?? Object.keys(branch.properties)).join(', ')}}`;
    unions.push({property, key, selected, shapes:`Valid ${property}.${key} shapes: ${schema.anyOf.map(shape).join('; ')}.`});
  }
  return unions;
}

/** Request-only diagnostics for Pi1.4.0's misleading anyOf errors on a discriminated union argument.
 * The error is reported against the branch the discriminator names, or the valid values are named. */
export function createValidationFeedback(tools, report) {
  const variants = new Map(tools.map(tool => [tool.name, discriminatedUnions(tool)]));
  const cache = new WeakMap();

  function diagnostic(call, result) {
    let text = null;
    const original = result.content;
    const header = `Validation failed for tool "${call.name}":\n`;
    // Pinned Pi supplies durationMs whenever execute ran, including exceptions
    // and zero-duration calls. Immediate parser/blocked errors have other headers.
    if (!(result.isError === true && !Object.hasOwn(result, 'durationMs')
        && !Object.hasOwn(call, 'argumentsError') && result.toolName === call.name
        && original?.length === 1 && original[0].type === 'text'
        && original[0].text.startsWith(header))) return null;
    const union = variants.get(call.name)?.find(({property}) => object(call.arguments?.[property]));
    if (!union) return null;
    const kind = call.arguments[union.property][union.key];
    const memo = cache.get(result);
    if (memo?.call === call) return memo.text;
    const label = `${union.property}.${union.key}`;
    if (typeof kind !== 'string' || !union.selected.has(kind)) {
      // The discriminator names no branch, so no branch's errors apply.
      text = `${header}${label} must be one of ${[...union.selected.keys()].map(k => JSON.stringify(k)).join(', ')}`
        + ` (got ${kind === undefined ? 'nothing' : JSON.stringify(kind)}).\n${union.shapes}`;
    } else {
      const narrowed = union.selected.get(kind);
      if (narrowed) {
        try { validateToolArguments(narrowed, call); }
        catch (error) {
          if (error instanceof Error && error.message.startsWith(header)) {
            text = `Selected ${label}=${JSON.stringify(kind)}.\n${error.message}\n${union.shapes}`;
          }
        }
      }
    }
    cache.set(result, {call, text});
    if (text !== null) report({tool_call_id:call.id, tool:call.name,
      selected:{property:union.property, key:union.key, value:kind ?? null}, original_result:result, projected_text:text});
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
