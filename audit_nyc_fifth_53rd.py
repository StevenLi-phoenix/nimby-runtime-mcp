import json,math,os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
s=json.loads(Path('work/nyc-f-built.json').read_bytes());p=json.loads(Path('data/nyc_fifth_53rd_stacked.json').read_bytes());v=json.loads(Path('work/nyc-fifth-53rd-native.json').read_bytes());ns={n['id']:n for n in v['nodes']};assert len(ns)==8
fig,axes=plt.subplots(1,2,figsize=(8,9));report=[]
for ax,e,src in zip(axes,s['fifth_53rd_platforms'],p['platforms']):
 tx,ty=src['axis'].values();c=src['center'];scale=p['scale'];lo,hi=src['source_side_bounds_metres']
 def xy(x,y):return (-(x-c['x'])*ty+(y-c['y'])*tx)*scale,((x-c['x'])*tx+(y-c['y'])*ty)*scale
 ps=[ns[i] for i in e['platform_nodes']];length=math.hypot(ps[0]['x']-ps[1]['x'],ps[0]['y']-ps[1]['y'])*scale;assert abs(length-140)<.02;faces=0
 for i in e['nodes']:
  n=ns[i];assert n['depth']==src['depth'] and n['track_type']==3 and not n['branches'];assert n['station_id']==(s['fifth_53rd_station_id'] if i in e['platform_nodes'] else '0')
  q=[xy(*a) for a in n['curve']]
  if q:ax.plot(*zip(*q),color='steelblue')
  for b in n['buildings']:
   assert b['depth']==src['depth']
   if b['type'] not in [13,27]:continue
   dx,dy=b['direction_x'],b['direction_y'];d=math.hypot(dx,dy);dx/=d;dy/=d
   corners=[xy(b['x']+(a*dx*b['width']-z*dy*b['height'])/(2*scale),b['y']+(a*dy*b['width']+z*dx*b['height'])/(2*scale)) for a,z in [(-1,-1),(1,-1),(1,1),(-1,1)]]
   assert all(lo-.01<=x<=hi+.01 for x,y in corners);faces+=1;ax.add_patch(Polygon(corners,color='#b99362' if b['type']==13 else '#777777',alpha=.5))
 assert faces==8
 ax.set(aspect='equal',xlim=(-2,7),ylim=(125,-125),title=f"D{e['track_ref']} depth {e['depth']}");ax.grid(alpha=.2);report.append(dict(ref=e['track_ref'],depth=e['depth'],length_metres=length,side_bounds_metres=[lo,hi]))
fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-fifth-53rd-audit.png',dpi=120)
r=dict(station_id=s['fifth_53rd_station_id'],nodes=len(ns),buildings=sum(len(n['buildings']) for n in ns.values()),platforms=report,construction_pending=any(n['blueprint'] for n in ns.values()));Path('work/nyc-fifth-53rd-audit.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
