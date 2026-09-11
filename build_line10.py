"""Checkpoint each native MCP command for the complete Beijing Line 10 ring.

An uncertain command leaves pending set. Inspect native state before clearing it;
never automatically replay a timed-out construction command.
"""
import json
import math
import sys
from pathlib import Path

from build_line1 import distance, simplify
from session_call import call

CHECKPOINT = Path('work/line10-built.json')


def run():
    plan = json.loads(Path('data/line10_plan.json').read_text(encoding='utf-8'))
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
        result = mutate('create_platform', start_x=a['x'], start_y=a['y'], end_x=b['x'], end_y=b['y'], depth=-1)
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
        if s['depth'] != -1:
            mutate('set_track_depth', node_ids=[n['id'] for n in result['nodes']], depth=s['depth'])
        if s.get('interchange_station_id'):
            mutate('assign_platform_station', node_ids=record['platform_nodes'], station_id=s['interchange_station_id'])
            record['native_station'] = s['interchange_station_id']
            save()
        else:
            mutate('rename_station', station_id=record['native_station'], name=s['name'])
        print(f"Station {len(state['stations'])}/45: {s['name']}", flush=True)
    state['status'] = 'stations-created-awaiting-corridor-plan'
    save()
    if '--stations-only' in sys.argv:
        return
    route = plan['route']
    chain = [0.0]
    for a, b in zip(route, route[1:]):
        chain.append(chain[-1]+distance(a, b))
    stations = state['stations']
    for i in range(len(state['corridors']), 45):
        first, second = stations[i], stations[(i+1) % 45]
        if 'active_corridor' not in state:
            start = call('get_track_node', node_id=first['east_primary'])
            end = call('get_track_node', node_id=second['west_primary'])
            margin = 160/math.cos(math.radians(first['latitude']))
            total = chain[-1]
            span = (second['chainage']-first['chainage']) % total
            interior = sorted(((c-first['chainage']) % total, p) for p,c in zip(route[:-1],chain[:-1]) if margin < (c-first['chainage']) % total < span-margin)
            points = simplify([start]+[p for _,p in interior]+[end], tolerance=12)
            for point in points[1:-1]:
                point['depth'] = -2 if (first['depth']==-2 and distance(point,first)<400) or (second['depth']==-2 and distance(point,second)<400) else -1
            state['active_corridor'] = dict(index=i, current=start, end=end, points=points, point_index=1)
            save()
        active = state['active_corridor']
        assert active['index'] == i
        while active['point_index'] < len(active['points'])-1:
            p = active['points'][active['point_index']]
            current = active['current']
            if distance(current, p) >= 40:
                result = mutate('extend_track', node_id=current['id'], end_x=p['x'], end_y=p['y'], depth=p['depth'])
                active['current'] = min([n for n in result['nodes'] if n['id'] != current['id']], key=lambda n: distance(n, p))
            active['point_index'] += 1
            save()
        result = mutate('connect_track_endpoints', start_node_id=active['current']['id'], end_node_id=active['end']['id'], dual=True)
        state['corridors'].append(dict(from_station=first['name'], to_station=second['name'], result=result))
        del state['active_corridor']
        save()
        print(f"Corridor {i+1}/45: {first['name']} — {second['name']}", flush=True)
    state['status'] = 'blueprints-awaiting-construction-check'
    save()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run()
