"""Compare local express offsets against PATH and Sixth Avenue local source rails."""
import json,math
from pathlib import Path
from shapely.geometry import LineString,Point

def evaluate():
 p=json.loads(Path('data/nyc_sixth_express_corridors.json').read_bytes());src=json.loads(Path('data/nyc_sixth_express_source.json').read_bytes());scale=p['scale'];results=[]
 ways=[(w,LineString([(q['x'],q['y']) for q in w['points']])) for w in src['ways'] if w['tags'].get('name')=='PATH' or (w['tags'].get('name')=='IND Sixth Avenue Line' and w['tags'].get('railway:track_ref') in ['1','2'])]
 profile=[(1180,-3),(1260,-2),(1360,-1),(1510,-1),(1610,-2),(1700,-3)]
 for c in p['corridors']:
  line=LineString([(q['x'],q['y']) for q in c['points']]);sign=-1 if c['track_ref']=='3' else 1
  for shift in [0,.5,1,1.25,1.5,1.75,2]:
   minima={'PATH':999,'IND Sixth Avenue Line':999};worst={}
   for d in range(1180,1701,2):
    z=next(x+(y-x)*(d-a)/(b-a) for (a,x),(b,y) in zip(profile,profile[1:]) if a<=d<=b)
    q=line.interpolate(d/scale);a=line.interpolate((d-1)/scale);b=line.interpolate((d+1)/scale);dx,dy=b.x-a.x,b.y-a.y;length=math.hypot(dx,dy);weight=min(1,(d-1180)/60,(1700-d)/60);q=Point(q.x-sign*dy/length*shift*weight/scale,q.y+sign*dx/length*shift*weight/scale)
    for w,rail in ways:
     if abs(float(w['tags'].get('level',-99))-z)>.25:continue
     gap=q.distance(rail)*scale;name=w['tags']['name']
     if gap<minima[name]:minima[name]=gap;worst[name]=dict(metres=d,source_way=w['osm_way_id'],depth=z)
   results.append(dict(ref=c['track_ref'],offset_metres=shift,minima=minima,worst=worst))
 return results
if __name__=='__main__':
 r=evaluate();Path('data/nyc_sixth_express_offset_comparison.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print([(q['ref'],q['offset_metres'],{k:round(v,3) for k,v in q['minima'].items()}) for q in r])
