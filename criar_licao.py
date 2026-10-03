#!/usr/bin/env python3
"""Prepara uma lição independente para o Clave Sol a partir de um .mscz."""
import argparse
import base64
import binascii
from bisect import bisect_right
import importlib.util
import copy
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent


def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')


def one_line(value):
    return ' '.join(str(value).split())


def synchronize_media(media, sequence):
    """Use the same notated clock for cursor and sound, after structural matching."""
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
            if not times[field] or any(not math.isfinite(t) or t < 0 for t in times[field]) or times[field] != sorted(times[field]):
                raise ValueError('eventos ausentes, inválidos ou fora de ordem')
        measures = sequence['measureStarts']
        segments = sequence['cursorEvents']
        if len(events['mposXML']) != len(measures) or len(events['sposXML']) != len(segments):
            raise ValueError('quantidade de compassos ou posições diferente entre MuseScore e MusicXML')
        if [m['measure'] for m in measures] != list(range(1, len(measures) + 1)):
            raise ValueError('partes com compassos desalinhados não são suportadas')
        measure_elements = {e.attrib['id'] for e in trees['mposXML'].findall('elements/element')}
        for index, event in enumerate(events['mposXML']):
            if event.attrib['elid'] != str(index) or event.attrib['elid'] not in measure_elements:
                raise ValueError('ordem de compassos incompatível com reprodução linear')
        for time, segment in zip(times['sposXML'], segments):
            if bisect_right(times['mposXML'], time) != segment['measure']:
                raise ValueError('posição associada a um compasso diferente no MusicXML')
        max_difference = max(abs(old - event['time']) for old, event in zip(times['sposXML'], segments))
        for field, expected in [('mposXML', measures), ('sposXML', segments)]:
            for event, position in zip(events[field], expected):
                event.set('position', f"{position['time'] * 1000:.3f}")
            normalized[field] = base64.b64encode(ET.tostring(trees[field], encoding='utf-8')).decode('ascii')
    except (binascii.Error, ET.ParseError, ValueError, KeyError, TypeError) as error:
        raise ValueError(f'Não foi possível sincronizar o cursor: {error}. Nenhum ajuste proporcional foi aplicado.') from error
    normalized['metadata']['duration'] = duration
    return normalized, reported, max_difference


