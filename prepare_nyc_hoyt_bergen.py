"""Plan the G approach and short F mainline interfaces at the Bergen merge."""
import bisect
import json
import math
from pathlib import Path

from prepare_nyc_g_corridors import simplify, offset


def interpolate(route, chainage):
    chain = [p['chainage'] for p in route]
    i = max(0, min(len(route)-2, bisect.bisect_right(chain, chainage)-1))
    f = (chainage-chain[i])/(chain[i+1]-chain[i])
    return {k: route[i][k]+f*(route[i+1][k]-route[i][k]) for k in ('x', 'y')}


def prepare():
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    g = json.loads(Path('data/nyc_g_plan.json').read_bytes())
    f = json.loads(Path('data/nyc_f_plan.json').read_bytes())
    live = json.loads(Path('work/nyc-hoyt-bergen-live.json').read_bytes())
    nodes = {n['id']: n for n in live['nodes']}
    stations = {s['plan_index']: s for s in state['stations']}
    hoyt, bergen = stations[12], stations[13]
    result = []
    for ref, gkey, fkey, junction_id, primary in [
        ('1', 'to_church', 'to_coney_island', 7644660141, False),
        ('2', 'to_court_square', 'to_jamaica', 7644660142, True),
    ]:
        gd, fd = g['directions'][gkey], f['directions'][fkey]
        junction = next(p for p in fd['route'] if p['osm_node_id'] == junction_id)
        fsign = -1 if ref == '1' else 1
        scale = math.cos(math.radians(junction['latitude']))
        stub = interpolate(fd['route'], junction['chainage']+fsign*120/scale)
        end_id = bergen['west_primary' if primary else 'west_secondary']
        start_id = hoyt['east_primary' if primary else 'east_secondary']
        start = nodes[start_id]
        route = gd['route']
        chain = [p['chainage'] for p in route]
        candidates = []
        for i, (a, b) in enumerate(zip(route, route[1:])):
            distance, t = offset(start, a, b)
            candidates.append((distance, chain[i]+t*(chain[i+1]-chain[i])))
        s0 = min(candidates)[1]
        s1 = next(p['chainage'] for p in route if p['osm_node_id'] == junction_id)
        points = [dict(**p, depth=gd['segments'][min(i, len(gd['segments'])-1)]['candidate_depth'])
                  for i, p in enumerate(route) if min(s0, s1)+35 < p['chainage'] < max(s0, s1)-35]
        if s1 < s0:
            points.reverse()
        points = [dict(x=start['x'], y=start['y'], depth=start['depth'])] + points
        points += [dict(x=junction['x'], y=junction['y'], depth=-1)]
        # The exact junction will be projected onto the native F mainline curve.
        kept = simplify(points, tolerance=5)
        result.append(dict(track_ref=ref, g_start_node_id=start_id, bergen_endpoint_id=end_id,
                           source_junction_node_id=junction_id,
                           source_junction={k: junction[k] for k in ('x', 'y')},
                           f_stub_start=dict(**stub, depth=-1), g_candidate_points=kept,
                           status='native_branch_position_pending'))
    return dict(section='Hoyt–Bergen G/F merge', tracks=result,
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright',
                adaptations=['Preserve existing Hoyt platforms; connect its primary to B2 and secondary to B1.',
                             'F interfaces extend only 120 actual metres upstream of the source merge; not depots.',
                             'Native branch positions must be sampled before connecting G.'],
                pending=['Continue F mainline north to Jay Street.', 'Verify operational directions and junction signals.'])


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_hoyt_bergen_merge.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
