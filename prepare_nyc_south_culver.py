"""Extract Church--18 Av source tracks and plan the three-track Ditmas station."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from prepare_geometry import project
from prepare_nyc_culver import centroid, nearest
from prepare_nyc_direction import source_depth


def prepare(snapshot, station_specs=None, source_url='https://api.openstreetmap.org/api/0.6/map.json?bbox=-73.982,40.626,-73.973,40.643'):
    raw = snapshot.read_bytes()
    objects = json.loads(raw)['elements']
    nodes = {e['id']: e for e in objects if e['type'] == 'node'}
    ways = []
    for e in objects:
        if e['type'] != 'way' or e.get('tags', {}).get('railway') not in ('subway', 'platform'):
            continue
        ways.append(dict(osm_way_id=e['id'], version=e['version'], tags=e['tags'],
                         node_ids=e['nodes'], points=[dict(zip(('x', 'y'), project(nodes[i]))) for i in e['nodes']]))
    plan = json.loads(Path('data/nyc_f_plan.json').read_bytes())
    route = plan['directions']['to_coney_island']
    stations = []
    if station_specs is None:
        station_specs = [(33, {427044489, 427044490}, {'1', '2', '3-4'}),
                                      (34, {427044431, 427044432}, {'1', '2', '3-4'}),
                                      (35, {427044447, 427044448}, {'1', '2', '3-4'})]
    for index, ids, expected_refs in station_specs:
        s = route['stations'][index]
        footprints = [w for w in ways if w['osm_way_id'] in ids]
        assert len(footprints) == 2
        scale = math.cos(math.radians(s['latitude']))
        centers = []
        for f in footprints:
            assert f['node_ids'][0] == f['node_ids'][-1]
            relative = [{k:p[k]-s[k] for k in ['x','y']} for p in f['points']]
            c = centroid(relative)
            centers.append({k:c[k]+s[k] for k in ['x','y']})
        center = {k:sum(c[k] for c in centers)/len(centers) for k in ['x','y']}
        _, _, (tx,ty) = nearest(route['route'], center)
        crossings = []
        for w in ways:
            if w['tags'].get('railway') != 'subway': continue
            for a,b in zip(w['points'], w['points'][1:]):
                da=(a['x']-center['x'])*tx+(a['y']-center['y'])*ty
                db=(b['x']-center['x'])*tx+(b['y']-center['y'])*ty
                if abs(db-da)<1e-9 or not 0<=-da/(db-da)<=1: continue
                f=-da/(db-da); q={k:a[k]+f*(b[k]-a[k]) for k in ['x','y']}
                offset=(-(q['x']-center['x'])*ty+(q['y']-center['y'])*tx)*scale
                if abs(offset)>60: continue
                if any(c['osm_way_id']==w['osm_way_id'] and abs(c['offset_metres']-offset)<.01 for c in crossings): continue
                crossings.append(dict(osm_way_id=w['osm_way_id'],track_ref=w['tags'].get('railway:track_ref'),
                                      offset_metres=offset,depth=source_depth(w['tags']),**q))
        crossings.sort(key=lambda c:c['offset_metres'])
        assert len(crossings)==3 and {c['track_ref'] for c in crossings}==expected_refs
        assert all(c['depth']==2 for c in crossings)
        stations.append(dict(plan_index=index,name=s['name'],center=center,scale=scale,
                             southbound_tangent=dict(x=tx,y=ty),cross_section=crossings,
                             platform_footprints=footprints,
                             layout='two_islands_shared_center_track' if index in (34,39) else 'two_side_platforms'))
    source=dict(source_url=source_url,
                source_sha256=hashlib.sha256(raw).hexdigest(),ways=ways,stations=stations,
                operator_reference='https://www.mta.info/maps/subway-line-maps/f-line',
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')
    s=stations[0]; by={c['track_ref']:c for c in s['cross_section']}; t=s['southbound_tangent']
    tracks=[]
    for ref in ['1','3-4','2']:
        c=by[ref]
        tracks.append(dict(track_ref=ref,source_way_id=c['osm_way_id'],
                           role='center_through_no_platform' if ref=='3-4' else 'local_platform',
                           points=[dict(x=c['x']+d*t['x']/s['scale'],y=c['y']+d*t['y']/s['scale'],depth=2)
                                   for d in [-120,-70,0,70,120]]))
    ditmas=dict(station=s['name'],plan_index=s['plan_index'],scale=s['scale'],center=s['center'],
                southbound_tangent=t,platform_length_metres=140,native_depth=2,
                primary_ref='2',secondary_ref='1',track_spacing_metres=by['2']['offset_metres']-by['1']['offset_metres'],
                tracks=tracks,source='data/nyc_south_culver_source.json',
                stage='candidate_three_track_station_native_audit_pending',
                pending=['Church four-to-three merge and portal transitions need separate native geometry audit.',
                         '18 Av needs two island faces sharing one physical center track; do not duplicate center rail.',
                         'No depot, yard storage fan or yard links.'])
    return source,ditmas


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path);a=p.parse_args()
    source,ditmas=prepare(a.snapshot)
    for name,value in [('nyc_south_culver_source',source),('nyc_ditmas_three_tracks',ditmas)]:
        Path(f'data/{name}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(name=s['name'],cross_section=s['cross_section']) for s in source['stations']]))
