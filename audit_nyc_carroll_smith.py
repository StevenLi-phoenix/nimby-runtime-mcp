"""Audit native four-track curves, clearances, buildings and existing controls."""
import json
import argparse
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import MultiLineString


def audit(section='carroll_smith'):
    assert section in ('carroll_smith', 'smith_fourth', 'fourth_seventh', 'seventh_fifteenth', 'hamilton', 'church')
    file_section = section.replace('_', '-')
    target_index = {'carroll_smith':15, 'smith_fourth':16, 'fourth_seventh':17, 'seventh_fifteenth':18, 'hamilton':19, 'church':20}[section]
    target_key = {15:'smith',16:'fourth',17:'seventh',18:'fifteenth',19:'hamilton',20:'church'}[target_index]
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    old = json.loads(Path(f'work/nyc-{file_section}-live.json').read_bytes())
    now = json.loads(Path(f'work/nyc-{file_section}-connected.json').read_bytes())
    before = {n['id']: n for n in old['nodes']}
    nodes = {n['id']: n for n in now['nodes']}
    smith = next(s for s in state['stations'] if s['plan_index'] == target_index)
    groups, changes, clearances = {}, [], []
    for node_id, node in before.items():
        other = nodes[node_id]
        if not node['blueprint']:
            for key in ['depth', 'track_type', 'station_id', 'blueprint', 'buildings', 'building_tapes', 'branch_parent', 'branches']:
                assert node[key] == other[key], (node_id, key)
            if node != other:
                changes.append(dict(id=node_id, fields=[k for k in node if node[k] != other[k]],
                                    moved_metres=math.hypot(node['x']-other['x'], node['y']-other['y'])
                                    / math.cosh(node['y']/6378137)))
        if node['station_id'] != '0':
            assert node['x'] == other['x'] and node['y'] == other['y']
    for n in nodes.values():
        assert all(b['depth'] == n['depth'] for b in n['buildings'])
    for c in state[section+'_corridors']:
        ref = c['track_ref']
        ids = set(c['nodes']+[c['start_node_id']])
        if ref in ['1', '2']:
            seed = smith['west_secondary' if ref == '1' else 'west_primary']
            queue, station_ids = [seed], set(smith['nodes'])
            while queue:
                node_id = queue.pop()
                if node_id not in station_ids or node_id in ids:
                    continue
                ids.add(node_id)
                queue.extend([nodes[node_id]['previous'], nodes[node_id]['next']])
        else:
            if target_index in (17,20):
                ids.update(state[target_key+'_tracks'][ref]['nodes'])
            else:
                ids.update(next(t['nodes'] for t in state[target_key+'_express_tracks'] if t['track_ref'] == ref))
        groups[ref] = ids
    assert len(set.union(*groups.values())) == sum(map(len, groups.values()))
    scale = 1/math.cosh(nodes[smith['west_primary']]['y']/6378137)
    origin = {15:(-8237200,4964400),16:(-8236500,4963830),17:(-8235425,4963225),18:(-8235365,4962350),19:(-8234950,4961025),20:(-8235380,4959973)}[target_index]
    def xy(x, y):
        return (x-origin[0])*scale, (y-origin[1])*scale
    lines = {ref: MultiLineString([[xy(*p) for p in nodes[i]['curve']] for i in ids if nodes[i].get('curve')])
             for ref, ids in groups.items()}
    pairs=[('1','2'),('3','4')] if target_index in (19,20) else ([('1', '3'), ('3', '4'), ('4', '2')] if '3' in lines else [('1','2')])
    for a, b in pairs:
        clearances.append(dict(tracks=[a, b], minimum_metres=lines[a].distance(lines[b])))
    if target_index == 20:
        upper = {}
        for ref, ids in groups.items():
            segments = []
            for node_id in ids:
                n = nodes[node_id]
                curve = n.get('curve', [])
                if not curve or n['depth'] != -2:
                    continue
                center = min(range(len(curve)), key=lambda i: math.hypot(curve[i][0]-n['x'], curve[i][1]-n['y']))
                for half, neighbor in [(curve[:center+1], n['previous']), (curve[center:], n['next'])]:
                    if len(half)>1 and neighbor in nodes and nodes[neighbor]['depth']==-2:
                        segments.append([xy(*p) for p in half])
            upper[ref] = MultiLineString(segments)
        for a,b in [('1','3'),('4','2')]:
            clearances.append(dict(tracks=[a,b], depth=-2, minimum_metres=upper[a].distance(upper[b])))
    fig, axes = plt.subplots(1, 3, figsize=(16, 9))
    for ref, color in [('1', 'green'), ('2', 'blue'), ('3', 'orange'), ('4', 'red')]:
        if ref not in groups:
            continue
        first = True
        for node_id in groups[ref]:
            n = nodes[node_id]
            curve = n.get('curve', [])
            if curve:
                xs, ys = zip(*(xy(*p) for p in curve))
                for ax in axes[:2]:
                    ax.plot(xs, ys, c=color, lw=1.3, label=ref if first else None)
                first = False
            x, y = xy(n['x'], n['y'])
            for ax in axes[:2]:
                ax.scatter(x, y, s=7, c=color)
        c = next(c for c in state[section+'_corridors'] if c['track_ref'] == ref)
        points = [nodes[i] for i in [c['start_node_id']]+c['nodes']+[c['end_node_id']]]
        chain = [0.0]
        for a, b in zip(points, points[1:]):
            chain.append(chain[-1]+math.hypot(a['x']-b['x'], a['y']-b['y'])*scale)
        axes[2].plot(chain, [p['depth'] for p in points], '.-', c=color, label=ref)
    axes[0].set(aspect='equal', title='Native corridor tracks')
    crossovers = state.get('fourth_crossovers', []) if target_index == 16 else []
    for cross in crossovers:
        pair = [nodes[i] for i in cross['native_node_ids']]
        assert len(pair) == 2 and all(n['depth'] == 2 for n in pair)
        assert {n['branch_parent'] for n in pair} == {e['edge_id'] for e in cross['endpoints']}
        assert pair[0]['next'] == pair[1]['id'] or pair[0]['previous'] == pair[1]['id']
        for n in pair:
            endpoint = next(e for e in cross['endpoints'] if e['edge_id'] == n['branch_parent'])
            assert math.hypot(n['x']-endpoint['x'], n['y']-endpoint['y']) < .1
            xs, ys = zip(*(xy(*p) for p in n['curve']))
            for ax in axes[:2]:
                ax.plot(xs, ys, c='#84552b', lw=1.2)
                ax.scatter(*xy(n['x'], n['y']), c='#84552b', s=10)
    axes[1].set(aspect='equal', xlim=(-225, 105) if target_index == 16 else (-120, 105),
                ylim=(-150, 150) if target_index == 16 else (-150, 70),
                title=smith['name']+' and north approach')
    axes[2].set(title='Actual control layers', xlabel='Metres from previous station endpoint')
    for ax in axes:
        ax.grid(alpha=.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig(Path(os.environ['TEMP'])/f'nyc-{file_section}-native.png', dpi=160)
    result = dict(count=now['count'], blueprint_nodes=sum(n['blueprint'] for n in nodes.values()),
                  group_counts={ref: len(ids) for ref, ids in groups.items()}, clearances=clearances,
                  existing_changes=changes, station_positions_unchanged=True, building_depth_mismatches=[],
                  crossovers_verified=len(crossovers))
    Path(f'work/nyc-{file_section}-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--section', choices=['carroll_smith', 'smith_fourth', 'fourth_seventh', 'seventh_fifteenth', 'hamilton', 'church'], default='carroll_smith')
    audit(parser.parse_args().section)
