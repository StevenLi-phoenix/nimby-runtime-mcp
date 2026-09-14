"""Audit Church express approaches, Ditmas merge topology and crossover curves."""
import json
import math
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString, box


def audit():
    f=json.loads(Path('work/nyc-f-built.json').read_bytes())
    plan=json.loads(Path('data/nyc_ditmas_merge.json').read_bytes())
    before={n['id']:n for n in json.loads(Path('work/nyc-ditmas-merge-live.json').read_bytes())['nodes']}
    net=json.loads(Path('work/nyc-ditmas-merge-connected.json').read_bytes());nodes={n['id']:n for n in net['nodes']}
    groups={t['track_ref']:[t['start_node_id']]+t['nodes']+[t['end_node_id']] for t in f['church_ditmas_outer']}
    for t in f['ditmas_express_merge']:
        groups[t['track_ref']]=[t['start_node_id']]+t['nodes']+([t['end_node_id']] if 'end_node_id' in t else [])
    parents={t['start_node_id'] for t in f['ditmas_express_merge']}|{f['ditmas_center_track']['north_endpoint'],f['ditmas_b3_merge_candidate']['edge_id']}
    crossovers=f.get('ditmas_crossovers',[])
    parents|={p['edge_id'] for c in crossovers for p in c['candidates']}
    approach_neighbors={before[t['start_node_id']][k] for t in f['ditmas_express_merge'] for k in ['previous','next']} - {'0'}
    changes=[]
    for i,n in before.items():
        fields=[k for k in n if n[k]!=nodes[i][k]]
        if fields:
            if i in approach_neighbors and fields==['curve']:
                changes.append(dict(id=i,fields=fields,adjacent_endpoint_curve_recalculated=True))
                continue
            if i in f['ditmas_center_track']['nodes'] and i not in parents:
                assert nodes[i]['previous']==n['next'] and nodes[i]['next']==n['previous']
                assert set(fields)<={'previous','next','curve'}
                changes.append(dict(id=i,fields=fields,native_chain_orientation_reversed=True))
                continue
            assert i in parents and set(fields)<= {'previous','next','curve','branches'},(i,fields)
            changes.append(dict(id=i,fields=fields))
    added={i for t in f['ditmas_express_merge'] for i in t['nodes']}|{i for c in crossovers for i in c['nodes']}
    assert set(nodes)-set(before)==added
    assert all(nodes[i]['track_type']==3 and not nodes[i]['buildings'] for i in added)
    branch=next(t for t in f['ditmas_express_merge'] if t['track_ref']=='3')['branch_node']
    assert nodes[branch]['branch_parent']==f['ditmas_b3_merge_candidate']['edge_id']
    for c in crossovers:
        pair=[nodes[i] for i in c['nodes']]
        assert len(pair)==2 and all(n['depth']==2 for n in pair)
        assert {n['branch_parent'] for n in pair}=={p['edge_id'] for p in c['candidates']}
        assert pair[1]['id'] in [pair[0]['previous'],pair[0]['next']]
        for p in c['candidates']:
            n=next(n for n in pair if n['branch_parent']==p['edge_id'])
            assert math.hypot(n['x']-p['x'],n['y']-p['y'])*plan['scale']<.1
    for t in f['ditmas_express_merge']:
        ids=groups[t['track_ref']]
        for a,b in zip(ids,ids[1:]):assert b in [nodes[a]['previous'],nodes[a]['next']]
        depths=[nodes[i]['depth'] for i in ids];assert depths==sorted(depths) and set(depths)=={-2,-1,0,1,2}
    lines={r:MultiLineString([nodes[i]['curve'] for i in ids]) for r,ids in groups.items()}
    g=json.loads(Path('work/nyc-g-built.json').read_bytes())
    lower={i for t in g['church_relay']['tails'] for i in t['nodes']}|set(g['church_relay']['crossover_nodes'])
    assert all(nodes[i]==before[i] and nodes[i]['depth']==-3 for i in lower)
    assert all(nodes[i]['depth']>=-2 for i in added)
    # Exclude the final B3-to-B1 turnout taper only, retaining the entire
    # four-parallel-track approach through the source crossover origin.
    cutoff=plan['corridors'][0]['points'][-2]['y']
    approach=box(-8240000,cutoff, -8230000,4961000)
    gaps={'1 / 3 before turnout':lines['1'].intersection(approach).distance(lines['3'].intersection(approach))*plan['scale'],
          '3 / 4':lines['3'].distance(lines['4'])*plan['scale'],
          '4 / 2':lines['4'].distance(lines['2'])*plan['scale']}
    # Report geometry before asserting, so failed candidates remain reviewable.
    origin=before[groups['3'][0]];scale=plan['scale'];tx,ty=.148,-.989
    def xy(x,y):
        dx,dy=x-origin['x'],y-origin['y'];return (-dx*ty+dy*tx)*scale,(dx*tx+dy*ty)*scale
    fig,axes=plt.subplots(1,2,figsize=(10,10))
    for ref,ids in groups.items():
        color={'1':'#268543','2':'#287cbe','3':'#b88722','4':'#c74646'}[ref]
        for i in ids:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']))
            for ax in axes:ax.plot(x,y,color=color)
    for c in crossovers:
        for i in c['nodes']:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']))
            for ax in axes:ax.plot(x,y,color='#8056a4')
    axes[0].set(aspect='equal',ylim=(450,-40),title='Church to Ditmas: four to three')
    axes[1].set(aspect='equal',ylim=(445,320),title='Ditmas north junctions')
    for ax in axes:ax.grid(alpha=.2);ax.set(xlabel='Metres across',ylabel='Metres south')
    fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-ditmas-merge-audit.png',dpi=150)
    result=dict(added_nodes=len(added),clearances_metres=gaps,existing_changes=changes,
                source_crossovers_present=len(crossovers),construction_pending=any(nodes[i]['blueprint'] for i in added))
    Path('work/nyc-ditmas-merge-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    assert min(gaps.values())>3.5,gaps


if __name__=='__main__':audit()
