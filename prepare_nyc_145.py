"""Survey IND 145th Street's two levels without duplicating the shared middle track."""
import json
import math
from pathlib import Path
from prepare_nyc_culver import centroid, nearest


def prepare():
    source = json.loads(Path('data/nyc_harlem_source.json').read_bytes())
    stop = json.loads(Path('data/nyc_d_plan.json').read_bytes())['directions']['to_coney_island']['stations'][11]
    scale = math.cos(math.radians(stop['latitude']))
    levels = []
    for depth, platform_ids in [(-2, [677322266, 677322267]), (-3, [677322270, 677322271])]:
        platforms = [w for w in source['ways'] if w['osm_way_id'] in platform_ids]
        assert len(platforms) == 2
        centers = []
        for w in platforms:
            c = centroid([{k: p[k]-stop[k] for k in ['x', 'y']} for p in w['points']])
            centers.append({k: c[k]+stop[k] for k in c})
        center = {k: sum(c[k] for c in centers)/2 for k in ['x', 'y']}
        ways = [w for w in source['ways'] if w['tags'].get('railway') == 'subway'
                and w['tags'].get('level', w['tags'].get('layer')) == str(depth)
                and w['tags'].get('name', '').startswith('IND ')]
        ref = min(ways, key=lambda w: nearest(w['points'], center)[0])
        _, _, (tx, ty) = nearest(ref['points'], center)
        if ty > 0:
            tx, ty = -tx, -ty
        def offset(p):
            return (-(p['x']-center['x'])*ty+(p['y']-center['y'])*tx)*scale
        cross = []
        for w in ways:
            for a, b in zip(w['points'], w['points'][1:]):
                da = (a['x']-center['x'])*tx+(a['y']-center['y'])*ty
                db = (b['x']-center['x'])*tx+(b['y']-center['y'])*ty
                if abs(db-da) < 1e-9 or not 0 <= -da/(db-da) <= 1:
                    continue
                q = {k: a[k]-da/(db-da)*(b[k]-a[k]) for k in ['x', 'y']}
                if abs(offset(q)) < 40:
                    cross.append(dict(source_way_id=w['osm_way_id'], tags=w['tags'],
                                      offset_metres=offset(q), **q))
        cross.sort(key=lambda p: p['offset_metres'])
        assert len(cross) == (4 if depth == -2 else 3), cross
        for track in cross:
            track['candidate_points'] = [dict(x=track['x']+tx*d/scale, y=track['y']+ty*d/scale, depth=depth)
                                         for d in [-120, -70, 70, 120]]
        islands = []
        for w, c in zip(platforms, centers):
            left = max((p for p in cross if p['offset_metres'] < offset(c)), key=lambda p: p['offset_metres'])
            right = min((p for p in cross if p['offset_metres'] > offset(c)), key=lambda p: p['offset_metres'])
            spacing = right['offset_metres']-left['offset_metres']
            assert spacing > 3.05
            islands.append(dict(platform_way_id=w['osm_way_id'],
                                adjacent_way_ids=[left['source_way_id'], right['source_way_id']],
                                track_spacing_metres=spacing, available_width_metres=spacing-3.05,
                                candidate_bounds_metres=[left['offset_metres']+1.525, right['offset_metres']-1.525],
                                source_bounds_metres=[min(map(offset, w['points'])), max(map(offset, w['points']))]))
        levels.append(dict(depth=depth, center=center, southbound_axis=dict(x=tx, y=ty), tracks=cross, islands=islands))
    return dict(name='145th Street', source='data/nyc_harlem_source.json', attribution=source['attribution'],
                scale=scale, levels=levels, stage='source_cross_section_native_layout_pending',
                constraints=['Create lower middle track once; both islands share it.',
                             'Unify both levels under one station.',
                             'Native platform layout and approach junctions require separate verification.'])


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_145_cross_sections.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))
