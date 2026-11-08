#!/usr/bin/env node
// Runs one curator session in the current working directory (the session workspace).
//   node run.mjs --config <curator-host/1 JSON file>
// Reads brief.md from the workspace and prompt.md from this package. The proxy URL, the session
// token and the workbench interpreter come from the environment the sandbox provides
// (CURATOR_PROXY_URL, CURATOR_PROXY_TOKEN, CURATOR_PYTHON). Telemetry is JSON lines on stdout.
import { lstat, open } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { CONFIG_LIMIT_BYTES, HostError, runCurator } from './host.mjs';

const BRIEF_LIMIT_BYTES = 262144;

async function readBounded(path, limit, reason) {
  const info = await lstat(path);
  if (!info.isFile() || info.size > limit) throw new HostError(reason);
  const file = await open(path, 'r');
  try { return (await file.readFile()).toString('utf8'); } finally { await file.close(); }
}

const emit = event => process.stdout.write(JSON.stringify(event) + '\n');
const controller = new AbortController();
process.on('SIGINT', () => controller.abort());
process.on('SIGTERM', () => controller.abort());
try {
  const [flag, configPath, ...rest] = process.argv.slice(2);
  if (flag !== '--config' || !configPath || rest.length) throw new HostError('invalid-arguments');
  const [configuration, systemPrompt, brief] = await Promise.all([
    readBounded(configPath, CONFIG_LIMIT_BYTES, 'invalid-configuration-file').then(JSON.parse),
    readBounded(fileURLToPath(new URL('./prompt.md', import.meta.url)), BRIEF_LIMIT_BYTES, 'invalid-prompt'),
    readBounded('brief.md', BRIEF_LIMIT_BYTES, 'invalid-brief'),
  ]);
  const result = await runCurator({ configuration, systemPrompt, brief, cwd: process.cwd(), onEvent: emit, signal: controller.signal });
  process.exitCode = result.ok ? 0 : 1;
} catch (error) {
  emit({ type: 'host-end', wall_time: new Date().toISOString(), monotonic_ms: performance.now(), ok: false,
    reason: error instanceof HostError ? error.reason : 'invalid-input', requests: 0, tool_calls: 0 });
  process.exitCode = 1;
}
