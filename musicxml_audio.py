"""Convert the playable subset of MusicXML into a compact browser sequence."""
from pathlib import Path
import math
import xml.etree.ElementTree as ET


STEPS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
UNITS = {'whole': 4, 'half': 2, 'quarter': 1, 'eighth': .5, '16th': .25, '32nd': .125}


def local(element):
    return element.tag.rsplit('}', 1)[-1]


def child(element, name):
    return next((item for item in element if local(item) == name), None)


def text(element, name, default=None):
    item = child(element, name)
    return item.text.strip() if item is not None and item.text else default


def number(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'MusicXML: {label} inválido') from error
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f'MusicXML: {label} inválido')
    return result


def tempo_marking(direction):
    kind = None
    for item in direction.iter():
        if local(item) == 'metronome':
            kind = item
            break
    if kind is None:
        return None
    unit = text(kind, 'beat-unit')
    per_minute = text(kind, 'per-minute')
    if unit not in UNITS or per_minute is None:
        return None
    dots = sum(1 for item in kind if local(item) == 'beat-unit-dot')
    factor = UNITS[unit] * sum(.5 ** dot for dot in range(dots + 1))
    bpm = number(per_minute, 'andamento') * factor
    symbols = {'whole': '𝅝', 'half': '𝅗𝅥', 'quarter': '♩', 'eighth': '♪', '16th': '𝅘𝅥𝅯'}
    return bpm, f'{symbols.get(unit, unit)}{"." * dots} = {per_minute}'


