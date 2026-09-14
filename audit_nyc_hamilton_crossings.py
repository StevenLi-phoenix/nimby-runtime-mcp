"""Verify layers at actual local/express half-curve intersections."""
import json
import argparse
from pathlib import Path
from shapely.geometry import LineString
parser=argparse.ArgumentParser()
parser.add_argument('--section', choices=['hamilton','church'], default='hamilton')
section=parser.parse_args().section
state=json.loads(Path('work/nyc-g-built.json').read_bytes());net=json.loads(Path(f'work/nyc-{section}-connected.json').read_bytes());nodes={n['id']:n for n in net['nodes']}
locals=set()
for key in (['seventh_fifteenth_corridors','hamilton_corridors'] if section=='hamilton' else ['church_corridors']):
 for c in state[key]:
  if c['track_ref'] in ['1','2']:locals.update([c['start_node_id'],*c['nodes'],c['end_node_id']])
for s in state['stations']:
 if section=='hamilton' and s['plan_index'] in [18,19]:locals.update(s['nodes'])
 if section=='church' and s['plan_index']==20:
  locals.update(i for ref in ['1','2'] for i in state['church_tracks'][ref]['nodes'])
express=set()
for c in state[section+'_corridors']:
 if c['track_ref'] in ['3','4']:express.update([c['start_node_id'],*c['nodes'],c['end_node_id']])
if section=='hamilton':
 for t in state['hamilton_express_tracks']:express.update(t['nodes'])
else:
 for ref in ['3','4']:express.update(state['church_tracks'][ref]['nodes'])
def halves(n):
 curve=n.get('curve',[])
 if len(curve)<3:return []
 center=min(range(len(curve)),key=lambda i:(curve[i][0]-n['x'])**2+(curve[i][1]-n['y'])**2)
 assert (curve[center][0]-n['x'])**2+(curve[center][1]-n['y'])**2<.001
 out=[]
 for points,neighbor in [(curve[:center+1],n['previous']),(curve[center:],n['next'])]:
  if len(points)>1 and neighbor in nodes:out.append((LineString(points),{n['depth'],nodes[neighbor]['depth']},neighbor))
 return out
hits=[]
for a in sorted(locals):
 for b in sorted(express):
  for la,ad,an in halves(nodes[a]):
   for lb,bd,bn in halves(nodes[b]):
    cross=la.intersection(lb)
    if cross.is_empty:continue
    assert ad=={-2} and bd=={-3},(a,b,ad,bd,cross.wkt)
    hits.append(dict(local_node=a,local_neighbor=an,express_node=b,express_neighbor=bn,local_depth=-2,express_depth=-3,intersection=cross.wkt,both_edge_controls_same_layer=True))
assert hits
result=dict(intersections=hits,all_grade_separated=True,section=section,scope='Native local/express curves and both endpoint layers of every intersecting half-edge')
Path(f'work/nyc-{section}-crossing-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
