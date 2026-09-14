"""Prepare source-derived local platforms and express tracks on Central Park West."""
import json
import math
from pathlib import Path

from prepare_nyc_culver import nearest


def prepare():
    source_path = Path('data/nyc_central_park_west_source.json')
    source = json.loads(source_path.read_bytes())
    survey = json.loads(Path('data/nyc_central_park_west_station_survey.json').read_bytes())
    ways = {w['osm_way_id']: w for w in source['ways']}
    names = ['72nd Street', '81st Street', '86th Street', '96th Street',
             '103rd Street', '110th Street', '116th Street']
    stations = []
    for name in names:
        platforms = [p for p in survey['platforms']
                     if p['name'].replace('103th', '103rd') == name]
        assert len(platforms) == 2
        center = {k: sum(p['center'][k] for p in platforms)/2 for k in ['x', 'y']}
        latitude = math.degrees(2*math.atan(math.exp(center['y']/6378137))-math.pi/2)
        scale = math.cos(math.radians(latitude))
        rail = ways[platforms[0]['nearest_rail']]
        _, _, (tx, ty) = nearest(rail['points'], center)
        if ty > 0:
            tx, ty = -tx, -ty

        def offset(q):
            return (-(q['x']-center['x'])*ty+(q['y']-center['y'])*tx)*scale

        tracks = []
        for w in ways.values():
            if w['tags'].get('name') != 'IND Eighth Avenue Line':
                continue
            for a, b in zip(w['points'], w['points'][1:]):
                da = (a['x']-center['x'])*tx+(a['y']-center['y'])*ty
                db = (b['x']-center['x'])*tx+(b['y']-center['y'])*ty
                if abs(db-da) < 1e-9 or not 0 <= -da/(db-da) < 1:
                    continue
                q = {k: a[k]-da/(db-da)*(b[k]-a[k]) for k in ['x', 'y']}
                if abs(offset(q)) > 35:
                    continue
                depth = int(w['tags'].get('level', w['tags']['layer']))
                ref = w['tags']['railway:track_ref']
                tracks.append(dict(source_way_id=w['osm_way_id'], track_ref=ref,
                                   depth=depth, offset_metres=offset(q),
                                   role='local' if ref in ['1', '2'] else 'express',
                                   points=[dict(x=q['x']+tx*d/scale,
                                                y=q['y']+ty*d/scale, depth=depth)
                                           for d in [-120, -70, 70, 120]], **q))
        assert len(tracks) == 4 and {t['track_ref'] for t in tracks} == {'1','2','3','4'}, tracks
        for p in platforms:
            t = next(t for t in tracks if t['track_ref'] == p['track_ref'])
            assert t['depth'] == int(p['depth'])
            offsets = [offset(q) for q in ways[p['platform_way']]['points']]
            p['source_lateral_bounds_metres'] = [min(offsets), max(offsets)]
            p['source_width_metres'] = max(offsets)-min(offsets)
            p['track_offset_metres'] = t['offset_metres']
        gaps = [abs(a['offset_metres']-b['offset_metres'])
                for i, a in enumerate(tracks) for b in tracks[i+1:]
                if a['depth'] == b['depth']]
        assert min(gaps) > 3.05
        stations.append(dict(name=name, center=center, scale=scale,
                             southbound_axis=dict(x=tx, y=ty), tracks=tracks,
                             platforms=platforms, minimum_same_depth_spacing_metres=min(gaps)))
    return dict(source=str(source_path), source_sha256=source['sha256'],
                attribution=source['attribution'], platform_length_metres=140,
                stage='source_cross_sections_native_platform_design_pending',
                stations=stations,
                pending=['Design native single-sided platforms without adding express stops.',
                         'Check source continuity and level transitions between stations.',
                         'Read live surroundings before creating each station and corridor.'])


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_central_park_west_cross_sections.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([dict(name=s['name'], tracks=[(t['track_ref'], t['depth'])
                        for t in s['tracks']], gap=s['minimum_same_depth_spacing_metres'])
                      for s in result['stations']]))
