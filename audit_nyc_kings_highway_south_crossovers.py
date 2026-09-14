"""Verify source-mapped southern Kings Highway crossovers and protect main tracks."""
import json, math, os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def audit():
 f=json.loads(Path('work/nyc-f-built.json').read_bytes());cs=f['kings_highway_south_crossovers']
 old={n['id']:n for n in json.loads(Path('work/nyc-kings-highway-south-crossovers-before.json').read_bytes())['nodes']}
 ns={n['id']:n for n in json.loads(Path('work/nyc-kings-highway-south-crossovers-connected.json').read_bytes())['nodes']}
 ids={i for c in cs for i in c['nodes']};assert len(ids)==4 and set(ns)-set(old)==ids
 expected={}
 for c in cs:
  for i,p in zip(c['nodes'],c['candidates']):expected.setdefault(p['edge_id'],[]).append(i)
 for i,n in old.items():
  assert {k:v for k,v in n.items() if k!='branches'}=={k:v for k,v in ns[i].items() if k!='branches'}
  assert set(ns[i]['branches'])==set(n['branches'])|set(expected.get(i,[]))
 scale=.7592437006614161
 def xy(x,y):return (x+8234560)*scale,(4953900-y)*scale
 fig,ax=plt.subplots(figsize=(7,10))
 for i,n in ns.items():
  if 4953500<n['y']<4953900:
   x,y=zip(*(xy(*p) for p in n['curve']));ax.plot(x,y,color='#c45431' if i in ids else '#537387',linewidth=1.5)
 lengths=[]
 for c in cs:
  a,b=[ns[i] for i in c['nodes']];assert b['id'] in [a['previous'],a['next']]
  for n,p in zip([a,b],c['candidates']):
   assert n['branch_parent']==p['edge_id'] and abs(n['branch_position']-p['position'])<1e-6
   assert n['depth']==2 and n['track_type']==3 and n['station_id']=='0' and not n['buildings']
   assert math.hypot(n['x']-p['x'],n['y']-p['y'])*scale<.01
  lengths.append(math.hypot(a['x']-b['x'],a['y']-b['y'])*scale)
 ax.set(aspect='equal',title='Kings Highway: two southern crossovers',xlabel='Metres east',ylabel='Metres south',ylim=(270,-20));ax.grid(alpha=.2)
 fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-kings-highway-south-crossovers-audit.png',dpi=150)
 result=dict(new_nodes=4,crossovers=2,source_way_ids=[c['source_way_id'] for c in cs],endpoint_distances_metres=lengths,existing_geometry_unchanged=True,construction_pending=any(ns[i]['blueprint'] for i in ids),south_crossovers_pending=False)
 Path('work/nyc-kings-highway-south-crossovers-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':audit()
