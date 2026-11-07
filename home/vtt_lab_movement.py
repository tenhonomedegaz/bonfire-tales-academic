"""Bounded flat, single-cell walking; NetworkX is imported only by plan_walk."""

import math
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
from importlib.metadata import PackageNotFoundError, version
from uuid import UUID


MAX_OCCUPANTS = 128
MAX_BUDGET = 2 ** 53 - 1


def networkx_version():
    try:
        return version('networkx')
    except PackageNotFoundError:
        return 'unavailable'


def _integer(value, minimum=0, maximum=MAX_BUDGET):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Movement requires bounded integer cells and units')
    return value


def _number(value, *, positive=False):
    if (type(value) not in (int, float) or not 0 <= value <= 1_000_000
            or not math.isfinite(value) or (positive and not value)):
        raise ValueError('Movement measurements must be finite nonnegative numbers')
    return value


def _actor(value):
    if type(value) is not str:
        raise ValueError('Movement IDs must be UUID strings')
    try:
        return str(UUID(value))
    except ValueError as error:
        raise ValueError('Invalid movement actor UUID') from error


def validate_board(board):
    """Normalize legacy board defaults without inventing any token movement speed."""
    if type(board) is not dict or set(board) - {
            'width', 'height', 'cell_meters', 'cell_feet', 'metric', 'movement', 'blocked_cells', 'terrain_cells'}:
        raise ValueError('Invalid movement board fields')
    width = _integer(board.get('width', 24), 1, 64)
    height = _integer(board.get('height', 18), 1, 64)
    metric = board.get('metric', 'manhattan3d')
    if metric not in ('manhattan3d', 'manhattan'):
        raise ValueError('Only Manhattan walking is supported')
    policy = {'step_cost': 12, 'cost_scale': 12, 'terrain_costs': {'normal': 1, 'difficult': 2},
              'allies': 'pass-through', 'enemies': 'block', 'end_occupied': False}
    movement = board.get('movement', policy)
    if (type(movement) is not dict or set(movement) != set(policy)
            or movement['allies'] != 'pass-through' or movement['enemies'] != 'block'
            or movement['end_occupied'] is not False
            or type(movement['terrain_costs']) is not dict
            or set(movement['terrain_costs']) != {'normal', 'difficult'}):
        raise ValueError('Unsupported movement policy')
    for value in (movement['step_cost'], movement['cost_scale'], *movement['terrain_costs'].values()):
        _integer(value, 1, 1_000_000)
    blocked = board.get('blocked_cells', [])
    if type(blocked) is not list or len(blocked) > 4096:
        raise ValueError('Too many blocked cells')
    cells = set()
    for cell in blocked:
        if type(cell) is not dict or set(cell) != {'x', 'y'}:
            raise ValueError('Invalid blocked cell')
        cells.add((_integer(cell['x'], 0, width - 1), _integer(cell['y'], 0, height - 1)))
    terrain = board.get('terrain_cells', {})
    if type(terrain) is not dict or len(terrain) > 4096:
        raise ValueError('Invalid terrain cells')
    normalized = {}
    for key, kind in terrain.items():
        if type(key) is not str or key.count(',') != 1 or kind not in ('normal', 'difficult'):
            raise ValueError('Unsupported terrain cell')
        try:
            x, y = (int(part) for part in key.split(','))
        except ValueError as error:
            raise ValueError('Invalid terrain cell key') from error
        if key != f'{x},{y}':
            raise ValueError('Terrain keys must be canonical x,y cells')
        _integer(x, 0, width - 1)
        _integer(y, 0, height - 1)
        normalized[key] = kind
    return {'width': width, 'height': height, 'cell_meters': _number(board.get('cell_meters', 1.5), positive=True),
            'cell_feet': _number(board.get('cell_feet', 5), positive=True), 'metric': metric,
            'movement': deepcopy(movement), 'blocked_cells': [{'x': x, 'y': y} for x, y in sorted(cells)],
            'terrain_cells': dict(sorted(normalized.items()))}


