"""Create L corridor candidates from verified source geometry and live endpoints."""
import bisect
import hashlib
import json
import math
from pathlib import Path


def distance(a, b):
    return math.hypot(a['x']-b['x'], a['y']-b['y'])


def offset(point, a, b):
    dx, dy = b['x']-a['x'], b['y']-a['y']
    t = max(0, min(1, ((point['x']-a['x'])*dx+(point['y']-a['y'])*dy)/(dx*dx+dy*dy)))
    return math.hypot(point['x']-a['x']-t*dx, point['y']-a['y']-t*dy), t


def simplify(points, tolerance=8):
    if len(points) <= 2:
        return points
    distances = [offset(p, points[0], points[-1])[0] for p in points[1:-1]]
    peak = max(distances)
    if peak <= tolerance:
        return [points[0], points[-1]]
    i = distances.index(peak)+1
    return simplify(points[:i+1], tolerance)[:-1]+simplify(points[i:], tolerance)


def prepare():
    raw = Path('data/nyc_l_plan.json').read_bytes()
    plan = json.loads(raw)
    state = json.loads(Path('work/nyc-l-built.json').read_text(encoding='utf-8'))
    live = json.loads(Path('work/nyc-l-live-topology.json').read_text(encoding='utf-8'))
    nodes = {n['id']: n for n in live['nodes']}
    stations = {s['plan_index']: s for s in state['stations']}
    source = plan['directions']['to_canarsie']
    route, segments = source['route'], source['segments']
    chain = [p['chainage'] for p in route]
    def chain_at(point):
        options = []
        for i, (a, b) in enumerate(zip(route, route[1:])):
            d, t = offset(point, a, b)
            options.append((d, chain[i]+t*(chain[i+1]-chain[i])))
        return min(options)[1]
    corridors = []
    for i in range(23):
        a, b = stations[i], stations[i+1]
        start, end = nodes[a['east_primary']], nodes[b['west_primary']]
        s0, s1 = chain_at(start), chain_at(end)
        if s1 <= s0:
            raise ValueError(f'Reversed corridor {i}')
        points = [dict(x=start['x'], y=start['y'], depth=start['depth'], chainage=s0, reason='live_endpoint')]
        for j, p in enumerate(route):
            if not s0+40 < p['chainage'] < s1-40:
                continue
            dep = segments[min(j, len(segments)-1)]['candidate_depth']
            previous_dep = segments[max(0, j-1)]['candidate_depth']
            points.append(dict(x=p['x'], y=p['y'], depth=dep, chainage=p['chainage'],
                               source_node_id=p['osm_node_id'],
                               reason='layer_boundary' if dep != previous_dep else 'geometry'))
        points.append(dict(x=end['x'], y=end['y'], depth=end['depth'], chainage=s1, reason='live_endpoint'))
        anchors = [0]+[j for j,p in enumerate(points[1:-1],1) if p['reason']=='layer_boundary']+[len(points)-1]
        kept = []
        for lo, hi in zip(anchors, anchors[1:]):
            kept.extend(simplify(points[lo:hi+1])[:-1])
        kept.append(points[-1])
        adaptations = []
        if i == 16:
            # This untagged short approach is between the tunnel and a level-2
            # viaduct. A ground control caused a native street collision.
            for p in kept:
                if p.get('source_node_id') == 7607533646:
                    p['depth'] = 1
                    p['reason'] = 'open_air_viaduct_approach_game_adaptation'
            adaptations.append('Untagged portal-to-viaduct approach uses depth 1; original source tags remain in the source plan.')
        if i == 21:
            # The unlevelled embankment lies between two level-1 bridges. Keep
            # it elevated and start the descent only beyond the last bridge.
            for p in kept:
                if p.get('source_node_id') in (1013731495, 1013719975, 1013719982):
                    p['depth'] = 1
            kept = [p for p in kept if p.get('source_node_id') != 1013719975]
            adaptations.append('Bridge/embankment/bridge sequence stays at depth 1; descent toward explicit level 0 starts after the final bridge.')
        issues = []
        for first, second in zip(kept, kept[1:]):
            if distance(first, second) < 40:
                issues.append('short_control_spacing_requires_review')
        if i in (14, 15):
            issues.append('Wilson_directional_layers_require_single_track_paths')
        corridors.append(dict(index=i, from_station=a['name'], to_station=b['name'],
                              start_node_id=start['id'], end_node_id=end['id'],
                              points=kept, issues=sorted(set(issues)),
                              adaptations=adaptations,
                              already_connected=i in (0,1),
                              status='candidate_requires_curve_review'))
    return dict(source_plan_sha256=hashlib.sha256(raw).hexdigest(),
                projection=plan['projection'], attribution=plan['attribution'],
                tolerance_world_metres=8, corridors=corridors,
                limitations=['Depth transition candidates require native grade and crossing review.',
                             'Source ways are simplified only between layer boundaries.',
                             'Endpoint IDs are seeds; inspect live free endpoints before each operation.'])


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_l_corridors.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([dict(index=c['index'], controls=len(c['points'])-2, issues=c['issues'],
                           depths=[p['depth'] for p in c['points']]) for c in result['corridors']]))
