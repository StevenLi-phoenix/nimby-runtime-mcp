"""Configure current built Line 8 with station-after terminal reversals and a pilot train."""
import json
from pathlib import Path

from session_call import call

CHECKPOINT = Path('work/line8-operation.json')


def run():
    stations = json.loads(Path('work/line8-built.json').read_text(encoding='utf-8'))['stations']
    state = json.loads(CHECKPOINT.read_text(encoding='utf-8')) if CHECKPOINT.exists() else {
        'commands': [], 'pending': None, 'line_id': None, 'named': False, 'fleet': [], 'opened': False}
    assert state['pending'] is None, 'Inspect uncertain native operation; never replay'
    assert call('runtime_status')['speed'] == 0
    network = call('get_track_network', seed_node_ids=[s['west_stop'] for s in stations])
    assert len(network['nodes']) == 736 and all(not n['blueprint'] for n in network['nodes'])
    byid = {n['id']:n for n in network['nodes']}
    assert all(byid[n]['station_id']==s['native_station'] for s in stations for n in s['platform_nodes'])
    stops = [dict(name=s['name'], node=s['east_stop']) for s in stations]
    stops += [dict(name=s['name'], node=s['west_stop']) for s in reversed(stations)]
    assert len(stops) == 70

    def save():
        tmp = CHECKPOINT.with_suffix('.tmp')
        tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(CHECKPOINT)

    def mutate(tool, **args):
        state['pending'] = dict(tool=tool,arguments=args)
        save()
        result = call(tool,**args)
        state['commands'].append(dict(**state['pending'],result=result))
        return result

    def finish():
        state['pending'] = None
        save()

    if not state['line_id']:
        result = mutate('create_line')
        state['line_id'] = result['line']['id']
        finish()
    line_id = state['line_id']
    if not state['named']:
        mutate('set_line_name',line_id=line_id,name='北京地铁8号线',code='bj-8',color='#00997A',base_fare=25,fare_per_km=5)
        state['named'] = True
        finish()
    line = call('get_line',line_id=line_id)
    assert [s['node_id'] for s in line['stops']] == [s['node'] for s in stops[:line['stop_count']]]
    for index in range(line['stop_count'],len(stops)):
        result = mutate('add_line_stop',line_id=line_id,platform_node_id=stops[index]['node'])
        state['last_stop_result'] = result
        finish()
        print(f'Stop {index+1}/70 configured',flush=True)
    state['line'] = call('get_line',line_id=line_id)
    assert [s['node_id'] for s in state['line']['stops']] == [s['node'] for s in stops]
    state['expected_stops'] = stops
    save()
    if not state['fleet']:
        result = mutate('purchase_six_car_trains',line_id=line_id,count=1)
        state['fleet'] = result['trains']
        finish()
    if not state['opened']:
        mutate('set_line_service',line_id=line_id,service=2,reference_train_id=state['fleet'][0]['id'])
        state['opened'] = True
        finish()
    state['line'] = call('get_line',line_id=line_id)
    state['status'] = 'pilot-configured-awaiting-native-path-and-running-verification'
    save()
    print(json.dumps(dict(line_id=line_id,train_id=state['fleet'][0]['id'],stops=70)))


if __name__ == '__main__':
    run()
