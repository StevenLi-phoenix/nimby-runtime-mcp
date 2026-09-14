"""Reuse live G directed stops for F's eight shared Brooklyn stations."""
import json
from pathlib import Path
from session_call import _call


def prepare():
    g = json.loads(Path('work/nyc-g-built.json').read_bytes())
    line = _call('get_line', {'line_id': g['line_id']})
    assert line['code'] == 'nyc-g' and line['stop_count'] == 42
    selected = sorted((s for s in g['stations'] if 13 <= s['plan_index'] <= 20), key=lambda s: s['plan_index'])
    directed = [(s, line['stops'][s['plan_index']], line['stops'][41-s['plan_index']]) for s in selected]
    ids = [stop['node_id'] for _, a, b in directed for stop in [a, b]]
    live = _call('get_track_network', dict(seed_node_ids=ids, detail='geometry'))
    nodes = {n['id']: n for n in live['nodes']}
    rows = []
    for station, south, north in directed:
        assert south['node_id'] != north['node_id']
        for stop in [south, north]:
            n = nodes[stop['node_id']]
            assert n['station_id'] == station['native_station'] and not n['blueprint']
        rows.append(dict(f_plan_index=station['plan_index']+12, station_id=station['native_station'],
                         to_coney_island=south, to_jamaica=north))
    result = dict(source_line_id=line['id'], source_line_code=line['code'], source_service=line['service'],
                  shared_stations=rows, stage='live_directed_platform_mapping_only',
                  pending=['Map remaining F stations and configure native line.',
                           'Verify F boundary paths at Jay Street and Ditmas Avenue.',
                           'Verify terminal reversal and live F trains.'])
    Path('data/nyc_f_shared_directed_stops.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(shared_stations=len(rows), directed_platforms=len(ids), source_service=line['service'])))


if __name__ == '__main__':
    prepare()
