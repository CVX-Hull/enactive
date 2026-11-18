"""Static spectator assets shared by the supervised gateway and recorded viewer."""
from pathlib import Path
import re

WEB = Path(__file__).resolve().parents[1] / 'web'
PAGE_POLICY = "default-src 'self'; img-src 'self' blob:; frame-ancestors 'none'"
STATIC_PART = re.compile(r'[A-Za-z0-9_][A-Za-z0-9._-]*')
STATIC_TYPES = {'.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
                '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml',
                '.png': 'image/png', '.woff2': 'font/woff2', '.html': 'text/html; charset=utf-8'}
LIVE_MARKUP = re.compile(rb'<!-- live only -->.*?<!-- end live only -->', re.DOTALL)


def static_file(web: Path, path: str, *, recorded: bool = False) -> tuple[bytes, str] | None:
    """The page and its `app/` and `vendor/` files; nothing else under web/ is served."""
    if path == '/':
        parts = ['index.html']
    elif path.startswith(('/app/', '/vendor/')):
        parts = path[1:].split('/')
    else:
        return None
    media = STATIC_TYPES.get(Path(parts[-1]).suffix)
    if media is None or not all(STATIC_PART.fullmatch(part) for part in parts):
        return None
    candidate = web.joinpath(*parts)
    try:
        if candidate.is_symlink() or not candidate.is_file() or not candidate.resolve().is_relative_to(web.resolve()):
            return None
        data = candidate.read_bytes()
        return LIVE_MARKUP.sub(b'', data) if recorded and path == '/' else data, media
    except OSError:
        return None
