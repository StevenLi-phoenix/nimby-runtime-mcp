"""Plan four separate source-connected approaches into Coney Island."""
import hashlib
import json
from pathlib import Path

from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import simplify


def prepare():
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    raw = Path('data/nyc_coney_culver_source.json').read_bytes()
    source = json.loads(raw)
    nodes = {n['id']: n for n in json.loads(Path('work/nyc-west-eighth-coney-live.json').read_bytes())['nodes']}
    scale = json.loads(Path('data/nyc_coney_four_islands.json').read_bytes())['scale']
    specs = [('F', 0, 1, '2', '6', 'east_primary', 'east_secondary'),
             ('F', 0, 1, '1', '5', 'east_secondary', 'east_primary'),
             ('Q', 1, 2, '4', '4', 'east_primary', 'east_secondary'),
             ('Q', 1, 2, '3', '3', 'east_secondary', 'east_primary')]
    corridors = []
    for service, level, island, start_ref, end_ref, start_key, end_key in specs:
        name = 'IND Culver Line' if service == 'F' else 'BMT Brighton Line'
        selected = [w for w in source['ways'] if w['tags'].get('name') == name
                    and w['tags'].get('railway') == 'subway' and not w['tags'].get('service')
                    and (w['tags'].get('railway:track_ref') in {start_ref, end_ref}
                         or service == 'Q' and start_ref == '4' and w['osm_way_id'] == 320752597)]
        # Normalize only the graph selector; retain source tags separately.
        ways = [dict(w, tags=dict(w['tags'], name='IND Culver Line', **{'railway:track_ref': 'route'})) for w in selected]
        start_id = state['west_eighth_levels'][level][start_key]
        end_id = state['coney_islands'][island][end_key]
        start, end = nodes[start_id], nodes[end_id]
        assert '0' in [start['previous'], start['next']]
        assert '0' in [end['previous'], end['next']]
        route, used, gaps = route_between(ways, 'route', start, end)
        originals = {w['osm_way_id']: w for w in selected}
        chain = [0.0]
        for a, b in zip(route, route[1:]):
            chain.append(chain[-1] + distance(a, b) * scale)
        points = [dict(p) for p in simplify(route, tolerance=1.5)]
        for p, n in [(points[0], start), (points[-1], end)]:
            p.update(x=n['x'], y=n['y'])
        segments = [dict(source_way_id=w['osm_way_id'], start_metres=chain[i], end_metres=chain[i+1],
                         depth=int(originals[w['osm_way_id']]['tags']['level'])) for i, w in enumerate(used)]
        corridors.append(dict(service=service, start_ref=start_ref, end_ref=end_ref,
                              start_node_id=start_id, end_node_id=end_id, points=points,
                              source_route=route, source_segments=segments,
                              source_length_metres=chain[-1], source_projection_gaps_world_metres=gaps,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in used))))
    return dict(corridors=corridors, scale=scale, source_sha256=hashlib.sha256(raw).hexdigest(),
                stage='source_routes_verified_native_geometry_and_layer_transitions_pending',
                pending=['Audit endpoint tangents and parallel clearance.',
                         'Design Q +3 to +2 transition from source segments.',
                         'Create and inspect native curves before selected construction.',
                         'Build station-after relays and verify operating paths.'],
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_west_eighth_coney_corridors.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps([dict(service=c['service'], refs=[c['start_ref'], c['end_ref']],
                           length=c['source_length_metres'], points=len(c['points']),
                           gaps=c['source_projection_gaps_world_metres']) for c in result['corridors']]))
