#!/usr/bin/env python3
"""Regenera MusicXML, SVGs e timing.json de partituras existentes.

Exemplos (executar na raiz do projeto):
    python3 regenerate.py hino-134
    python3 regenerate.py hinos/bb/hino-175
    python3 regenerate.py assets/music/hinos/bb/coro-1
    python3 regenerate.py hino-134 hino-175 coro-1

O arquivo score.mscz é a origem e NUNCA é substituído.
Não modifica Markdown, PDFs, outros arquivos, Git nem dist/.
Requer os módulos do projeto: musicxml_audio, scripts.score_timing e score_catalog.
"""

import argparse
import base64
import binascii
from bisect import bisect_right
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
MUSIC = ROOT / 'assets' / 'music'
SVG_NAME = re.compile(r'^score-[1-9][0-9]*\.svg$')


def use_project_venv():
    """Mesmo comportamento de criar_licao.py em projetos com .venv."""
    venv = ROOT / '.venv'
    python = venv / 'bin' / 'python'
    if (importlib.util.find_spec('markdown') is None
            and python.is_file()
            and Path(sys.prefix).resolve() != venv.resolve()):
        os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])


def find_directory(argument):
    """Aceita pasta pelo nome ou caminho relativo a assets/music, ou à raiz."""
    value = Path(argument).expanduser()
    if value.is_absolute():
        options = [value]
    else:
        options = [ROOT / value, MUSIC / value, ROOT / 'assets' / value]
        if len(value.parts) == 1:
            # Nome isolado: localiza o diretório sem presumir hinos/bb.
            options.extend(path for path in MUSIC.rglob(value.name) if path.is_dir())

    matches = []
    for option in options:
        resolved = option.resolve()
        if resolved.is_dir() and resolved.is_relative_to(MUSIC.resolve()) and resolved not in matches:
            matches.append(resolved)
    if not matches:
        raise ValueError(f"Pasta não encontrada dentro de assets/music: {argument!r}")
    if len(matches) > 1:
        names = '\n  '.join(str(p.relative_to(ROOT)) for p in matches)
        raise ValueError(f"Nome ambíguo {argument!r}. Informe um caminho mais completo:\n  {names}")
    return matches[0]


def get_musescore(explicit):
    executable = (explicit or os.environ.get('MUSESCORE')
                  or shutil.which('musescore') or shutil.which('mscore'))
    if not executable:
        candidate = Path.home() / 'bin' / 'musescore'
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        raise ValueError('MuseScore não encontrado. Informe --musescore /caminho/do/executavel.')
    return executable


def read_tempo(directory, explicit):
    """Respeita o Tempo do cadastro, quando existir, como faz criar_licao.py."""
    if explicit is not None:
        return explicit
    key = directory.relative_to(MUSIC)
    markdown = ROOT / 'partituras' / key.with_suffix('.md')
    if markdown.is_file():
        # Metadados do cadastro ficam antes da primeira linha em branco.
        header = re.split(r'\r?\n[ \t]*\r?\n', markdown.read_text(encoding='utf-8'), maxsplit=1)[0]
        match = re.search(r'^Tempo:[ \t]*(.+?)[ \t]*$', header, re.I | re.M)
        if match:
            try:
                return float(match.group(1))
            except ValueError as error:
                raise ValueError(f'Tempo inválido em {markdown}: {match.group(1)!r}') from error
    return None


