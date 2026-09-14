"""Plan East Broadway's two-track island station from source geometry."""
import json
import math
from pathlib import Path
from prepare_nyc_culver import centroid, nearest


def prepare():
    source = json.loads(Path('data/nyc_east_broadway_source.json').read_bytes())
    stop = json.loads(Path('data/nyc_f_plan.json').read_bytes())['directions']['to_coney_island']['stations'][22]
    footprints = [w for w in source['ways'] if w['osm_way_id'] in [907931667]]
    assert len(footprints) == 1
    centers = []
    for w in footprints:
        c = centroid([{k:p[k]-stop[k] for k in ['x', 'y']} for p in w['points']])
        centers.append({k:c[k]+stop[k] for k in c})
    center = {k:sum(c[k] for c in centers)/len(centers) for k in ['x', 'y']}
    scale = math.cos(math.radians(stop['latitude']))
    ref = min((w for w in source['ways'] if w['tags'].get('name') == 'IND Sixth Avenue Line'), key=lambda w:nearest(w['points'],center)[0])
    _, _, (tx, ty) = nearest(ref['points'], center)
    if ty > 0:
        tx, ty = -tx, -ty
    def offset(p):
        return (-(p['x']-center['x'])*ty+(p['y']-center['y'])*tx)*scale
    cross = []
    for w in source['ways']:
        if w['tags'].get('railway') != 'subway' or w['tags'].get('level') != '-4':
            continue
        if w['tags'].get('name') not in ['IND Sixth Avenue Line']:
            continue
        for a, b in zip(w['points'], w['points'][1:]):
            da = (a['x']-center['x'])*tx+(a['y']-center['y'])*ty
            db = (b['x']-center['x'])*tx+(b['y']-center['y'])*ty
            if abs(db-da) < 1e-9 or not 0 <= -da/(db-da) <= 1:
                continue
            q = {k:a[k]-da/(db-da)*(b[k]-a[k]) for k in ['x', 'y']}
            if abs(offset(q)) < 40:
                cross.append(dict(source_way_id=w['osm_way_id'], track_ref=w['tags']['railway:track_ref'],
                                  line_name=w['tags']['name'], offset_metres=offset(q), **q))
    cross.sort(key=lambda p:p['offset_metres'])
    assert len(cross) == 2, cross
    islands = []
    for footprint, c in sorted(zip(footprints, centers), key=lambda pair:offset(pair[1])):
        left = max((p for p in cross if p['offset_metres'] < offset(c)), key=lambda p:p['offset_metres'])
        right = min((p for p in cross if p['offset_metres'] > offset(c)), key=lambda p:p['offset_metres'])
        spacing = right['offset_metres']-left['offset_metres']
        assert 3.05 < spacing < 30
        tracks = [dict(p, points=[dict(x=p['x']+tx*d/scale, y=p['y']+ty*d/scale, depth=-3)
                                 for d in [-120, -70, 70, 120]]) for p in [left, right]]
        islands.append(dict(platform_way_id=footprint['osm_way_id'], tracks=tracks,
                            track_spacing_metres=spacing, island_width_metres=spacing-3.05))
    return dict(name='East Broadway', plan_index=22, center=center, scale=scale,
                southbound_axis=dict(x=tx,y=ty), cross_section=cross, islands=islands,
                depth=-3, platform_length_metres=140, source='data/nyc_east_broadway_source.json',
                reserved_other_services=[], source_depth=-4,
                adaptation='Source -4 station maps to native minimum -3; surrounding tunnel crossings require separate verification.',
                stage='candidate_native_platform_audit_pending',
                pending=['Verify island platform buildings.',
                         'Connect F south through Rutgers Street Tunnel to York Street and north to Delancey Street.',
                         'Verify Rutgers Street Tunnel source geometry before crossing the river.'])


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_east_broadway_islands.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['cross_section']))



