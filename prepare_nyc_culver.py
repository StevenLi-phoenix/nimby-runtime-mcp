"""Audit Culver station cross-sections from OSM platform polygons and rail ways.

This is source geometry, not a native construction plan. Directional stop positions
are retained as evidence but are never interpreted as lateral track separation.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from prepare_geometry import project
from prepare_nyc_direction import source_depth


def centroid(points):
    """Area centroid of a closed polygon; reject degenerate footprints."""
    cross = [a['x'] * b['y'] - b['x'] * a['y']
             for a, b in zip(points, points[1:])]
    total = sum(cross)
    if abs(total) < 0.001:
        raise ValueError('Degenerate platform polygon')
    return {k: sum((a[k] + b[k]) * c for a, b, c in
                   zip(points, points[1:], cross)) / (3 * total)
            for k in ('x', 'y')}


def nearest(route, point):
    best = None
    for a, b in zip(route, route[1:]):
        dx, dy = b['x'] - a['x'], b['y'] - a['y']
        length = math.hypot(dx, dy)
        if not length:
            continue
        f = max(0, min(1, ((point['x'] - a['x']) * dx +
                           (point['y'] - a['y']) * dy) / length**2))
        q = dict(x=a['x'] + f * dx, y=a['y'] + f * dy)
        distance = math.hypot(q['x'] - point['x'], q['y'] - point['y'])
        if best is None or distance < best[0]:
            best = distance, q, (dx / length, dy / length)
    if best is None:
        raise ValueError('Empty rail geometry')
    return best


def prepare(plan_path, snapshot_dir):
    plan_raw = plan_path.read_bytes()
    plan = json.loads(plan_raw)
    south = plan['directions']['to_church']
    north = {s['name']: s for s in plan['directions']['to_court_square']['stations']}
    names = {13: 'bergen', 17: '7av', 20: 'church'}
    # Explicit Culver platform identities exclude the nearby R platforms at 4 Av.
    # 15 St has one island footprint; the other seven stations have two polygons.
    platform_ids = {13: {903989647, 903989648}, 14: {903989649, 903989650},
                    15: {426568720, 426568721}, 16: {422879097, 422879100},
                    17: {904605001, 904605002}, 18: {904605003},
                    19: {904608248, 904608249}, 20: {904610340, 904610341}}
    stations, sources = [], []
    for index in range(13, 21):
        filename = f"nyc-culver-{names[index]}.json" if index in names else f'nyc-culver-station-{index}.json'
        path = snapshot_dir / filename
        raw = path.read_bytes()
        elements = json.loads(raw)['elements']
        nodes = {e['id']: e for e in elements if e['type'] == 'node'}
        ways = [e for e in elements if e['type'] == 'way']
        s = south['stations'][index]
        n = north[s['name']]
        scale = math.cos(math.radians(s['latitude']))
        seed = {k: (s[k] + n[k]) / 2 for k in ('x', 'y')}
        footprints = []
        rails = []
        for way in ways:
            tags = way.get('tags', {})
            if tags.get('railway') not in ('platform', 'subway'):
                continue
            points = [dict(zip(('x', 'y'), project(nodes[nid]))) for nid in way['nodes']]
            record = dict(osm_way_id=way['id'], version=way['version'],
                          tags=tags, node_ids=way['nodes'], points=points)
            if tags['railway'] == 'subway':
                rails.append(record)
            elif way['id'] in platform_ids[index] and way['nodes'][0] == way['nodes'][-1]:
                # Translate before shoelace products to avoid cancellation at EPSG:3857 magnitudes.
                relative = [{k: p[k] - seed[k] for k in ('x', 'y')} for p in points]
                c = centroid(relative)
                c = {k: c[k] + seed[k] for k in ('x', 'y')}
                if math.hypot(c['x'] - seed['x'], c['y'] - seed['y']) * scale < 200:
                    footprints.append(dict(**record, center=c))
        if {f['osm_way_id'] for f in footprints} != platform_ids[index]:
            raise ValueError(f"{s['name']}: missing expected nearby platform polygons")
        center = {k: sum(f['center'][k] for f in footprints) / len(footprints) for k in ('x', 'y')}
        _, _, tangent = nearest(south['route'], center)
        tx, ty = tangent
        crossings = []
        for rail in rails:
            for a, b in zip(rail['points'], rail['points'][1:]):
                da = (a['x'] - center['x']) * tx + (a['y'] - center['y']) * ty
                db = (b['x'] - center['x']) * tx + (b['y'] - center['y']) * ty
                if abs(db - da) < 1e-9 or not 0 <= -da / (db - da) <= 1:
                    continue
                f = -da / (db - da)
                q = {k: a[k] + f * (b[k] - a[k]) for k in ('x', 'y')}
                offset = (-(q['x'] - center['x']) * ty + (q['y'] - center['y']) * tx) * scale
                if abs(offset) > 60:
                    continue
                item = dict(osm_way_id=rail['osm_way_id'], track_ref=rail['tags'].get('railway:track_ref'),
                            source_depth=source_depth(rail['tags']), offset_metres=offset, **q)
                if not any(c['osm_way_id'] == item['osm_way_id'] and
                           abs(c['offset_metres'] - offset) < 0.01 for c in crossings):
                    crossings.append(item)
        crossings.sort(key=lambda c: (c['offset_metres'], c['source_depth']))
        local_ids = {s['source_way_id'], n['source_way_id']}
        # A stop can sit on a different way from the station midpoint. Ref identity
        # is scoped to this station and source ways, never treated as global identity.
        refs = {r['tags'].get('railway:track_ref') for r in rails if r['osm_way_id'] in local_ids}
        refs.discard(None)
        for c in crossings:
            c['local_route_candidate'] = c['osm_way_id'] in local_ids or c['track_ref'] in refs
        if len([c for c in crossings if c['local_route_candidate']]) != 2:
            raise ValueError(f"{s['name']}: could not resolve two local tracks at cross-section")
        sources.append(dict(file=filename, sha256=hashlib.sha256(raw).hexdigest(),
                            endpoint='https://api.openstreetmap.org/api/0.6/map.json'))
        stations.append(dict(plan_index=index, name=s['name'], center=center,
                             southbound_tangent=dict(x=tx, y=ty), scale=scale,
                             stop_position_distance_metres=math.hypot(s['x']-n['x'], s['y']-n['y']) * scale,
                             directional_stop_node_ids=[s['osm_node_id'], n['osm_node_id']],
                             platform_footprints=footprints, cross_section=crossings,
                             source_rails=rails))
    return dict(stage='source_cross_sections_verified_native_layout_pending',
                source_plan_sha256=hashlib.sha256(plan_raw).hexdigest(), sources=sources,
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright',
                method='Mean of explicitly selected platform polygon area centroids; normal to nearby southbound source rail.',
                limitations=['Cross-sections cover rails within 60 actual metres, not remote express bypasses.',
                             'Source offsets are not native platform spacing or an approved construction layout.',
                             'Church relay geometry and Bergen branch connections require separate design.',
                             'No existing game tracks are moved by this source audit.'], stations=stations)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot_dir', type=Path)
    parser.add_argument('--plan', type=Path, default=Path('data/nyc_g_plan.json'))
    parser.add_argument('--output', type=Path, default=Path('data/nyc_culver_cross_sections.json'))
    args = parser.parse_args()
    result = prepare(args.plan, args.snapshot_dir)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps([dict(name=s['name'], tracks=[dict(ref=c['track_ref'], depth=c['source_depth'],
                      offset=round(c['offset_metres'], 2), local=c['local_route_candidate'])
                      for c in s['cross_section']]) for s in result['stations']], ensure_ascii=True))
