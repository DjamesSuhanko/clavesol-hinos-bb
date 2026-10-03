"""Export matching SVG pages and cursor data from MuseScore --score-media JSON.

Page-relative coordinates follow MuseScore PositionsWriter:
https://github.com/musescore/MuseScore/blob/v4.7.5/src/notation/internal/positionswriter.cpp
The MSA export uses scale 12; --scale supports other export resolutions.
"""
import argparse
import base64
from bisect import bisect_right
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from score_catalog import validate_timing


def convert_media(data, scale=12):
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('A escala deve ser positiva')
    svgs = [base64.b64decode(svg) for svg in data['svgs']]
    dimensions = [list(map(float, ET.fromstring(svg).attrib['viewBox'].replace(',', ' ').split()))
                  for svg in svgs]
    if not dimensions or any(len(d) != 4 or d[2] <= 0 or d[3] <= 0 for d in dimensions):
        raise ValueError('Páginas SVG inválidas')

    def positions(key):
        xml = ET.fromstring(base64.b64decode(data[key]))
        elements = {e.attrib['id']: e.attrib for e in xml.findall('elements/element')}
        return [(float(e.attrib['position']) / 1000, elements[e.attrib['elid']])
                for e in xml.findall('events/event')]

    measures = positions('mposXML')
    starts = [start for start, _ in measures]
    if not starts or starts != sorted(starts):
        raise ValueError('Eventos de compasso ausentes ou fora de ordem')
    events = []
    for time, element in positions('sposXML'):
        number = int(element['page'])
        if not 0 <= number < len(svgs):
            raise ValueError('Página inexistente no mapa de posições')
        left, top, width, height = dimensions[number]
        x, y, w, h = [float(element[k]) / scale for k in ('x', 'y', 'sx', 'sy')]
        index = bisect_right(starts, time) - 1
        if index < 0:
            raise ValueError('Nota antes do primeiro compasso')
        measure = int(measures[index][1]['id']) + 1
        events.append(dict(time=time, page=number + 1, x=(x-left)/width*100,
                           y=(y-top)/height*100, width=w/width*100,
                           height=h/height*100, measure=measure))
    timing = dict(duration=float(data['metadata']['duration']), events=events)
    validate_timing(timing, len(svgs))
    return svgs, timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('media', type=Path, help='JSON puro exportado por MuseScore --score-media')
    parser.add_argument('output', type=Path, help='Pasta de arquivos da lição')
    parser.add_argument('--scale', type=float, default=12)
    parser.add_argument('--force', action='store_true', help='Substituir SVGs e timing existentes')
    args = parser.parse_args()
    svgs, timing = convert_media(json.loads(args.media.read_text()), args.scale)
    files = {f'score-{i}.svg': svg for i, svg in enumerate(svgs, 1)}
    files['timing.json'] = json.dumps(timing, separators=(',', ':')).encode()
    stale = [p for p in args.output.glob('score-*.svg') if p.name not in files]
    if stale:
        parser.error('Há SVGs de páginas excedentes. Use uma pasta nova ou remova-os após conferir.')
    if not args.force and any((args.output / name).exists() for name in files):
        parser.error('Os arquivos já existem. Use --force para atualizar esta exportação.')
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output / name).write_bytes(data)
    print(f'{len(svgs)} página(s), {len(timing["events"])} posições, {timing["duration"]:g} segundos')


if __name__ == '__main__':
    main()
