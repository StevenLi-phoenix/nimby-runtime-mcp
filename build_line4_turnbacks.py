"""Add Line 4 station-after reversals from live endpoints, preserving player edits."""
import json
import math
from pathlib import Path

from audit_crossings import native_crossings
from session_call import call

CHECKPOINT = Path('work/line4-station-after-turnbacks.json')


def run():
    assert not CHECKPOINT.exists(), 'Inspect saved operations before resuming; do not replay'
    stations = json.loads(Path('work/line4-built.json').read_text(encoding='utf-8'))['stations']
    seeds = [s['west_stop'] for s in stations]
    before = call('get_track_network', seed_node_ids=seeds)
    assert call('runtime_status')['speed'] == 0
    assert len(before['nodes']) == 458 and all(not n['blueprint'] for n in before['nodes'])
    state = dict(before=before, commands=[], pending=None, turnbacks=[])

    def save():
        tmp = CHECKPOINT.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(CHECKPOINT)

    def mutate(tool, **arguments):
        state['pending'] = dict(tool=tool, arguments=arguments)
        save()
        result = call(tool, **arguments)
        state['commands'].append(dict(**state['pending'], result=result))
        state['pending'] = None
        save()
        return result

    for station, side in [(stations[0], 'west'), (stations[-1], 'east')]:
        live = call('get_track_network', seed_node_ids=seeds)
        byid = {n['id']: n for n in live['nodes']}
        primary = byid[station[f'{side}_primary']]
        secondary = byid[station[f'{side}_secondary']]
        assert '0' in (primary['previous'], primary['next'])
        assert '0' in (secondary['previous'], secondary['next'])
        assert primary['depth'] == secondary['depth']
        inside = byid[primary['next'] if primary['previous'] == '0' else primary['previous']]
        dx, dy = primary['x']-inside['x'], primary['y']-inside['y']
        length = math.hypot(dx, dy)
        scale = math.cosh(primary['y']/6378137)
        end_x = primary['x'] + dx/length*400*scale
        end_y = primary['y'] + dy/length*400*scale
        mutate('rebuild_track_blueprints', node_ids=[primary['id'], secondary['id']])
        extended = mutate('extend_track', node_id=primary['id'], end_x=end_x,
                          end_y=end_y, depth=primary['depth'])
        new_nodes = [n for n in extended['nodes'] if n['id'] not in byid]
        assert len(new_nodes) == 2
        if primary['previous'] == '0':
            start_edge = primary['id']
            end_edge = next(n['id'] for n in new_nodes if n['previous'] == secondary['id'])
        else:
            start_edge = next(n['id'] for n in new_nodes if n['previous'] == primary['id'])
            end_edge = secondary['id']
        branch = mutate('create_track_branch', start_edge_id=start_edge, start_position=.35,
                        end_edge_id=end_edge, end_position=.35, depth=primary['depth'])
        state['turnbacks'].append(dict(station=station['name'], depth=primary['depth'],
             extension_metres=400, new_nodes=[n['id'] for n in new_nodes+branch['nodes']]))
        save()

    network = call('get_track_network', seed_node_ids=seeds)
    ids = {n['id'] for n in network['nodes']}
    assert len(ids) == 466
    blueprint_ids = [n['id'] for n in network['nodes'] if n['blueprint']]
    assert len(blueprint_ids) == 12
    checks = call('get_track_build_checks', node_ids=blueprint_ids)
    lines = [call('get_line', line_id=i) for i in ['1125899906842625', '1125899906973697',
             '1125899907039233', '1125899907104769', '1125899907170305', '1125899907301377',
             '1125899907366913']]
    world = call('get_track_network', seed_node_ids=seeds+[l['stops'][0]['node_id'] for l in lines])
    crossline = [h for h in native_crossings(world['nodes']) if (h['a'] in ids) != (h['b'] in ids)]
    state.update(network=network, checks=checks, crossline=crossline)
    save()
    assert not checks['blocked'] and not crossline, 'Inspect live conflicts before building'
    mutate('build_selected_blueprints', node_ids=blueprint_ids, protected_node_ids=[])
    state['after'] = call('get_track_network', seed_node_ids=seeds)
    assert all(not n['blueprint'] for n in state['after']['nodes'])
    save()
    print(json.dumps(dict(nodes=len(ids), built=True, turnbacks=state['turnbacks']), ensure_ascii=True))


if __name__ == '__main__':
    run()
