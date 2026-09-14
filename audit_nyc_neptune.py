"""Verify Neptune Avenue's two tracks and single island platform."""
import json,math,os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

def audit():
 f=json.loads(Path('work/nyc-f-built.json').read_bytes());s=next(s for s in f['stations'] if s['plan_index']==42);p=json.loads(Path('data/nyc_neptune_island.json').read_bytes());net=json.loads(Path('work/nyc-neptune-native.json').read_bytes());ns={n['id']:n for n in net['nodes']};scale=p['scale'];tx,ty=p['southbound_tangent'].values();c=p['center'];refs={r['track_ref']:r['offset_metres'] for r in p['cross_section']}
 def xy(x,y):return (-(x-c['x'])*ty+(y-c['y'])*tx)*scale,((x-c['x'])*tx+(y-c['y'])*ty)*scale
 assert len(ns)==8 and sum(len(n['buildings']) for n in ns.values())==12
 groups={r:[] for r in refs};fig,ax=plt.subplots(figsize=(5,10));faces=[];limits=(refs['1']+1.525,refs['2']-1.525)
 for n in ns.values():
  assert n['depth']==2 and n['track_type']==3 and not n['branches'];assert n['station_id']==(s['native_station'] if n['id'] in s['platform_nodes'] else '0')
  ref=min(refs,key=lambda r:abs(xy(n['x'],n['y'])[0]-refs[r]));groups[ref].append(n)
  x,y=zip(*(xy(*q) for q in n['curve']));ax.plot(x,y,color='#436879')
  for b in n['buildings']:
   assert b['depth']==2
   if b['type'] not in [13,27]:continue
   dx,dy=b['direction_x'],b['direction_y'];length=math.hypot(dx,dy);dx/=length;dy/=length
   corners=[xy(b['x']+(a*dx*b['width']-z*dy*b['height'])/(2*scale),b['y']+(a*dy*b['width']+z*dx*b['height'])/(2*scale)) for a,z in [(-1,-1),(1,-1),(1,1),(-1,1)]]
   lo,hi=min(q[0] for q in corners),max(q[0] for q in corners);assert limits[0]-.01<=lo<hi<=limits[1]+.01
   faces.append(dict(id=b['id'],type=b['type'],lo=lo,hi=hi));ax.add_patch(Polygon(corners,color='#b99362' if b['type']==13 else '#777777',alpha=.5))
 for nodes in groups.values():
  assert len(nodes)==4;a,b=[n for n in nodes if n['station_id']!='0'];assert b['id'] in [a['previous'],a['next']];assert abs(math.hypot(a['x']-b['x'],a['y']-b['y'])*scale-140)<.02
 assert len(faces)==8
 ax.set(aspect='equal',ylim=(125,-125),xlim=(-10,10),title='Neptune Avenue: one island, two tracks');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-neptune-audit.png',dpi=150)
 north=all(any(j!='0' and j not in ns for j in [ns[i]['previous'],ns[i]['next']]) for i in [s['west_primary'],s['west_secondary']])
 result=dict(station_id=s['native_station'],nodes=8,buildings=12,island_width_metres=limits[1]-limits[0],platform_length_metres=140,construction_pending=any(n['blueprint'] for n in ns.values()),north_connected=north,south_connection_pending=True)
 Path('work/nyc-neptune-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':audit()
