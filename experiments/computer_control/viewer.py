"""Passive candidate pixels and an explicit operator stop; no gameplay semantics."""
from __future__ import annotations

from pathlib import Path
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import re
from urllib.parse import parse_qs, urlsplit

from .protocol import read_json


def serve(run: Path, port: int = 8766) -> tuple[ThreadingHTTPServer, threading.Thread]:
    config = read_json(run / 'control.json')
    session = config['session']
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, data, kind, code=200):
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            try:
                if self.path == '/':
                    self.send(PAGE.replace('__SESSION__', session).encode(), 'text/html; charset=utf-8')
                elif self.path == '/status':
                    target = read_json(run / 'bridge/state.json')
                    status = read_json(run / 'status.json') if (run / 'status.json').exists() else {}
                    self.send(json.dumps(dict(target=target, remaining=status.get('remaining'),
                        ended=(run / 'receipt.json').exists())).encode(), 'application/json')
                elif self.path.startswith('/frame.png'):
                    name = parse_qs(urlsplit(self.path).query).get('name', [''])[0]
                    if re.fullmatch(r'frame-[1-9][0-9]*\.png', name) is None:
                        raise ValueError('Invalid frame')
                    path = run / 'bridge' / name
                    if path.is_symlink():
                        raise ValueError('Invalid frame')
                    self.send(path.read_bytes(), 'image/png')
                else:
                    self.send(b'Not found', 'text/plain', 404)
            except (OSError, ValueError, KeyError, TypeError):
                self.send(b'Target unavailable; retained history is not current control', 'text/plain', 503)

        def do_POST(self):
            if (self.path != '/pause' or self.headers.get('X-Computer-Control') != session
                    or self.headers.get('Content-Type') != 'application/json'
                    or self.headers.get('Origin') not in (None, f'http://127.0.0.1:{port}')):
                return self.send(b'Refused', 'text/plain', 403)
            (run / 'bridge/pause').touch()
            self.send(b'{"paused":true}', 'application/json')
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


PAGE = '''<!doctype html><meta charset="utf-8"><title>Computer-control proof</title>
<style>body{background:#15181d;color:#e7edf5;font:16px system-ui;max-width:1100px;margin:24px auto}img{max-width:100%;image-rendering:auto}button{padding:10px}pre{white-space:pre-wrap}</style>
<h1>Computer-control proof</h1><p>Actual target pixels. The player owns all game interpretation.</p>
<button id="pause">Pause and end this proof</button> <strong id="state">Connecting</strong>
<p id="resources"></p><img id="frame" alt="Last retained target capture"><p id="capture"></p>
<button id="download">Download local frame timing</button><pre id="error"></pre>
<script>
let last=null, busy=false, timings=[];
const frame=document.querySelector('#frame');
async function update(){try{let s=await(await fetch('/status')).json();
 document.querySelector('#state').textContent=s.ended?'Stopped · retained history':s.target.paused?'Paused · no rearm':'Owned target · remote control active';
 document.querySelector('#error').textContent=s.target.error||'';
 document.querySelector('#resources').textContent=s.remaining?JSON.stringify(s.remaining):'No operation yet';
 let c=s.target.latest_frame;if(c&&c.capture_id!==last&&!busy){last=c.capture_id;busy=true;frame.onload=()=>{timings.push({...c,dom_loaded_ms:Date.now()});if(timings.length>8192)timings.shift();busy=false;};frame.onerror=()=>{busy=false;};frame.src='/frame.png?name='+encodeURIComponent(c.name);document.querySelector('#capture').textContent='Capture '+last+' · presented '+new Date(c.presented_ms).toISOString();}
 }catch(e){document.querySelector('#state').textContent='Disconnected · retained history';}setTimeout(update,250);}
 document.querySelector('#pause').onclick=()=>fetch('/pause',{method:'POST',headers:{'Content-Type':'application/json','X-Computer-Control':'__SESSION__'},body:'{}'});
 document.querySelector('#download').onclick=()=>{let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({schema:'computer-observer/1',scope:'Local DOM-load proxy, not physical paint or attention',samples:timings})],{type:'application/json'}));a.download='computer-observer-'+Date.now()+'.json';a.click();URL.revokeObjectURL(a.href);};update();
</script>'''
