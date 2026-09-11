"""Add Line 9 station-after reversals from live endpoints, preserving player edits."""
import json
import math
from pathlib import Path

from audit_crossings import native_crossings
from session_call import call

CHECKPOINT = Path('work/line9-station-after-turnbacks.json')


def run():
    assert not CHECKPOINT.exists(), 'Inspect saved operations before resuming; do not replay'
    stations = json.loads(Path('work/line9-built.json').read_text(encoding='utf-8'))['stations']
    seeds = [s['west_stop'] for s in stations]
    before = call('get_track_network', seed_node_ids=seeds)
    assert call('runtime_status')['speed'] == 0
    assert len(stations) == 13 and all(n['blueprint'] for n in before['nodes'])
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
        extended = mutate('extend_track', node_id=primary['id'], end_x=end_x,
                          end_y=end_y, depth=max(-1,primary['depth']))
        new_nodes = [n for n in extended['nodes'] if n['id'] not in byid]
        assert len(new_nodes) == 2
        if primary['previous'] == '0':
            start_edge = primary['id']
            end_edge = next(n['id'] for n in new_nodes if n['previous'] == secondary['id'])
        else:
            start_edge = next(n['id'] for n in new_nodes if n['previous'] == primary['id'])
            end_edge = secondary['id']
        branch = mutate('create_track_branch', start_edge_id=start_edge, start_position=.35,
                        end_edge_id=end_edge, end_position=.35, depth=max(-1,primary['depth']))
        if primary['depth'] < -1:
            mutate('set_track_depth', node_ids=[primary['id'], secondary['id']]+[n['id'] for n in new_nodes+branch['nodes']], depth=primary['depth'])
        state['turnbacks'].append(dict(station=station['name'], depth=primary['depth'],
             extension_metres=400, new_nodes=[n['id'] for n in new_nodes+branch['nodes']]))
        save()

    network = call('get_track_network', seed_node_ids=seeds)
    assert len(network['nodes']) == len(before['nodes']) + 8
    assert all(n['blueprint'] for n in network['nodes'])
    state.update(after=network,status='turnback-blueprints-awaiting-audit')
    save()
    print(json.dumps(dict(nodes=len(network['nodes']),turnbacks=state['turnbacks']),ensure_ascii=True))


if __name__ == '__main__':
    run()
