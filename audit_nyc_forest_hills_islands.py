"""Audit Forest Hills-71st Avenue's two island platforms and four physical tracks."""
import json,math,os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

def audit():
 f=json.loads(Path('work/nyc-f-built.json').read_bytes());p=json.loads(Path('data/nyc_forest_hills_islands.json').read_bytes());ns={n['id']:n for n in json.loads(Path('work/nyc-forest_hills-native.json').read_bytes())['nodes']};assert len(ns)==16;scale=p['scale'];tx,ty=p['southbound_axis'].values();c=p['center']
 def xy(x,y):return (-(x-c['x'])*ty+(y-c['y'])*tx)*scale,((x-c['x'])*tx+(y-c['y'])*ty)*scale
 fig,ax=plt.subplots(figsize=(8,10));results=[]
 for island,src in zip(f['forest_hills_islands'],p['islands']):
  offsets=[t['offset_metres'] for t in src['tracks']];groups=[[],[]];faces=0;lo_limit=offsets[0]+1.525;hi_limit=offsets[1]-1.525
  for i in island['nodes']:
   n=ns[i];assert n['depth']==-2 and n['track_type']==3 and not n['branches'];assert n['station_id']==(f['forest_hills_station_id'] if i in island['platform_nodes'] else '0');j=min(range(2),key=lambda j:abs(xy(n['x'],n['y'])[0]-offsets[j]));groups[j].append(n)
   x,y=zip(*(xy(*q) for q in n['curve']));ax.plot(x,y,color='#436879')
   for b in n['buildings']:
    assert b['depth']==-2
    if b['type'] not in [13,27]:continue
    dx,dy=b['direction_x'],b['direction_y'];length=math.hypot(dx,dy);dx/=length;dy/=length
    corners=[xy(b['x']+(a*dx*b['width']-z*dy*b['height'])/(2*scale),b['y']+(a*dy*b['width']+z*dx*b['height'])/(2*scale)) for a,z in [(-1,-1),(1,-1),(1,1),(-1,1)]];lo,hi=min(q[0] for q in corners),max(q[0] for q in corners);assert lo_limit-.01<=lo<hi<=hi_limit+.01;faces+=1;ax.add_patch(Polygon(corners,color='#b99362' if b['type']==13 else '#777777',alpha=.5))
  assert faces==8 and sum(len(ns[i]['buildings']) for i in island['nodes'])==12
  for group in groups:
   assert len(group)==4;a,b=[n for n in group if n['station_id']!='0'];assert b['id'] in [a['previous'],a['next']];assert abs(math.hypot(a['x']-b['x'],a['y']-b['y'])*scale-140)<.02
  results.append(dict(source_platform_way=src['platform_way_id'],island_width_metres=hi_limit-lo_limit))
 ax.set(aspect='equal',ylim=(125,-125),title='Forest Hills-71st Avenue: two islands, four tracks');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-forest_hills-islands-audit.png',dpi=150)
 result=dict(station_id=f['forest_hills_station_id'],nodes=16,buildings=24,islands=results,construction_pending=any(n['blueprint'] for n in ns.values()),approaches_pending=True);Path('work/nyc-forest_hills-islands-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':audit()






