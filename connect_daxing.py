"""Blueprint the live Gongyixiqiao connection and Tiangongyuan turnback; do not build."""
import json
import math
from pathlib import Path

from build_line1 import distance, simplify
from session_call import call


def run():
    path = Path('work/daxing-connection.json')
    assert not path.exists(), 'Inspect saved native operations; never replay an uncertain connection'
    assert call('runtime_status')['speed'] == 0
    stations = json.loads(Path('work/daxing-built.json').read_text(encoding='utf-8'))['stations']
    corridors = json.loads(Path('work/daxing-corridors.json').read_text(encoding='utf-8'))
    assert len(stations) == 11 and len(corridors['corridors']) == 10 and corridors['pending'] is None
    plan = json.loads(Path('data/daxing_plan.json').read_text(encoding='utf-8'))
    old = json.loads(Path('work/line4-station-after-turnbacks.json').read_text(encoding='utf-8'))
    anchor_ids = old['turnbacks'][0]['new_nodes'][:2]
    anchor = call('get_track_node', node_id=anchor_ids[0])
    companion = call('get_track_node', node_id=anchor_ids[1])
    assert anchor['previous'] == '0' and companion['next'] == '0'
    assert anchor['depth'] == companion['depth'] == -1
    state = dict(commands=[], pending=None, anchors_before=[anchor, companion])

    def save():
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)

    def mutate(tool, **arguments):
        state['pending'] = dict(tool=tool, arguments=arguments)
        save()
        result = call(tool, **arguments)
        state['commands'].append(dict(**state['pending'], result=result))
        state['pending'] = None
        save()
        return result

    # Only use source points south of the live tail endpoint; never draw back into the station.
    route = plan['route']; chain = [0.]
    for a, b in zip(route, route[1:]):
        chain.append(chain[-1]+distance(a, b))
    projection = []
    for i, (a, b) in enumerate(zip(route, route[1:])):
        dx, dy = b['x']-a['x'], b['y']-a['y']
        t = max(0, min(1, ((anchor['x']-a['x'])*dx+(anchor['y']-a['y'])*dy)/(dx*dx+dy*dy)))
        x, y = a['x']+t*dx, a['y']+t*dy
        projection.append((math.hypot(anchor['x']-x, anchor['y']-y), chain[i]+t*math.hypot(dx, dy)))
    offset, end_chain = min(projection)
    assert offset < 100, 'Player endpoint needs an individual connection design'
    last = stations[-1]
    start = call('get_track_node', node_id=last['east_primary'])
    margin = 170/math.cos(math.radians(last['latitude']))
    points = simplify([start]+[p for p, c in zip(route, chain)
                       if last['chainage']+margin < c < end_chain-50]+[anchor], tolerance=16)
    assert all(distance(a, b) >= 35 for a, b in zip(points, points[1:]))
    state['connection_points'] = points
    save()
    current = start
    for point in points[1:-1]:
        result = mutate('extend_track', node_id=current['id'], end_x=point['x'], end_y=point['y'], depth=point['depth'])
        current = min([n for n in result['nodes'] if n['id'] != current['id']], key=lambda n: distance(n, point))
    mutate('rebuild_track_blueprints', node_ids=anchor_ids)
    mutate('connect_track_endpoints', start_node_id=current['id'], end_node_id=anchor['id'], dual=True)
    state['connection_verified'] = call('get_track_network', seed_node_ids=[start['id']])
    assert any(n['id'] == anchor['id'] for n in state['connection_verified']['nodes'])
    save()

    terminal = stations[0]
    primary = call('get_track_node', node_id=terminal['west_primary'])
    secondary = call('get_track_node', node_id=terminal['west_secondary'])
    inside = call('get_track_node', node_id=primary['next'])
    assert primary['previous'] == '0' and secondary['next'] == '0' and primary['depth'] == -1
    dx, dy = primary['x']-inside['x'], primary['y']-inside['y']
    length = math.hypot(dx, dy); scale = math.cosh(primary['y']/6378137)
    result = mutate('extend_track', node_id=primary['id'], end_x=primary['x']+dx/length*400*scale,
                    end_y=primary['y']+dy/length*400*scale, depth=-1)
    new = [n for n in result['nodes'] if n['id'] != primary['id']]
    assert len(new) == 2
    edge = next(n['id'] for n in new if n['previous'] == secondary['id'])
    branch = mutate('create_track_branch', start_edge_id=primary['id'], start_position=.35,
                    end_edge_id=edge, end_position=.35, depth=-1)
    state['turnback'] = dict(station=terminal['name'], extension_metres=400,
                             new_nodes=[n['id'] for n in new+branch['nodes']])
    state['network'] = call('get_track_network', seed_node_ids=[start['id']])
    state['checks'] = call('get_track_build_checks', node_ids=[n['id'] for n in state['network']['nodes'] if n['blueprint']])
    state['status'] = 'blueprints-connected-awaiting-curve-review-and-user-build'
    save()
    print(json.dumps(dict(nodes=len(state['network']['nodes']), blueprints=sum(n['blueprint'] for n in state['network']['nodes']),
                          checks=state['checks']), ensure_ascii=True))


if __name__ == '__main__':
    run()