def prepare(source, method=None, *, msa=False, hinos=False, root=ROOT, slug=None, title=None, lesson=None,
            method_title=None, executable=None, update=False, pdf=False, tempo=None, hinario=None):
    from score_catalog import load_catalog, safe_key, validate_timing, read_markdown
    from musicxml_audio import parse_musicxml
    from scripts.score_timing import convert_media

    source = Path(source).expanduser().resolve()
    root = Path(root).resolve()
    if not source.is_file() or source.suffix.lower() != '.mscz':
        raise ValueError('Informe o caminho de um arquivo .mscz existente, contendo somente esta lição.')
    if sum((bool(method), msa, hinos)) > 1:
        raise ValueError('Escolha --metodo, --msa ou --hinos; não ambos nem múltiplos destinos.')
    if hinario and (not hinos or hinario not in ('bb', 'do', 'eb', 'outros')):
        raise ValueError('--hinario exige --hinos e deve ser bb, do, eb ou outros.')
    category = f'hinos/{hinario}' if hinos and hinario else 'hinos' if hinos else 'msa' if msa else None
    if category and method_title:
        raise ValueError('--nome-metodo só pode ser usado com métodos.')
    if not category:
        method = safe_key(method)
    slug = safe_key(slug or slugify(source.stem))
    if (method and '/' in method) or '/' in slug:
        raise ValueError('Método e lição devem ser nomes simples, sem barras.')
    key = f'{category}/{slug}' if category else f'metodos/{method}/{slug}'
    md = root / 'partituras' / f'{key}.md'
    if md.exists() and not md.is_file():
        raise ValueError(f'O cadastro deve ser um arquivo Markdown, não uma pasta: {md}')
    existing_meta = read_markdown(md)[0] if md.is_file() else {}
    asset_key = safe_key(existing_meta.get('assets', f'music/{key}'))
    assets = root / 'assets' / asset_key
    if not assets.resolve().is_relative_to((root / 'assets').resolve()):
        raise ValueError('Assets deve ficar dentro da pasta assets do projeto.')
    for path in (md, assets):
        if not path.resolve().is_relative_to(root):
            raise ValueError('O destino não pode apontar para fora do projeto.')
    if (md.exists() or assets.exists()) and not update:
        raise ValueError(f'A lição {key} já existe. Use --atualizar para substituir os exports e preservar seu texto.')
    if assets.exists() and not assets.is_dir():
        raise ValueError(f'O destino não é uma pasta: {assets}')
    if md.exists() and not md.is_file():
        raise ValueError(f'O cadastro deve ser um arquivo Markdown, não uma pasta: {md}')
    if source.is_relative_to(assets.resolve()):
        raise ValueError('Use o original fora da pasta de assets; ela será substituída na atualização.')
    tempo = tempo if tempo is not None else existing_meta.get('tempo')
    if any(existing_meta.get(k) for k in ('pages', 'measures')) and not update:
        raise ValueError('Use --atualizar para renovar o cadastro existente.')
    pdf = pdf or (assets / 'score.pdf').is_file()
    executable = executable or os.environ.get('MUSESCORE') or shutil.which('musescore') or shutil.which('mscore')
    if not executable:
        candidate = Path.home() / 'bin/musescore'
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        raise ValueError('MuseScore não encontrado. Informe --musescore /caminho/do/executavel.')

    # Stage everything before changing the working tree; no git command is executed.
    with tempfile.TemporaryDirectory(prefix='clavesol-') as directory:
        stage = Path(directory)
        output = stage / 'assets' / asset_key
        output.mkdir(parents=True)
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')

        def export(arguments):
            try:
                result = subprocess.run([str(executable), *arguments, str(source)],
                                        capture_output=True, env=env, timeout=180, check=True)
            except subprocess.CalledProcessError as error:
                raise ValueError('MuseScore falhou: ' + error.stderr.decode(errors='replace')[-1500:]) from error
            except subprocess.TimeoutExpired as error:
                raise ValueError('MuseScore excedeu 180 segundos. Nenhum arquivo da lição foi alterado.') from error
            return result.stdout

        print('Exportando MusicXML…', flush=True)
        export(['-o', str(output / 'score.musicxml')])
        sequence = parse_musicxml(output / 'score.musicxml', tempo, include_cursor=True)
        print('Exportando páginas e cursor…', flush=True)
        media = json.loads(export(['--score-media']))
        normalized, reported, cursor_difference = synchronize_media(media, sequence)
        svgs, timing = convert_media(normalized)
        validate_timing(timing, len(svgs))
        for i, svg in enumerate(svgs, 1):
            (output / f'score-{i}.svg').write_bytes(svg)
        (output / 'timing.json').write_text(json.dumps(timing, separators=(',', ':')), encoding='utf-8')
        shutil.copy2(source, output / 'score.mscz')
        if pdf:
            export(['-o', str(output / 'score.pdf')])
        xml = ET.parse(output / 'score.musicxml').getroot()
        composer = next((e.text for e in xml.iter('creator') if e.get('type') == 'composer' and e.text), '')
        instrument = next((e.text for e in xml.iter('part-name') if e.text), '')
        if md.exists():
            meta, _ = read_markdown(md)
            original = md.read_text(encoding='utf-8')
            header, separator, body = original, '\n\n', ''
            split = re.split(r'\r?\n[ \t]*\r?\n', original, maxsplit=1)
            if len(split) == 2:
                header, body = split
            updates = {'playback': 'generated', 'cursor': 'true', 'draft': 'false'}
            if 'pages' in meta: updates['pages'] = str(len(svgs))
            if 'measures' in meta: updates['measures'] = str(max(e['measure'] for e in timing['events']))
            if title: updates['title'] = one_line(title)
            if lesson: updates['lesson'] = str(lesson)
            if tempo: updates['tempo'] = str(tempo)
            lines = [line for line in header.splitlines() if line.split(':', 1)[0].lower() not in updates]
            lines += [f'{name.title()}: {value}' for name, value in updates.items()]
            markdown = '\n'.join(lines) + separator + body
        else:
            title = title or source.stem.replace('_', ' ')
            markdown = f'Title: {one_line(title)}\nAuthor: {one_line(composer)}\nInstrument: {one_line(instrument)}\n'
            if lesson: markdown += f'Lesson: {lesson}\n'
            if tempo: markdown += f'Tempo: {tempo}\n'
            markdown += 'Playback: generated\nCursor: true\nDraft: false\n\n'
        staged_md = stage / 'partituras' / f'{key}.md'
        staged_md.parent.mkdir(parents=True)
        staged_md.write_text(markdown, encoding='utf-8')
        load_catalog(stage)
        # Check the complete catalog with this replacement, without touching dist/.
        validation = stage / 'validation'
        for tree in ('partituras', 'assets'):
            if (root / tree).exists():
                shutil.copytree(root / tree, validation / tree)
        vassets = validation / 'assets' / asset_key
        if vassets.exists(): shutil.rmtree(vassets)
        shutil.copytree(output, vassets)
        vmd = validation / 'partituras' / f'{key}.md'
        vmd.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged_md, vmd)
        load_catalog(validation)
        # Preserve unrelated files when replacing generated exports.
        if assets.exists():
            for file in assets.iterdir():
                if file.name not in {'score.musicxml','score.mscz','score.pdf','score.mp3','score.ogg','sequence.json','timing.json'} and not re.fullmatch(r'score-[0-9]+\.svg', file.name):
                    if file.is_dir(): shutil.copytree(file, output / file.name)
                    else: shutil.copy2(file, output / file.name)
        assets.parent.mkdir(parents=True, exist_ok=True)
        md.parent.mkdir(parents=True, exist_ok=True)
        backup = stage / 'previous-assets'
        old_md = md.read_bytes() if md.exists() else None
        try:
            if assets.exists(): shutil.move(str(assets), backup)
            shutil.copytree(output, assets)
            md.write_text(markdown, encoding='utf-8')
        except Exception:
            if assets.exists(): shutil.rmtree(assets)
            if backup.exists(): shutil.move(str(backup), assets)
            if old_md is not None: md.write_bytes(old_md)
            elif md.exists(): md.unlink()
            raise
        indices = [(md.parent/'_index.md', 'Hinos' if hinos else 'MSA')] if category else [
            (root/'partituras/metodos/_index.md', 'Métodos'),
            (md.parent/'_index.md', method_title or method.replace('-', ' ').title())]
        if hinos and hinario:
            indices = [(root/'partituras/hinos/_index.md', 'Hinos'),
                       (md.parent/'_index.md', {'bb':'Bb', 'do':'C', 'eb':'Eb', 'outros':'Outros'}[hinario])]
        for path, heading in indices:
            if not path.exists(): path.write_text(f'Title: {one_line(heading)}\n', encoding='utf-8')
        print(f'Pronto: {key}\n{len(svgs)} página(s), {sequence["duration"]:g}s, {sequence["marking"]}')
        print(f"Cursor conferido: {len(sequence['cursorEvents'])} posições no mesmo relógio das notas; "
              f"diferença máxima da exportação original: {cursor_difference:.6f}s.")
        if abs(reported - sequence['duration']) > .05:
            print(f"Duração final do estudo: {sequence['duration']:g}s (MuseScore: {reported:g}s). "
                  'Sem comprimir ou esticar os tempos da lição.')
        return key


