"""Generate a segmented lateral-offset candidate; native curve audit remains required."""
import json,math
from pathlib import Path
from shapely.geometry import LineString

def prepare():
 p=json.loads(Path('data/nyc_sixth_express_depth_candidate.json').read_bytes());base=json.loads(Path('data/nyc_sixth_express_corridors.json').read_bytes());choices={'3':(1.2,1.1),'4':(.7,1.3)}
 for c,b in zip(p['corridors'],base['corridors']):
  line=LineString([(q['x'],q['y']) for q in b['points']]);up,down=choices[c['track_ref']];sign=-1 if c['track_ref']=='3' else 1
  offsets=[(0,0),(1120,0),(1180,up),(1360,up),(1510,down),(1700,down),(1760,0),(b['source_length_metres'],0)]
  stations=sorted(set([q['metres'] for q in c['points']]+[d for d,v in offsets]));profile=c['points'];points=[]
  for d in stations:
   z=next((a['depth']+(v['depth']-a['depth'])*(d-a['metres'])/(v['metres']-a['metres']) for a,v in zip(profile,profile[1:]) if a['metres']<=d<=v['metres']),-3)
   shift=next((x+(y-x)*(d-a)/(v-a) for (a,x),(v,y) in zip(offsets,offsets[1:]) if a<=d<=v),0)
   q=line.interpolate(d/p['scale']);a=line.interpolate(max(0,d-1)/p['scale']);v=line.interpolate((d+1)/p['scale']);dx,dy=v.x-a.x,v.y-a.y;length=math.hypot(dx,dy)
   points.append(dict(x=q.x-sign*dy/length*shift/p['scale'],y=q.y+sign*dx/length*shift/p['scale'],depth=round(z),metres=d,lateral_offset_metres=shift))
  points=[q for q in points if not (1700<q['metres']<1715)]
  points[0].update({k:b['points'][0][k] for k in ['x','y','depth']});points[-1].update({k:b['points'][-1][k] for k in ['x','y','depth']});c['points']=points;c['offset_profile']=offsets
 p.pop('path_clearance_flags',None);p['stage']='segmented_candidate_native_audit_pending';p['adaptation']='Local rise to -1 across Canarsie; independently offset ascent/descent to preserve PATH and local rail spacing. Source-sample screening is not native clearance proof.'
 return p
if __name__=='__main__':
 p=prepare();Path('data/nyc_sixth_express_segmented_candidate.json').write_text(json.dumps(p,indent=2),encoding='utf-8');print([(c['track_ref'],len(c['points'])) for c in p['corridors']])
