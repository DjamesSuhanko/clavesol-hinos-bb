"""Resolve written repeat bars and numbered endings into measure visits.

No musical navigation is guessed from decorative text. Da capo/segno/coda
remain the caller's explicit unsupported cases. Limits prevent endless input.
"""
from dataclasses import dataclass, field
import re


def local(node):
    return node.tag.rsplit('}', 1)[-1]


def ending_numbers(value):
    result = set()
    for item in value.split(','):
        match = re.fullmatch(r'\s*(\d+)(?:\s*-\s*(\d+))?\s*', item)
        if not match:
            raise ValueError('MusicXML: números de casas inválidos')
        first, last = int(match[1]), int(match[2] or match[1])
        if not 1 <= first <= last <= 32:
            raise ValueError('MusicXML: casas devem estar entre 1 e 32')
        result.update(range(first, last + 1))
    return frozenset(result)


@dataclass
class Block:
    start: int
    end: int
    count: int | None
    endings: list = field(default_factory=list)

    @property
    def extent(self):
        return max([self.end] + [end for start, end, numbers in self.endings])


def playback_order(parts):
    measures = [[n for n in part if local(n) == 'measure'] for part in parts]
    size = len(measures[0])
    controls = [{} for _ in range(size)]
    any_repeat = any(local(n) in ('repeat', 'ending') for part in parts for n in part.iter())
    if not any_repeat:
        return list(range(size))
    if any(len(rows) != size for rows in measures):
        raise ValueError('MusicXML: partes com compassos desalinhados nas repetições')
    for rows in measures:
        for index, measure in enumerate(rows):
            for bar in measure:
                if local(bar) != 'barline':
                    continue
                for node in bar:
                    tag = local(node)
                    if tag == 'repeat':
                        direction = node.get('direction')
                        if direction not in ('forward', 'backward'):
                            raise ValueError('MusicXML: direção de ritornelo inválida')
                        required_location = 'left' if direction == 'forward' else 'right'
                        if bar.get('location', 'right') != required_location:
                            raise ValueError('MusicXML: ritornelo fora do limite esperado do compasso')
                        value = None
                        if node.get('times') is not None:
                            try:
                                value = int(node.get('times'))
                            except ValueError:
                                raise ValueError('MusicXML: quantidade de repetições inválida')
                            if not 1 <= value <= 32:
                                raise ValueError('MusicXML: quantidade de repetições deve estar entre 1 e 32')
                        key = direction
                    elif tag == 'ending':
                        kind = node.get('type')
                        if kind not in ('start', 'stop', 'discontinue'):
                            raise ValueError('MusicXML: limite de casa inválido')
                        if bar.get('location', 'right') != ('left' if kind == 'start' else 'right'):
                            raise ValueError('MusicXML: casa fora do limite esperado do compasso')
                        value = ending_numbers(node.get('number', ''))
                        label = (node.text or '').strip()
                        if label and re.fullmatch(r'[\d\s.,]+', label):
                            printed = frozenset(map(int, re.findall(r'\d+', label)))
                            if printed != value:
                                raise ValueError(f'MusicXML: casa no compasso {index+1} mostra {label}, mas está configurada para {sorted(value)}')
                        key = 'ending-start' if kind == 'start' else 'ending-end'
                    else:
                        continue
                    if key in controls[index] and controls[index][key] != value:
                        raise ValueError(f'MusicXML: repetições divergentes entre partes no compasso {index+1}')
                    controls[index][key] = value

    stack, blocks, spans = [], [], []
    active = None
    implicit_start = 0
    for index, control in enumerate(controls):
        if 'forward' in control:
            stack.append(index)
        if 'ending-start' in control:
            if active is not None:
                raise ValueError('MusicXML: casas sobrepostas')
            active = (index, control['ending-start'])
        if 'ending-end' in control:
            if active is None or active[1] != control['ending-end']:
                raise ValueError('MusicXML: início e fim de casa incompatíveis')
            spans.append((active[0], index, active[1]))
            active = None
        if 'backward' in control:
            start = stack.pop() if stack else implicit_start
            blocks.append(Block(start, index, control['backward']))
            if not stack:
                implicit_start = index + 1
    if stack or active is not None:
        raise ValueError('MusicXML: ritornelo ou casa sem fechamento')
    if not blocks:
        raise ValueError('MusicXML: casas sem ritornelo correspondente')

    for span in spans:
        start, end, _ = span
        # A trailing final ending belongs to the just-ended repeat, even when
        # that repeat is nested inside another block.
        adjacent = [b for b in blocks if b.endings and b.extent + 1 == start]
        candidates = adjacent or [b for b in blocks if b.start <= start <= end <= b.end]
        if not candidates:
            raise ValueError('MusicXML: casa sem ritornelo correspondente')
        owner = min(candidates, key=lambda b: b.end - b.start)
        owner.endings.append(span)
    for block in blocks:
        if block.endings:
            seen = set()
            for start, end, numbers in block.endings:
                if seen.intersection(numbers):
                    raise ValueError('MusicXML: passagem atribuída a mais de uma casa')
                seen.update(numbers)
            count = max(seen)
            if seen != set(range(1, count+1)):
                raise ValueError('MusicXML: casas não cobrem todas as passagens desde a primeira')
            if block.count is not None and block.count != count:
                raise ValueError('MusicXML: quantidade de repetições incompatível com as casas')
            block.count = count
            # Earlier endings terminate at the backward bar; the final one
            # follows it. Other layouts need their own explicitly tested path.
            if any(end != block.end for start, end, nums in block.endings if max(nums) < count):
                raise ValueError('MusicXML: casa intermediária sem ritornelo no final')
        else:
            block.count = block.count or 2
    for i, a in enumerate(blocks):
        for b in blocks[i+1:]:
            if a.start == b.start or (a.start < b.start <= a.extent < b.extent) or (b.start < a.start <= b.extent < a.extent):
                raise ValueError('MusicXML: ritornelos sobrepostos ou ambíguos')
    by_start = {block.start: block for block in blocks}
    order = []

    def emit(start, end, owner=None, iteration=1, depth=0):
        if depth > 16:
            raise ValueError('MusicXML: excesso de ritornelos aninhados')
        index = start
        while index <= end:
            block = by_start.get(index)
            if block is not None and block is not owner:
                for turn in range(1, block.count+1):
                    emit(block.start, block.extent, block, turn, depth+1)
                index = block.extent + 1
                continue
            ending = next((s for s in owner.endings if s[0] <= index <= s[1]), None) if owner else None
            if ending and iteration not in ending[2]:
                index = ending[1] + 1
                continue
            order.append(index)
            if len(order) > 10000:
                raise ValueError('MusicXML: execução excede 10000 compassos')
            index += 1
    emit(0, size-1)
    return order
