"""Coordinate all four Kew Gardens approaches with the straight native station."""
import json
from pathlib import Path
from prepare_nyc_kew_75 import prepare
from prepare_nyc_carroll_smith import route_between, distance
from prepare_nyc_queens_approach import at, unit, bezier


def main():
    plan = prepare()
    ns = {n['id']: n for n in json.loads(Path('work/nyc-kew-75-live.json').read_bytes())['nodes']}
    source = json.loads(Path(plan['source']).read_bytes())
    eligible = [dict(w, tags=dict(w['tags'], name='IND Culver Line')) for w in source['ways'] if w['tags'].get('name') == 'IND Queens Boulevard Line' and w['tags'].get('service') != 'yard']
    for c in plan['corridors']:
        start, end = ns[c['start_node_id']], ns[c['end_node_id']]
        route, ways, gaps = route_between(eligible, c['track_ref'], start, end)
        chain = [0.0]
        for a, b in zip(route, route[1:]):
            chain.append(chain[-1]+distance(a, b)*plan['scale'])
        anchor, tangent = at(route, chain, 150)
        platform = ns[start['previous'] if start['previous'] != '0' else start['next']]
        outgoing = unit(platform, start)
        handle = distance(start, anchor)/3
        control = [{k: start[k] for k in ['x', 'y']},
                   {k: start[k]+handle*outgoing[k] for k in ['x', 'y']},
                   {k: anchor[k]-handle*tangent[k] for k in ['x', 'y']}, anchor]
        if c['track_ref'] == '4':
            direction = unit(start, anchor)
            for q in control[1:3]:
                q['x'] -= direction['y']*.4/plan['scale']
                q['y'] += direction['x']*.4/plan['scale']
            c['spacing_adaptation'] = 'D4 interior Bezier handles offset outward 0.4m; endpoints retained.'
        c['approach_control'] = control
        c['approach_samples'] = [bezier(control, i/64) for i in range(65)]
        c['points'] = [dict(bezier(control, t), metres=150*t, depth=-2, reason='coordinated_kew_approach') for t in [0, .25, .5, .75, 1]] + [q for q in c['points'] if q['metres'] > 180]
    plan['stage'] = 'coordinated_approach_candidate_native_audit_pending'
    plan['pending'] = ['Audit all four native approach curves and source junctions before construction.', 'Keep yard access unbuilt.']
    Path('data/nyc_kew_75_corridors.json').write_text(json.dumps(plan, indent=2)+'\n')
    print(json.dumps([dict(ref=c['track_ref'], points=len(c['points'])) for c in plan['corridors']]))


if __name__ == '__main__':
    main()
