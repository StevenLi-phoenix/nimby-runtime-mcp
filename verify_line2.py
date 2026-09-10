"""Read-only live completion audit, including both cycles and interchanges."""
import json
from pathlib import Path

from session_call import call


def run():
    cp = Path('work/line2-built.json')
    state = json.loads(cp.read_text(encoding='utf-8'))
    assert not state['pending']
    network = call('get_track_network', seed_node_ids=[i for s in state['stations'] for i in s['platform_nodes']])
    nodes = {n['id']: n for n in network['nodes']}
    assert len(state['stations']) == 18
    assert all(n['track_type'] == 3 and not n['blueprint'] for n in nodes.values())
    for key in ['east_stop', 'west_stop']:
        start = state['stations'][0][key]
        seen, current = set(), start
        while current not in seen and current != '0':
            seen.add(current)
            current = nodes[current]['next']
        assert current == start
        assert all(s[key] in seen for s in state['stations'])
    fleet = call('list_trains')['trains']
    assert len({t['serial'] for t in fleet}) == len(fleet)
    by_id = {t['id']: t for t in fleet}
    lines = []
    for service in state['services']:
        line = call('get_line', line_id=service['id'])
        assert line['stop_count'] == 18 and line['service'] == 2
        assert line['code'] == service['code'] and line['color'] == 0xff9b5200
        key = 'east_stop' if service['code'] == 'bj-2o' else 'west_stop'
        stations = state['stations'] if key == 'east_stop' else list(reversed(state['stations']))
        assert [s['node_id'] for s in line['stops']] == [s[key] for s in stations]
        assert len(service['trains']) == 6
        for i, train in enumerate(service['trains'], 1):
            actual = by_id[train['id']]
            assert actual['serial'] == f"{service['code']}-{i:04d}"
            assert actual['cars'] == 6 and actual['capacity'] == 900
        lines.append(line)
    links = []
    for a, b in [('562949954142209', '562949955977217'), ('562949954535425', '562949956435969')]:
        sa, sb = call('get_station', station_id=a), call('get_station', station_id=b)
        assert b in sa['walk_links'] and a in sb['walk_links']
        links.append([sa, sb])
    line1 = call('get_line', line_id='1125899906842625')
    assert line1['stop_count'] == 70 and line1['code'] == 'bj-1'
    network1 = call('get_track_network', seed_node_ids=[s['node_id'] for s in line1['stops']])
    assert network1['count'] == 688
    assert all(n['track_type'] == 3 and not n['blueprint'] for n in network1['nodes'])
    assert sum(t['serial'].startswith('bj-1-') for t in fleet) == 20
    result = dict(runtime=call('runtime_status'), lines=lines, interchanges=links,
                  new_track_nodes=len(nodes), all_medium_built=True, directed_rings=2,
                  new_trains=12, total_trains=len(fleet), preserved_line1_stops=70,
                  visual_evidence=['line2-inner-running.jpg', 'line2-outer-running.jpg'],
                  visual_observation='All twelve trains shown in service with passengers; both directions moving or exchanging passengers.')
    state['completion_audit'] = result
    state['status'] = 'operating-verified'
    cp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    out = Path('C:/Users/stevenli/Documents/Codex/2026-09-10/yo/outputs')
    (out/'line2-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ['lines', 'interchanges']}, ensure_ascii=False))


if __name__ == '__main__':
    run()
