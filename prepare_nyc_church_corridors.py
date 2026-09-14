"""Plan four source-aligned approaches to Church Avenue and express ascent."""
import json
from pathlib import Path

from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import simplify


def prepare():
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    sources = json.loads(Path('data/nyc_culver_cross_sections.json').read_bytes())['stations']
    ways = {w['osm_way_id']: w for s in sources for w in s['source_rails']}
    nodes = {n['id']: n for n in json.loads(Path('work/nyc-church-live.json').read_bytes())['nodes']}
    hamilton = next(s for s in state['stations'] if s['plan_index'] == 19)
    express = {t['track_ref']: t for t in state['hamilton_express_tracks']}
    starts = {'1': hamilton['east_secondary'], '2': hamilton['east_primary'],
              '3': express['3']['frontier'], '4': express['4']['start']}
    scale, corridors = sources[7]['scale'], []
    for ref, start_id in starts.items():
        end_id = state['church_tracks'][ref]['north_endpoint']
        start, end = nodes[start_id], nodes[end_id]
        route, route_ways, gaps = route_between(list(ways.values()), ref, start, end)
        chain = [0.0]
        for a, b in zip(route, route[1:]):
            chain.append(chain[-1]+distance(a, b)*scale)
        boundary = None
        if ref in ['3', '4']:
            boundary = next(chain[i] for i, w in enumerate(route_ways)
                            if w['tags'].get('level', w['tags'].get('layer')) == '-2')
            anchors = [(0, -3), (boundary-80, -3), (boundary, -2), (chain[-1], -2)]
        else:
            assert all(w['tags'].get('level', w['tags'].get('layer')) == '-2' for w in route_ways)
            anchors = [(0, -2), (chain[-1], -2)]
        assert all(a[0] < b[0] for a, b in zip(anchors, anchors[1:]))

        def at(position, depth):
            i = next(i for i in range(len(chain)-1) if chain[i] <= position <= chain[i+1])
            fraction = (position-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+fraction*(route[i+1]['x']-route[i]['x']),
                        y=route[i]['y']+fraction*(route[i+1]['y']-route[i]['y']),
                        depth=depth, chainage_metres=position, reason='layer_anchor')

        points = []
        for (a, depth), (b, end_depth) in zip(anchors, anchors[1:]):
            section = [at(a, depth)]
            section += [dict(**p, depth=depth, chainage_metres=d, reason='source_curve')
                        for p, d in zip(route, chain) if a+20 < d < b-20]
            section.append(at(b, end_depth))
            points += simplify(section, tolerance=3)[:-1]
        points.append(at(chain[-1], -2))
        for point, native in [(points[0], start), (points[-1], end)]:
            point.update(x=native['x'], y=native['y'], depth=native['depth'], reason='native_endpoint')
        corridors.append(dict(track_ref=ref, start_node_id=start_id, end_node_id=end_id,
                              points=points, source_length_metres=chain[-1],
                              express_upper_layer_boundary_metres=boundary,
                              source_projection_gaps_world_metres=gaps,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in route_ways)),
                              stage='candidate_native_curves_pending'))
    return dict(from_station='Fort Hamilton Parkway', to_station='Church Avenue', corridors=corridors,
                adaptations=['Express tracks rise from -3 to source -2 over the last 80m before the source layer boundary.',
                             'Local tracks stay at -2; preserve separate source paths through the bend.'],
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_church_corridors.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([dict(ref=c['track_ref'], length=c['source_length_metres'], points=len(c['points'])) for c in result['corridors']]))
