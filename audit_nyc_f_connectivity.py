"""Read-only F station inventory and undirected physical connectivity audit.

This does not prove directional routing, reversal, or operational readiness.
"""
import json
from collections import deque
from pathlib import Path
from session_call import _call


def audit():
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    g = json.loads(Path('work/nyc-g-built.json').read_bytes())
    plan = json.loads(Path('data/nyc_f_plan.json').read_bytes())['directions']['to_coney_island']['stations']
    seed = json.loads(Path('work/nyc-179-169-connected.json').read_bytes())
    live = _call('get_track_network', dict(seed_node_ids=[n['id'] for n in seed['nodes']], detail='geometry'))
    nodes = {n['id']: n for n in live['nodes']}
    keys = ['179', '169', 'parsons', 'sutphin', 'briarwood', 'kew_gardens',
            'seventy_fifth', 'forest_hills', 'jackson', 'queens_plaza', 'court23',
            'lexington53', 'fifth_53rd', 'rockefeller', 'bryant', 'herald',
            'twentythird', 'fourteenth', 'west_fourth', 'broadway_lafayette',
            'second_avenue', 'delancey', 'east_broadway', 'york', 'jay']
    station_ids = [state[k + '_station_id'] for k in keys]
    station_ids += [s['native_station'] for s in sorted(g['stations'], key=lambda s: s['plan_index']) if 13 <= s['plan_index'] <= 20]
    station_ids += [s['native_station'] for s in sorted(state['stations'], key=lambda s: s['plan_index'])]
    station_ids += [state['coney_station_id']]
    assert len(station_ids) == len(plan) == 45
    graph = {i: set() for i, n in nodes.items() if not n['blueprint']}
    for i in graph:
        n = nodes[i]
        for j in [n['previous'], n['next'], n['branch_parent']] + n['branches']:
            if j in graph and j != i:
                graph[i].add(j)
                graph[j].add(i)
    rows = []
    for index, sid in enumerate(station_ids):
        platforms = [i for i, n in nodes.items() if n['station_id'] == sid and not n['blueprint']]
        assert platforms, (index, sid)
        rows.append(dict(index=index, station_id=sid, source_name=plan[index].get('name'), built_platform_nodes=platforms))
    links = []
    for a, b in zip(rows, rows[1:]):
        queue = deque(a['built_platform_nodes'])
        prev = {i: None for i in queue}
        targets = set(b['built_platform_nodes'])
        found = None
        while queue:
            i = queue.popleft()
            if i in targets:
                found = i
                break
            for j in graph[i]:
                if j not in prev:
                    prev[j] = i
                    queue.append(j)
        path = []
        while found is not None:
            path.append(found)
            found = prev[found]
        links.append(dict(from_index=a['index'], to_index=b['index'], physically_connected=bool(path), undirected_path=list(reversed(path))))
    result = dict(stations=rows, adjacent_links=links, missing_links=[r for r in links if not r['physically_connected']],
                  live_node_count=len(nodes), scope='Undirected built-track connectivity only; may use other shared lines or wrong-direction tracks.',
                  operations_proven=False, pending=['Validate intended directional platform paths, not just station components.', 'Complete terminal reversal and live train service.'])
    Path('work/nyc-f-connectivity-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(stations=len(rows), adjacent_pairs=len(links), missing_links=result['missing_links'], operations_proven=False)))


if __name__ == '__main__':
    audit()
