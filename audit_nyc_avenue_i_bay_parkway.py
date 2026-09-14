"""Audit the three elevated tracks from Avenue I to Bay Parkway."""
import json
import math
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import MultiLineString


def audit():
    f=json.loads(Path('work/nyc-f-built.json').read_bytes())
    plan=json.loads(Path('data/nyc_avenue_i_bay_parkway_corridors.json').read_bytes())
    before={n['id']:n for n in json.loads(Path('work/nyc-avenue-i-bay-parkway-live.json').read_bytes())['nodes']}
    net=json.loads(Path('work/nyc-avenue-i-bay-parkway-connected.json').read_bytes());nodes={n['id']:n for n in net['nodes']}
    corridors=f['avenue_i_bay_parkway_corridors'];parents={i for c in corridors for i in [c['start_node_id'],c['end_node_id']]};changes=[]
    for i,n in before.items():
        fields=[k for k in n if n[k]!=nodes[i][k]]
        if fields:
            if i not in parents:
                assert i in f['bay_parkway_center_track']['nodes']
                assert set(fields)=={'previous','next','curve'}
                assert (n['previous'],n['next'])==(nodes[i]['next'],nodes[i]['previous'])
                assert n['curve']==nodes[i]['curve'][::-1]
                changes.append(dict(id=i,fields=fields,physical_curve_unchanged=True))
                continue
            assert i in parents and set(fields)<= {'previous','next','curve','x','y'},(i,fields)
            movement=math.hypot(n['x']-nodes[i]['x'],n['y']-nodes[i]['y'])*plan['scale'];assert movement<.001
            changes.append(dict(id=i,fields=fields,moved_metres=movement))
    added={i for c in corridors for i in c['nodes']}
    assert set(nodes)-set(before)==added
    assert all(nodes[i]['depth']==2 and nodes[i]['track_type']==3 for i in added)
    assert all(b['depth']==2 for i in added for b in nodes[i]['buildings'])
    groups={c['track_ref']:[c['start_node_id']]+c['nodes']+[c['end_node_id']] for c in corridors}
    for ids in groups.values():
        for a,b in zip(ids,ids[1:]):assert b in [nodes[a]['previous'],nodes[a]['next']]
    lines={r:MultiLineString([nodes[i]['curve'] for i in ids]) for r,ids in groups.items()}
    gaps={a+' / '+b:lines[a].distance(lines[b])*plan['scale'] for a,b in [('1','3-4'),('3-4','2')]}
    origin=before[groups['3-4'][0]];tx,ty=.143,-.990;scale=plan['scale']
    def xy(x,y):
        dx,dy=x-origin['x'],y-origin['y'];return (-dx*ty+dy*tx)*scale,(dx*tx+dy*ty)*scale
    fig,ax=plt.subplots(figsize=(5,10))
    for ref,ids in groups.items():
        for i in ids:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']));ax.plot(x,y,color={'1':'#268543','2':'#287cbe','3-4':'#c09231'}[ref])
    ax.set(aspect='equal',ylim=(300,-50),title='Avenue I to Bay Parkway',xlabel='Metres across',ylabel='Metres south');ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-avenue-i-bay-parkway-audit.png',dpi=150)
    result=dict(new_nodes=len(added),new_buildings=sum(len(nodes[i]['buildings']) for i in added),clearances_metres=gaps,
                existing_changes=changes,construction_pending=any(nodes[i]['blueprint'] for i in added),operating_verified=False)
    Path('work/nyc-avenue-i-bay-parkway-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    assert min(gaps.values())>3.5,gaps


if __name__=='__main__':audit()