def parse_musicxml(path: Path, tempo_override=None, *, include_cursor=False):
    """Return notes timed in seconds. Raises on data that would play misleadingly."""
    root = ET.parse(path).getroot()
    if local(root) != 'score-partwise':
        raise ValueError('MusicXML: use uma partitura no formato score-partwise')
    parts = [item for item in root if local(item) == 'part']
    if not parts:
        raise ValueError('MusicXML: nenhuma parte musical encontrada')

    for item in root.iter():
        if local(item) in ('repeat', 'ending', 'grace', 'unpitched'):
            raise ValueError('MusicXML: repetições, casas, ornamentos e percussão exigem Playback: recorded')
        if local(item) == 'sound' and any(item.get(key) for key in ('dacapo', 'dalsegno', 'tocoda', 'fine')):
            raise ValueError('MusicXML: saltos exigem Playback: recorded')
    raw_notes, tempos, markings = [], {}, {}
    score_end = 0.0
    fermatas = set()
    segments, measure_starts = {}, {}
    for part_index, part in enumerate(parts):
        divisions, transpose, base = 1.0, 0, 0.0
        open_ties = {}
        for measure_number, measure in enumerate((item for item in part if local(item) == 'measure'), 1):
            measure_starts[(measure_number, round(base, 9))] = base
            cursor = maximum = last_onset = 0.0
            for item in measure:
                tag = local(item)
                if tag == 'attributes':
                    value = text(item, 'divisions')
                    if value is not None:
                        divisions = number(value, 'divisions')
                    transposition = child(item, 'transpose')
                    if transposition is not None:
                        transpose = float(text(transposition, 'chromatic', '0')) + 12 * int(text(transposition, 'octave-change', '0'))
                elif tag == 'sound' and item.get('tempo'):
                    tempos[base + cursor] = number(item.get('tempo'), 'andamento')
                elif tag == 'direction':
                    offset = float(text(item, 'offset', '0')) / divisions
                    position = base + cursor + offset
                    if not math.isfinite(position) or position < 0:
                        raise ValueError('MusicXML: posição do andamento inválida')
                    sound = child(item, 'sound')
                    if sound is not None and sound.get('tempo'):
                        tempos[position] = number(sound.get('tempo'), 'andamento')
                    marking = tempo_marking(item)
                    if marking:
                        markings[position] = marking[1]
                        tempos.setdefault(position, marking[0])
                elif tag in ('backup', 'forward'):
                    duration = number(text(item, 'duration'), 'duração') / divisions
                    cursor += duration if tag == 'forward' else -duration
                    maximum = max(maximum, cursor)
                    if cursor < -1e-9:
                        raise ValueError('MusicXML: backup ultrapassa o início do compasso')
                elif tag == 'barline':
                    if any(local(node) in ('repeat', 'ending') for node in item.iter()):
                        raise ValueError('MusicXML: repetições e casas ainda exigem áudio gravado (Playback: recorded)')
                elif tag == 'note':
                    if child(item, 'grace') is not None:
                        continue
                    duration = number(text(item, 'duration'), 'duração da nota') / divisions
                    chord = child(item, 'chord') is not None
                    onset = last_onset if chord else cursor
                    if not chord:
                        last_onset = onset
                        cursor += duration
                        maximum = max(maximum, cursor)
                    maximum = max(maximum, onset + duration)
                    segments[(measure_number, round(base + onset, 9))] = base + onset
                    if any(local(node) == 'fermata' for node in item.iter()):
                        fermatas.add((round(base + onset, 9), round(base + onset + duration, 9)))
                    pitch = child(item, 'pitch')
                    if pitch is None:
                        continue
                    step = text(pitch, 'step')
                    octave = int(text(pitch, 'octave'))
                    alter = float(text(pitch, 'alter', '0'))
                    if step not in STEPS:
                        raise ValueError('MusicXML: altura de nota inválida')
                    midi = (octave + 1) * 12 + STEPS[step] + alter + transpose
                    if not 0 <= midi <= 127:
                        raise ValueError('MusicXML: nota fora da extensão MIDI')
                    ties = {node.get('type') for node in item if local(node) == 'tie'}
                    voice = text(item, 'voice', '1')
                    key = (part_index, voice, midi)
                    absolute = base + onset
                    if 'stop' in ties and key in open_ties:
                        previous = raw_notes[open_ties[key]]
                        previous['quarterDuration'] = absolute + duration - previous['quarter']
                        if 'start' not in ties:
                            del open_ties[key]
                        continue
                    note = {'quarter': absolute, 'quarterDuration': duration, 'midi': midi}
                    raw_notes.append(note)
                    if 'start' in ties:
                        open_ties[key] = len(raw_notes) - 1
            base += maximum
        score_end = max(score_end, base)

    if not raw_notes:
        raise ValueError('MusicXML: nenhuma nota com altura encontrada')
    if tempo_override is not None:
        tempos, markings = {0.0: number(tempo_override, 'Tempo')}, {}
    if not tempos:
        raise ValueError('MusicXML: andamento ausente; informe Tempo no Markdown')
    if min(tempos) > 0:
        first = tempos[min(tempos)]
        tempos[0.0] = first
    changes = sorted(tempos.items())

    def seconds(quarter):
        elapsed, previous, bpm = 0.0, 0.0, changes[0][1]
        for position, new_bpm in changes[1:]:
            if position >= quarter:
                break
            elapsed += (position - previous) * 60 / bpm
            previous, bpm = position, new_bpm
        return elapsed + (quarter - previous) * 60 / bpm

    notes = []
    for note in sorted(raw_notes, key=lambda value: (value['quarter'], value['midi'])):
        start = seconds(note['quarter'])
        end = seconds(note['quarter'] + note['quarterDuration'])
        notes.append({'time': round(start, 6), 'duration': round(end - start, 6), 'midi': note['midi']})
    duration = round(max(seconds(score_end), max(n['time'] + n['duration'] for n in notes)), 6)
    initial = changes[0][1]
    marking = f'♩ = {initial:g}' if tempo_override is not None else markings.get(0.0, f'♩ = {initial:g}')
    result = {'version': 1, 'duration': duration, 'quarterBpm': initial,
              'marking': marking, 'notes': notes}
    if fermatas:
        result['fermatas'] = [{'start': round(seconds(start), 6), 'end': round(seconds(end), 6)}
                              for start, end in sorted(fermatas)]
    if include_cursor:
        result['cursorEvents'] = [dict(measure=key[0], time=round(seconds(quarter), 6))
                                  for key, quarter in sorted(segments.items())]
        result['measureStarts'] = [dict(measure=key[0], time=round(seconds(quarter), 6))
                                   for key, quarter in sorted(measure_starts.items())]
    return result