def synchronize_media(media, sequence):
    """Sincronização original de criar_licao.py (sem escalonar artificialmente tempos)."""
    reported = float(media['metadata']['duration'])
    duration = sequence['duration']
    if not all(math.isfinite(value) and value > 0 for value in (reported, duration)):
        raise ValueError('MuseScore e MusicXML devem informar durações finitas e positivas.')
    normalized = copy.deepcopy(media)
    trees, events, times = {}, {}, {}
    try:
        for field in ('mposXML', 'sposXML'):
            tree = ET.fromstring(base64.b64decode(media[field], validate=True))
            trees[field] = tree
            events[field] = tree.findall('events/event')
            times[field] = [float(e.attrib['position']) / 1000 for e in events[field]]
            if (not times[field]
                    or any(not math.isfinite(t) or t < 0 for t in times[field])
                    or times[field] != sorted(times[field])):
                raise ValueError('eventos ausentes, inválidos ou fora de ordem')
        measures = sequence['measureStarts']
        segments = sequence['cursorEvents']
        if len(events['sposXML']) > len(segments):
            elements = {e.attrib['id']: e for e in trees['sposXML'].findall('elements/element')}
            empty = [event for event in events['sposXML']
                     if float(elements[event.attrib['elid']].attrib['sx']) == 0]
            if len(events['sposXML']) - len(empty) == len(segments):
                parent = trees['sposXML'].find('events')
                for event in empty:
                    parent.remove(event)
                events['sposXML'] = parent.findall('event')
                times['sposXML'] = [float(e.attrib['position']) / 1000 for e in events['sposXML']]
        if len(events['mposXML']) != len(measures) or len(events['sposXML']) != len(segments):
            raise ValueError('quantidade de compassos ou posições diferente entre MuseScore e MusicXML')
        if [m.get('visit', m['measure']) for m in measures] != list(range(1, len(measures) + 1)):
            raise ValueError('partes com compassos desalinhados não são suportadas')
        measure_elements = {e.attrib['id'] for e in trees['mposXML'].findall('elements/element')}
        for index, event in enumerate(events['mposXML']):
            if (event.attrib['elid'] != str(measures[index]['measure'] - 1)
                    or event.attrib['elid'] not in measure_elements):
                raise ValueError('percurso de compassos diferente entre MuseScore e MusicXML')
        for time, segment in zip(times['sposXML'], segments):
            visit = bisect_right(times['mposXML'], time)
            if (not visit or measures[visit - 1]['measure'] != segment['measure']
                    or segment.get('visit', visit) != visit):
                raise ValueError('posição associada a um compasso diferente no MusicXML')
        max_difference = max(abs(old - event['time']) for old, event in zip(times['sposXML'], segments))
        for field, expected in [('mposXML', measures), ('sposXML', segments)]:
            for event, position in zip(events[field], expected):
                event.set('position', f"{position['time'] * 1000:.3f}")
            normalized[field] = base64.b64encode(ET.tostring(trees[field], encoding='utf-8')).decode('ascii')
    except (binascii.Error, ET.ParseError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise ValueError(f'Não foi possível sincronizar o cursor: {error}. Nenhum ajuste proporcional foi aplicado.') from error
    normalized['metadata']['duration'] = duration
    return normalized, reported, max_difference


def export_musescore(executable, source, arguments):
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    try:
        completed = subprocess.run([str(executable), *arguments, str(source)],
                                   capture_output=True, env=env, timeout=180, check=True)
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors='replace')[-1500:]
        raise ValueError(f'MuseScore falhou: {detail}') from error
    except subprocess.TimeoutExpired as error:
        raise ValueError('MuseScore excedeu 180 segundos. Arquivos anteriores preservados.') from error
    return completed.stdout


def apply_generated(stage, directory):
    """Instala só exports gerados, com rollback se a substituição falhar."""
    generated = {file.name: file for file in stage.iterdir() if file.is_file()}
    expected = {'score.musicxml', 'timing.json'}
    if not expected.issubset(generated) or not any(SVG_NAME.fullmatch(n) for n in generated):
        raise ValueError('Exportação incompleta; nada foi substituído.')
    if any(name not in expected and not SVG_NAME.fullmatch(name) for name in generated):
        raise ValueError('Exportação contém arquivos inesperados; nada foi substituído.')

    old_svgs = {p.name for p in directory.iterdir() if p.is_file() and SVG_NAME.fullmatch(p.name)}
    names = set(generated) | old_svgs
    backup = stage.parent / 'anteriores'
    backup.mkdir()
    moved_old = []
    placed_new = []
    try:
        # Guarda cada arquivo antigo antes de instalar qualquer novo.
        for name in sorted(names):
            destination = directory / name
            if destination.is_symlink() or (destination.exists() and not destination.is_file()):
                raise ValueError(f'Destino não é um arquivo regular: {destination}')
            if destination.exists():
                os.replace(destination, backup / name)
                moved_old.append(name)
        for name, source in sorted(generated.items()):
            os.replace(source, directory / name)
            placed_new.append(name)
    except Exception:
        for name in placed_new:
            (directory / name).unlink(missing_ok=True)
        for name in reversed(moved_old):
            os.replace(backup / name, directory / name)
        raise
    return len(old_svgs - set(generated))


