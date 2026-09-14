"""Verify native relay geometry, branch parents, and reversal clearance."""
import json
import math
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import LineString
from shapely.ops import unary_union


def audit():
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    plan = json.loads(Path('data/nyc_coney_relays.json').read_bytes())
    nodes = {n['id']: n for n in json.loads(Path('work/nyc-coney-relays-live.json').read_bytes())['nodes']}
    before = {n['id']: n for n in state['coney_relay_before']['nodes']}
    leads = {p['id'] for p in state['coney_relay_lead_targets']}
    assert all(nodes[i] == n for i, n in before.items() if i not in leads)
    selected = set(leads)
    scale = plan['scale']
    fig, ax = plt.subplots(figsize=(7, 10))
    results = []
    for relay, color in zip(state['coney_relays'], ['#287bbb', '#be812b']):
        track_lines = []
        for track in relay['tracks']:
            ids = [track['start']] + track['nodes']
            selected.update(ids)
            assert [nodes[i]['depth'] for i in ids] == [2, 3, 3, 3, 3]
            for a, b in zip(ids, ids[1:]):
                assert b in [nodes[a]['previous'], nodes[a]['next']]
            assert '0' in [nodes[ids[-1]]['previous'], nodes[ids[-1]]['next']]
            line = unary_union([LineString(nodes[i]['curve']) for i in ids if len(nodes[i]['curve']) > 1])
            track_lines.append(line)
            for i in ids:
                n = nodes[i]
                assert n['station_id'] == '0' and not n['buildings'] and n['track_type'] == 3
                if n['curve']:
                    ax.plot([(p[0]+8235600)*scale for p in n['curve']],
                            [(p[1]-4950300)*scale for p in n['curve']], color=color)
        crossover = relay['crossovers'][0]
        a, b = [nodes[i] for i in crossover['nodes']]
        assert b['id'] in [a['previous'], a['next']]
        clearance = []
        for node, side, role in [(a, 'start', 'west_secondary'), (b, 'end', 'west_primary')]:
            candidate = crossover['candidate'][side]
            assert node['branch_parent'] == candidate['edge_id'] and node['depth'] == 3
            assert node['id'] in nodes[node['branch_parent']]['branches']
            track = next(t for t in relay['tracks'] if t['role'] == role)
            end = nodes[track['frontier']]
            clearance.append(math.hypot(end['x']-node['x'], end['y']-node['y'])*scale)
            selected.add(node['id'])
            ax.plot([(p[0]+8235600)*scale for p in node['curve']],
                    [(p[1]-4950300)*scale for p in node['curve']], color=color)
        assert min(clearance) > 150
        gap = track_lines[0].distance(track_lines[1])*scale
        assert gap > 10
        results.append(dict(service=relay['service'], clearance_metres=clearance, track_gap_metres=gap))
    assert set(nodes)-set(before) == selected-leads
    ax.set(aspect='equal', title='Coney Island F/Q station-after relays')
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(Path(os.environ['TEMP'])/'nyc-coney-relays-audit.png', dpi=140)
    result = dict(relays=results, selected_nodes=sorted(selected), unchanged_nodes=len(before)-len(leads),
                  construction_pending=any(nodes[i]['blueprint'] for i in selected),
                  operating_reversal_verification_pending=True)
    Path('work/nyc-coney-relays-audit.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    audit()
