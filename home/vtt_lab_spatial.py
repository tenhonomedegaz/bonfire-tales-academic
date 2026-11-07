"""Integer distance parity with bonfire-vtt/packages/spatial/src/distance.ts.

This measures token footprints, not routes, visibility or a movement budget.
"""
from decimal import Decimal
from math import isqrt


METRICS = ('manhattan3d', 'chebyshev3d', 'euclidean-round', 'alt-5-10-5')


def _integer(value, minimum=-1000000, maximum=1000000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Coordenadas e dimensoes devem ser inteiros limitados.')
    return value


def _footprint(value):
    if not isinstance(value, dict) or set(value) != {'pos', 'sizeCells'}:
        raise ValueError('Footprint invalido.')
    position, size = value['pos'], value['sizeCells']
    if not isinstance(position, dict) or set(position) != {'x', 'y', 'z'}:
        raise ValueError('Posicao invalida.')
    if not isinstance(size, dict) or set(size) != {'w', 'h', 'z'}:
        raise ValueError('Dimensoes invalidas.')
    return ({key: _integer(number) for key, number in position.items()},
            {key: _integer(number, 1, 1000) for key, number in size.items()})


def distance_units(metric, a, b):
    """Match the existing TS contract: cells, except alt returns half-cell units."""
    if metric not in METRICS:
        raise ValueError('Metrica espacial desconhecida.')
    pa, sa = _footprint(a)
    pb, sb = _footprint(b)
    gaps = [max(0, pb[axis] - (pa[axis] + sa[dim] - 1),
                pa[axis] - (pb[axis] + sb[dim] - 1))
            for axis, dim in (('x', 'w'), ('y', 'h'), ('z', 'z'))]
    if metric == 'manhattan3d':
        return sum(gaps)
    if metric == 'chebyshev3d':
        return max(gaps)
    if metric == 'euclidean-round':
        return isqrt(sum(gap * gap for gap in gaps))
    largest, second, _ = sorted(gaps, reverse=True)
    return 2 * largest + 2 * (second // 2)


def measure_tokens(state, origin_id, target_id):
    board = state.get('board')
    if not isinstance(board, dict):
        raise ValueError('Tabuleiro invalido.')
    scale = board.get('cell_meters')
    if type(scale) not in (int, float) or not 0 < scale <= 100:
        raise ValueError('Escala de celula invalida.')
    metric = board.get('metric', 'manhattan3d')
    tokens = {entry['id']: entry for entry in state['tokens']}
    if origin_id not in tokens or target_id not in tokens:
        raise ValueError('Origem ou alvo nao pertence a esta sessao.')
    def footprint(token):
        return {'pos': {axis: token[axis] for axis in ('x', 'y', 'z')},
                'sizeCells': token.get('size_cells', {'w': 1, 'h': 1, 'z': 1})}
    units = distance_units(metric, footprint(tokens[origin_id]), footprint(tokens[target_id]))
    divisor = 2 if metric == 'alt-5-10-5' else 1
    cells = Decimal(units) / divisor
    meters = cells * Decimal(str(scale))
    return {'origin_id': origin_id, 'target_id': target_id, 'metric': metric,
            'units': units, 'units_per_cell': divisor, 'cells': float(cells),
            'meters': float(meters), 'cell_meters': scale, 'scope': 'token_footprints',
            'path_validated': False, 'line_of_sight_validated': False}
