#!/usr/bin/env node
import { lstat, open, writeFile } from 'node:fs/promises';
import { INPUT_LIMIT_BYTES, HostError, runHost } from './host.mjs';

const output = event => process.stdout.write(JSON.stringify(event) + '\n');
const started = performance.now();
const controller = new AbortController();
const cancel = () => controller.abort();
process.on('SIGINT', cancel);
process.on('SIGTERM', cancel);
let timer;
try {
  const allowed = new Set(['--config', '--mcp-config', '--context', '--model', '--effort', '--timeout-seconds', '-o']);
  const args = {};
  for (let i=2; i<process.argv.length; i+=2) {
    const key = process.argv[i], value = process.argv[i+1];
    if (!allowed.has(key) || args[key] !== undefined || !value) throw new HostError('invalid-arguments');
    args[key] = value;
  }
  if (Object.keys(args).length !== allowed.size) throw new HostError('invalid-arguments');
  const seconds = Number(args['--timeout-seconds']);
  if (!Number.isFinite(seconds) || seconds <= 0 || seconds * 1000 > 2_147_483_647) throw new HostError('invalid-host-timeout');
  timer = setTimeout(cancel, seconds * 1000);
  async function readBounded(path) {
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
        if (controller.signal.aborted) throw new HostError('cancelled');
      }
      if (offset > INPUT_LIMIT_BYTES) throw new HostError('input-too-large');
      return data.subarray(0, offset).toString('utf8');
    } finally { await file.close(); }
  }
  const [route, mcp, context] = await Promise.all([readBounded(args['--config']), readBounded(args['--mcp-config']), readBounded(args['--context'])]);
  const prompt = await new Promise((resolve, reject) => {
    const chunks=[]; let length=0;
    const abort = () => { process.stdin.destroy(); reject(new HostError('cancelled')); };
    controller.signal.addEventListener('abort', abort, {once:true});
    if (controller.signal.aborted) return abort();
    process.stdin.on('data', chunk => {
      length += chunk.length;
      if (length > INPUT_LIMIT_BYTES) { process.stdin.destroy(); reject(new HostError('input-too-large')); }
      else chunks.push(chunk);
    });
    process.stdin.once('end', () => {controller.signal.removeEventListener('abort', abort); resolve(Buffer.concat(chunks).toString('utf8'));});
    process.stdin.once('error', () => reject(new HostError('stdin-failed')));
  });
  const remaining = seconds - (performance.now() - started) / 1000;
  if (remaining <= 0) throw new HostError('host-timeout');
  const result = await runHost({configuration:JSON.parse(route), mcpConfig:JSON.parse(mcp), context, prompt, model:args['--model'], effort:args['--effort'], timeoutSeconds:remaining, signal:controller.signal, onEvent:output});
  // campaign_player owns exclusive reservation of this exact final path. Like
  // its Codex subprocess, this runner writes the already reserved file.
  if (result.ok) await writeFile(args['-o'], result.finalText + '\n', {encoding:'utf8', signal:controller.signal});
  process.exitCode = result.ok ? 0 : 1;
} catch (error) {
  output({type:'settled', wall_time:new Date().toISOString(), monotonic_ms:performance.now() - started, ok:false, reason:error instanceof HostError ? error.reason : 'invalid-input-or-output', native_cleanup_claimed:false});
  process.exitCode=1;
} finally {
  clearTimeout(timer);
  process.off('SIGINT', cancel);
  process.off('SIGTERM', cancel);
}
