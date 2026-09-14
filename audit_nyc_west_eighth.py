"""Audit both West 8th Street levels and their common native station."""
import json,math,os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

def audit():
 f=json.loads(Path('work/nyc-f-built.json').read_bytes());s=next(s for s in f['stations'] if s['plan_index']==43);p=json.loads(Path('data/nyc_west_eighth_stacked.json').read_bytes());ns={n['id']:n for n in json.loads(Path('work/nyc-west-eighth-native.json').read_bytes())['nodes']};assert len(ns)==16
 fig,axes=plt.subplots(1,2,figsize=(8,10));results=[]
 for level,plan,ax in zip(f['west_eighth_levels'],p['levels'],axes):
  tx,ty=plan['southbound_tangent'].values();scale=plan['scale'];c=plan['center'];refs={r['track_ref']:r['offset_metres'] for r in plan['cross_section']};groups={r:[] for r in refs};faces=0
  def xy(x,y):return (-(x-c['x'])*ty+(y-c['y'])*tx)*scale,((x-c['x'])*tx+(y-c['y'])*ty)*scale
  for i in level['nodes']:
   n=ns[i];assert n['depth']==level['depth'] and n['track_type']==3 and not n['branches'];assert n['station_id']==(s['native_station'] if i in level['platform_nodes'] else '0')
   ref=min(refs,key=lambda r:abs(xy(n['x'],n['y'])[0]-refs[r]));groups[ref].append(n);x,y=zip(*(xy(*q) for q in n['curve']));ax.plot(x,y,color='#436879')
   for b in n['buildings']:
    assert b['depth']==level['depth']
    if b['type'] not in [13,27]:continue
    dx,dy=b['direction_x'],b['direction_y'];d=math.hypot(dx,dy);dx/=d;dy/=d
    corners=[xy(b['x']+(a*dx*b['width']-z*dy*b['height'])/(2*scale),b['y']+(a*dy*b['width']+z*dx*b['height'])/(2*scale)) for a,z in [(-1,-1),(1,-1),(1,1),(-1,1)]];lo,hi=min(q[0] for q in corners),max(q[0] for q in corners)
    assert hi<min(refs.values())-1.2 or lo>max(refs.values())+1.2
    faces+=1;ax.add_patch(Polygon(corners,color='#b99362' if b['type']==13 else '#777777',alpha=.5))
  assert faces==8 and sum(len(ns[i]['buildings']) for i in level['nodes'])==12
  for nodes in groups.values():
   assert len(nodes)==4;a,b=[n for n in nodes if n['station_id']!='0'];assert b['id'] in [a['previous'],a['next']];assert abs(math.hypot(a['x']-b['x'],a['y']-b['y'])*scale-140)<.02
  ax.set(aspect='equal',ylim=(125,-125),xlim=(-16,16),title=f"{level['service']} depth {level['depth']}");ax.grid(alpha=.2);results.append(dict(service=level['service'],depth=level['depth'],nodes=8,buildings=12,platform_length_metres=140))
 fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-west-eighth-audit.png',dpi=150)
 result=dict(station_id=s['native_station'],levels=results,construction_pending=any(n['blueprint'] for n in ns.values()),connections_pending=True);Path('work/nyc-west-eighth-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':audit()
