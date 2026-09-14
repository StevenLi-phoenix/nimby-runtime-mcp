"""Check live Ditmas curves, three physical tracks and outside platform faces."""
import json
import argparse
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from shapely.geometry import MultiLineString, box


def audit(plan_index=33):
    key={33:'ditmas',35:'avenue_i',36:'bay_parkway',37:'avenue_n',38:'avenue_p',40:'avenue_u',41:'avenue_x'}[plan_index]
    filename=key.replace('_','-')
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    station = next(s for s in state['stations'] if s['plan_index'] == plan_index)
    plan = json.loads(Path(f'data/nyc_{key}_three_tracks.json').read_bytes())
    net = json.loads(Path('work/nyc-ditmas-live.json' if plan_index==33 else f'work/nyc-{key.replace("_", "-")}-native.json').read_bytes())
    nodes = {n['id']: n for n in net['nodes']}
    center, scale, tangent = plan['center'], plan['scale'], plan['southbound_tangent']
    tx, ty = tangent['x'], tangent['y']

    def xy(x, y):
        dx, dy = x-center['x'], y-center['y']
        return (-dx*ty+dy*tx)*scale, (dx*tx+dy*ty)*scale

    groups = {'3-4': state[key+'_center_track']['nodes']}
    for ref, start_key in [('2', 'west_primary'), ('1', 'west_secondary')]:
        component, todo = set(), [station[start_key]]
        while todo:
            i = todo.pop()
            if i in component or i not in nodes:
                continue
            component.add(i)
            todo.extend([nodes[i]['previous'], nodes[i]['next']])
        groups[ref] = sorted(component)
    assert len(nodes) == 11 and sorted(map(len, groups.values())) == [3, 4, 4]
    assert set().union(*(set(v) for v in groups.values())) == set(nodes)
    assert sum(len(n['buildings']) for n in nodes.values()) == 12
    for n in nodes.values():
        assert n['depth'] == 2 and n['track_type'] == 3 and not n['branches']
        assert all(b['depth'] == 2 for b in n['buildings'])
        assert n['station_id'] == (station['native_station'] if n['id'] in station['platform_nodes'] else '0')
    assert all(not nodes[i]['buildings'] for i in groups['3-4'])
    lines = {ref: MultiLineString([[xy(*p) for p in nodes[i]['curve']] for i in ids]).intersection(box(-30,-70,30,70)) for ref, ids in groups.items()}
    gaps = {a+' / '+b: lines[a].distance(lines[b]) for a, b in [('1', '3-4'), ('3-4', '2')]}
    assert min(gaps.values()) > 3.5, gaps
    fig, ax = plt.subplots(figsize=(5, 10))
    faces = []
    for ref, ids in groups.items():
        for i in ids:
            n = nodes[i]
            x, y = zip(*(xy(*p) for p in n['curve']))
            ax.plot(x, y, color={'1':'#268543', '2':'#287cbe', '3-4':'#bd8827'}[ref])
            rail_offset = xy(n['x'], n['y'])[0]
            for b in n['buildings']:
                if b['type'] not in [13, 27]:
                    continue
                dx, dy = b['direction_x'], b['direction_y']
                length = math.hypot(dx, dy)
                dx, dy = dx/length, dy/length
                corners = [xy(b['x']+(a*dx*b['width']-c*dy*b['height'])/(2*scale),
                              b['y']+(a*dy*b['width']+c*dx*b['height'])/(2*scale))
                           for a, c in [(-1,-1),(1,-1),(1,1),(-1,1)]]
                lo, hi = min(p[0] for p in corners), max(p[0] for p in corners)
                # Native canopy overhang is 1.25 m from rail centre; the face starts at 1.825 m.
                clearance = 1.5 if b['type'] == 13 else 1.2
                assert (ref == '1' and hi <= rail_offset-clearance) or (ref == '2' and lo >= rail_offset+clearance), (ref, b['id'], lo, hi)
                ax.add_patch(Polygon(corners, color='#b99362' if b['type']==13 else '#777777', alpha=.5))
                faces.append(dict(id=b['id'], track_ref=ref, type=b['type'], lateral_min=lo, lateral_max=hi))
    assert len(faces) == 8
    ax.set(aspect='equal', xlim=(-22,22), ylim=(125,-125), title=station['name']+': three rails, two side platforms',
           xlabel='Metres across station', ylabel='Metres south of centre')
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(Path(os.environ['TEMP'])/f'nyc-{filename}-audit.png', dpi=160)
    north=[station['west_primary'],station['west_secondary'],state[key+'_center_track']['north_endpoint']]
    north_connected=all(any(j!='0' and j not in nodes for j in [nodes[i]['previous'],nodes[i]['next']]) for i in north)
    result = dict(station_id=station['native_station'], node_count=len(nodes), building_count=12,
                  minimum_track_gaps_metres=gaps, outside_platform_faces=faces, depth=2,
                  center_track_has_no_platform=True, construction_pending=any(n['blueprint'] for n in nodes.values()),
                  north_connection_topology_verified=north_connected, operating_verified=False)
    Path(f'work/nyc-{filename}-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan-index',type=int,choices=[33,35,36,37,38,40,41],default=33)
    audit(parser.parse_args().plan_index)
