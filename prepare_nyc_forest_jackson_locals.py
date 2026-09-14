"""Reserve unbuilt local alignments alongside verified native express geometry.

Retain source lateral separation, including station widening. These are
geometric candidates, not constructed tracks or a substitute for local stops.
"""
import json
import math
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.ops import nearest_points, substring, unary_union


def prepare():
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    plan = json.loads(Path('data/nyc_forest_jackson_corridors.json').read_bytes())
    ns = {n['id']: n for n in json.loads(Path('work/nyc-forest-jackson-connected.json').read_bytes())['nodes']}
    source = json.loads(Path(plan['source']).read_bytes())
    scale = plan['scale']
    candidates = []
    native = {}
    for e, c, ref, island, key in zip(state['forest_jackson_corridors'], plan['corridors'], ['1', '2'], [0, 1], ['secondary', 'primary']):
        ids = [e['start']] + e['nodes'] + [e['end']]
        coords = []
        for index, i in enumerate(ids):
            n = ns[i]
            forward = n['next'] == ids[index+1] if index < len(ids)-1 else n['previous'] == ids[index-1]
            part = n['curve'] if forward else n['curve'][::-1]
            if coords:
                assert math.dist(coords[-1], part[0]) < .001
            coords += part if not coords else part[1:]
        line = LineString(coords)
        start = Point(ns[e['start']]['x'], ns[e['start']]['y'])
        end = Point(ns[e['end']]['x'], ns[e['end']]['y'])
        line = substring(line, line.project(start), line.project(end))
        native[e['track_ref']] = line
        start_id = state['forest_hills_islands'][island]['east_'+key]
        end_id = state['jackson_islands'][island]['west_'+key]
        fast_source = unary_union([LineString([(p['x'], p['y']) for p in w['points']]) for w in source['ways'] if w['osm_way_id'] in c['source_way_ids']])
        local_source = unary_union([LineString([(p['x'], p['y']) for p in w['points']]) for w in source['ways'] if w['tags'].get('name') == 'IND Queens Boulevard Line' and w['tags'].get('railway:track_ref') == ref])
        samples = []
        count = math.ceil(line.length*scale/10)
        for index in range(count+1):
            d = line.length*index/count
            q = line.interpolate(d)
            a, b = line.interpolate(max(0, d-5/scale)), line.interpolate(min(line.length, d+5/scale))
            dx, dy = b.x-a.x, b.y-a.y
            length = math.hypot(dx, dy)
            normal = (-dy/length, dx/length)
            on_source = nearest_points(q, fast_source)[1]
            gap = max(3.8, on_source.distance(local_source)*scale)
            assert gap < 30
            sign = -1 if ref == '1' else 1
            samples.append(dict(x=q.x+sign*normal[0]*gap/scale,
                                y=q.y+sign*normal[1]*gap/scale,
                                metres=d*scale, source_separation_metres=gap))
        deltas = [{k: ns[i][k]-q[k] for k in ['x', 'y']} for i, q in [(start_id, samples[0]), (end_id, samples[-1])]]
        for q in samples:
            for remaining, delta in [(q['metres'], deltas[0]), (samples[-1]['metres']-q['metres'], deltas[1])]:
                t = max(0, 1-remaining/150)
                for k in ['x', 'y']:
                    q[k] += delta[k]*t*t*(3-2*t)
        candidates.append(dict(track_ref=ref, start_node_id=start_id, end_node_id=end_id, points=samples,
                               stage='reserved_geometry_not_built'))
    clearances = []
    for c in candidates:
        line = LineString([(q['x'], q['y']) for q in c['points']])
        assert line.is_simple
        for ref, fast in native.items():
            gap = line.distance(fast)*scale
            clearances.append(dict(local=c['track_ref'], express=ref, gap_metres=gap))
            assert gap > 3.5, clearances[-1]
    result = dict(source=plan['source'], native_snapshot='work/nyc-forest-jackson-connected.json',
                  scale=scale, candidates=candidates, clearances=clearances,
                  pending=['Plan and build local platforms at 67 Avenue, 63 Drive, Woodhaven Boulevard, Grand Avenue and Elmhurst Avenue.',
                           'Audit native local curves, grades and crossovers before construction.'])
    Path('data/nyc_forest_jackson_local_candidates.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(clearances))


if __name__ == '__main__':
    prepare()
