import json,math
from pathlib import Path
from prepare_nyc_culver import centroid,nearest
s=json.loads(Path('data/nyc_west_end_55_source.json').read_bytes());stop=json.loads(Path('data/nyc_d_plan.json').read_bytes())['directions']['to_coney_island']['stations'][27];centers=[]
for w in s['ways']:
 if w['osm_way_id'] in [427044441,427044442]:
  c=centroid([{k:p[k]-stop[k] for k in ['x','y']} for p in w['points']]);centers.append({k:c[k]+stop[k] for k in c})
c={k:sum(p[k] for p in centers)/2 for k in ['x','y']};ref=next(w for w in s['ways'] if w['osm_way_id']==427044476);_,_,(tx,ty)=nearest(ref['points'],c)
if ty>0:tx,ty=-tx,-ty
scale=math.cos(math.radians(stop['latitude']));rows=[]
for w in s['ways']:
 if w['tags'].get('railway')!='subway' or w['tags'].get('name')!='BMT West End Line':continue
 for a,b in zip(w['points'],w['points'][1:]):
  da=(a['x']-c['x'])*tx+(a['y']-c['y'])*ty;db=(b['x']-c['x'])*tx+(b['y']-c['y'])*ty
  if abs(db-da)<1e-9 or not 0<=-da/(db-da)<=1:continue
  q={k:a[k]-da/(db-da)*(b[k]-a[k]) for k in ['x','y']};off=(-(q['x']-c['x'])*ty+(q['y']-c['y'])*tx)*scale
  if abs(off)<30:rows.append(dict(source_way_id=w['osm_way_id'],offset_metres=off,track_ref=w['tags']['railway:track_ref'],tags=w['tags'],**q))
rows.sort(key=lambda r:r['offset_metres']);assert len(rows)==3
tracks=[dict(track_ref=r['track_ref'],source_way_id=r['source_way_id'],offset_metres=r['offset_metres'],points=[dict(x=r['x']+d*tx/scale,y=r['y']+d*ty/scale,depth=2) for d in [-120,-70,70,120]]) for r in rows]
p=dict(name='62nd Street',plan_index=27,center=c,scale=scale,southbound_axis=dict(x=tx,y=ty),tracks=tracks,source_platform_way_ids=[427044441,427044442],source='data/nyc_west_end_55_source.json',layout='two_islands_three_physical_tracks',depth=2,stage='candidate_native_creation_pending');Path('data/nyc_west_end_62_three_tracks.json').write_text(json.dumps(p,indent=2));print(json.dumps(rows))