def regenerate(directory, executable, explicit_tempo):
    from musicxml_audio import parse_musicxml
    from scripts.score_timing import convert_media
    from score_catalog import validate_timing

    source = directory / 'score.mscz'
    if not source.is_file() or source.is_symlink():
        raise ValueError(f'Arquivo original não encontrado: {source}')
    tempo = read_tempo(directory, explicit_tempo)
    print(f'\nRegenerando {directory.relative_to(ROOT)}', flush=True)

    # A geração acontece fora dos arquivos publicados. Mesmo o rollback
    # de substituições individuais preserva os arquivos existentes.
    with tempfile.TemporaryDirectory(prefix='.regenerate-', dir=directory) as temporary:
        temp = Path(temporary)
        staged = temp / 'gerados'
        staged.mkdir()
        target_xml = staged / 'score.musicxml'

        print('  Exportando MusicXML...', flush=True)
        export_musescore(executable, source, ['-o', str(target_xml)])
        if not target_xml.is_file() or target_xml.stat().st_size == 0:
            raise ValueError('MuseScore não gerou score.musicxml.')
        sequence = parse_musicxml(target_xml, tempo, include_cursor=True)

        print('  Gerando páginas SVG e sincronização do cursor...', flush=True)
        media = json.loads(export_musescore(executable, source, ['--score-media']))
        normalized, reported, difference = synchronize_media(media, sequence)
        svgs, timing = convert_media(normalized)
        validate_timing(timing, len(svgs))
        if not svgs:
            raise ValueError('Nenhuma página SVG foi gerada.')
        for index, svg in enumerate(svgs, 1):
            if not svg:
                raise ValueError(f'Página SVG {index} está vazia.')
            (staged / f'score-{index}.svg').write_bytes(svg)
        (staged / 'timing.json').write_text(
            json.dumps(timing, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')

        removed = apply_generated(staged, directory)

    print(f'  Pronto: {len(svgs)} página(s), {sequence["duration"]:g}s.', flush=True)
    print(f'  Cursor sincronizado; diferença máxima anterior: {difference:.6f}s.', flush=True)
    if removed:
        print(f'  {removed} SVG(s) antigo(s) excedente(s) removido(s).', flush=True)
    if abs(reported - sequence['duration']) > 0.05:
        print('  Duração ajustada pela notação do MusicXML, sem escalonamento proporcional.', flush=True)
    # Uma alteração de paginação pode exigir revisão manual dos metadados.
    md = ROOT / 'partituras' / directory.relative_to(MUSIC).with_suffix('.md')
    if md.is_file():
        header = re.split(r'\r?\n[ \t]*\r?\n', md.read_text(encoding='utf-8'), maxsplit=1)[0]
        match = re.search(r'^Pages:[ \t]*(\d+)[ \t]*$', header, re.I | re.M)
        if match and int(match.group(1)) != len(svgs):
            print(f'  ATENÇÃO: {md.relative_to(ROOT)} informa Pages: {match.group(1)}, '
                  f'mas foram geradas {len(svgs)} página(s). Revise o cadastro.', flush=True)
    return len(svgs)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('diretorios', nargs='+', help='Nome da pasta ou caminho dentro de assets/music')
    parser.add_argument('--musescore', help='Caminho do executável MuseScore (ou AppImage)')
    parser.add_argument('--tempo', type=float, help='Andamento em semínimas/minuto, quando necessário')
    args = parser.parse_args()
    use_project_venv()

    try:
        if not MUSIC.is_dir():
            raise ValueError(f'Estrutura ausente: {MUSIC}')
        executable = get_musescore(args.musescore)
        if args.tempo is not None and (not math.isfinite(args.tempo) or args.tempo <= 0):
            raise ValueError('--tempo deve ser um número positivo e finito.')
        directories = []
        for argument in args.diretorios:
            directory = find_directory(argument)
            if directory not in directories:
                directories.append(directory)
    except (ValueError, OSError) as error:
        parser.exit(2, f'Erro: {error}\n')

    errors = 0
    for directory in directories:
        try:
            regenerate(directory, executable, args.tempo)
        except (ImportError, ValueError, OSError, KeyError, TypeError, ET.ParseError,
                subprocess.SubprocessError) as error:
            errors += 1
            print(f'  ERRO ({directory.relative_to(ROOT)}): {error}', file=sys.stderr, flush=True)
    if errors:
        parser.exit(1, f'\n{errors} pasta(s) com erro. As demais, se concluídas, foram atualizadas.\n')
    print(f'\nConcluído: {len(directories)} pasta(s). Nenhum commit ou build foi executado.')


if __name__ == '__main__':
    main()
