import json,math,os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
p=json.loads(Path('data/nyc_west_end_50_side_platforms.json').read_bytes());v=json.loads(Path('work/nyc-west_end_50-native.json').read_bytes());c=p['center'];tx,ty=p['southbound_axis'].values();scale=p['scale'];fig,ax=plt.subplots(figsize=(6,9));widths=json.loads(Path('data/nyc_west_end_50_platform_widths.json').read_bytes());faces=0


def xy(x,y):return (-(x-c['x'])*ty+(y-c['y'])*tx)*scale,((x-c['x'])*tx+(y-c['y'])*ty)*scale
for n in v['nodes']:
 assert n['depth']==2 and n['track_type']==3
 if n['curve']:ax.plot(*zip(*(xy(*q) for q in n['curve'])),color='#446688')
 for b in n['buildings']:
  assert b['depth']==2
  if b['type'] not in [13,27]:continue
  dx,dy=b['direction_x'],b['direction_y'];d=math.hypot(dx,dy);dx/=d;dy/=d
  corners=[xy(b['x']+(a*dx*b['width']-z*dy*b['height'])/(2*scale),b['y']+(a*dy*b['width']+z*dx*b['height'])/(2*scale)) for a,z in [(-1,-1),(1,-1),(1,1),(-1,1)]]
  rail=xy(n['x'],n['y'])[0];lo,hi=min(q[0] for q in corners),max(q[0] for q in corners);limits=next(w['limits'] for w in widths if (sum(w['limits'])>0)==(rail>0))
  if rail>0:assert lo>=rail+1.52 and hi<=limits[1]+.01
  else:assert hi<=rail-1.52 and lo>=limits[0]-.01
  ax.add_patch(Polygon(corners,color='#b99362',alpha=.35));faces+=1
assert faces==8 and len(v['nodes'])==10
ax.set(aspect='equal',title='50th Street side platforms');ax.grid(alpha=.2);fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-west_end_50-audit.png',dpi=130)
print('Eight platform and roof faces verified; depth 2')

