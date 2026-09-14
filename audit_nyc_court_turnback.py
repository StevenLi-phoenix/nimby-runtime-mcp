"""Audit Court Square relay curves, future source crossings and preserved facilities."""
import json
import argparse
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import LineString, MultiLineString


def audit(built=False):
    state=json.loads(Path('work/nyc-g-built.json').read_bytes())
    relay=state['court_turnback']
    plan=json.loads(Path('data/nyc_court_turnback.json').read_bytes())
    before={n['id']:n for n in json.loads(Path('work/nyc-court-turnback-live.json').read_bytes())['nodes']}
    snapshot='built' if built else 'connected'
    current=json.loads(Path(f'work/nyc-court-turnback-{snapshot}.json').read_bytes())
    nodes={n['id']:n for n in current['nodes']}
    removed=set(relay['removed_north_crossovers'])
    assert set(before)-set(nodes)==removed
    parents={t['start_node_id'] for t in relay['tracks']}
    changes=[]
    for i,n in before.items():
        if i in removed:continue
        other=nodes[i]
        fields=[k for k in n if n[k]!=other[k]]
        if fields:
            assert i in parents, (i, fields)
            assert set(fields)<=set(['previous','next','curve','branches','building_tapes','x','y'])
            assert {b['id'] for b in n['building_tapes']}-{b['id'] for b in other['building_tapes']}<=set(relay['removed_one_way_signals'])
            changes.append(dict(id=i,fields=fields,moved_metres=math.hypot(n['x']-other['x'],n['y']-other['y'])*plan['scale']))
        if n['station_id']!='0':assert other==n
    added={i for t in relay['tracks'] for i in t['nodes']}|set(relay['crossover_nodes'])
    assert set(nodes)-set(before)==added and len(added)==10
    assert all(nodes[i]['track_type']==3 and not nodes[i]['buildings'] for i in added)
    origin=before[plan['tracks'][0]['start_node_id']]
    tx,ty=plan['outward_tangent']['x'],plan['outward_tangent']['y'];scale=plan['scale']
    def xy(x,y):
        dx,dy=x-origin['x'],y-origin['y']
        return (dx*tx+dy*ty)*scale,(-dx*ty+dy*tx)*scale
    lines={t['role']:MultiLineString([nodes[i]['curve'] for i in [t['start_node_id']]+t['nodes']]) for t in relay['tracks']}
    spacing=lines['west_primary'].distance(lines['west_secondary'])*scale
    assert spacing>4.8
    branch=[nodes[i] for i in relay['crossover_nodes']]
    candidates=relay['branch_candidates']
    assert {n['branch_parent'] for n in branch}=={c['edge_id'] for c in candidates}
    assert branch[0]['next']==branch[1]['id'] and all(n['depth']==-1 for n in branch)
    secondary=next(c for c in candidates if c['role']=='west_secondary')
    arrival_node=next(n for n in branch if n['branch_parent']==secondary['edge_id'])
    arrival_track=next(t for t in relay['tracks'] if t['role']=='west_secondary')
    end=nodes[arrival_track['frontier']]
    clearance=math.hypot(end['x']-arrival_node['x'],end['y']-arrival_node['y'])*scale
    assert clearance>140
    ways=json.loads(Path('data/nyc_court_square_source.json').read_bytes())['ways']
    crossings=[]
    for i in sorted(added|parents):
        n=nodes[i];curve=n['curve']
        center=min(range(len(curve)),key=lambda j:math.hypot(curve[j][0]-n['x'],curve[j][1]-n['y']))
        for half,neighbor in [(curve[:center+1],n['previous']), (curve[center:],n['next'])]:
            if len(half)<2 or neighbor not in nodes:continue
            depths={n['depth'],nodes[neighbor]['depth']}
            native=LineString(half)
            for w in ways:
                if w['tags'].get('name')=='IND Crosstown Line':continue
                source=LineString([(p['x'],p['y']) for p in w['points']])
                crossing=native.intersection(source)
                if crossing.is_empty:continue
                source_depth=int(w['tags'].get('level',w['tags'].get('layer')))
                assert source_depth not in depths,(i,w['osm_way_id'],depths,source_depth)
                crossings.append(dict(node_id=i,neighbor=neighbor,source_way_id=w['osm_way_id'],
                                      native_endpoint_depths=sorted(depths),source_depth=source_depth,intersection=crossing.wkt))
    assert crossings
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    for w in ways:
        x,y=zip(*(xy(p['x'],p['y']) for p in w['points']))
        axes[0].plot(x,y,color='#bbb',lw=.6)
    for t,color in zip(relay['tracks'],['#24863b','#3267ae']):
        ids=[t['start_node_id']]+t['nodes']
        for i in ids:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']))
            axes[0].plot(x,y,c=color,lw=1.6)
        axes[1].plot([xy(nodes[i]['x'],nodes[i]['y'])[0] for i in ids],
                     [nodes[i]['depth'] for i in ids],'.-',c=color,label=t['role'])
    for n in branch:
        x,y=zip(*(xy(*p) for p in n['curve']));axes[0].plot(x,y,c='#c18327',lw=2)
    axes[0].set(aspect='equal',xlim=(-120,430),ylim=(-100,100),title='Native relay; grey = source through tracks',xlabel='Metres beyond existing station lead')
    axes[1].set(title='Native control layers',xlabel='Metres beyond existing station lead',ylabel='Depth')
    for ax in axes:ax.grid(alpha=.2)
    axes[1].legend();fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-court-turnback.png',dpi=160)
    result=dict(total_nodes=current['count'],new_nodes=len(added),removed_branch_nodes=len(removed),
                minimum_parallel_spacing_metres=spacing,clear_length_beyond_arrival_branch_metres=clearance,
                future_source_crossings=crossings,existing_changes=changes,station_platforms_unchanged=True,
                all_source_crossings_grade_separated=True,construction_pending=any(nodes[i]['blueprint'] for i in added),
                operating_verified=False)
    Path('work/nyc-court-turnback-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--built',action='store_true')
    audit(parser.parse_args().built)
