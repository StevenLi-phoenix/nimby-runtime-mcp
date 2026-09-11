"""Build the two airport service branches through native single-track commands."""
import json
from pathlib import Path

from build_line1 import distance, simplify
from session_call import call

PATH = Path('work/airport-branches-built.json')


def run():
    plan = json.loads(Path('data/airport_plan.json').read_text(encoding='utf-8'))
    built = json.loads(Path('work/airport-built.json').read_text(encoding='utf-8'))
    anchors = json.loads(Path('work/airport-branch-anchors.json').read_text(encoding='utf-8'))['anchors']
    state = json.loads(PATH.read_text(encoding='utf-8')) if PATH.exists() else dict(commands=[], completed=[], pending=None)

    def save():
        PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    def mutate(tool, **args):
        assert state['pending'] is None
        state['pending'] = dict(tool=tool, arguments=args)
        save()
        result = call(tool, **args)
        state['commands'].append(dict(**state['pending'], result=result))
        state['pending'] = None
        save()
        return result

    assert state['pending'] is None, 'Inspect pending native command before resuming'
    assert call('runtime_status')['speed'] == 0
    terminal = built['stations'][4]
    specs = [('t3-to-t2', 'outbound', list(range(173, 213)), 'west_secondary'),
             ('t2-to-city', 'inbound', list(range(45, 0, -1)), 'west_primary')]
    for index in range(len(state['completed']), len(specs)):
        name, direction, indices, endpoint = specs[index]
        anchor = anchors[index]
        if 'active' not in state:
            end = call('get_track_node', node_id=terminal[endpoint])
            route, edges = plan[direction]['route'], plan[direction]['edges']
            interior = [dict(route[i], depth=edges[max(0, i-1)]['depth']) for i in indices
                        if distance(route[i], anchor['actual']) > 100 and distance(route[i], terminal) > 220]
            points = simplify([dict(anchor['actual'], depth=anchor['depth'])]+interior+[end], tolerance=12)
            state['active'] = dict(name=name, points=points, point_index=1,
                                   current={k: anchor[k] for k in ['edge_id', 'position', 'depth']}, end=end['id'])
            save()
        active = state['active']
        assert active['name'] == name
        while active['point_index'] < len(active['points'])-1:
            p = active['points'][active['point_index']]
            result = mutate('create_single_track_connection', start=active['current'],
                            end={k: p[k] for k in ['x', 'y', 'depth']})
            node = min(result['nodes'], key=lambda n: distance(n, p))
            active['current'] = {'id': node['id']}
            active['point_index'] += 1
            save()
        mutate('create_single_track_connection', start=active['current'], end={'id': active['end']})
        state['completed'].append(active)
        del state['active']
        save()
        print(name, 'blueprints created', flush=True)


if __name__ == '__main__':
    run()
