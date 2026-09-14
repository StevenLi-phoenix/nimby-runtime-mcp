"""Audit the outer Church--Ditmas tracks and existing G/center-track protection."""
import json
import math
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString


def audit():
    state=json.loads(Path('work/nyc-f-built.json').read_bytes())
    plan=json.loads(Path('data/nyc_church_ditmas_corridors.json').read_bytes())
    before={n['id']:n for n in json.loads(Path('work/nyc-church-ditmas-live.json').read_bytes())['nodes']}
    net=json.loads(Path('work/nyc-church-ditmas-connected.json').read_bytes())
    nodes={n['id']:n for n in net['nodes']}
    parents={t[k] for t in state['church_ditmas_outer'] for k in ['start_node_id','end_node_id']}
    changes=[]
    for i,n in before.items():
        fields=[k for k in n if n[k]!=nodes[i][k]]
        if fields:
            assert i in parents and set(fields)<= {'previous','next','curve','x','y'}, (i,fields)
            changes.append(dict(id=i,fields=fields,moved_metres=math.hypot(n['x']-nodes[i]['x'],n['y']-nodes[i]['y'])*plan['scale']))
    groups={t['track_ref']:[t['start_node_id']]+t['nodes']+[t['end_node_id']] for t in state['church_ditmas_outer']}
    added={i for t in state['church_ditmas_outer'] for i in t['nodes']}
    assert set(nodes)-set(before)==added and len(added)==10
    assert all(nodes[i]['track_type']==3 and not nodes[i]['buildings'] for i in added)
    for t in state['church_ditmas_outer']:
        for a,b in zip(groups[t['track_ref']],groups[t['track_ref']][1:]):
            assert b in [nodes[a]['previous'],nodes[a]['next']]
        depths=[nodes[i]['depth'] for i in groups[t['track_ref']]]
        assert depths==sorted(depths) and set(depths)=={-2,-1,0,1,2}
    lines={r:MultiLineString([nodes[i]['curve'] for i in ids]) for r,ids in groups.items()}
    gap=lines['1'].distance(lines['2'])*plan['scale'];assert gap>3.5
    # Curves include half of each neighbouring edge; clip at each node centre to
    # check the actual endpoint layers of crossings with existing lower G tracks.
    intersections=[]
    g=json.loads(Path('work/nyc-g-built.json').read_bytes())
    lower={i for t in g['church_relay']['tails'] for i in t['nodes']}|set(g['church_relay']['crossover_nodes'])
    for i in added|parents:
        n=nodes[i];curve=n['curve']
        mid=min(range(len(curve)),key=lambda j:math.hypot(curve[j][0]-n['x'],curve[j][1]-n['y']))
        for half,other in [(curve[:mid+1],n['previous']),(curve[mid:],n['next'])]:
            if len(half)<2 or other not in nodes:continue
            for j in lower:
                cross=LineString(half).intersection(LineString(nodes[j]['curve']))
                if cross.is_empty:continue
                assert -3 not in {n['depth'],nodes[other]['depth']}
                intersections.append(dict(node=i,neighbor=other,relay=j,depths=[n['depth'],nodes[other]['depth']],geometry=cross.wkt))
    origin=before[next(iter(groups.values()))[0]];scale=plan['scale']
    tx,ty=.148,-.989
    def xy(x,y):
        dx,dy=x-origin['x'],y-origin['y'];return (-dx*ty+dy*tx)*scale,(dx*tx+dy*ty)*scale
    fig,axes=plt.subplots(1,2,figsize=(10,10))
    for ref,ids in groups.items():
        for i in ids:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']));axes[0].plot(x,y,color={'1':'#268543','2':'#287cbe'}[ref])
        axes[1].plot([xy(nodes[i]['x'],nodes[i]['y'])[1] for i in ids],[nodes[i]['depth'] for i in ids],'.-',label='B'+ref)
    for i in lower:
        x,y=zip(*(xy(*p) for p in nodes[i]['curve']));axes[0].plot(x,y,color='#9977b0',alpha=.5)
    axes[0].set(aspect='equal',ylim=(450,-60),title='Church to Ditmas: outer local tracks',xlabel='Metres across corridor',ylabel='Metres south')
    axes[1].set(title='Native control layers',xlabel='Metres south',ylabel='Layer');axes[1].legend()
    for ax in axes:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-church-ditmas-audit.png',dpi=150)
    result=dict(new_nodes=len(added),minimum_outer_gap_metres=gap,existing_changes=changes,
                g_relay_intersections=intersections,station_platforms_and_buildings_unchanged=True,
                construction_pending=any(nodes[i]['blueprint'] for i in added),express_connections_pending=True)
    Path('work/nyc-church-ditmas-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':audit()
