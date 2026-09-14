"""Verify 7th Avenue native platform surfaces form two islands between four rails."""
import json
import argparse
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon


def audit(plan_index=17):
    assert plan_index in (17,18,20)
    key={17:'seventh',18:'fifteenth',20:'church'}[plan_index]
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    source = json.loads(Path('data/nyc_culver_cross_sections.json').read_bytes())['stations'][plan_index-13]
    native = json.loads(Path(f'work/nyc-{key}-native.json').read_bytes())
    station = next(s for s in state['stations'] if s['plan_index'] == plan_index)
    refs = {c['track_ref']: c for c in source['cross_section']}
    tx, ty = source['southbound_tangent'].values()
    center, scale = source['center'], source['scale']
    def xy(x, y):
        dx, dy = x-center['x'], y-center['y']
        return (-dx*ty+dy*tx)*scale, (dx*tx+dy*ty)*scale
    fig, ax = plt.subplots(figsize=(7, 10))
    surfaces = []
    islands=state[key+'_islands'] if plan_index in (17,20) else [dict(primary_ref='2',secondary_ref='1',platform_nodes=station['platform_nodes'])]
    clearance=1.825 if plan_index==17 else 1.525
    for island in islands:
        lo = refs[island['secondary_ref']]['offset_metres']+clearance
        hi = refs[island['primary_ref']]['offset_metres']-clearance
        for building in state[key+'_building_geometry']['buildings']:
            if building['node_id'] not in island['platform_nodes'] or building['type'] not in [13, 27]:
                continue
            assert building['depth'] == station['depth']
            dx, dy = building['direction_x'], building['direction_y']
            length = math.hypot(dx, dy)
            dx, dy = dx/length, dy/length
            corners = [xy(building['x']+(a*dx*building['width']-b*dy*building['height'])/(2*scale),
                          building['y']+(a*dy*building['width']+b*dx*building['height'])/(2*scale))
                       for a, b in [(-1,-1), (1,-1), (1,1), (-1,1)]]
            actual_lo, actual_hi = min(p[0] for p in corners), max(p[0] for p in corners)
            assert lo-.01 <= actual_lo < actual_hi <= hi+.01, (building['id'], lo, hi, actual_lo, actual_hi)
            ax.add_patch(Polygon(corners, facecolor='#b99362' if building['type']==13 else '#797979',
                                 edgecolor='none', alpha=.75 if building['type']==13 else .4))
            if building['type']==13:
                surfaces.append(dict(id=building['id'], island=[island['secondary_ref'],island['primary_ref']],
                                     lateral_min=actual_lo, lateral_max=actual_hi))
    assert len(surfaces)==len(station['platform_nodes'])
    for node in native['nodes']:
        assert node['depth']==station['depth'] and all(b['depth']==node['depth'] for b in node['buildings'])
        if node['station_id']!='0': assert node['station_id']==station['native_station']
        if node.get('curve'):
            x,y=zip(*(xy(*p) for p in node['curve']))
            ax.plot(x,y,color='#303b46',lw=1.3)
    for ref, crossing in refs.items():
        ax.text(crossing['offset_metres'], 85, 'B'+ref, ha='center')
    ax.set(aspect='equal', xlim=(-23,23), ylim=(-130,130),
           xlabel='Metres across station', ylabel='Metres along station',
           title=station['name']+': native island platforms')
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(Path(os.environ['TEMP'])/f'nyc-{key}-islands.png',dpi=160)
    native_by={n['id']:n for n in native['nodes']}
    tracks=state[key+'_tracks'].values() if plan_index in (17,20) else [dict(north_endpoint=station[k]) for k in ['west_primary','west_secondary']]
    north_connected=all(any(i!='0' and i not in native_by for i in
                            [native_by[t['north_endpoint']]['previous'],native_by[t['north_endpoint']]['next']])
                        for t in tracks)
    result=dict(station_id=station['native_station'],nodes=native['count'],platform_nodes=len(station['platform_nodes']),
                surfaces_within_islands=surfaces,building_depth_mismatches=[],
                layout_verified=True,construction_pending=any(n['blueprint'] for n in native['nodes']),
                north_connections_verified=north_connected)
    Path(f'work/nyc-{key}-island-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan-index',type=int,choices=[17,18,20],default=17)
    audit(parser.parse_args().plan_index)
