import { closeSync, fstatSync, openSync, readFileSync, readSync } from 'node:fs';
import { createInterface } from 'node:readline';

// Isolated helper process for reading `--knowledge-updates` and its listed version files.
// Running these reads outside the host's own libuv threadpool lets the host terminate a
// stalled filesystem read on settlement without blocking CLI exit.
const input = createInterface({input:process.stdin, crlfDelay:Infinity});
input.on('line', line => {
  if (!line) return;
  let request;
  try { request = JSON.parse(line); } catch { return; }
  const {id, path, offset, limit} = request;
  try {
    let buffer;
    if (offset == null) {
      buffer = readFileSync(path);
    } else {
      const fd = openSync(path, 'r');
      try {
        const remaining = fstatSync(fd).size - offset;
        const length = Math.min(Math.max(remaining, 0), limit);
        if (length <= 0) buffer = Buffer.alloc(0);
        else {
          const data = Buffer.alloc(length);
          const bytesRead = readSync(fd, data, 0, length, offset);
          buffer = data.subarray(0, bytesRead);
        }
      } finally { closeSync(fd); }
    }
    process.stdout.write(JSON.stringify({id, ok:true, data:buffer.toString('base64')}) + '\n');
  } catch {
    process.stdout.write(JSON.stringify({id, ok:false}) + '\n');
  }
});
