"""Sequential live MCP fare trials. No save rewinds or balance modifications."""
import json
import time
from pathlib import Path

from session_call import call

LINE = '1125899906842625'
RESULTS = Path('work/fare-trials-daily.json')


def wait_game(seconds, label):
    start = call('runtime_status')
    target = start['simulation_time'] + seconds
    last_report = time.monotonic()
    deadline = last_report + max(900, seconds / 10)
    current_speed = min(10000, max(1, seconds // 3))
    call('set_simulation_speed', speed=current_speed)
    while True:
        time.sleep(0.1)
        state = call('runtime_status')
        if state['cash'] < 15_000_000:
            raise RuntimeError('Trial cash reserve reached; stopped before further spending')
        if state['simulation_time'] >= target:
            call('set_simulation_speed', speed=0)
            return call('runtime_status')
        remaining = target - state['simulation_time']
        desired_speed = min(10000, max(1, remaining // 3))
        if desired_speed != current_speed and (desired_speed == 1 or desired_speed < current_speed * 0.9):
            call('set_simulation_speed', speed=desired_speed)
            current_speed = desired_speed
        if time.monotonic() > deadline:
            raise TimeoutError('Simulation did not advance within trial deadline')
        if time.monotonic() - last_report >= 30:
            print(label, 'game seconds', state['simulation_time']-start['simulation_time'],
                  'cash', round(state['cash']), flush=True)
            last_report = time.monotonic()


def run(cases, matched_phase=None):
    rows = []
    if RESULTS.exists():
        rows = json.loads(RESULTS.read_text(encoding='utf-8'))
    try:
        call('set_simulation_speed', speed=0)
        line = call('get_line', line_id=LINE)
        for base, per_km in cases:
            call('set_line_name', line_id=LINE, name=line['name'], code='bj-1',
                 base_fare=base, fare_per_km=per_km)
            print('TRIAL', base, per_km, flush=True)
            # Each window covers a full 24 hours, after one round trip of
            # warmup. This covers both peaks without a whole idle day between trials.
            warmup_seconds = 10800
            if matched_phase is not None:
                now = call('runtime_status')['simulation_time']
                target = ((now + 10800 - matched_phase) // 604800 + 1) * 604800 + matched_phase
                warmup_seconds = target-now
            start = wait_game(warmup_seconds, f'{base}+{per_km} warmup')
            fleet_before = sorted(t['id'] for t in call('list_trains')['trains']
                                  if t['serial'].startswith('bj-1-'))
            Path('work/fare-daily-current.json').write_text(json.dumps({
                'base_fare': base, 'fare_per_km': per_km, 'start': start,
                'target_simulation_time': start['simulation_time'] + 86400,
            }, indent=2), encoding='utf-8')
            end = wait_game(86400, f'{base}+{per_km} full day')
            fleet_after = sorted(t['id'] for t in call('list_trains')['trains']
                                 if t['serial'].startswith('bj-1-'))
            final_line = call('get_line', line_id=LINE)
            row = {'base_fare': base, 'fare_per_km': per_km,
                   'start': start, 'end': end,
                   'net_profit': end['cash']-start['cash'],
                   'profit_per_game_hour': (end['cash']-start['cash'])*3600/
                   (end['simulation_time']-start['simulation_time']),
                   'fleet_size': len(fleet_before),
                   'matched_week_phase': matched_phase,
                   'measurement_seconds': end['simulation_time']-start['simulation_time'],
                   'valid_full_day': abs(end['simulation_time']-start['simulation_time']-86400) <= 10
                       and fleet_before == fleet_after and final_line['stops'] == line['stops']
                       and final_line['base_fare'] == base and final_line['fare_per_km'] == per_km,
                   'caveat': ('Matched weekday and start time; unchanged fleet. Stochastic demand remains; not a global optimum.'
                              if matched_phase is not None else
                              'Full 24-hour windows with unchanged fleet. Different weekdays and demand; not a global optimum.')}
            rows.append(row)
            RESULTS.write_text(json.dumps(rows, indent=2), encoding='utf-8')
            print('RESULT', json.dumps(row), flush=True)
    finally:
        call('set_simulation_speed', speed=0)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', nargs='?', default='[[50,10],[100,10],[100,5]]')
    parser.add_argument('--matched-phase', type=int)
    args = parser.parse_args()
    run(json.loads(args.cases), args.matched_phase)
