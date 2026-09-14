"""Audit saved live merge geometry against the pre-connection native snapshot."""
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def audit():
    def read(name):
        return json.loads(Path('work', name).read_bytes())
    old = read('nyc-hoyt-bergen-live.json')
    now = read('nyc-hoyt-bergen-current.json')
    saved = read('nyc-hoyt-bergen-connected.json')
    before = {n['id']: n for n in old['nodes']}
    current = {n['id']: n for n in now['nodes']}
    assert current == {n['id']: n for n in saved['nodes']}
    changes = []
    for node_id, node in before.items():
        other = current[node_id]
        fields = [k for k, v in node.items() if v != other.get(k)]
        if fields:
            changes.append(dict(id=node_id, changed_fields=fields,
                                moved_metres=math.hypot(node['x']-other['x'], node['y']-other['y'])
                                / math.cosh(node['y']/6378137)))
        for key in ['depth', 'track_type', 'station_id', 'blueprint', 'buildings',
                    'building_tapes', 'branch_parent', 'branch_position',
                    'structure_parent', 'parallel_offset_metres']:
            assert node[key] == other[key], (node_id, key)
        if node['station_id'] != '0':
            assert (node['x'], node['y']) == (other['x'], other['y'])
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    for ax, (cx, cy, radius) in zip(axes, [(-8236200, 4966620, 120), (-8236548, 4966310, 85)]):
        for net, color, label in [(old, '#bbbbbb', 'Before'), (now, '#087f8c', 'Current')]:
            first = True
            for node in net['nodes']:
                if abs(node['x']-cx) > radius*3 or abs(node['y']-cy) > radius*3:
                    continue
                curve = node.get('curve', [])
                if curve:
                    ax.plot([p[0]-cx for p in curve], [p[1]-cy for p in curve],
                            color=color, lw=1.4, label=label if first else None)
                    first = False
                if node['branch_parent'] != '0':
                    ax.scatter(node['x']-cx, node['y']-cy, c=color, s=20)
        ax.set(xlim=(-radius, radius), ylim=(-radius, radius), aspect='equal')
        ax.legend()
        ax.grid(alpha=.2)
    axes[0].set_title('Hoyt crossover: native parent-curve recalculation')
    axes[1].set_title('Bergen: G merge into F local tracks')
    fig.tight_layout()
    fig.savefig(Path(os.environ['TEMP'])/'nyc-hoyt-preservation.png', dpi=160)
    result = dict(changes=changes, station_positions_unchanged=True,
                  buildings_signals_layers_types_unchanged=True, live_matches_saved_connected=True)
    Path('work/nyc-hoyt-bergen-preservation-audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    audit()
