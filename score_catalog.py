"""Load the sheet-music catalog from Markdown, validating before publishing."""
from dataclasses import dataclass
from pathlib import Path
import json
import math
import re
import xml.etree.ElementTree as ET

import markdown
from musicxml_audio import parse_musicxml


@dataclass
class Group:
    key: str
    title: str
    description: str = ''
    body: str = ''


@dataclass
class Score:
    key: str
    title: str
    author: str
    instrument: str
    description: str
    body: str
    assets: str
    pages: list
    downloads: list
    audio: list
    playback: str
    sequence: dict | None
    timing: bool
    measures: int
    lesson: int
    legacy: str

    @property
    def category(self):
        return self.key.split('/')[0]

    @property
    def parent(self):
        return self.key.rsplit('/', 1)[0]

    @property
    def route(self):
        return 'partituras/' + self.key


@dataclass
class Catalog:
    groups: dict
    scores: list


def read_markdown(path):
    parser = markdown.Markdown(extensions=['meta', 'fenced_code', 'tables'])
    body = parser.convert(path.read_text(encoding='utf-8'))
    return {k: ' '.join(v) for k, v in parser.Meta.items()}, body


def flag(meta, name, default=False):
    value = meta.get(name, str(default)).lower()
    if value not in ('true', 'false'):
        raise ValueError(f'{name}: use true ou false')
    return value == 'true'


def positive_int(value, name):
    if not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise ValueError(f'{name}: informe um número inteiro positivo')
    return int(value)


def safe_key(value):
    if not value or not all(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', part)
                            for part in value.split('/')):
        raise ValueError(f'Caminho inválido: {value}. Use minúsculas, números e hífens.')
    return value


def svg_size(path):
    svg = ET.parse(path).getroot()
    if svg.tag.rsplit('}', 1)[-1] != 'svg':
        raise ValueError(f'{path.name}: não é um SVG')
    view = svg.get('viewBox', '').replace(',', ' ').split()
    if len(view) == 4:
        width, height = map(float, view[2:])
    else:
        width = float(svg.get('width', '').removesuffix('px'))
        height = float(svg.get('height', '').removesuffix('px'))
    if not all(math.isfinite(n) and n > 0 for n in (width, height)):
        raise ValueError(f'{path.name}: dimensões inválidas')
    return width, height


def validate_timing(data, page_count):
    duration = data['duration']
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('timing.json: duração inválida')
    events = data['events']
    if not isinstance(events, list) or not events:
        raise ValueError('timing.json: faltam eventos')
    last = -1
    for event in events:
        for name in ('time', 'x', 'y', 'width', 'height'):
            value = event[name]
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f'timing.json: {name} inválido')
        if not 0 <= event['time'] < duration or event['time'] < last:
            raise ValueError('timing.json: eventos fora de ordem ou duração')
        last = event['time']
        if not (0 <= event['x'] < 100 and 0 <= event['y'] < 100
                and 0 < event['width'] <= 100 and 0 < event['height'] <= 100):
            raise ValueError('timing.json: posições devem ser percentuais da página')
        page = event.get('page', 1 if page_count == 1 else None)
        if type(page) is not int or not 1 <= page <= page_count:
            raise ValueError('timing.json: cada evento deve indicar page, começando em 1')
        if type(event['measure']) is not int or event['measure'] < 1:
            raise ValueError('timing.json: compasso inválido')
    return max(e['measure'] for e in events)


