"""Create both ring services after verified normal-money construction."""
import json
from pathlib import Path

from session_call import call


def run():
    p = Path('work/line2-built.json')
    s = json.loads(p.read_text(encoding='utf-8'))
    assert s.get('build', {}).get('verified')
    assert not s.get('pending')
    assert 'services' not in s, 'Inspect current services before resuming; do not duplicate'
    s['services'] = []

    def save():
        p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')

    def mutate(tool, **args):
        s['pending'] = dict(tool=tool, arguments=args)
        save()
        result = call(tool, **args)
        s['commands'].append(dict(**s['pending'], result=result))
        s['pending'] = None
        save()
        return result

    # Same oriented platform conventions already validated on Line 1.
    for label, code, stations, key in [('外环', 'bj-2o', s['stations'], 'east_stop'),
                                        ('内环', 'bj-2i', list(reversed(s['stations'])), 'west_stop')]:
        line = mutate('create_line')['line']
        record = dict(id=line['id'], code=code, direction=label)
        s['services'].append(record)
        save()
        mutate('set_line_name', line_id=line['id'], name='北京地铁2号线'+label, code=code,
               base_fare=25, fare_per_km=10, color='#00529B')
        for station in stations:
            mutate('add_line_stop', line_id=line['id'], platform_node_id=station[key])
        record['trains'] = mutate('purchase_six_car_trains', line_id=line['id'], count=6)['trains']
        save()
        mutate('set_line_service', line_id=line['id'], service=2, reference_train_id=record['trains'][0]['id'])
        record['line'] = call('get_line', line_id=line['id'])
        assert record['line']['stop_count'] == 18
        save()
        print(code, '18 stops, 6 trains', flush=True)
    s['status'] = 'built-awaiting-operation-and-transfer-validation'
    save()


if __name__ == '__main__':
    run()
