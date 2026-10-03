"""Version local asset URLs and expose a stable, content-derived release ID."""
from hashlib import sha256
from pathlib import Path
import json,re
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit


def finish_build(out: Path, base: str):
    assets=out/'assets'
    # The browser caches imported modules independently of their entry script.
    music=assets/'music.js'
    source=music.read_text()
    for dependency in ('music-timing.mjs','music-synth.mjs'):
        module=assets/dependency
        if module.is_file():
            digest=sha256(module.read_bytes()).hexdigest()[:16]
            source=source.replace(f"'./{dependency}'",f"'./{dependency}?v={digest}'")
    music.write_text(source)
    hashes={p.relative_to(out).as_posix():sha256(p.read_bytes()).hexdigest()[:16]
            for p in assets.rglob('*') if p.is_file()}
    prefix=f'{base}/assets/'
    def version_url(match):
        url=match.group(2);parts=urlsplit(url)
        if not parts.path.startswith(prefix) or parts.scheme or parts.netloc:return match.group(0)
        key=parts.path[len(base)+1:]
        if key not in hashes:return match.group(0)
        query=dict(parse_qsl(parts.query));query['v']=hashes[key]
        revised=urlunsplit(('', '', parts.path, urlencode(query), parts.fragment))
        return f'{match.group(1)}="{revised}"'
    pages=sorted(out.rglob('*.html'))
    for p in pages:
        p.write_text(re.sub(r'\b(href|src|data-timing|data-sequence)="([^"]+)"',version_url,p.read_text()))
    digest=sha256()
    for p in sorted(out.rglob('*')):
        if p.is_file():
            digest.update(p.relative_to(out).as_posix().encode());digest.update(b'\0');digest.update(p.read_bytes())
    version=digest.hexdigest()[:20]
    for p in pages:p.write_text(p.read_text().replace('__CLAVESOL_VERSION__',version))
    (out/'version.json').write_text(json.dumps({'version':version}))
