#!/usr/bin/env node
import { lstat, mkdtemp, open, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { emptyAgenda, validateAgenda } from './agenda.mjs';
import { INPUT_LIMIT_BYTES, HostError, runHost, validateConfiguration, validateMcpConfiguration } from './host.mjs';

// player-host/13 modes: `run` hosts one actor, `validate` checks route and MCP
// table offline. Each required flag occurs exactly once and each optional flag at
// most once; values are non-empty. The flag set is closed.
function parseFlags(argv, required, optional = new Set()) {
  const args = {};
  for (let i=0; i<argv.length; i+=2) {
    const key = argv[i], value = argv[i+1];
    if ((!required.has(key) && !optional.has(key)) || args[key] !== undefined || !value) throw new HostError('invalid-arguments');
    args[key] = value;
  }
  if ([...required].some(key => args[key] === undefined)) throw new HostError('invalid-arguments');
  return args;
}
async function readBounded(path, signal) {
  const stat = await lstat(path);
  if (!stat.isFile() || stat.size > INPUT_LIMIT_BYTES) throw new HostError('invalid-input-file');
  const file = await open(path, 'r');
  try {
    const data = Buffer.alloc(INPUT_LIMIT_BYTES + 1);
    let offset = 0;
    while (offset < data.length) {
      const {bytesRead} = await file.read(data, offset, data.length - offset, null);
      if (!bytesRead) break;
      offset += bytesRead;
      if (signal?.aborted) throw new HostError('cancelled');
    }
    if (offset > INPUT_LIMIT_BYTES) throw new HostError('input-too-large');
    return data.subarray(0, offset).toString('utf8');
  } finally { await file.close(); }
}
async function writeAgenda(path, agenda) {
  const tmp = await mkdtemp(join(dirname(path), '.player-agenda-'));
  try {
    const file = join(tmp, 'agenda.json');
    await writeFile(file, JSON.stringify(agenda), {mode:0o600});
    await rename(file, path);
  } finally { await rm(tmp, {recursive:true, force:true}); }
}
async function validateMode(argv) {
  try {
    const args = parseFlags(argv, new Set(['--config', '--mcp-config', '--model', '--effort']));
    const [route, mcp] = await Promise.all([readBounded(args['--config']), readBounded(args['--mcp-config'])]);
    validateConfiguration(JSON.parse(route), args['--model'], args['--effort']);
    validateMcpConfiguration(JSON.parse(mcp));
    process.exitCode = 0;
  } catch (error) {
    process.stderr.write(`invalid: ${error instanceof HostError ? error.reason : 'invalid-input'}\n`);
    process.exitCode = 1;
  }
}
const mode = process.argv[2];
if (mode === 'validate') {
  await validateMode(process.argv.slice(3));
  process.exit(process.exitCode);
}

const output = event => {
  const start = performance.now(), line = JSON.stringify(event) + '\n';
  const encoded = performance.now(), accepted = process.stdout.write(line);
  const enqueued = performance.now();
  return {json_ms:encoded - start, enqueue_ms:enqueued - encoded,
    bytes:Buffer.byteLength(line), backpressure_signals:accepted ? 0 : 1};
};
const started = performance.now();
const controller = new AbortController();
const cancel = () => controller.abort();
process.on('SIGINT', cancel);
process.on('SIGTERM', cancel);
let timer;
try {
  if (mode !== 'run') throw new HostError('invalid-arguments');
  const args = parseFlags(process.argv.slice(3), new Set(['--config', '--mcp-config', '--context', '--prompt', '--session', '--actor-id', '--pending-control-id', '--delivered-knowledge', '--finish-reserve-usd', '--model', '--effort', '--timeout-seconds', '-o']),
    new Set(['--knowledge-updates', '--agenda', '--agenda-out']));
  const seconds = Number(args['--timeout-seconds']);
  if (!Number.isFinite(seconds) || seconds <= 0 || seconds * 1000 > 2_147_483_647) throw new HostError('invalid-host-timeout');
  timer = setTimeout(cancel, seconds * 1000);
  const [route, mcp, context, prompt, knowledge, agendaText] = await Promise.all([readBounded(args['--config'], controller.signal), readBounded(args['--mcp-config'], controller.signal), readBounded(args['--context'], controller.signal), readBounded(args['--prompt'], controller.signal), readFile(args['--delivered-knowledge'], {encoding:'utf8', signal:controller.signal}), args['--agenda'] ? readBounded(args['--agenda'], controller.signal) : null]);
  let agenda;
  try { agenda = agendaText === null ? emptyAgenda() : validateAgenda(JSON.parse(agendaText)); }
  catch { throw new HostError('invalid-agenda'); }
  const remaining = seconds - (performance.now() - started) / 1000;
  if (remaining <= 0) throw new HostError('host-timeout');
  let settlement;
  const result = await runHost({configuration:JSON.parse(route), mcpConfig:JSON.parse(mcp), context, prompt, agenda, knowledge:JSON.parse(knowledge), knowledgeUpdates:args['--knowledge-updates'] ?? null, finishReserveUsd:args['--finish-reserve-usd'], session:args['--session'], actorId:args['--actor-id'], pendingControlId:args['--pending-control-id'] === 'none' ? null : args['--pending-control-id'], control:process.stdin, model:args['--model'], effort:args['--effort'], timeoutSeconds:remaining, signal:controller.signal, onEvent:event => {
    if (event.type === 'settled') settlement = event;
    else return output(event);
  }});
  let writeFailed = false;
  if (args['--agenda-out']) {
    try { await writeAgenda(args['--agenda-out'], result.agenda); }
    catch (error) {
      writeFailed = true;
      process.stderr.write(`player_host: failed to write agenda output: ${error?.message ?? error}\n`);
    }
  }
  // campaign_player owns exclusive reservation of this exact final path; the
  // contract writes only the report from a direct accepted finish invocation.
  if (result.ok && ['task_complete', 'cannot_continue', 'external_stop_complete'].includes(result.reason)) await writeFile(args['-o'], result.finalText + '\n', {encoding:'utf8', signal:controller.signal});
  // Always emit the real settlement with intact spend/request counts before setting non-zero exit on agenda-out I/O failure.
  output(settlement);
  process.exitCode = result.ok && !writeFailed ? 0 : 1;
} catch (error) {
  output({type:'settled', wall_time:new Date().toISOString(), monotonic_ms:performance.now() - started, ok:false, reason:error instanceof HostError ? error.reason : 'invalid-input-or-output', native_cleanup_claimed:false});
  process.exitCode=1;
} finally {
  clearTimeout(timer);
  process.off('SIGINT', cancel);
  process.off('SIGTERM', cancel);
}