def lesson_paths(root, key):
    from score_catalog import read_markdown
    meta, _ = read_markdown(Path(root) / 'partituras' / f'{key}.md')
    paths = [f'partituras/{key}.md', 'assets/' + meta.get('assets', f'music/{key}')]
    parent = key.rsplit('/', 1)[0]
    if key.startswith('hinos/') and len(key.split('/')) == 3:
        paths.append('partituras/hinos/_index.md')
    if key.startswith('metodos/'):
        paths.append('partituras/metodos/_index.md')
    paths.append(f'partituras/{parent}/_index.md')
    return paths


def commit_lesson(root, paths, message):
    subprocess.run(['git', 'add', '--', *paths], cwd=root, check=True)
    changed = subprocess.run(['git', 'diff', '--cached', '--quiet', '--', *paths], cwd=root)
    if changed.returncode == 1:
        subprocess.run(['git', 'commit', '--only', '-m', message, '--', *paths], cwd=root, check=True)
    elif changed.returncode != 0:
        raise ValueError('Não foi possível verificar as alterações para o commit.')


def main():
    if importlib.util.find_spec('markdown') is None:
        interpreter = ROOT / '.venv/bin/python'
        if interpreter.is_file() and Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
            os.execv(str(interpreter), [str(interpreter), str(Path(__file__).resolve()), *sys.argv[1:]])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arquivo', type=Path, help='Caminho completo da lição.mscz')
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument('--metodo', help='Pasta do método, por exemplo domingos-pecci')
    destination.add_argument('--msa', action='store_true', help='Importa diretamente na categoria MSA')
    destination.add_argument('--hinos', action='store_true', help='Importa diretamente na categoria Hinos')
    parser.add_argument('--hinario', choices=['bb','do','eb','outros'], help='Coleção de hinos: Bb, C (do), Eb ou Outros; exige --hinos')
    parser.add_argument('--slug', help='Nome da lição no site; padrão: nome do .mscz normalizado')
    parser.add_argument('--titulo', help='Título da lição')
    parser.add_argument('--nome-metodo', help='Título de uma coleção nova')
    parser.add_argument('--licao', type=int, help='Número positivo para ordenar as lições')
    parser.add_argument('--musescore', help='Executável do MuseScore')
    parser.add_argument('--atualizar', action='store_true', help='Substitui exports existentes e preserva o texto do Markdown')
    parser.add_argument('--commit', action='store_true', help='Cria commit somente dos arquivos desta lição; depois basta git push')
    parser.add_argument('--pdf', action='store_true', help='Exporta também PDF para download')
    parser.add_argument('--tempo', type=float, help='Semínimas/minuto, somente se o MusicXML não informar andamento')
    args = parser.parse_args()
    method = args.metodo
    if (args.msa or args.hinos) and args.nome_metodo:
        parser.error('--nome-metodo só pode ser usado com métodos.')
    if not method and not args.msa and not args.hinos:
        if not sys.stdin.isatty():
            parser.error('Informe --metodo, --msa ou --hinos para execução sem perguntas.')

        available = sorted(
            p.name for p in (ROOT / 'partituras/metodos').glob('*')
            if p.is_dir() and p.name != 'assets'
        )
        if not available:
            parser.error('Nenhum método disponível. Informe --metodo para criar ou selecionar um método.')

        print('Métodos disponíveis:')
        for index, name in enumerate(available, 1):
            print(f'  {index}) {name}')

        choice = input('Digite o número do método: ').strip()
        if not choice:
            parser.error('É obrigatório informar o número do método.')
        if not choice.isdigit():
            parser.error('Informe somente o número correspondente ao método desejado.')

        index = int(choice)
        if not 1 <= index <= len(available):
            parser.error(f'Número de método inválido. Escolha um valor entre 1 e {len(available)}.')

        method = available[index - 1]
    if args.licao is not None and args.licao <= 0: parser.error('--licao deve ser positivo')
    try:
        key = prepare(args.arquivo, method, msa=args.msa, hinos=args.hinos, slug=args.slug, title=args.titulo,
                      method_title=args.nome_metodo, lesson=args.licao, executable=args.musescore,
                      update=args.atualizar, pdf=args.pdf, tempo=args.tempo, hinario=args.hinario)
    except ImportError:
        parser.exit(1, 'Ative o ambiente do projeto: source .venv/bin/activate\nDepois: pip install -r requirements.txt\n')
    except (ValueError, OSError, KeyError, ET.ParseError) as error:
        parser.exit(1, f'Não foi possível preparar a lição: {error}\n')
    paths = lesson_paths(ROOT, key)
    if args.commit:
        try:
            commit_lesson(ROOT, paths, f'Prepara lição {key}')
        except (subprocess.CalledProcessError, ValueError) as error:
            parser.exit(1, f'Arquivos preparados, mas o commit não foi concluído: {error}\nConfira git status.\n')
        print('\nPreparado e commitado. Para publicar: git push origin main')
        return
    print('\nRevise e publique, na raiz do projeto:')
    print('git add ' + ' '.join(paths))
    print(f'git commit -m "Adiciona ou atualiza {key}"\ngit push origin main')


if __name__ == '__main__':
    main()
