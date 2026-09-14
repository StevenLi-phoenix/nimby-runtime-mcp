"""Plan four continuous Culver tracks and an explicit tunnel-to-viaduct transition."""
import hashlib
import heapq
import json
import math
from pathlib import Path

from prepare_nyc_g_corridors import offset, simplify


def distance(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])


def route_between(ways, ref, start, end):
    graph, coords, edges = {}, {}, []
    for way in ways:
        if way['tags'].get('railway:track_ref') != ref or way['tags'].get('name') != 'IND Culver Line':
            continue
        for node_id, point in zip(way['node_ids'], way['points']):
            coords[node_id] = point
        for a, b in zip(way['node_ids'], way['node_ids'][1:]):
            length = distance(coords[a], coords[b])
            if not length:
                continue
            for u, v in [(a, b), (b, a)]:
                graph.setdefault(u, []).append((v, length, way))
            edges.append((a, b, length, way))
    projections, projected_edges = [], []
    for key, point in [(-1, start), (-2, end)]:
        gap, fraction, edge = min(((*offset(point, coords[a], coords[b]), (a, b, length, way))
                                   for a, b, length, way in edges), key=lambda x: x[0])
        a, b, length, way = edge
        assert gap < 40, (ref, key, gap)
        coords[key] = {k: coords[a][k]+fraction*(coords[b][k]-coords[a][k]) for k in ['x', 'y']}
        for node_id, length in [(a, length*fraction), (b, length*(1-fraction))]:
            graph.setdefault(key, []).append((node_id, length, way))
            graph[node_id].append((key, length, way))
        projections.append(gap)
        projected_edges.append((a, b, fraction, edge[2], way))
    # Two projected endpoints may lie on the same long OSM segment. Connect
    # their positions directly instead of forcing a detour via either OSM node.
    a, b, fraction, length, way = projected_edges[0]
    c, d, other_fraction, _, _ = projected_edges[1]
    if {a, b} == {c, d}:
        if (a, b) != (c, d):
            other_fraction = 1-other_fraction
        step = abs(fraction-other_fraction)*length
        graph[-1].append((-2, step, way))
        graph[-2].append((-1, step, way))
    queue, best, previous = [(0, -1)], {-1: 0}, {}
    while queue:
        length, node_id = heapq.heappop(queue)
        if length != best[node_id]:
            continue
        if node_id == -2:
            break
        for other, step, way in graph[node_id]:
            new = length+step
            if new < best.get(other, math.inf):
                best[other] = new
                previous[other] = (node_id, way)
                heapq.heappush(queue, (new, other))
    assert -2 in best, (ref, 'Disconnected source geometry')
    ids, route_ways = [-2], []
    while ids[-1] != -1:
        parent, way = previous[ids[-1]]
        ids.append(parent)
        route_ways.append(way)
    ids.reverse()
    route_ways.reverse()
    points = [dict(**coords[i], source_node_id=i) for i in ids]
    return points, route_ways, projections


def prepare():
    raw = Path('data/nyc_culver_cross_sections.json').read_bytes()
    source = json.loads(raw)['stations']
    ways = {r['osm_way_id']: r for station in source for r in station['source_rails']}
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    live = json.loads(Path('work/nyc-carroll-smith-live.json').read_bytes())
    nodes = {n['id']: n for n in live['nodes']}
    stations = {s['plan_index']: s for s in state['stations']}
    carroll, smith = stations[14], stations[15]
    ec = {t['track_ref']: t for t in state['carroll_express_tracks']}
    es = {t['track_ref']: t for t in state['smith_express_tracks']}
    ends = {'1': (carroll['east_secondary'], smith['west_secondary']),
            '2': (carroll['east_primary'], smith['west_primary']),
            '3': (ec['3']['frontier'], es['3']['start']),
            '4': (ec['4']['start'], es['4']['frontier'])}
    scale = source[2]['scale']
    corridors = []
    for ref, (start_id, end_id) in ends.items():
        start, end = nodes[start_id], nodes[end_id]
        points, route_ways, gaps = route_between(list(ways.values()), ref, start, end)
        chain = [0.0]
        for a, b in zip(points, points[1:]):
            chain.append(chain[-1]+distance(a, b)*scale)
        portal = next(chain[i] for i, way in enumerate(route_ways) if way['tags'].get('embankment') == 'yes')
        bridge = next(chain[i] for i, way in enumerate(route_ways) if way['tags'].get('bridge') == 'yes')
        transitions = [(0, -2), (portal-10, -1), (portal+50, 0),
                       (bridge, 1), (bridge+80, 2), (bridge+160, 3), (chain[-1], 3)]
        assert all(b[0] > a[0] for a, b in zip(transitions, transitions[1:])), transitions
        def at(position, depth):
            i = next((i for i in range(len(chain)-1) if chain[i] <= position <= chain[i+1]), len(chain)-2)
            fraction = (position-chain[i])/(chain[i+1]-chain[i])
            return dict(x=points[i]['x']+fraction*(points[i+1]['x']-points[i]['x']),
                        y=points[i]['y']+fraction*(points[i+1]['y']-points[i]['y']),
                        depth=depth, chainage_metres=position, reason='layer_transition')
        candidates = []
        for (a, depth), (b, next_depth) in zip(transitions, transitions[1:]):
            section = [at(a, depth)]
            section += [dict(**point, depth=depth, chainage_metres=dist, reason='source_curve')
                        for point, dist in zip(points, chain) if a+15 < dist < b-15]
            section.append(at(b, next_depth))
            candidates += simplify(section, tolerance=5)[:-1]
        candidates.append(at(chain[-1], 3))
        for point, native in [(candidates[0], start), (candidates[-1], end)]:
            point.update(x=native['x'], y=native['y'], depth=native['depth'], reason='native_endpoint')
        corridors.append(dict(track_ref=ref, start_node_id=start_id, end_node_id=end_id,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in route_ways)),
                              source_projection_gaps_world_metres=gaps, source_length_metres=chain[-1],
                              portal_chainage_metres=portal, bridge_chainage_metres=bridge,
                              points=candidates, stage='candidate_native_curves_pending'))
    return dict(from_station='Carroll Street', to_station='Smith–9th Streets', corridors=corridors,
                source_sha256=hashlib.sha256(raw).hexdigest(),
                adaptations=['All four tracks use their own connected OSM node chain.',
                             'Short untagged source gaps at the portal do not cause a ground-to-tunnel dip.',
                             'Explicit monotonic -2,-1,0,+1,+2,+3 transition; source bridge +4 maps to +3.',
                             'Layer transitions interpolate along source geometry, not straight shortcuts.'],
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_carroll_smith_corridors.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([dict(track=c['track_ref'], points=len(c['points']), length=c['source_length_metres'],
                           layers=[p['depth'] for p in c['points']]) for c in result['corridors']]))
