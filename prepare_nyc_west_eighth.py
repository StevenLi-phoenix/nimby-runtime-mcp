"""Plan West 8th Street's stacked F/Q side platforms from OSM footprints."""
import json,math
from pathlib import Path
from prepare_nyc_culver import centroid,nearest
from prepare_nyc_direction import source_depth

def prepare():
 source=json.loads(Path('data/nyc_coney_culver_source.json').read_bytes());route=json.loads(Path('data/nyc_f_plan.json').read_bytes())['directions']['to_coney_island'];stop=route['stations'][43];scale=math.cos(math.radians(stop['latitude']));levels=[]
 for service,depth,ids in [('F',2,[427044498,427044500]),('Q',3,[427044497,427044499])]:
  footprints=[w for w in source['ways'] if w['osm_way_id'] in ids];assert len(footprints)==2
  centers=[]
  for w in footprints:
   c=centroid([{k:p[k]-stop[k] for k in ['x','y']} for p in w['points']]);centers.append({k:c[k]+stop[k] for k in ['x','y']})
  center={k:sum(p[k] for p in centers)/2 for k in ['x','y']};_,_,(tx,ty)=nearest(route['route'],center);cross=[]
  for w in source['ways']:
   if w['tags'].get('railway')!='subway' or source_depth(w['tags'])!=depth:continue
   for a,b in zip(w['points'],w['points'][1:]):
    da=(a['x']-center['x'])*tx+(a['y']-center['y'])*ty;db=(b['x']-center['x'])*tx+(b['y']-center['y'])*ty
    if abs(db-da)<1e-9 or not 0<=-da/(db-da)<=1:continue
    f=-da/(db-da);q={k:a[k]+f*(b[k]-a[k]) for k in ['x','y']};off=(-(q['x']-center['x'])*ty+(q['y']-center['y'])*tx)*scale
    if abs(off)<20:cross.append(dict(source_way_id=w['osm_way_id'],track_ref=w['tags'].get('railway:track_ref'),line_name=w['tags'].get('name'),offset_metres=off,depth=depth,**q))
  cross.sort(key=lambda c:c['offset_metres']);assert len(cross)==2,cross
  levels.append(dict(service=service,depth=depth,center=center,scale=scale,southbound_tangent=dict(x=tx,y=ty),cross_section=cross,platform_footprints=footprints,layout='two_side_platforms',platform_length_metres=140,tracks=[dict(track_ref=c['track_ref'],source_way_id=c['source_way_id'],points=[dict(x=c['x']+d*tx/scale,y=c['y']+d*ty/scale,depth=depth) for d in [-120,-70,70,120]]) for c in cross]))
 return dict(plan_index=43,name='West 8th Street–NY Aquarium',levels=levels,source='data/nyc_coney_culver_source.json',stage='candidate_native_geometry_pending',station_assignment='one_shared_station_for_both_levels',attribution=source['attribution'])
if __name__=='__main__':
 p=prepare();Path('data/nyc_west_eighth_stacked.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps([dict(service=s['service'],depth=s['depth'],center=s['center'],cross_section=s['cross_section']) for s in p['levels']]))
