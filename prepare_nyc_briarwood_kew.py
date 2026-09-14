"""Plan four through tracks between Briarwood and Kew Gardens; yard links excluded."""
import json
from pathlib import Path
from prepare_nyc_carroll_smith import route_between, distance
from prepare_nyc_g_corridors import simplify


def prepare():
    s = json.loads(Path('work/nyc-f-built.json').read_bytes())
    ns = {n['id']: n for n in json.loads(Path('work/nyc-briarwood-kew-live.json').read_bytes())['nodes']}
    source_path = 'data/nyc_briarwood_kew_source.json'
    source = json.loads(Path(source_path).read_bytes())
    scale = json.loads(Path('data/nyc_briarwood_side_platforms.json').read_bytes())['scale']
    local = s['briarwood_platform_groups'][0]
    express = {e['track_ref']: e for e in s['briarwood_express_tracks']}
    pairs = [('1', local['east_secondary'], s['kew_gardens_islands'][0]['west_secondary']),
             ('3', express['3']['east'], s['kew_gardens_islands'][0]['west_primary']),
             ('4', express['4']['east'], s['kew_gardens_islands'][1]['west_secondary']),
             ('2', local['east_primary'], s['kew_gardens_islands'][1]['west_primary'])]
    eligible = [dict(w, tags=dict(w['tags'], name='IND Culver Line')) for w in source['ways'] if w['tags'].get('name') == 'IND Queens Boulevard Line' and w['tags'].get('service') != 'yard']
    corridors = []
    for ref, start, end in pairs:
        assert all('0' in [ns[i]['previous'], ns[i]['next']] for i in [start, end])
        route, ways, gaps = route_between(eligible, ref, ns[start], ns[end])
        assert all(int(w['tags'].get('level', w['tags'].get('layer', -2))) == -2 for w in ways)
        chain = [0.0]
        for a, b in zip(route, route[1:]):
            chain.append(chain[-1]+distance(a, b)*scale)
        points = simplify([dict(q, depth=-2, metres=d) for q, d in zip(route, chain)], tolerance=1)
        for d in [chain[-1]/3, 2*chain[-1]/3]:
            if min(abs(q['metres']-d) for q in points) < 35:
                continue
            i = next(i for i in range(len(chain)-1) if chain[i] <= d <= chain[i+1])
            f = (d-chain[i])/(chain[i+1]-chain[i])
            points.append(dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),
                               y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']), depth=-2, metres=d))
        points.sort(key=lambda q: q['metres'])
        for q, i in [(points[0], start), (points[-1], end)]:
            q.update(x=ns[i]['x'], y=ns[i]['y'])
        corridors.append(dict(track_ref=ref, start_node_id=start, end_node_id=end, points=points,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in ways)),
                              source_length_metres=chain[-1], source_projection_gaps_world_metres=gaps))
    return dict(source=source_path, scale=scale, corridors=corridors,
                stage='candidate_native_curves_pending',
                pending=['Audit native curves, grade crossings and station approaches.',
                         'Keep yard tracks and yard access unbuilt.'])


if __name__ == '__main__':
    p = prepare()
    Path('data/nyc_briarwood_kew_corridors.json').write_text(json.dumps(p, indent=2)+'\n')
    print(json.dumps([dict(ref=c['track_ref'], length=c['source_length_metres'], points=len(c['points']), gaps=c['source_projection_gaps_world_metres']) for c in p['corridors']]))
