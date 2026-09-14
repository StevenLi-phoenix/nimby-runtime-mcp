"""Prepare Neptune Avenue's single island and preserve southern Culver source."""
import argparse,hashlib,json,math
from pathlib import Path
from prepare_geometry import project
from prepare_nyc_culver import centroid,nearest
from prepare_nyc_direction import source_depth

def prepare(snapshot):
 raw=snapshot.read_bytes();objects=json.loads(raw)['elements'];ns={e['id']:e for e in objects if e['type']=='node'}
 ways=[dict(osm_way_id=e['id'],version=e['version'],tags=e['tags'],node_ids=e['nodes'],points=[dict(zip(('x','y'),project(ns[i]))) for i in e['nodes']]) for e in objects if e['type']=='way' and e.get('tags',{}).get('railway') in ('subway','platform')]
 route=json.loads(Path('data/nyc_f_plan.json').read_bytes())['directions']['to_coney_island'];s=route['stations'][42]
 platform=next(w for w in ways if w['osm_way_id']==427044496);assert platform['node_ids'][0]==platform['node_ids'][-1]
 c=centroid([{k:p[k]-s[k] for k in ['x','y']} for p in platform['points']]);center={k:c[k]+s[k] for k in ['x','y']};scale=math.cos(math.radians(s['latitude']));_,_,(tx,ty)=nearest(route['route'],center)
 cross=[]
 for w in ways:
  if w['tags'].get('name')!='IND Culver Line' or w['tags'].get('railway')!='subway':continue
  for a,b in zip(w['points'],w['points'][1:]):
   da=(a['x']-center['x'])*tx+(a['y']-center['y'])*ty;db=(b['x']-center['x'])*tx+(b['y']-center['y'])*ty
   if abs(db-da)<1e-9 or not 0<=-da/(db-da)<=1:continue
   f=-da/(db-da);q={k:a[k]+f*(b[k]-a[k]) for k in ['x','y']};off=(-(q['x']-center['x'])*ty+(q['y']-center['y'])*tx)*scale
   if abs(off)<30:cross.append(dict(track_ref=w['tags'].get('railway:track_ref'),source_way_id=w['osm_way_id'],offset_metres=off,depth=source_depth(w['tags']),**q))
 cross.sort(key=lambda c:c['offset_metres']);assert len(cross)==2 and {c['track_ref'] for c in cross}=={'1','2'} and all(c['depth']==2 for c in cross)
 source=dict(source_url='https://api.openstreetmap.org/api/0.6/map.json?bbox=-73.983,40.574,-73.970,40.590',source_sha256=hashlib.sha256(raw).hexdigest(),ways=ways,attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')
 plan=dict(plan_index=42,name='Neptune Avenue',center=center,scale=scale,southbound_tangent=dict(x=tx,y=ty),platform_footprint=platform,cross_section=cross,layout='one_island_two_tracks',platform_length_metres=140,native_depth=2,source='data/nyc_coney_culver_source.json',stage='candidate_native_geometry_pending',tracks=[dict(track_ref=c['track_ref'],source_way_id=c['source_way_id'],points=[dict(x=c['x']+d*tx/scale,y=c['y']+d*ty/scale,depth=2) for d in [-120,-70,70,120]]) for c in cross])
 return source,plan
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path);a=p.parse_args();source,plan=prepare(a.snapshot)
 for name,v in [('nyc_coney_culver_source',source),('nyc_neptune_island',plan)]:Path('data/'+name+'.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({k:v for k,v in plan.items() if k not in ['platform_footprint','tracks']}))
