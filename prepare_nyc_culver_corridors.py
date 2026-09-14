"""Plan four independent Bergen–Carroll connections from source and native endpoints."""
import hashlib
import json
import math
from pathlib import Path

from prepare_nyc_g_corridors import offset, simplify


def project_chain(route, point):
    chain = [0.0]
    for a, b in zip(route, route[1:]):
        chain.append(chain[-1] + math.hypot(b['x']-a['x'], b['y']-a['y']))
    candidates = []
    for i, (a, b) in enumerate(zip(route, route[1:])):
        distance, fraction = offset(point, a, b)
        candidates.append((distance, chain[i]+fraction*(chain[i+1]-chain[i])))
    return min(candidates)[1], chain


def prepare():
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    source_raw = Path('data/nyc_culver_cross_sections.json').read_bytes()
    source = json.loads(source_raw)['stations'][0]
    g = json.loads(Path('data/nyc_g_plan.json').read_bytes())
    live = json.loads(Path('work/nyc-bergen-carroll-live.json').read_bytes())
    nodes = {n['id']: n for n in live['nodes']}
    stations = {s['plan_index']: s for s in state['stations']}
    bergen, carroll = stations[13], stations[14]
    express_b = {t['track_ref']: t for t in state['bergen_express_tracks']}
    express_c = {t['track_ref']: t for t in state['carroll_express_tracks']}
    endpoints = {
        '1': (bergen['east_secondary'], carroll['west_secondary']),
        '2': (bergen['east_primary'], carroll['west_primary']),
        '3': (express_b['3']['frontier'], express_c['3']['start']),
        '4': (express_b['4']['start'], express_c['4']['frontier']),
    }
    corridors = []
    for ref, (start_id, end_id) in endpoints.items():
        start, end = nodes[start_id], nodes[end_id]
        if ref in ('1', '2'):
            d = g['directions']['to_church' if ref == '1' else 'to_court_square']
            route = [dict(x=p['x'], y=p['y'], source_node_id=p['osm_node_id'],
                          depth=d['segments'][min(i, len(d['segments'])-1)]['candidate_depth'])
                     for i, p in enumerate(d['route'])]
        else:
            way_id = next(c['osm_way_id'] for c in source['cross_section'] if c['track_ref'] == ref)
            way = next(w for w in source['source_rails'] if w['osm_way_id'] == way_id)
            route = [dict(**p, source_node_id=nid, depth=-2)
                     for p, nid in zip(way['points'], way['node_ids'], strict=True)]
        s0, chain = project_chain(route, start)
        s1, _ = project_chain(route, end)
        if s0 > s1:
            route.reverse()
            s0, chain = project_chain(route, start)
            s1, _ = project_chain(route, end)
        assert s0 < s1
        points = [dict(x=start['x'], y=start['y'], depth=start['depth'], reason='native_endpoint')]
        points += [dict(**p, reason='source_geometry') for p, dist in zip(route, chain)
                   if s0+40 < dist < s1-40]
        points += [dict(x=end['x'], y=end['y'], depth=end['depth'], reason='native_endpoint')]
        anchors = {0, len(points)-1}
        for i in range(1, len(points)):
            if points[i]['depth'] != points[i-1]['depth']:
                anchors.update((i-1, i))
        anchors = sorted(anchors)
        kept = []
        for a, b in zip(anchors, anchors[1:]):
            kept += simplify(points[a:b+1], tolerance=6)[:-1]
        kept.append(points[-1])
        corridors.append(dict(track_ref=ref, start_node_id=start_id, end_node_id=end_id,
                              points=kept, stage='candidate_native_curves_pending'))
    return dict(from_station='Bergen Street', to_station='Carroll Street',
                source_sha256=hashlib.sha256(source_raw).hexdigest(), corridors=corridors,
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright',
                limitations=['Independent tracks; do not use dual extension that resets spacing.',
                             'Depth transitions and native curves require inspection before construction.',
                             'Bergen northern G/F merge and both onward corridors remain separate work.'])


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_bergen_carroll_corridors.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
