"""Refresh live nodes from checkpoint seeds without replaying old geometry or stops."""
import json
from collections import Counter
from pathlib import Path

from session_call import call


def refresh():
    checkpoint = json.loads(Path('work/line1-built.json').read_text(encoding='utf-8'))
    seeds = set()

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str) and value.isascii() and value.isdecimal():
            if int(value) >> 48 == 1:
                seeds.add(value)

    walk(checkpoint)
    line = call('get_line', line_id=checkpoint['line']['id'])
    seeds.update(s['node_id'] for s in line['stops'])
    network = call('get_track_network', seed_node_ids=sorted(seeds))
    result = {'line': line, **network}
    Path('work/live-network.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print('Nodes:', network['count'], 'types:', dict(Counter(n['track_type'] for n in network['nodes'])),
          'blueprints:', sum(n['blueprint'] for n in network['nodes']))
    return result


if __name__ == '__main__':
    refresh()