def load_catalog(root):
    directory = root / 'partituras'
    groups, scores, routes = {}, [], set()
    if not directory.exists():
        return Catalog(groups, scores)

    def group(key):
        if key not in groups:
            groups[key] = Group(key, key.rsplit('/', 1)[-1].replace('-', ' ').title())

    for source in sorted(directory.rglob('_index.md')):
        key = safe_key(source.parent.relative_to(directory).as_posix())
        if len(key.split('/')) not in (1, 2):
            raise ValueError(f'{source}: índices devem estar na categoria ou coleção')
        meta, body = read_markdown(source)
        group(key.split('/')[0])
        groups[key] = Group(key, meta.get('title', key), meta.get('description', ''), body)

    for source in sorted(directory.rglob('*.md')):
        if source.name == '_index.md':
            continue
        try:
            meta, body = read_markdown(source)
            if flag(meta, 'draft'):
                continue
            key = safe_key(source.relative_to(directory).with_suffix('').as_posix())
            if len(key.split('/')) not in (2, 3):
                raise ValueError('Use categoria/lição.md ou categoria/coleção/lição.md')
            if key in groups:
                raise ValueError('O endereço da lição coincide com uma coleção')
            title = meta.get('title', '').strip()
            if not title:
                raise ValueError('Title é obrigatório')
            asset_key = safe_key(meta.get('assets', 'music/' + key))
            folder = root / 'assets' / asset_key
            if not folder.resolve().is_relative_to((root / 'assets').resolve()):
                raise ValueError('Assets deve ficar dentro de assets/')
            if not folder.is_dir():
                raise ValueError(f'Pasta de arquivos não encontrada: assets/{asset_key}')
            numbered = []
            for path in folder.glob('score-*.svg'):
                match = re.fullmatch(r'score-([1-9][0-9]*)\.svg', path.name)
                if match:
                    numbered.append((int(match[1]), path))
            numbered.sort()
            if [n for n, _ in numbered] != list(range(1, len(numbered) + 1)):
                raise ValueError('Numere os SVGs consecutivamente: score-1.svg, score-2.svg…')
            pages = [(p.name, *svg_size(p)) for _, p in numbered]
            if 'pages' in meta and positive_int(meta['pages'], 'Pages') != len(pages):
                raise ValueError('Pages não corresponde ao número de SVGs')
            downloads = [(name, label) for name, label in
                         [('score.musicxml', 'MusicXML'), ('score.pdf', 'PDF'), ('score.mscz', 'MuseScore')]
                         if (folder / name).is_file()]
            if not pages and not downloads:
                raise ValueError('Adicione SVGs ou ao menos um arquivo para baixar (MusicXML, PDF ou MSCZ)')
            audio = [(name, mime) for name, mime in [('score.ogg', 'audio/ogg'), ('score.mp3', 'audio/mpeg')]
                     if (folder / name).is_file()]
            requested = meta.get('playback', '').strip().lower()
            if requested and requested not in ('generated', 'recorded', 'none'):
                raise ValueError('Playback: use generated, recorded ou none')
            if not requested:
                if 'audio' in meta and not flag(meta, 'audio'):
                    requested = 'none'
                elif (folder / 'score.musicxml').is_file():
                    requested = 'generated'
                elif audio:
                    requested = 'recorded'
                else:
                    requested = 'none'
            if not meta.get('playback') and requested == 'none' and 'audio' in meta and flag(meta, 'audio'):
                raise ValueError('Audio: true exige MusicXML ou score.ogg/score.mp3')
            sequence = None
            if requested == 'generated':
                musicxml = folder / 'score.musicxml'
                if not musicxml.is_file():
                    raise ValueError('Playback: generated exige score.musicxml')
                tempo = meta.get('tempo')
                sequence = parse_musicxml(musicxml, tempo)
                audio = []
            elif requested == 'recorded':
                if not audio:
                    raise ValueError('Playback: recorded exige score.ogg ou score.mp3')
            else:
                audio = []
            timing = flag(meta, 'cursor', bool(requested != 'none' and pages and (folder / 'timing.json').is_file()))
            count = 0
            if timing:
                if requested == 'none' or not pages or not (folder / 'timing.json').is_file():
                    raise ValueError('Cursor exige player, SVGs e timing.json')
                timing_data = json.loads((folder / 'timing.json').read_text())
                count = validate_timing(timing_data, len(pages))
                if sequence and abs(timing_data['duration'] - sequence['duration']) > .05:
                    raise ValueError('MusicXML e timing.json têm durações diferentes; exporte ambos da mesma revisão')
            measures = positive_int(meta['measures'], 'Measures') if 'measures' in meta else count
            if measures < count:
                raise ValueError('Measures é menor que o último compasso do cursor')
            lesson = positive_int(meta['lesson'], 'Lesson') if 'lesson' in meta else 0
            legacy = meta.get('legacy', '')
            if legacy:
                safe_key(legacy)
                if not legacy.startswith('musica/') or legacy in ('musica/msa',):
                    raise ValueError('Legacy deve ser um endereço de lição em musica/')
                if legacy in routes:
                    raise ValueError('Endereço Legacy duplicado')
                routes.add(legacy)
            for length in range(1, len(key.split('/'))):
                group('/'.join(key.split('/')[:length]))
            scores.append(Score(key, title, meta.get('author', ''), meta.get('instrument', ''),
                                meta.get('description', ''), body, asset_key, pages, downloads,
                                audio, requested, sequence, timing, measures, lesson, legacy))
        except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as error:
            raise ValueError(f'{source.relative_to(root)}: {error}') from error
    for score in scores:
        if score.key in groups:
            raise ValueError(f'partituras/{score.key}: uma lição e uma coleção usam o mesmo endereço')
    scores.sort(key=lambda s: (s.parent, s.lesson, s.title.casefold(), s.key))
    return Catalog(groups, scores)
