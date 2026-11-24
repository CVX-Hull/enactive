// The curator host's workspace tools. Each tool works on paths relative to the session
// workspace (the host's working directory) and refuses `..`, absolute paths and links.
// The sandbox is the real boundary; these checks make a refusal clear to the model and keep
// a mistaken call from reaching the sandbox at all.
import { constants } from 'node:fs';
import { lstat, mkdir, open, readdir, rename, rm } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { dirname, join } from 'node:path';

export const WRITABLE_DIRECTORIES = ['submissions', 'drafts', 'scratch'];
export const READ_DEFAULT_BYTES = 65536;
export const READ_MAX_BYTES = 262144;
export const WRITE_MAX_BYTES = 524288;
export const FRAME_MAX_BYTES = 5 * 1048576;
export const LIST_MAX_ENTRIES = 500;
export const WORKBENCH_OUTPUT_BYTES = 49152;
export const WORKBENCH_MAX_ARGS = 40;
export const VALIDATOR_OUTPUT_BYTES = 1048576;
export const VALIDATION_TEXT_CHARS = 49152;
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
  await confirmDestination(root, names, path);
  // Write a sibling temporary file and rename it into place, so a reader (the gate, or close-out after a
  // provider error) sees either the whole new file or the whole old one, never a partial write. The temporary
  // name has a fixed short length, so a destination name up to the file system's limit still fits.
  const temporary = join(dirname(target.path), `.enactive-tmp-${process.pid}-${randomBytes(8).toString('hex')}`);
  let handle;
  try { handle = await open(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o644); }
  catch (error) { throw new ToolError(`cannot write ${path}: ${error.code ?? 'error'}`); }
  try {
    try {
      await handle.writeFile(bytes);
      await handle.sync();
    } finally { await handle.close(); }
    // Check again just before the rename: the parent chain and the destination may have changed while the
    // bytes were written. Node has no openat/renameat, so a change between this check and the rename is still
    // possible; the Seatbelt sandbox, not this check, confines the host to the workspace.
    await confirmDestination(root, names, path);
    await rename(temporary, target.path);
  } catch (error) {
    await rm(temporary, { force: true }).catch(() => {});
    if (error instanceof ToolError) throw error;
    throw new ToolError(`cannot write ${path}: ${error.code ?? 'error'}`);
  }
  return textResult(`wrote ${bytes.length} bytes to ${names.join('/')}`);
}

/** Every parent of `names` under `root` is a real directory, not a link, and the destination is absent or a
 * regular file (not a link or a directory). */
