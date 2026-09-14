"""Audit four through tracks and the independent lower Church G reversal route."""
import argparse
import json
import math
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import LineString,MultiLineString,Point


def audit(built=False):
    state=json.loads(Path('work/nyc-g-built.json').read_bytes())
    relay=state['church_relay'];plan=json.loads(Path('data/nyc_church_relay.json').read_bytes())
    old={n['id']:n for n in json.loads(Path('work/nyc-church-relay-live.json').read_bytes())['nodes']}
    snapshot='built' if built else 'connected'
    net=json.loads(Path(f'work/nyc-church-relay-{snapshot}.json').read_bytes());nodes={n['id']:n for n in net['nodes']}
    parents={t['start_node_id'] for t in relay['through_tracks']};changes=[]
    for i,n in old.items():
        other=nodes[i];fields=[k for k in n if n[k]!=other[k]]
        if fields:
            assert i in parents and set(fields)<=set(['previous','next','curve','x','y']), (i,fields)
            changes.append(dict(id=i,fields=fields,moved_metres=math.hypot(n['x']-other['x'],n['y']-other['y'])*plan['scale']))
        if n['station_id']!='0':assert n==other
    main={t['track_ref']:[t['start_node_id']]+t['nodes'] for t in relay['through_tracks']}
    lower={t['track_ref']:[t['branch_node']]+t['nodes'] for t in relay['tails']}
    added={i for ids in main.values() for i in ids if i not in old}|{i for ids in lower.values() for i in ids}|set(relay['crossover_nodes'])
    assert set(nodes)-set(old)==added and len(added)==22
    assert all(nodes[i]['track_type']==3 and not nodes[i]['buildings'] for i in added)
    for t in relay['through_tracks']:
        assert all(nodes[i]['depth']==-2 for i in t['nodes'])
        assert '0' in [nodes[t['frontier']]['previous'],nodes[t['frontier']]['next']]
    for t in relay['tails']:
        assert nodes[t['branch_node']]['branch_parent']==t['through_edge_id']
        assert all(nodes[i]['depth']==-3 for i in t['nodes'])
        assert '0' in [nodes[t['frontier']]['previous'],nodes[t['frontier']]['next']]
    scale=plan['scale'];lines={r:MultiLineString([nodes[i]['curve'] for i in ids]) for r,ids in main.items()}
    clearances=[dict(tracks=[a,b],metres=lines[a].distance(lines[b])*scale) for a,b in [('1','3'),('3','4'),('4','2')]]
    assert min(c['metres'] for c in clearances)>3.5
    cross=[nodes[i] for i in relay['crossover_nodes']]
    assert len(cross)==2 and cross[0]['next']==cross[1]['id'] and all(n['depth']==-3 for n in cross)
    assert {n['branch_parent'] for n in cross}=={c['edge_id'] for c in relay['crossover_candidates']}
    arrival=next(t for t in relay['tails'] if t['track_ref']=='1')
    entry=next(n for n in cross if n['branch_parent']==arrival['nodes'][1]);end=nodes[arrival['frontier']]
    reversal_clearance=math.hypot(entry['x']-end['x'],entry['y']-end['y'])*scale
    assert reversal_clearance>140
    def halves(n):
        curve=n['curve'];center=min(range(len(curve)),key=lambda j:math.hypot(curve[j][0]-n['x'],curve[j][1]-n['y']))
        for half,neighbor in [(curve[:center+1],n['previous']),(curve[center:],n['next'])]:
            if len(half)>1 and neighbor in nodes:
                yield LineString(half),{n['depth'],nodes[neighbor]['depth']},neighbor
    lower_ids={i for ids in lower.values() for i in ids}|set(relay['crossover_nodes'])
    main_ids={i for ids in main.values() for i in ids}
    intersections=[]
    branch_points=[Point(nodes[t['branch_node']]['x'],nodes[t['branch_node']]['y']) for t in relay['tails']]
    for i in sorted(lower_ids):
        for lower_line,depths,neighbor in halves(nodes[i]):
            for j in sorted(main_ids):
                intersection=lower_line.intersection(LineString(nodes[j]['curve']))
                if intersection.is_empty:continue
                junction=any(intersection.distance(p)<.1/scale for p in branch_points)
                assert junction or -2 not in depths,(i,j,depths,intersection.wkt)
                intersections.append(dict(relay_node=i,main_node=j,relay_depths=sorted(depths),
                                          intended_branch_junction=junction,geometry=intersection.wkt))
    origin=old[plan['through_tracks'][0]['start_node_id']];tx,ty=plan['southbound_tangent'].values()
    def xy(x,y):
        dx,dy=x-origin['x'],y-origin['y'];return (-dx*ty+dy*tx)*scale,(dx*tx+dy*ty)*scale
    fig,axes=plt.subplots(1,2,figsize=(10,9))
    for ref,color in [('1','#298442'),('3','#bf9128'),('4','#cc4840'),('2','#3277ae')]:
        for i in main[ref]:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']));axes[0].plot(x,y,c=color,lw=1.2)
    for ref,ids in lower.items():
        for i in ids:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']));axes[0].plot(x,y,c='#704bb0',lw=1.5)
        axes[1].plot([xy(nodes[i]['x'],nodes[i]['y'])[1] for i in ids], [nodes[i]['depth'] for i in ids],'.-',label='G relay '+ref)
    for n in cross:
        x,y=zip(*(xy(*p) for p in n['curve']));axes[0].plot(x,y,c='#704bb0',lw=2)
    axes[0].set(aspect='equal',ylim=(470,-80),title='Church: through tracks and lower relay',xlabel='Metres across track',ylabel='Metres south of station lead')
    axes[1].set(title='Relay native control layers',xlabel='Metres south of station lead',ylabel='Depth');axes[1].legend()
    for ax in axes:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-church-relay.png',dpi=160)
    result=dict(total_nodes=net['count'],new_nodes=len(added),main_clearances=clearances,
                reversal_clearance_metres=reversal_clearance,intersections=intersections,
                four_through_frontiers_open=True,station_platforms_unchanged=True,existing_changes=changes,
                construction_pending=any(nodes[i]['blueprint'] for i in added),operating_verified=False)
    Path('work/nyc-church-relay-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--built',action='store_true');audit(parser.parse_args().built)
