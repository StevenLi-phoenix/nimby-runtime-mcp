"""Local tangent planning from a fresh native network, without changing geometry."""
import math


def unit(x, y):
    length = math.hypot(x, y)
    if length < 1e-6:
        raise ValueError('Coincident controls cannot define a tangent')
    return x / length, y / length


def calculate_tangents(nodes, node_ids, paired_nodes=()):
    by_id = {n['id']: n for n in nodes}
    points, details = {}, {}
    for node_id in node_ids:
        n = by_id.get(node_id)
        if not n or not n['blueprint'] or n['station_id'] != '0':
            raise ValueError(f'{node_id}: expected a non-platform blueprint control')
        if n.get('branch_parent', '0') != '0' or n.get('branches'):
            raise ValueError(f'{node_id}: junction controls require an explicit route tangent')
        a, b = by_id.get(n['previous']), by_id.get(n['next'])
        if not a or not b:
            raise ValueError(f'{node_id}: connect both neighbours before calculating a tangent')
        incoming = unit(n['x']-a['x'], n['y']-a['y'])
        outgoing = unit(b['x']-n['x'], b['y']-n['y'])
        dot = max(-1., min(1., sum(x*y for x, y in zip(incoming, outgoing))))
        turn = math.degrees(math.acos(dot))
        if turn >= 120:
            raise ValueError(f'{node_id}: {turn:.1f} degree turn needs geometry review')
        incoming_length = math.hypot(n['x']-a['x'], n['y']-a['y'])
        outgoing_length = math.hypot(b['x']-n['x'], b['y']-n['y'])
        # Keep long straight spans straight; confine a transition to nearby controls.
        # Comparable lengths use the angle bisector, independently of absolute scale.
        if incoming_length >= 4*outgoing_length:
            dx, dy = incoming
            method = 'long-incoming-span'
        elif outgoing_length >= 4*incoming_length:
            dx, dy = outgoing
            method = 'long-outgoing-span'
        else:
            dx, dy = unit(incoming[0]+outgoing[0], incoming[1]+outgoing[1])
            method = 'unit-vector-bisector'
        points[node_id] = dict(id=node_id, x=n['x'], y=n['y'], dx=dx, dy=dy)
        details[node_id] = dict(id=node_id, turn_degrees=turn, method=method,
                                previous=n['previous'], next=n['next'])
    used = set()
    for pair in paired_nodes:
        if len(pair) != 2 or pair[0] == pair[1] or any(i not in points or i in used for i in pair):
            raise ValueError('Pairs must contain two distinct selected IDs, each used once')
        used.update(pair)
        a, b = [points[i] for i in pair]
        if math.hypot(a['x']-b['x'], a['y']-b['y']) > 30:
            raise ValueError('Paired controls must be within 30 world metres; align their positions first')
        dot = a['dx']*b['dx']+a['dy']*b['dy']
        sign = 1 if dot >= 0 else -1
        if abs(dot) < math.cos(math.radians(30)):
            raise ValueError('Paired controls disagree by more than 30 degrees')
        dx, dy = unit(a['dx']+sign*b['dx'], a['dy']+sign*b['dy'])
        a.update(dx=dx, dy=dy)
        b.update(dx=sign*dx, dy=sign*dy)
    return dict(points=list(points.values()), nodes=[dict(details[i], angle_degrees=math.degrees(
        math.atan2(points[i]['dy'], points[i]['dx']))) for i in node_ids],
        angle_convention='degrees counterclockwise from world +X, oriented previous to next',
        method='preserve dominant straight span at length ratio >=4; otherwise unit-vector bisector; paired controls share an axis')
