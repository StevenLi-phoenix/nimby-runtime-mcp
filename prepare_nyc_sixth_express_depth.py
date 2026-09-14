"""Prepare a local native-depth candidate for the Sixth Avenue express crossing."""
import json
from pathlib import Path
from shapely.geometry import LineString,Point

def prepare():
 p=json.loads(Path('data/nyc_sixth_express_corridors.json').read_bytes());source=json.loads(Path('data/nyc_sixth_express_source.json').read_bytes());profile=[(0,-3),(1180,-3),(1260,-2),(1360,-1),(1510,-1),(1610,-2),(1700,-3)];reviews=[]
 for c in p['corridors']:
  old=c['points'];line=LineString([(q['x'],q['y']) for q in old]);length=line.length*p['scale'];stations=sorted(set([q['metres'] for q in old]+[d for d,z in profile]))
  def depth(d):
   for (a,x),(b,y) in zip(profile,profile[1:]):
    if a<=d<=b:return x+(y-x)*(d-a)/(b-a)
   return -3
  c['points']=[dict(x=line.interpolate(d/p['scale']).x,y=line.interpolate(d/p['scale']).y,depth=round(depth(d)),metres=d) for d in stations]
  c['points'][0].update({k:old[0][k] for k in ['x','y','depth']});c['points'][-1].update({k:old[-1][k] for k in ['x','y','depth']})
  for d in range(1180,1701,5):
   q=line.interpolate(d/p['scale']);z=depth(d)
   for w in source['ways']:
    if w['tags'].get('name')!='PATH':continue
    zd=float(w['tags'].get('level',-99));gap=q.distance(LineString([(a['x'],a['y']) for a in w['points']]))*p['scale']
    if gap<3.5 and abs(z-zd)<.25:reviews.append(dict(ref=c['track_ref'],metres=d,source_way=w['osm_way_id'],gap_metres=gap,candidate_depth=z,source_depth=zd))
 p['adaptation']='Candidate local -3/-2/-1/-2/-3 profile; not native geometry. Close PATH approaches require resolution before creation.';p['stage']='candidate_clearance_review';p['path_clearance_flags']=reviews
 return p
if __name__=='__main__':
 p=prepare();Path('data/nyc_sixth_express_depth_candidate.json').write_text(json.dumps(p,indent=2),encoding='utf-8');print('PATH close approach samples',len(p['path_clearance_flags']));print(p['path_clearance_flags'][:4])
