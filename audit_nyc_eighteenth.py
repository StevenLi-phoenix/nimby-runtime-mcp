"""Validate two islands surrounding one shared central platform track at 18 Avenue."""
import json
import math
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from shapely.geometry import MultiLineString, box


def audit():
    f=json.loads(Path('work/nyc-f-built.json').read_bytes())
    s=next(s for s in f['stations'] if s['plan_index']==34)
    src=json.loads(Path('data/nyc_south_culver_source.json').read_bytes())['stations'][1]
    net=json.loads(Path('work/nyc-eighteenth-native.json').read_bytes());nodes={n['id']:n for n in net['nodes']}
    scale=src['scale'];tx,ty=src['southbound_tangent'].values();center=src['center'];refs={c['track_ref']:c['offset_metres'] for c in src['cross_section']}
    def xy(x,y):
        dx,dy=x-center['x'],y-center['y'];return (-dx*ty+dy*tx)*scale,(dx*tx+dy*ty)*scale
    groups={ref:[] for ref in refs}
    assert len(nodes)==12 and sum(len(n['buildings']) for n in nodes.values())==22
    for n in nodes.values():
        assert n['depth']==2 and n['track_type']==3 and not n['branches']
        assert all(b['depth']==2 for b in n['buildings'])
        assert n['station_id']==(s['native_station'] if n['id'] in s['platform_nodes'] else '0')
        ref=min(refs,key=lambda r:abs(xy(n['x'],n['y'])[0]-refs[r]));groups[ref].append(n['id'])
    assert all(len(ids)==4 for ids in groups.values())
    lengths={}
    for ref,ids in groups.items():
        platforms=[nodes[i] for i in ids if nodes[i]['station_id']!='0'];assert len(platforms)==2
        a,b=platforms;assert b['id'] in [a['previous'],a['next']]
        length=math.hypot(a['x']-b['x'],a['y']-b['y'])*scale;assert abs(length-140)<.02;lengths[ref]=length
    lines={r:MultiLineString([[xy(*p) for p in nodes[i]['curve']] for i in ids]).intersection(box(-30,-70,30,70)) for r,ids in groups.items()}
    gaps={a+' / '+b:lines[a].distance(lines[b]) for a,b in [('1','3-4'),('3-4','2')]};assert min(gaps.values())>8
    islands=[(refs['1']+1.525,refs['3-4']-1.525),(refs['3-4']+1.525,refs['2']-1.525)]
    fig,ax=plt.subplots(figsize=(5,10));faces=[]
    for n in nodes.values():
        for b in n['buildings']:
            if b['type'] not in [13,27]:continue
            dx,dy=b['direction_x'],b['direction_y'];length=math.hypot(dx,dy);dx,dy=dx/length,dy/length
            corners=[xy(b['x']+(a*dx*b['width']-c*dy*b['height'])/(2*scale),b['y']+(a*dy*b['width']+c*dx*b['height'])/(2*scale)) for a,c in [(-1,-1),(1,-1),(1,1),(-1,1)]]
            lo,hi=min(p[0] for p in corners),max(p[0] for p in corners)
            island=next((j for j,(a,c) in enumerate(islands) if a-.01<=lo<hi<=c+.01),None);assert island is not None,(b['id'],lo,hi)
            faces.append(dict(id=b['id'],node_id=n['id'],type=b['type'],island=island,lateral_min=lo,lateral_max=hi))
            ax.add_patch(Polygon(corners,color='#b99362' if b['type']==13 else '#777777',alpha=.5))
        x,y=zip(*(xy(*p) for p in n['curve']));ax.plot(x,y,color='#30495c',linewidth=1)
    assert len(faces)==16
    central=set(f['eighteenth_center_platform']['platform_nodes'])
    for i in central:
        assert {b['island'] for b in faces if b['node_id']==i and b['type']==13}=={0,1}
    ax.set(aspect='equal',ylim=(125,-125),xlim=(-14,14),title='18 Avenue: two islands, shared center rail',xlabel='Metres across',ylabel='Metres south')
    ax.grid(alpha=.2);fig.tight_layout();fig.savefig(Path(os.environ['TEMP'])/'nyc-eighteenth-audit.png',dpi=160)
    north=[s['west_primary'],s['west_secondary'],f['eighteenth_center_platform']['north_endpoint']]
    connected=all(any(j!='0' and j not in nodes for j in [nodes[i]['previous'],nodes[i]['next']]) for i in north)
    result=dict(station_id=s['native_station'],nodes=12,buildings=22,physical_tracks=3,platform_lengths_metres=lengths,
                gaps_metres=gaps,island_widths_metres=[b-a for a,b in islands],central_track_serves_both_islands=True,
                faces=faces,construction_pending=any(n['blueprint'] for n in nodes.values()),ditmas_connection_pending=not connected)
    Path('work/nyc-eighteenth-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='faces'}))


if __name__=='__main__':audit()
