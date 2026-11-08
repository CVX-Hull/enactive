// The curator host's workspace tools. Each tool works on paths relative to the session
// workspace (the host's working directory) and refuses `..`, absolute paths and links.
// The sandbox is the real boundary; these checks make a refusal clear to the model and keep
// a mistaken call from reaching the sandbox at all.
import { constants } from 'node:fs';
import { lstat, mkdir, open, readdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { join } from 'node:path';

export const WRITABLE_DIRECTORIES = ['submissions', 'drafts', 'scratch'];
export const READ_DEFAULT_BYTES = 65536;
export const READ_MAX_BYTES = 262144;
export const WRITE_MAX_BYTES = 524288;
export const FRAME_MAX_BYTES = 5 * 1048576;
export const LIST_MAX_ENTRIES = 500;
export const WORKBENCH_OUTPUT_BYTES = 49152;
export const WORKBENCH_MAX_ARGS = 40;
const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

/** A refusal or failure the model should read; never an internal error. */
export class ToolError extends Error {
  constructor(message) { super(message); this.name = 'ToolError'; }
}

function parts(path) {
  if (typeof path !== 'string' || path.length === 0 || path.length > 512 || path.includes('\0') || path.includes('\\')) {
    throw new ToolError('invalid path');
  }
  if (path.startsWith('/')) throw new ToolError('absolute paths are not allowed; use a path relative to the workspace');
  const result = path.split('/').filter(part => part !== '' && part !== '.');
  if (result.includes('..')) throw new ToolError('".." is not allowed');
  return result;
}

/** Absolute path of `relative` inside `root`. Every existing component must be a plain
 * directory (or, for the last one, any entry when `last` is true); links are refused. */
async function locate(root, relative, { createDirectories = false } = {}) {
  const names = parts(relative);
  let current = root;
  for (const [index, name] of names.entries()) {
    const next = join(current, name);
    const isLast = index === names.length - 1;
    let info;
    try { info = await lstat(next); }
    catch (error) {
      if (error.code !== 'ENOENT') throw new ToolError(`cannot access ${name}: ${error.code ?? 'error'}`);
      if (isLast) return { path: next, names, exists: false };
      if (!createDirectories) throw new ToolError(`no such directory: ${names.slice(0, index + 1).join('/')}`);
      await mkdir(next);
      info = await lstat(next);
    }
    if (info.isSymbolicLink()) throw new ToolError(`links are not allowed: ${names.slice(0, index + 1).join('/')}`);
    if (!isLast && !info.isDirectory()) throw new ToolError(`not a directory: ${names.slice(0, index + 1).join('/')}`);
    current = next;
  }
  return { path: current, names, exists: true };
}

function textResult(text, isError = false) {
  return { content: [{ type: 'text', text }], details: undefined, isError };
}

function bounded(value, fallback, maximum) {
  if (value === undefined) return fallback;
  if (!Number.isSafeInteger(value) || value < 0) throw new ToolError('numbers must be non-negative integers');
  return Math.min(value, maximum);
}

export async function listDir(root, { path = '.', offset, limit }) {
  const target = await locate(root, path);
  if (!target.exists) throw new ToolError(`no such directory: ${path}`);
  const info = await lstat(target.path);
  if (!info.isDirectory()) throw new ToolError(`not a directory: ${path}`);
  const names = (await readdir(target.path)).sort();
  const start = bounded(offset, 0, names.length), count = bounded(limit, 200, LIST_MAX_ENTRIES);
  const lines = [];
  for (const name of names.slice(start, start + count)) {
    let entry;
    try { entry = await lstat(join(target.path, name)); } catch { continue; }
    const kind = entry.isSymbolicLink() ? 'link' : entry.isDirectory() ? 'dir' : entry.isFile() ? 'file' : 'other';
    lines.push(`${kind}\t${kind === 'file' ? entry.size : '-'}\t${name}`);
  }
  const rest = names.length - start - lines.length;
  return textResult(`${path}: ${names.length} entries (kind, bytes, name)\n${lines.join('\n')}`
    + (rest > 0 ? `\n[${rest} more; use offset=${start + lines.length}]` : ''));
}

export async function readFile(root, { path, offset, max_bytes }) {
  const target = await locate(root, path);
  if (!target.exists) throw new ToolError(`no such file: ${path}`);
  const start = bounded(offset, 0, Number.MAX_SAFE_INTEGER), count = bounded(max_bytes, READ_DEFAULT_BYTES, READ_MAX_BYTES);
  let handle;
  try { handle = await open(target.path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK); }
  catch (error) { throw new ToolError(`cannot open ${path}: ${error.code ?? 'error'}`); }
  try {
    const info = await handle.stat();
    if (!info.isFile()) throw new ToolError(`not a regular file: ${path}`);
    const buffer = Buffer.alloc(count);
    const { bytesRead } = await handle.read(buffer, 0, count, start);
    const data = buffer.subarray(0, bytesRead);
    if (data.includes(0)) throw new ToolError(`${path} is binary; read text files only (frames: use view_frame)`);
    const remaining = Math.max(0, info.size - start - bytesRead);
    return textResult(data.toString('utf8') + (remaining > 0 ? `\n[truncated: ${remaining} more bytes; use offset=${start + bytesRead}]` : ''));
  } finally { await handle.close(); }
}

export async function writeFile(root, { path, content }) {
  const names = parts(path);
  if (names.length < 2 || !WRITABLE_DIRECTORIES.includes(names[0])) {
    throw new ToolError(`writes are allowed only inside ${WRITABLE_DIRECTORIES.join(', ')} (for example submissions/<id>/submission.json)`);
  }
  if (typeof content !== 'string' || !content.isWellFormed()) throw new ToolError('content must be well-formed text');
  const bytes = Buffer.from(content, 'utf8');
  if (bytes.length > WRITE_MAX_BYTES) throw new ToolError(`content is ${bytes.length} bytes; the limit is ${WRITE_MAX_BYTES}`);
  const target = await locate(root, names.join('/'), { createDirectories: true });
  let handle;
  try { handle = await open(target.path, constants.O_WRONLY | constants.O_CREAT | constants.O_TRUNC | constants.O_NOFOLLOW, 0o644); }
  catch (error) { throw new ToolError(`cannot write ${path}: ${error.code ?? 'error'}`); }
  try {
    if (!(await handle.stat()).isFile()) throw new ToolError(`not a regular file: ${path}`);
    await handle.writeFile(bytes);
  } finally { await handle.close(); }
  return textResult(`wrote ${bytes.length} bytes to ${names.join('/')}`);
}

export async function viewFrame(root, { frame }) {
  if (typeof frame !== 'string') throw new ToolError('frame must be a string');
  const id = frame.replace(/^trace\/frames\//, '').replace(/\.png$/, '');
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(id)) throw new ToolError('a frame is cited by its source id, for example "<session>-<n>"');
  const target = await locate(root, `trace/frames/${id}.png`);
  if (!target.exists) throw new ToolError(`no such frame: ${id}`);
  let handle;
  try { handle = await open(target.path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK); }
  catch (error) { throw new ToolError(`cannot open frame ${id}: ${error.code ?? 'error'}`); }
  try {
    const info = await handle.stat();
    if (!info.isFile() || info.size > FRAME_MAX_BYTES) throw new ToolError(`frame ${id} is not a regular file of at most ${FRAME_MAX_BYTES} bytes`);
    const data = Buffer.alloc(info.size);
    const { bytesRead } = await handle.read(data, 0, info.size, 0);
    if (bytesRead !== info.size || !data.subarray(0, 8).equals(PNG_MAGIC)) throw new ToolError(`frame ${id} is not a PNG`);
    return { content: [{ type: 'text', text: `frame ${id} (${info.size} bytes)` },
      { type: 'image', data: data.toString('base64'), mimeType: 'image/png' }], details: undefined, isError: false };
  } finally { await handle.close(); }
}

export function runWorkbench(root, { args }, { python, env, timeoutSeconds }) {
  if (!Array.isArray(args) || args.length === 0 || args.length > WORKBENCH_MAX_ARGS
      || args.some(arg => typeof arg !== 'string' || arg.length > 1000 || arg.includes('\0'))) {
    throw new ToolError(`args must be 1 to ${WORKBENCH_MAX_ARGS} strings of at most 1000 characters`);
  }
  if (typeof python !== 'string' || !python.startsWith('/')) throw new ToolError('the workbench interpreter is not configured');
  return new Promise(resolve => {
    const child = spawn(python, ['-m', 'harness.trace.workbench', ...args], {
      cwd: join(root, 'workbench'), env, stdio: ['ignore', 'pipe', 'pipe'], detached: false,
    });
    const streams = { stdout: [], stderr: [] };
    let size = 0, truncated = false, timedOut = false, settled = false;
    const take = name => chunk => {
      if (truncated) return;
      const room = WORKBENCH_OUTPUT_BYTES - size;
      streams[name].push(chunk.subarray(0, Math.max(0, room)));
      size += Math.min(chunk.length, Math.max(0, room));
      if (chunk.length > room) { truncated = true; child.kill('SIGKILL'); }
    };
    child.stdout.on('data', take('stdout'));
    child.stderr.on('data', take('stderr'));
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeoutSeconds * 1000);
    const finish = (code, error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      const out = Buffer.concat(streams.stdout).toString('utf8'), err = Buffer.concat(streams.stderr).toString('utf8');
      const notes = [truncated ? `[output truncated at ${WORKBENCH_OUTPUT_BYTES} bytes; narrow the query]` : '',
        timedOut ? `[timed out after ${timeoutSeconds} s]` : '', error ? `[could not run: ${error.code ?? 'error'}]` : ''].filter(Boolean);
      resolve(textResult([`exit code: ${code ?? 'none'}`, out ? `--- stdout ---\n${out}` : '', err ? `--- stderr ---\n${err}` : '', ...notes]
        .filter(Boolean).join('\n'), code !== 0));
    };
    child.on('error', error => finish(null, error));
    child.on('close', code => finish(code));
  });
}
