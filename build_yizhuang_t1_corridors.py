"""Connect current Yizhuang T1 station blueprints; never build or restore old station geometry."""
import bisect
import json
import math
import sys
import time
from pathlib import Path

from build_line1 import distance, simplify
from session_call import call

CHECKPOINT = Path('work/yizhuang_t1-corridors.json')


def run():
    stations = json.loads(Path('work/yizhuang_t1-built.json').read_text(encoding='utf-8'))['stations']
    plan = json.loads(Path('data/yizhuang_t1_plan.json').read_text(encoding='utf-8'))
    state = json.loads(CHECKPOINT.read_text(encoding='utf-8')) if CHECKPOINT.exists() else {
        'corridors': [], 'commands': [], 'pending': None}
    assert state['pending'] is None, 'Inspect uncertain command before resuming'
    assert call('runtime_status')['speed'] == 0

    def save():
        tmp = CHECKPOINT.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        for attempt in range(20):
            try:
                tmp.replace(CHECKPOINT)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.1)


    def mutate(tool, **args):
        assert state['pending'] is None
        state['pending'] = dict(tool=tool, arguments=args)
        save()
        result = call(tool, **args)
        state['commands'].append(dict(**state['pending'], result=result))
        return result

    def finish():
        state['pending'] = None
        save()

    route = plan['route']
    chain = [0.0]
    for a, b in zip(route, route[1:]):
        chain.append(chain[-1]+distance(a, b))

    for i in range(len(state['corridors']), len(stations)-1):
        first, second = stations[i:i+2]
        if 'active' not in state:
            start = call('get_track_node', node_id=first['east_primary'])
            end = call('get_track_node', node_id=second['west_primary'])
            assert start['blueprint'] and end['blueprint']
            assert '0' in (start['previous'], start['next']) and '0' in (end['previous'], end['next']), 'Endpoint already connected'
            margin = 170/math.cos(math.radians(first['latitude']))
            points = []
            for p, c in zip(route, chain):
                if not first['chainage']+margin < c < second['chainage']-margin:
                    continue
                depth = p['depth']
                if start['depth'] < -1 and c-first['chainage'] < 500:
                    depth = start['depth']
                if end['depth'] < -1 and second['chainage']-c < 500:
                    depth = end['depth']
                points.append(dict(p, depth=depth, chainage=c))
            points = simplify([start]+points+[end], tolerance=16)
            if i == 5:
                # Preserve the last ground approach before the bridge, omitting
                # two collinear controls separated by only 28m and 7m.
                points = [p for p in points if p.get('osm_id') not in {9990843688, 11294857316}]
            if i == 10:
                # Source bridge end and first ground point are 2.5m apart.
                # Retain the bridge end; place its ground transition 40m farther
                # along the outgoing alignment instead of constructing a kink.
                j = next(j for j,p in enumerate(points) if p.get('osm_id') == 6205716946)
                a, b = points[j], points[j+1]
                span = distance(a, b)
                points[j] = dict(a, x=a['x']+(b['x']-a['x'])*40/span,
                                 y=a['y']+(b['y']-a['y'])*40/span,
                                 geometry_note='Ground transition extended 40 world metres beyond source bridge end')
            # Do not silently omit short grade changes; leave them for explicit review.
            short = [(j, distance(a, b)) for j, (a,b) in enumerate(zip(points, points[1:])) if distance(a,b)<35]
            assert not short, f'{first["name"]} to {second["name"]}: short controls {short}'
            state['active'] = dict(index=i, from_station=first['name'], to_station=second['name'],
                points=points, point_index=1, current=start, end=end,
                initial_endpoints=[start, end], desired_depths={start['id']:start['depth'], end['id']:end['depth']},
                created_ids=[], stage='extending')
            save()
        active = state['active']
        assert active['index'] == i
        while active['point_index'] < len(active['points'])-1:
            p = active['points'][active['point_index']]
            current = call('get_track_node', node_id=active['current']['id'])
            assert current['blueprint'] and '0' in (current['previous'], current['next'])
            result = mutate('extend_track', node_id=current['id'], end_x=p['x'], end_y=p['y'], depth=max(-1,p['depth']))
            new = [n for n in result['nodes'] if n['id'] != current['id']]
            active['current'] = min(new, key=lambda n:distance(n,p))
            for n in new:
                # Extension returns the new control pair. Preserve already-recorded endpoint layers.
                if n['id'] not in active['desired_depths']:
                    active['desired_depths'][n['id']] = p['depth']
                    active['created_ids'].append(n['id'])
            active['point_index'] += 1
            finish()
        if active['stage'] == 'extending':
            result = mutate('connect_track_endpoints', start_node_id=active['current']['id'], end_node_id=active['end']['id'], dual=True)
            active['connection'] = result
            active['stage'] = 'connected'
            finish()
        if active['stage'] == 'connected':
            # Native connection commands can reset endpoint layers. Restore desired layers after connection.
            for depth in sorted(set(active['desired_depths'].values())):
                ids = [n for n,d in active['desired_depths'].items() if d == depth]
                changed = [n for n in ids if call('get_track_node',node_id=n)['depth'] != depth]
                if changed:
                    mutate('set_track_depth', node_ids=changed, depth=depth)
                    finish()
            active['stage'] = 'layers-verified'
            save()
        state['corridors'].append(active)
        del state['active']
        save()
        print(f'Corridor {i+1}/13 connected', flush=True)
    state['status'] = 'corridor-blueprints-awaiting-paired-tangents-crossings-and-visual-review'
    save()


if __name__ == '__main__':
    run()
