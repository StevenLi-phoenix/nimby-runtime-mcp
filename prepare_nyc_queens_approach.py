"""Coordinate four Queens Plaza approach curves against the live straight platforms.

This produces candidates only. The two local approaches reserve geometry for
later construction; source crossovers must be reattached and audited separately.
"""
import json
import math
from pathlib import Path

from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_queens_express import prepare


def unit(a, b):
    length = distance(a, b)
    return {k: (b[k] - a[k]) / length for k in ('x', 'y')}


def at(route, chain, position):
    i = next(i for i in range(len(chain)-1) if chain[i] <= position <= chain[i+1])
    f = (position-chain[i])/(chain[i+1]-chain[i])
    return {k: route[i][k]+f*(route[i+1][k]-route[i][k]) for k in ('x', 'y')}, unit(route[i], route[i+1])


def bezier(control, t):
    a, b, c, d = control
    return dict(**{k: (1-t)**3*a[k]+3*(1-t)**2*t*b[k]+3*(1-t)*t*t*c[k]+t**3*d[k] for k in ('x', 'y')},
                **{'d'+k: 3*((1-t)**2*(b[k]-a[k])+2*(1-t)*t*(c[k]-b[k])+t*t*(d[k]-c[k])) for k in ('x', 'y')})


def main():
    plan = prepare()
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    nodes = {n['id']: n for n in json.loads(Path('work/nyc-queens-express-live.json').read_bytes())['nodes']}
    source = json.loads(Path(plan['source']).read_bytes())
    ways = [dict(w, tags=dict(w['tags'], name='IND Culver Line')) for w in source['ways'] if w['tags'].get('name') == 'IND Queens Boulevard Line']
    endpoints = {'1': state['queens_plaza_islands'][0]['west_secondary'],
                 '3': state['queens_plaza_islands'][0]['west_primary'],
                 '4': state['queens_plaza_islands'][1]['west_secondary'],
                 '2': state['queens_plaza_islands'][1]['west_primary']}
    approaches = []
    anchor = None
    for ref in ['3', '4', '1', '2']:
        corridor = next((c for c in plan['corridors'] if c['track_ref'] == ref), None)
        end = nodes[endpoints[ref]]
        start = nodes[corridor['start_node_id']] if corridor else anchor
        route, route_ways, gaps = route_between(ways, ref, start, end)
        chain = [0.0]
        for a, b in zip(route, route[1:]):
            chain.append(chain[-1]+distance(a, b)*plan['scale'])
        cut = chain[-1]-250 if corridor else 0
        a, direction = at(route, chain, cut)
        if ref == '3':
            anchor = a
        platform = nodes[end['previous'] if end['previous'] != '0' else end['next']]
        incoming = unit(end, platform)
        handle = distance(a, end)/3
        control = [a, {k: a[k]+handle*direction[k] for k in ('x', 'y')},
                   {k: end[k]-handle*incoming[k] for k in ('x', 'y')}, {k: end[k] for k in ('x', 'y')}]
        samples = [dict(bezier(control, i/64), depth=-2) for i in range(65)]
        approaches.append(dict(track_ref=ref, end_node_id=end['id'], control=control, samples=samples,
                               source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in route_ways)),
                               stage='candidate' if corridor else 'reserved_local_approach_not_built'))
        if corridor:
            points = [p for p in corridor['points'] if p['metres'] < cut-20]
            points += [dict(bezier(control, t), depth=-2, metres=cut+t*(chain[-1]-cut), reason='coordinated_station_approach') for t in [0, .25, .5, .75, 1]]
            # Retain a flat -2 plateau after Jackson, then descend over 100 m.
            # Delay the western ascent until beyond the D2 source crossing.
            boundaries = [i for i in range(1, len(route_ways)) if route_ways[i]['tags'].get('level', route_ways[i]['tags'].get('layer')) != route_ways[i-1]['tags'].get('level', route_ways[i-1]['tags'].get('layer'))]
            transitions = [(chain[i], max(-3, int(route_ways[i]['tags'].get('level', route_ways[i]['tags'].get('layer', -1))))) for i in boundaries]
            down = next(d for d, depth in transitions if depth == -3)
            up = next(d for d, depth in transitions if depth == -2 and d > down)
            for d, depth in [(down-100, -2), (up+100, -2)]:
                q, _ = at(route, chain, d)
                points.append(dict(q, metres=d, depth=depth, reason='flat_plateau_and_100m_ramp'))
            for q in points:
                if down <= q['metres'] <= up:
                    q['depth'] = -3
            corridor.update(points=sorted(points, key=lambda q: q['metres']), approach_control=control)
    plan['coordinated_approaches'] = approaches
    plan['adaptation'] = 'Four coordinated cubic station approaches; local tracks are reserved candidates only. Jackson -2 plateau and delayed western ascent retained.'
    plan['pending'] = ['Inspect native express curves and grade crossings.', 'Adapt source crossovers to the coordinated local approaches before adding them.']
    Path('data/nyc_queens_express_corridors.json').write_text(json.dumps(plan, indent=2)+'\n')
    print(json.dumps([dict(ref=c['track_ref'], points=len(c['points'])) for c in plan['corridors']]))


if __name__ == '__main__':
    main()
