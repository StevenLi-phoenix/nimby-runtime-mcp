"""Plan a shallow Court Square relay without occupying future through tracks."""
import hashlib
import json
import math
from pathlib import Path


def prepare():
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    live = json.loads(Path('work/nyc-court-turnback-live.json').read_bytes())
    nodes = {n['id']: n for n in live['nodes']}
    station = next(s for s in state['stations'] if s['plan_index'] == 0)
    a, b = station['start'], station['end']
    length = math.hypot(a['x']-b['x'], a['y']-b['y'])
    tx, ty = (a['x']-b['x'])/length, (a['y']-b['y'])/length
    scale = 1/math.cosh(a['y']/6378137)
    tracks = []
    for key in ['west_primary', 'west_secondary']:
        start = nodes[station[key]]
        assert start['depth'] == -2 and not start['blueprint']
        assert '0' in [start['previous'], start['next']]
        points = [dict(x=start['x'], y=start['y'], depth=-2, metres=0)]
        points += [dict(x=start['x']+tx*d/scale, y=start['y']+ty*d/scale, depth=depth, metres=d)
                   for d, depth in [(20,-2), (70,-1), (230,-1), (400,-1)]]
        tracks.append(dict(role=key, start_node_id=start['id'], points=points))
    parent_ids = {t['start_node_id'] for t in tracks}
    branches = [n['id'] for n in nodes.values() if n['branch_parent'] in parent_ids]
    assert len(branches) == 4
    return dict(station='Court Square', station_id=station['native_station'], tracks=tracks,
                outward_tangent=dict(x=tx,y=ty), scale=scale,
                crossover=dict(from_role='west_secondary', from_metres=250,
                               to_role='west_primary', to_metres=190, depth=-1,
                               clear_length_beyond_arrival_branch_metres=150),
                superseded_north_crossovers=branches,
                source_sha256=hashlib.sha256(Path('data/nyc_court_square_source.json').read_bytes()).hexdigest(),
                adaptation='400m shallow station-after relay at -1; real source leads join Queens Boulevard at -2. Future Queens Boulevard and 60th Street Tunnel tracks also occupy -3. This relay is a game adaptation, not a claimed real facility; no depot or yard links.',
                stage='native_blueprint_geometry_pending')


if __name__ == '__main__':
    result=prepare()
    Path('data/nyc_court_turnback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
