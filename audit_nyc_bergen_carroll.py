"""Plot the saved native four-track corridor and its actual control-point layers."""
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def audit():
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    native = json.loads(Path('work/nyc-bergen-carroll-connected.json').read_bytes())
    by = {n['id']: n for n in native['nodes']}
    stations = {s['plan_index']: s for s in state['stations']}
    source = json.loads(Path('data/nyc_culver_cross_sections.json').read_bytes())['stations']
    a, b = source[0]['center'], source[1]['center']
    dx, dy = b['x']-a['x'], b['y']-a['y']
    length = math.hypot(dx, dy)
    tx, ty, scale = dx/length, dy/length, source[0]['scale']

    def xy(x, y):
        return ((-(x-a['x'])*ty+(y-a['y'])*tx)*scale,
                ((x-a['x'])*tx+(y-a['y'])*ty)*scale)

    groups = []
    for ref in ['1', '2', '3', '4']:
        if ref in ('1', '2'):
            seed = stations[13]['west_secondary' if ref == '1' else 'west_primary']
        else:
            seed = next(t['start'] for t in state['bergen_express_tracks'] if t['track_ref'] == ref)
        seen, queue = set(), [seed]
        while queue:
            node_id = queue.pop()
            if node_id == '0' or node_id in seen:
                continue
            seen.add(node_id)
            n = by[node_id]
            assert n['branch_parent'] == '0' and not n['branches']
            queue.extend([n['previous'], n['next']])
        groups.append(seen)
    assert sum(map(len, groups)) == len(set.union(*groups)) == native['count']
    blueprint_count = sum(n['blueprint'] for n in by.values())
    assert blueprint_count in (0, len(by)), 'Mixed construction state requires inspection'
    assert not [b for n in by.values() for b in n['buildings'] if b['depth'] != n['depth']]
    fig, axes = plt.subplots(1, 2, figsize=(12, 9))
    summary = []
    for ref, ids, color in zip(['B1 local', 'B2 local', 'B3 express', 'B4 express'], groups,
                              ['#008447', '#2466cc', '#e38021', '#bb3344']):
        first = True
        transitions = []
        for node_id in sorted(ids):
            n = by[node_id]
            ps = n.get('curve', [])
            if ps:
                x, y = zip(*(xy(*p) for p in ps))
                axes[0].plot(x, y, color=color, lw=1.5, label=ref if first else None)
                first = False
            x, y = xy(n['x'], n['y'])
            axes[0].scatter(x, y, s=7, c=color)
            # Draw layer changes between actual node coordinates. A node's render
            # polyline can cover half-edges, so its bounds are not depth endpoints.
            previous = by.get(n['previous'])
            if previous:
                py = xy(previous['x'], previous['y'])[1]
                axes[1].plot([previous['depth'], n['depth']], [py, y], color=color, lw=1.5)
                if previous['depth'] != n['depth']:
                    transitions.append(dict(from_node=previous['id'], to_node=n['id'],
                                            from_depth=previous['depth'], to_depth=n['depth'],
                                            horizontal_metres=math.hypot(n['x']-previous['x'], n['y']-previous['y'])*scale))
        summary.append(dict(track=ref, node_count=len(ids), depth_transitions=transitions))
    for ax in axes:
        ax.grid(alpha=.2)
        ax.invert_yaxis()
        ax.axhline(0, color='gray', ls=':')
        ax.axhline(length*scale, color='gray', ls=':')
        ax.set_ylabel('Metres south of Bergen center')
    axes[0].set_xlabel('Lateral metres from center-to-center axis')
    axes[0].legend()
    axes[1].set_xlabel('Native layer (between actual control points)')
    axes[1].set_xlim(-2.3, -.7)
    phase = 'blueprint' if blueprint_count else 'built'
    fig.suptitle(f'Bergen to Carroll — four native {phase} paths / layer transitions')
    fig.tight_layout()
    output = Path(os.environ['TEMP'])/'nyc-bergen-carroll-four-tracks.png'
    fig.savefig(output, dpi=130)
    evidence = dict(tracks=summary, nodes=native['count'], blueprint_nodes=blueprint_count, buildings=sum(len(n['buildings']) for n in by.values()),
                    scope='Saved native geometry; visual curve review and build checks required separately.')
    Path('work/nyc-bergen-carroll-geometry-audit.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(output=str(output), **evidence)))


if __name__ == '__main__':
    audit()
