export const frozenPrice = value => typeof value === 'string'
  && value.length <= 64 && /^(0|[1-9]\d*)(?:\.\d+)?(?![\s\S])/.test(value);

// Convert a nonnegative decimal to integer nanodollars, rounding upward.
export function ceilDecimal(value, scale) {
  const match = /^(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i.exec(String(value));
  if (!match || !Number.isFinite(Number(value))) throw new RangeError('Invalid decimal price');
  const [, whole, fraction = '', exponent = '0'] = match;
  const shift = Number(exponent) + scale - fraction.length;
  if (!Number.isSafeInteger(shift) || Math.abs(shift) > 1024) throw new RangeError('Invalid price scale');
  const numerator = BigInt(whole + fraction);
  if (shift >= 0) return numerator * 10n ** BigInt(shift);
  const divisor = 10n ** BigInt(-shift);
  return (numerator + divisor - 1n) / divisor;
}

export class RequestBudget {
  constructor(route) {
    if (typeof route.max_cost_nano_usd !== 'string' || !/^(0|[1-9]\d{0,17})$/.test(route.max_cost_nano_usd))
      throw new RangeError('Invalid host dollar allocation');
    this.allocation = BigInt(route.max_cost_nano_usd);
    const {cost, contextWindow, maxTokens} = route.model;
    this.inputRate = [cost.input, cost.cacheRead, cost.cacheWrite]
      .map(value => ceilDecimal(value, 3)).reduce((max, value) => value > max ? value : max, 0n);
    this.outputRate = ceilDecimal(cost.output, 3);
    this.context = contextWindow;
    this.output = maxTokens;
    this.bound = BigInt(contextWindow) * this.inputRate + BigInt(maxTokens) * this.outputRate;
    this.charged = 0n;
    this.pending = false;
    this.usage = null;
    this.uncertain = false;
    this.violation = false;
    this.observedViolation = null;
  }

  reserve() {
    if (this.pending || this.charged + this.bound > this.allocation) return false;
    this.pending = true;
    this.usage = null;
    this.uncertain = false;
    return true;
  }

  observe(usage, associated) {
    if (!this.pending || usage == null) return;
    const {prompt_tokens: input, completion_tokens: output, cost} = usage;
    let billed = 0n;
    if (cost != null) {
      try {
        if (typeof cost !== 'number' && typeof cost !== 'string') throw new RangeError('Invalid provider cost');
        billed = ceilDecimal(cost, 9);
      } catch {
        this.uncertain = true;
      }
    }
    const validInput = Number.isSafeInteger(input) && input >= 0;
    const validOutput = Number.isSafeInteger(output) && output >= 0;
    const valid = validInput && validOutput;
    const cached = usage.prompt_tokens_details?.cached_tokens ?? usage.prompt_cache_hit_tokens ?? usage.cached_tokens ?? 0;
    const written = usage.prompt_tokens_details?.cache_write_tokens ?? 0;
    const reasoning = usage.completion_tokens_details?.reasoning_tokens ?? 0;
    const detailsValid = [cached, written, reasoning].every(value => Number.isSafeInteger(value) && value >= 0)
      && cached + written <= input && reasoning <= output;
    const priced = valid ? BigInt(input) * this.inputRate + BigInt(output) * this.outputRate : 0n;
    const charge = billed > priced ? billed : priced;
    if (charge > this.bound || (validInput && input > this.context) || (validOutput && output > this.output)) {
      this.violation = true;
      this.observedViolation ??= {observed_nano_usd:String(charge),
        ...(validInput ? {prompt_tokens:input} : {}), ...(validOutput ? {completion_tokens:output} : {})};
    }
    if (!associated || !valid || !detailsValid
        || (usage.total_tokens != null && usage.total_tokens !== input + output) || this.usage !== null) {
      this.uncertain = true;
      return;
    }
    this.usage = charge;
  }

  settle(complete) {
    if (!this.pending) return null;
    this.pending = false;
    const reconciled = complete && !this.uncertain && !this.violation && this.usage !== null;
    const charge = reconciled ? this.usage : this.bound;
    this.charged += charge;
    return {charged_nano_usd:String(charge), reconciled, violation:this.violation, ...this.observedViolation};
  }
}
// Certify a complete SSE terminal event before releasing any reservation.
// Keep only a short line prefix and discard the rest of large payload lines.
export class CompletionMarker {
  line = '';
  overflow = false;
  data = null;
  complete = false;
  decoder = new TextDecoder();

  push(chunk) {
    const decoded = this.decoder.decode(chunk, {stream:true});
    const lines = decoded.split('\n');
    for (const [index, fragment] of lines.entries()) {
      this.overflow ||= this.line.length + fragment.length > 32;
      this.line = (this.line + fragment.slice(0, 32)).slice(0, 32);
      if (index === lines.length - 1) break;
      const line = this.line.replace(/\r$/, '');
      if (!this.overflow && line === '') {
        this.complete ||= this.data === '[DONE]';
        this.data = null;
      } else if (/^data(?::|$)/.test(line)) {
        this.data = !this.overflow && this.data === null && /^data: ?\[DONE\]$/.test(line)
          ? '[DONE]' : false;
      }
      this.line = '';
      this.overflow = false;
    }
  }
}
