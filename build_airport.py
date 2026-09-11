"""Checkpoint each native MCP command for the Capital Airport Express station blueprints.

An uncertain command leaves pending set. Inspect native state before clearing it;
never automatically replay a timed-out construction command.
"""
import json
import sys
from pathlib import Path

from build_line1 import distance, simplify
from session_call import call

CHECKPOINT = Path('work/airport-built.json')


def run():
    plan = json.loads(Path('data/airport_plan.json').read_text(encoding='utf-8'))
    state = json.loads(CHECKPOINT.read_text(encoding='utf-8')) if CHECKPOINT.exists() else dict(stations=[], corridors=[], commands=[], pending=None)

    def save():
        tmp = CHECKPOINT.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(CHECKPOINT)

    def mutate(tool, **args):
        assert state['pending'] is None, 'Uncertain command requires inspection'
        state['pending'] = dict(tool=tool, arguments=args)
        save()
        result = call(tool, **args)
        state['commands'].append(dict(**state['pending'], result=result))
        state['pending'] = None
        save()
        return result

    assert state['pending'] is None, 'Inspect pending native command before resuming'
    status = call('runtime_status')
    assert status['speed'] == 0, 'Pause through MCP before building'
    if 'initial_runtime' not in state:
        state['initial_runtime'] = status
        save()
    # Blueprint creation precedes the actual native construction bill.
    for s in state['stations']:
        node = call('get_track_node', node_id=s['platform_nodes'][0])
        assert node and node['station_id'] == s['native_station'], 'Checkpoint is not this live world'
    for s in plan['stations'][len(state['stations']):]:
        a, b = s['start'], s['end']
        result = mutate('create_platform', start_x=a['x'], start_y=a['y'], end_x=b['x'], end_y=b['y'], depth=1 if s['depth'] == 1 else -1)
        platforms = [n for n in result['nodes'] if n['station_id'] != '0']
        assert len(platforms) == 4
        byid = {n['id']: n for n in platforms}
        p0 = min(platforms, key=lambda n: distance(n, a))
        p1 = byid[p0['next']]
        p2 = next(n for n in platforms if n['id'] not in [p0['id'], p1['id']] and n['next'] in byid)
        p3 = byid[p2['next']]
        record = dict(**s, native_station=p0['station_id'], west_stop=p0['id'], east_stop=p2['id'],
                      west_primary=p0['previous'], east_primary=p1['next'],
                      west_secondary=p3['next'], east_secondary=p2['previous'], platform_nodes=list(byid))
        state['stations'].append(record)
        save()
        if s['depth'] not in [-1, 1]:
            mutate('set_track_depth', node_ids=[n['id'] for n in result['nodes']], depth=s['depth'])
        if s.get('interchange_station_id'):
            mutate('assign_platform_station', node_ids=record['platform_nodes'], station_id=s['interchange_station_id'])
            record['native_station'] = s['interchange_station_id']
            save()
        else:
            mutate('rename_station', station_id=record['native_station'], name=s['name'])
        print(f"Station {len(state['stations'])}/5: {s['name']}", flush=True)
    state['status'] = 'stations-created-awaiting-corridor-plan'
    save()
    if '--stations-only' in sys.argv:
        return
    # The urban section has two parallel tracks; airport branches are planned separately.
    for i in range(len(state['corridors']), 2):
        first, second = state['stations'][i:i+2]
        if 'active_corridor' not in state:
            start = call('get_track_node', node_id=first['east_primary'])
            end = call('get_track_node', node_id=second['west_primary'])
            route = plan['outbound']['route']
            interior = [dict(p, depth=-2) for p in route[first['route_index']+1:second['route_index']]
                        if distance(p, first) > 220 and distance(p, second) > 220]
            points = simplify([start]+interior+[end], tolerance=12)
            state['active_corridor'] = dict(index=i, current=start, end=end, points=points, point_index=1)
            save()
        active = state['active_corridor']
        assert active['index'] == i
        while active['point_index'] < len(active['points'])-1:
            p = active['points'][active['point_index']]
            current = active['current']
            if distance(current, p) >= 40:
                result = mutate('extend_track', node_id=current['id'], end_x=p['x'], end_y=p['y'], depth=-1)
                mutate('set_track_depth', node_ids=[n['id'] for n in result['nodes']], depth=-2)
                active['current'] = min([n for n in result['nodes'] if n['id'] != current['id']], key=lambda n: distance(n, p))
            active['point_index'] += 1
            save()
        result = mutate('connect_track_endpoints', start_node_id=active['current']['id'], end_node_id=active['end']['id'], dual=True)
        state['corridors'].append(dict(from_station=first['name'], to_station=second['name'], result=result))
        del state['active_corridor']
        save()
        print(f"Urban corridor {i+1}/2: {first['name']} — {second['name']}", flush=True)
    if len(state['corridors']) == 2:
        first, second = state['stations'][2:4]
        if 'active_corridor' not in state:
            start = call('get_track_node', node_id=first['east_primary'])
            end = call('get_track_node', node_id=second['west_primary'])
            route, edges = plan['outbound']['route'], plan['outbound']['edges']
            interior = []
            for index in range(first['route_index']+1, second['route_index']):
                p = route[index]
                if distance(p, first) <= 220 or distance(p, second) <= 220:
                    continue
                depth = -2 if distance(p, first) < 450 else edges[index-1]['depth']
                interior.append(dict(p, depth=depth))
            points = simplify([start]+interior+[end], tolerance=12)
            state['active_corridor'] = dict(index=2, current=start, end=end, points=points, point_index=1)
            save()
        active = state['active_corridor']
        assert active['index'] == 2
        while active['point_index'] < len(active['points'])-1:
            p = active['points'][active['point_index']]
            current = active['current']
            if distance(current, p) >= 40:
                result = mutate('extend_track', node_id=current['id'], end_x=p['x'], end_y=p['y'], depth=max(-1, p['depth']))
                if p['depth'] == -2:
                    mutate('set_track_depth', node_ids=[n['id'] for n in result['nodes']], depth=-2)
                active['current'] = min([n for n in result['nodes'] if n['id'] != current['id']], key=lambda n: distance(n, p))
            active['point_index'] += 1
            save()
        result = mutate('connect_track_endpoints', start_node_id=active['current']['id'], end_node_id=active['end']['id'], dual=True)
        state['corridors'].append(dict(from_station=first['name'], to_station=second['name'], result=result))
        del state['active_corridor']
        print('Airport trunk: 三元桥 — T3', flush=True)
    state['status'] = 'trunk-blueprints-created-airport-branches-pending'
    save()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run()
