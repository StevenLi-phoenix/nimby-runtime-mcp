"""Check three Culver approach curves and explicit source crossovers."""
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
    plan=json.loads(Path('data/nyc_ditmas_eighteenth_corridors.json').read_bytes())
    before={n['id']:n for n in json.loads(Path('work/nyc-ditmas-eighteenth-live.json').read_bytes())['nodes']}
    net=json.loads(Path('work/nyc-ditmas-eighteenth-connected.json').read_bytes());nodes={n['id']:n for n in net['nodes']}
    corridors=f['ditmas_eighteenth_corridors'];crossovers=f.get('ditmas_eighteenth_crossovers',[])
    ends={c[k] for c in corridors for k in ['start_node_id','end_node_id']}
    branches={p['edge_id'] for c in crossovers for p in c['candidates']}
    center=set(f['eighteenth_center_platform']['nodes']);changes=[]
    for i,n in before.items():
        other=nodes[i];fields=[k for k in n if n[k]!=other[k]]
        if not fields:continue
        allowed={'curve'}
        if i in ends:allowed|={'previous','next','x','y'}
        if i in branches:allowed|={'branches'}
        if i in center:
            allowed|={'previous','next','buildings'}
            if i not in ends:assert other['previous']==n['next'] and other['next']==n['previous']
            old_buildings={b['id']:b for b in n['buildings']};new_buildings={b['id']:b for b in other['buildings']}
            assert old_buildings.keys()==new_buildings.keys()
            for bid,b in old_buildings.items():
                after=new_buildings[bid]
                assert all(b[k]==after[k] for k in b if k!='width')
                assert abs(b['width']-after['width'])<.0001
        assert set(fields)<=allowed and (i in ends|branches|center),(i,fields)
        movement=math.hypot(n['x']-other['x'],n['y']-other['y'])*plan['scale'];assert movement<.001
        changes.append(dict(id=i,fields=fields,moved_metres=movement))
    groups={c['track_ref']:[c['start_node_id']]+c['nodes']+[c['end_node_id']] for c in corridors}
    added={i for c in corridors for i in c['nodes']}|{i for c in crossovers for i in c['nodes']}
    assert set(nodes)-set(before)==added
    assert all(nodes[i]['depth']==2 and nodes[i]['track_type']==3 and not nodes[i]['buildings'] for i in added)
    for ids in groups.values():
        for a,b in zip(ids,ids[1:]):assert b in [nodes[a]['previous'],nodes[a]['next']]
    for c in crossovers:
        pair=[nodes[i] for i in c['nodes']];assert len(pair)==2
        assert pair[1]['id'] in [pair[0]['previous'],pair[0]['next']]
        assert {n['branch_parent'] for n in pair}=={p['edge_id'] for p in c['candidates']}
        for p in c['candidates']:
            n=next(n for n in pair if n['branch_parent']==p['edge_id'])
            assert math.hypot(n['x']-p['x'],n['y']-p['y'])*plan['scale']<.1
    lines={r:MultiLineString([nodes[i]['curve'] for i in ids]) for r,ids in groups.items()}
    gaps={a+' / '+b:lines[a].distance(lines[b])*plan['scale'] for a,b in [('1','3-4'),('3-4','2')]}
    origin=before[groups['3-4'][0]];tx,ty=.144,-.990;scale=plan['scale']
    def xy(x,y):
        dx,dy=x-origin['x'],y-origin['y'];return (-dx*ty+dy*tx)*scale,(dx*tx+dy*ty)*scale
    fig,axes=plt.subplots(1,2,figsize=(9,10))
    for ref,ids in groups.items():
        for i in ids:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']))
            for ax in axes:ax.plot(x,y,color={'1':'#268543','2':'#287cbe','3-4':'#c09231'}[ref])
    for c in crossovers:
        for i in c['nodes']:
            x,y=zip(*(xy(*p) for p in nodes[i]['curve']))
            for ax in axes:ax.plot(x,y,color='#8257b1')
    axes[0].set(aspect='equal',ylim=(530,-55),title='Ditmas to 18 Avenue: three tracks')
    axes[1].set(aspect='equal',ylim=(240,25),title='Source crossover group')
    for ax in axes:ax.grid(alpha=.2);ax.set(xlabel='Metres across',ylabel='Metres south')
    fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-ditmas-eighteenth-audit.png',dpi=150)
    result=dict(new_nodes=len(added),clearances_metres=gaps,existing_changes=changes,
                source_crossovers_present=len(crossovers),construction_pending=any(nodes[i]['blueprint'] for i in added))
    Path('work/nyc-ditmas-eighteenth-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    assert min(gaps.values())>3.5,gaps


if __name__=='__main__':audit()
