import json,math,os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
p=json.loads(Path('data/nyc_ninth_avenue_three_tracks.json').read_bytes());e=json.loads(Path('work/nyc-d-built.json').read_bytes())['ninth_avenue_station'];ns=json.loads(Path('work/nyc-ninth-native.json').read_bytes())['nodes'];tx,ty=p['southbound_axis'].values();scale=p['scale'];c=p['center'];off=[t['offset_metres'] for t in p['tracks']]
def xy(x,y):return (-(x-c['x'])*ty+(y-c['y'])*tx)*scale,((x-c['x'])*tx+(y-c['y'])*ty)*scale
fig,ax=plt.subplots(figsize=(7,10));groups=[[],[],[]];faces=0
for n in ns:
 assert n['depth']==-1 and n['track_type']==3 and not n['branches'];x,y=xy(n['x'],n['y']);j=min(range(3),key=lambda j:abs(x-off[j]));assert abs(x-off[j])<.01;groups[j].append(n);ax.plot(*zip(*(xy(*q) for q in n['curve'])),color='steelblue')
 if n['id'] in e['platform_nodes']:assert n['station_id']==e['station_id']
 for b in n['buildings']:
  assert b['depth']==-1
  if b['type'] not in [13,27]:continue
  dx,dy=b['direction_x'],b['direction_y'];l=math.hypot(dx,dy);dx/=l;dy/=l
  corners=[xy(b['x']+(a*dx*b['width']-z*dy*b['height'])/(2*scale),b['y']+(a*dy*b['width']+z*dx*b['height'])/(2*scale)) for a,z in [(-1,-1),(1,-1),(1,1),(-1,1)]];lo=min(q[0] for q in corners);hi=max(q[0] for q in corners)
  assert any(i['offset_min']-.01<=lo<hi<=i['offset_max']+.01 for i in p['islands']),(b['id'],lo,hi)
  faces+=1;ax.add_patch(Polygon(corners,color='tan' if b['type']==13 else 'grey',alpha=.5))
for group in groups:
 assert len(group)==4;a,b=[n for n in group if n['id'] in e['platform_nodes']];assert b['id'] in [a['previous'],a['next']];assert abs(math.hypot(a['x']-b['x'],a['y']-b['y'])*scale-140)<.02
assert faces==16
ax.set(aspect='equal',ylim=(125,-125),title='9th Avenue: three tracks, two islands');ax.grid();fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-ninth-audit.png',dpi=120)
r=dict(nodes=len(ns),buildings=sum(len(n['buildings']) for n in ns),platform_building_faces=faces,platform_lengths_metres=[140]*3,construction_pending=any(n['blueprint'] for n in ns));Path('work/nyc-ninth-audit.json').write_text(json.dumps(r,indent=2));print(r)
