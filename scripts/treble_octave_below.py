#!/usr/bin/env python3
"""Change the Bb bass clefs to G8vb without changing sounding pitches.

Stage all exports and compare audio/lyrics before --apply touches source assets.
The staging directory must be outside the repository; it also holds backups.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from criar_licao import synchronize_media
from musicxml_audio import parse_musicxml
from score_catalog import read_markdown, load_catalog
from scripts.score_timing import convert_media

CLEF = re.compile(rb'<(defaultClef|concertClefType|transposingClefType)>F</\1>')


def transform_archive(source, destination):
    """Only change native clef types; never transpose native Note/pitch values."""
    count = 0
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, 'w') as changed:
        for info in original.infolist():
            data = original.read(info.filename)
            if info.filename.endswith('.mscx'):
                data, n = CLEF.subn(lambda m: b'<' + m[1] + b'>G8vb</' + m[1] + b'>', data)
                count += n
            changed.writestr(info, data)
    return count


def media_musicxml(media):
    packed = base64.b64decode(media['mxml'], validate=True)
    with zipfile.ZipFile(io.BytesIO(packed)) as archive:
        container = ET.fromstring(archive.read('META-INF/container.xml'))
        entry = next(e.attrib['full-path'] for e in container.iter() if e.tag.rsplit('}', 1)[-1] == 'rootfile')
        return archive.read(entry)


def lyric_text(root):
    return [[(e.tag, (e.text or '').strip()) for e in lyric] for lyric in root.iter('lyric')]


def prepare(folder, stage, executable):
    destination = stage / 'exports' / folder.name
    destination.mkdir(parents=True, exist_ok=True)
    count = transform_archive(folder / 'score.mscz', destination / 'score.mscz')
    if not count:
        return {'hymn': folder.name, 'changed': False}
    meta, _ = read_markdown(ROOT / 'partituras/hinos/bb' / (folder.name + '.md'))
    before = parse_musicxml(folder / 'score.musicxml', meta.get('tempo'), include_cursor=True)
    # SVGs stay vector-based; 72 dpi avoids enormous unused preview rasters.
    result = subprocess.run([executable, '-r', '72', '--score-media', str(destination / 'score.mscz')],
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'), capture_output=True, timeout=180)
    (destination / 'export.log').write_bytes(result.stderr)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors='replace')[-1200:])
    media = json.loads(result.stdout)
    (destination / 'score.musicxml').write_bytes(media_musicxml(media))
    after = parse_musicxml(destination / 'score.musicxml', meta.get('tempo'), include_cursor=True)
    if before != after:
        differing = [k for k in before.keys() | after.keys() if before.get(k) != after.get(k)]
        raise ValueError('Audio/cursor clock changed: ' + ', '.join(differing))
    old_xml = ET.parse(folder / 'score.musicxml').getroot()
    new_xml = ET.parse(destination / 'score.musicxml').getroot()
    if lyric_text(old_xml) != lyric_text(new_xml):
        raise ValueError('Lyrics changed during native export')
    old_clefs, new_clefs = list(old_xml.iter('clef')), list(new_xml.iter('clef'))
    if len(old_clefs) != len(new_clefs):
        raise ValueError('Number of clef changes differs')
    for old, new in zip(old_clefs, new_clefs):
        if old.findtext('sign') == 'F':
            if (new.findtext('sign'), new.findtext('line'), new.findtext('clef-octave-change')) != ('G', '2', '-1'):
                raise ValueError('Expected octave-down treble clef missing')
        elif [(e.tag, e.text) for e in old] != [(e.tag, e.text) for e in new]:
            raise ValueError('An unrelated clef changed')
    normalized, _, _ = synchronize_media(media, after)
    svgs, timing = convert_media(normalized, scale=.72)
    for n, svg in enumerate(svgs, 1):
        (destination / f'score-{n}.svg').write_bytes(svg)
    (destination / 'timing.json').write_text(json.dumps(timing, separators=(',', ':')))
    (destination / 'preview.png').write_bytes(base64.b64decode(media['pngs'][0]))
    # Replace the archive's old bass-clef thumbnail with the new first page.
    archive_path = destination / 'score.mscz'
    with zipfile.ZipFile(archive_path) as z:
        entries = [(info, z.read(info.filename)) for info in z.infolist()]
    with zipfile.ZipFile(archive_path, 'w') as z:
        for info, data in entries:
            if info.filename == 'Thumbnails/thumbnail.png':
                data = (destination / 'preview.png').read_bytes()
            z.writestr(info, data)
    return {'hymn': folder.name, 'changed': True, 'clefs': count, 'pages': len(svgs),
            'notes': len(after['notes']), 'duration': after['duration'], 'audio_identical': True,
            'lyrics_identical': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--musescore', default=str(Path.home() / 'bin/musescore'))
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    stage = args.stage.resolve()
    if stage.is_relative_to(ROOT):
        parser.error('Use a staging directory outside the repository')
    if json.loads((ROOT / 'hinario.json').read_text())['collection'] != 'bb':
        parser.error('This migration is only for the Bb hymnal')
    stage.mkdir(parents=True, exist_ok=True)
    folders = sorted((ROOT / 'assets/music/hinos/bb').iterdir(), key=lambda p: int(p.name.split('-')[-1]))
    reports, failures = [], []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(prepare, p, stage, args.musescore): p for p in folders if p.is_dir()}
        for future in as_completed(futures):
            folder = futures[future]
            try:
                reports.append(future.result())
            except Exception as error:
                failures.append({'hymn': folder.name, 'error': str(error)})
                print(f'FAILED {folder.name}: {error}', flush=True)
            finished = len(reports) + len(failures)
            if finished % 25 == 0 or finished == len(futures):
                print(f'{finished}/{len(futures)} checked; {len(failures)} failures', flush=True)
    report = {'scores': sorted(reports, key=lambda r: int(r['hymn'].split('-')[-1])), 'failures': failures}
    (stage / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit('No source assets changed: resolve failed exports first.')
    if not args.apply:
        print('Staged and validated. Run with --apply to replace source assets.')
        return
    for entry in reports:
        if not entry['changed']:
            continue
        name = entry['hymn']
        source, destination = ROOT / 'assets/music/hinos/bb' / name, stage / 'exports' / name
        backup = stage / 'backup' / name
        if backup.exists():
            raise SystemExit(f'Backup already exists: {backup}')
        shutil.copytree(source, backup)
        for old in source.glob('score-*.svg'):
            old.unlink()
        for exported in destination.iterdir():
            if exported.name in {'score.mscz', 'score.musicxml', 'timing.json'} or re.fullmatch(r'score-\d+\.svg', exported.name):
                shutil.copy2(exported, source / exported.name)
        markdown = ROOT / 'partituras/hinos/bb' / (name + '.md')
        text = markdown.read_text()
        updated = re.sub(r'^([Pp]ages:\s*)\d+', lambda m: m[1] + str(entry['pages']), text, flags=re.M)
        if text != updated:
            shutil.copy2(markdown, backup / 'metadata.md')
            markdown.write_text(updated)
    load_catalog(ROOT)
    print(f'Applied {sum(r["changed"] for r in reports)} scores. Backups: {stage / "backup"}', flush=True)


if __name__ == '__main__':
    main()