async function confirmDestination(root, names, path) {
  let current = root;
  for (const [index, name] of names.entries()) {
    current = join(current, name);
    const isLast = index === names.length - 1;
    let info;
    try { info = await lstat(current); }
    catch (error) {
      if (isLast && error.code === 'ENOENT') return;
      throw new ToolError(`cannot write ${path}: ${error.code ?? 'error'}`);
    }
    if (info.isSymbolicLink()) throw new ToolError(`links are not allowed: ${names.slice(0, index + 1).join('/')}`);
    if (!isLast && !info.isDirectory()) throw new ToolError(`not a directory: ${names.slice(0, index + 1).join('/')}`);
    if (isLast && !info.isFile()) throw new ToolError(`not a regular file: ${path}`);
  }
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

/** Run the workbench interpreter from workbench/ with its output piped and bounded, never inherited:
 * the host's stdout is its telemetry. */
function capture(python, args, { cwd, env, timeoutSeconds, limit }) {
  return new Promise(resolve => {
    const child = spawn(python, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'], detached: false });
    const streams = { stdout: [], stderr: [] };
    let size = 0, truncated = false, timedOut = false, settled = false;
    const take = name => chunk => {
      if (truncated) return;
      const room = limit - size;
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
      resolve({ code, error, truncated, timedOut,
        stdout: Buffer.concat(streams.stdout).toString('utf8'), stderr: Buffer.concat(streams.stderr).toString('utf8') });
    };
    child.on('error', error => finish(null, error));
    child.on('close', code => finish(code));
  });
}

function requirePython(python) {
  if (typeof python !== 'string' || !python.startsWith('/')) throw new ToolError('the workbench interpreter is not configured');
}

export async function runWorkbench(root, { args }, { python, env, timeoutSeconds }) {
  if (!Array.isArray(args) || args.length === 0 || args.length > WORKBENCH_MAX_ARGS
      || args.some(arg => typeof arg !== 'string' || arg.length > 1000 || arg.includes('\0'))) {
    throw new ToolError(`args must be 1 to ${WORKBENCH_MAX_ARGS} strings of at most 1000 characters`);
  }
  requirePython(python);
  const { code, error, truncated, timedOut, stdout: out, stderr: err } = await capture(python, ['-m', 'harness.trace.workbench', ...args],
    { cwd: join(root, 'workbench'), env, timeoutSeconds, limit: WORKBENCH_OUTPUT_BYTES });
  const notes = [truncated ? `[output truncated at ${WORKBENCH_OUTPUT_BYTES} bytes; narrow the query]` : '',
    timedOut ? `[timed out after ${timeoutSeconds} s]` : '', error ? `[could not run: ${error.code ?? 'error'}]` : ''].filter(Boolean);
  return textResult([`exit code: ${code ?? 'none'}`, out ? `--- stdout ---\n${out}` : '', err ? `--- stderr ---\n${err}` : '', ...notes]
    .filter(Boolean).join('\n'), code !== 0);
}

const SHA256 = /^[0-9a-f]{64}$/;
const list = value => Array.isArray(value);

/** The validator's result, or null when it is not the documented shape. */
function validationShape(value) {
  const row = entry => entry !== null && typeof entry === 'object' && typeof entry.id === 'string'
    && typeof entry.path === 'string' && (entry.sha256 === null || SHA256.test(entry.sha256))
    && ['passed', 'rejected'].includes(entry.status) && list(entry.diagnostics) && list(entry.scope_changes);
  return value !== null && typeof value === 'object' && typeof value.ok === 'boolean' && typeof value.all_passed === 'boolean'
    && typeof value.submission === 'string' && list(value.prefix) && value.prefix.length > 0 && value.prefix.every(row)
    && list(value.diagnostics) && list(value.scope_changes) ? value : null;
}

function formatValidation(validation) {
  const lines = [`submission ${validation.submission}: ${validation.ok ? 'passes' : 'rejected'} (nothing was published)`,
    validation.all_passed
      ? 'Every submission up to and including it passes. The host recorded these exact files: if the provider fails before finish, close-out still gates them. Validate again after any change.'
      : 'Not every submission up to it passes. The gate skips a rejected submission without advancing the version, and after a provider error it gates nothing past it. Fix or remove each rejected one and validate again.',
    'Submissions in gate order:'];
  for (const row of validation.prefix) {
    lines.push(`- ${row.id}: ${row.status}, ${row.base_version ?? '?'} -> ${row.candidate_version ?? '(no new version)'}`);
    for (const diagnostic of row.diagnostics) lines.push(`  diagnostic: ${String(diagnostic)}`);
    for (const change of row.scope_changes) {
      lines.push(`  article scope change: ${change?.slug}: ${JSON.stringify(change?.from)} -> ${JSON.stringify(change?.to)}`);
    }
  }
  const text_ = lines.join('\n');
  return text_.length <= VALIDATION_TEXT_CHARS ? text_
    : `${text_.slice(0, VALIDATION_TEXT_CHARS)}\n[truncated: ${text_.length - VALIDATION_TEXT_CHARS} more characters; fix the first diagnostics and validate again]`;
}

/** Check `submissions/<submission>/submission.json`, and every submission before it in directory-name order,
 * against the published base with `harness.curator.validate`. Publishes nothing. Returns the tool result and, when
 * the validator ran, its structured result as `validation` (for the host's `submission-validated` event). */
export async function validateSubmission(root, { submission }, { python, env, timeoutSeconds }) {
  if (typeof submission !== 'string' || submission.length === 0 || submission.length > 255 || submission === '.'
      || submission === '..' || /[/\\\u0000-\u001f\u007f]/.test(submission)) {
    throw new ToolError('submission must be one directory name under submissions/, for example "01"');
  }
  const target = await locate(root, `submissions/${submission}/submission.json`);
  if (!target.exists) throw new ToolError(`no such file: submissions/${submission}/submission.json`);
  if (!(await lstat(target.path)).isFile()) throw new ToolError(`not a regular file: submissions/${submission}/submission.json`);
  requirePython(python);
  const workbench = join(root, 'workbench');
  const childEnv = { ...env, PYTHONPATH: [workbench, env?.PYTHONPATH].filter(Boolean).join(':') };
  // One `--option=value` argument each, so a directory name that starts with "-" stays a value for argparse.
  const run = await capture(python, ['-m', 'harness.curator.validate', `--workspace=${root}`, `--submission=${submission}`],
    { cwd: workbench, env: childEnv, timeoutSeconds, limit: VALIDATOR_OUTPUT_BYTES });
  const failed = reason => ({ ...textResult(`validation could not run: ${reason}`, true), validation: null });
  if (run.error) return failed(run.error.code ?? 'error');
  if (run.timedOut) return failed(`timed out after ${timeoutSeconds} s`);
  if (run.truncated) return failed(`the validator wrote more than ${VALIDATOR_OUTPUT_BYTES} bytes`);
  if (run.code !== 0) {
    const detail = run.stderr.trim().split('\n').at(-1)?.slice(0, 2000) || `exit code ${run.code}`;
    return failed(detail);
  }
  let validation;
  try { validation = validationShape(JSON.parse(run.stdout)); } catch { validation = null; }
  if (!validation || validation.submission !== submission) return failed('the validator returned an unexpected result');
  return { ...textResult(formatValidation(validation)), validation };
}
