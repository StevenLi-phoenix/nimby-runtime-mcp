"""Create Line 17 station blueprints only; never commit construction implicitly."""
import hashlib
import json
import math
from pathlib import Path

from session_call import call

CHECKPOINT = Path('work/line17-built.json')


def run():
    raw = Path('data/line17_plan.json').read_bytes()
    plan = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    state = json.loads(CHECKPOINT.read_text(encoding='utf-8')) if CHECKPOINT.exists() else {
        'plan_sha256': digest, 'stations': [], 'commands': [], 'pending': None}
    assert state['plan_sha256'] == digest, 'Plan changed; inspect current world before proceeding'
    assert state['pending'] is None, 'Uncertain command: inspect its result, never replay'
    assert call('runtime_status')['speed'] == 0

    def save():
        tmp = CHECKPOINT.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(CHECKPOINT)

    def mutate(tool, **arguments):
        state['pending'] = dict(tool=tool, arguments=arguments)
        save()
        result = call(tool, **arguments)
        state['commands'].append(dict(**state['pending'], result=result))
        # Keep pending until the caller has recorded the native IDs and stage.
        return result

    def finish():
        state['pending'] = None
        save()

    for index, s in enumerate(plan['stations']):
        if index == len(state['stations']):
            a, b = s['start'], s['end']
            nearby = call('get_nearby_track_nodes', x=s['x'], y=s['y'], radius=80)['nodes']
            assert not any(n['station_id'] != '0' and n['blueprint'] for n in nearby), 'Existing blueprint: inspect before creating'
            result = mutate('create_platform', start_x=a['x'], start_y=a['y'],
                            end_x=b['x'], end_y=b['y'], depth=max(-1, s['depth']))
            platforms = {n['id']: n for n in result['nodes'] if n['station_id'] != '0'}
            assert len(platforms) == 4
            p0 = min(platforms.values(), key=lambda n: math.hypot(n['x']-a['x'], n['y']-a['y']))
            p1 = platforms[p0['next']]
            p2 = next(n for n in platforms.values() if n['id'] not in (p0['id'], p1['id']) and n['next'] in platforms)
            p3 = platforms[p2['next']]
            state['stations'].append(dict(**s, native_station=p0['station_id'],
                temporary_station=p0['station_id'], nodes=[n['id'] for n in call('get_track_network', seed_node_ids=list(platforms))['nodes']],
                platform_nodes=list(platforms), west_stop=p0['id'], east_stop=p2['id'],
                west_primary=p0['previous'], east_primary=p1['next'],
                west_secondary=p3['next'], east_secondary=p2['previous'], stage='created'))
            finish()
        record = state['stations'][index]
        live = call('get_track_node', node_id=record['west_stop'])
        assert live and live['station_id'] == record['native_station'], 'World differs from checkpoint'
        if record['stage'] == 'created':
            if s['depth'] < -1:
                mutate('set_track_depth', node_ids=record['nodes'], depth=s['depth'])
            record['stage'] = 'layered'
            finish()
        if record['stage'] == 'layered':
            if s.get('interchange_station_id'):
                mutate('assign_platform_station', node_ids=record['platform_nodes'], station_id=s['interchange_station_id'])
                record['native_station'] = s['interchange_station_id']
            else:
                mutate('rename_station', station_id=record['native_station'], name=s['name'])
            record['stage'] = 'assigned'
            finish()
        if record['stage'] == 'assigned':
            verified = [call('get_track_node', node_id=n) for n in record['platform_nodes']]
            assert all(n['station_id'] == record['native_station'] and n['blueprint'] and n['depth'] == s['depth'] for n in verified)
            assert all(b['depth'] == s['depth'] for n in verified for b in n['buildings'])
            record['stage'] = 'verified'
            save()
        print(f"Station {index+1}/20 verified", flush=True)
    state['status'] = 'station-blueprints-awaiting-corridors-and-curve-review'
    save()
    if not state.get('temporary_stations_cleaned'):
        inventory = {s['id']: s for s in call('get_station_inventory')['stations']}
        temporary = [s['temporary_station'] for s in state['stations']
                     if s['temporary_station'] != s['native_station']
                     and s['temporary_station'] in inventory]
        assert all(inventory[s]['track_count'] == 0 for s in temporary)
        if temporary:
            mutate('delete_empty_stations', station_ids=temporary)
        state['temporary_stations_cleaned'] = True
        finish()


if __name__ == '__main__':
    run()