def validate_movement(profile):
    if profile is None:
        return None
    if (type(profile) is not dict or not {'schema', 'unit', 'speeds', 'warnings'} <= set(profile)
            or set(profile) - {'schema', 'unit', 'speeds', 'warnings', 'properties', 'fall'}
            or type(profile['schema']) is not int or profile['schema'] != 1 or profile['unit'] != 'ft'
            or type(profile['speeds']) is not dict or len(profile['speeds']) > 32
            or type(profile['warnings']) is not list or len(profile['warnings']) > 64):
        raise ValueError('Invalid server movement snapshot')
    for key, value in profile['speeds'].items():
        if type(key) is not str or not 0 < len(key) <= 80:
            raise ValueError('Invalid movement speed identifier')
        _number(value)
    if any(type(warning) is not str or len(warning) > 500 for warning in profile['warnings']):
        raise ValueError('Invalid movement warnings')
    if 'properties' in profile:
        properties = profile['properties']
        if type(properties) is not dict or len(properties) > 8:
            raise ValueError('Invalid movement properties')
        for mode, value in properties.items():
            if (mode not in {'walk', 'fly', 'swim', 'climb', 'burrow'} or mode not in profile['speeds']
                    or type(value) is not dict or set(value) != {'hover'} or type(value['hover']) is not bool):
                raise ValueError('Invalid movement properties')
    if 'fall' in profile:
        fall = profile['fall']
        if type(fall) is not dict or set(fall) != {'threshold_ft', 'max_per_turn_ft'}:
            raise ValueError('Invalid falling metadata')
        _number(fall['threshold_ft'])
        _number(fall['max_per_turn_ft'], positive=True)
    return deepcopy(profile)


def movement_budget(board, profile):
    profile = validate_movement(profile)
    if profile is None or 'walk' not in profile['speeds']:
        return None
    # Decimal strings become exact fractions before flooring, not binary float arithmetic.
    units = (Fraction(Decimal(str(profile['speeds']['walk']))) * board['movement']['cost_scale']
             / Fraction(Decimal(str(board['cell_feet']))))
    return _integer(units.numerator // units.denominator)


def validate_positions(board, positions):
    if type(positions) is not dict or not 1 <= len(positions) <= MAX_OCCUPANTS:
        raise ValueError('Invalid occupancy snapshot')
    result = {}
    for key, position in positions.items():
        actor = _actor(key)
        if actor in result or type(position) is not dict or not {'x', 'y', 'z'} <= set(position) or set(
                position) - {'x', 'y', 'z', 'footprint'}:
            raise ValueError('Invalid occupancy position')
        result[actor] = {'x': _integer(position['x'], 0, board['width'] - 1),
                         'y': _integer(position['y'], 0, board['height'] - 1),
                         'z': _integer(position['z'], 0, 100),
                         'footprint': _integer(position.get('footprint', 1), 1, 64)}
    return result


def flat_available(positions):
    return all(position['z'] == 0 and position['footprint'] == 1 for position in positions.values())


def plan_walk(board, positions, teams, actor_id, destination, budget_remaining):
    board = validate_board(board)
    positions = validate_positions(board, positions)
    actor = _actor(actor_id)
    _integer(budget_remaining)
    if (type(teams) is not dict or actor not in teams or actor not in positions
            or any(key not in positions or type(team) is not str or not 0 < len(team) <= 80
                   for key, team in teams.items())):
        raise ValueError('Only encounter participants may walk')
    if not flat_available(positions):
        raise ValueError('Only flat z=0 single-cell walking is supported')
    if type(destination) is not dict or set(destination) != {'x', 'y', 'z'}:
        raise ValueError('Invalid walking destination')
    goal = (_integer(destination['x'], 0, board['width'] - 1),
            _integer(destination['y'], 0, board['height'] - 1))
    if type(destination['z']) is not int or destination['z'] != 0:
        raise ValueError('Walking destination must have z=0')
    occupied = {(position['x'], position['y']) for key, position in positions.items() if key != actor}
    if goal in occupied:
        raise ValueError('Walking cannot end in an occupied cell')
    forbidden = {(cell['x'], cell['y']) for cell in board['blocked_cells']}
    forbidden.update((position['x'], position['y']) for key, position in positions.items()
                     if key != actor and (key not in teams or teams[key] != teams[actor]))
    origin = (positions[actor]['x'], positions[actor]['y'])
    if origin in forbidden or goal in forbidden:
        raise ValueError('Walking origin or destination is blocked')
    try:
        import networkx as nx
    except ImportError as error:
        raise ValueError('NetworkX is unavailable; automatic walking is disabled') from error
    graph = nx.DiGraph()
    for y in range(board['height']):
        for x in range(board['width']):
            if (x, y) not in forbidden:
                graph.add_node((x, y))
    for x, y in list(graph):
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            neighbor = x + dx, y + dy
            if neighbor in graph:
                terrain = board['terrain_cells'].get(f'{neighbor[0]},{neighbor[1]}', 'normal')
                graph.add_edge((x, y), neighbor, weight=(board['movement']['step_cost']
                               * board['movement']['terrain_costs'][terrain]))
    try:
        cost, path = nx.single_source_dijkstra(graph, origin, target=goal, cutoff=budget_remaining, weight='weight')
    except (nx.NetworkXNoPath, nx.NodeNotFound) as error:
        raise ValueError('No walking path within the remaining movement budget') from error
    return {'actor_id': actor, 'path': [{'x': x, 'y': y, 'z': 0} for x, y in path],
            'cost_units': cost, 'remaining_units': budget_remaining - cost}
