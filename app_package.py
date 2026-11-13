"""Build the app-only archive from the final, generated site assets."""
import hashlib
import json
import re
import zipfile
from pathlib import Path


def build_app_package(out, catalog, collection):
    destination = out / 'downloads'
    destination.mkdir(exist_ok=True)
    target = destination / f'cantuscaeli-{collection}.zip'
    temporary = target.with_suffix('.zip.tmp')
    manifest = {'format': 1, 'collection': collection, 'hymns': {}}
    total = 0
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=False) as archive:
            for score in sorted(catalog.scores, key=lambda score: score.key):
                hymn = Path(score.assets).name
                if not re.fullmatch(r'(hino|coro)-[1-9][0-9]*', hymn) or hymn in manifest['hymns']:
                    raise ValueError(f'Identificador inválido ou duplicado: {hymn}')
                folder = out / 'assets' / score.assets
                pages = sorted(folder.glob('score-*.svg'),
                               key=lambda path: int(path.stem.split('-')[-1]))
                if not 1 <= len(pages) <= 50 or [p.name for p in pages] != [f'score-{n}.svg' for n in range(1, len(pages)+1)]:
                    raise ValueError(f'Páginas inválidas: {hymn}')
                files = [folder / name for name in ('sequence.json', 'timing.json', 'score.musicxml')] + pages
                entries = {}
                for path in files:
                    if path.is_symlink() or not path.is_file():
                        raise ValueError(f'Arquivo ausente ou link: {path}')
                    data = path.read_bytes()
                    if not 0 < len(data) <= 24 * 1024 * 1024:
                        raise ValueError(f'Tamanho inválido: {path}')
                    total += len(data)
                    if total > 2 * 1024 * 1024 * 1024:
                        raise ValueError('Pacote excede o limite descompactado')
                    entries[path.name] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                    info = zipfile.ZipInfo(f'{hymn}/{path.name}', (2020, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, data, compresslevel=6)
                manifest['hymns'][hymn] = entries
            payload = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
            if len(payload) > 4 * 1024 * 1024:
                raise ValueError('Manifesto muito grande')
            info = zipfile.ZipInfo('manifest.json', (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload, compresslevel=6)
        if temporary.stat().st_size > 512 * 1024 * 1024:
            raise ValueError('Pacote excede o limite de download')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
