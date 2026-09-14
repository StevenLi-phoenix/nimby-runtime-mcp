"""Plan the four Culver tracks and six source crossovers north of 4th Avenue."""
import hashlib
import json
from pathlib import Path

from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import simplify


def prepare():
    raw = Path('data/nyc_culver_cross_sections.json').read_bytes()
    sources = json.loads(raw)['stations']
    ways = {r['osm_way_id']: r for s in sources for r in s['source_rails']}
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    live = json.loads(Path('work/nyc-smith-fourth-live.json').read_bytes())
    nodes = {n['id']: n for n in live['nodes']}
    stations = {s['plan_index']: s for s in state['stations']}
    start_station, end_station = stations[15], stations[16]
    start_express = {t['track_ref']: t for t in state['smith_express_tracks']}
    end_express = {t['track_ref']: t for t in state['fourth_express_tracks']}
    ends = {'1': (start_station['east_secondary'], end_station['west_secondary']),
            '2': (start_station['east_primary'], end_station['west_primary']),
            '3': (start_express['3']['frontier'], end_express['3']['start']),
            '4': (start_express['4']['start'], end_express['4']['frontier'])}
    scale = sources[3]['scale']
    corridors = []
    for ref, (start_id, end_id) in ends.items():
        start, end = nodes[start_id], nodes[end_id]
        route, route_ways, gaps = route_between(list(ways.values()), ref, start, end)
        chain = [0.0]
        for a, b in zip(route, route[1:]):
            chain.append(chain[-1]+distance(a, b)*scale)
        boundary = next(chain[i] for i, w in enumerate(route_ways)
                        if w['tags'].get('level', w['tags'].get('layer')) == '2')
        anchors = [(0, 3), (boundary-80, 3), (boundary, 2), (chain[-1], 2)]
        assert all(a[0] < b[0] for a, b in zip(anchors, anchors[1:]))
        def at(position, depth):
            i = next(i for i in range(len(chain)-1) if chain[i] <= position <= chain[i+1])
            f = (position-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),
                        y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']),
                        chainage_metres=position, depth=depth, reason='layer_anchor')
        points = []
        for (a, depth), (b, end_depth) in zip(anchors, anchors[1:]):
            section = [at(a, depth)]
            section += [dict(**p, depth=depth, chainage_metres=d, reason='source_curve')
                        for p, d in zip(route, chain) if a+15 < d < b-15]
            section.append(at(b, end_depth))
            points += simplify(section, tolerance=4)[:-1]
        points.append(at(chain[-1], 2))
        for point, native in [(points[0], start), (points[-1], end)]:
            point.update(x=native['x'], y=native['y'], depth=native['depth'], reason='native_endpoint')
        corridors.append(dict(track_ref=ref, start_node_id=start_id, end_node_id=end_id,
                              points=points, source_length_metres=chain[-1],
                              lower_viaduct_boundary_metres=boundary, source_projection_gaps_world_metres=gaps,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in route_ways)),
                              stage='candidate_native_curves_pending'))
    crossovers = []
    for way_id in range(426568708, 426568714):
        way = ways[way_id]
        endpoints = []
        for i in [0, -1]:
            refs = {w['tags']['railway:track_ref'] for w in ways.values()
                    if way['node_ids'][i] in w['node_ids'] and w['tags'].get('name') == 'IND Culver Line'
                    and 'railway:track_ref' in w['tags']}
            assert len(refs) == 1
            endpoints.append(dict(**way['points'][i], track_ref=refs.pop(), source_node_id=way['node_ids'][i]))
        crossovers.append(dict(source_way_id=way_id, endpoints=endpoints, source_points=way['points'], depth=2,
                               stage='native_branch_projection_pending'))
    return dict(from_station='Smith–9th Streets', to_station='4th Avenue', corridors=corridors,
                crossovers=crossovers, source_sha256=hashlib.sha256(raw).hexdigest(),
                adaptations=['Source +4 viaduct maps to +3; descend to source +2 over an 80m approach.',
                             'Preserve six source crossovers; these normal same-layer junctions are not grade-separated.'],
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_smith_fourth_corridors.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(corridors=[dict(ref=c['track_ref'], points=len(c['points']), length=c['source_length_metres'])
                                    for c in result['corridors']], crossovers=len(result['crossovers']))))
