"""Plan the local approach from 15th Street and express bypass from 7th Avenue."""
import json
from pathlib import Path

from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import offset, simplify


def align_local_controls(corridors, routes, scale):
    """Keep corresponding curve controls when independent simplification drops one."""
    def project(point, route):
        choices, chain = [], 0.0
        for a, b in zip(route, route[1:]):
            gap, fraction = offset(point, a, b)
            length = distance(a, b)
            choices.append((gap, chain+fraction*length,
                            {k: a[k]+fraction*(b[k]-a[k]) for k in ['x', 'y']}))
            chain += length
        return min(choices, key=lambda item: item[0])

    locals_by_ref = {c['track_ref']: c for c in corridors if c['track_ref'] in ['1', '2']}
    original = {ref: list(c['points']) for ref, c in locals_by_ref.items()}
    for ref, other in [('1', '2'), ('2', '1')]:
        route = routes[ref]
        points = list(original[ref])
        for point in original[other][1:-1]:
            gap, chain, projected = project(point, route)
            assert gap*scale < 10, (ref, gap*scale)
            if min(abs(project(p, route)[1]-chain)*scale for p in points) > 25:
                points.append(dict(**projected, depth=-2, reason='paired_source_curve'))
        locals_by_ref[ref]['points'] = sorted(points, key=lambda p: project(p, route)[1])


def prepare():
    state=json.loads(Path('work/nyc-g-built.json').read_bytes())
    sources=json.loads(Path('data/nyc_culver_cross_sections.json').read_bytes())['stations']
    ways={w['osm_way_id']:w for s in sources for w in s['source_rails']}
    nodes={n['id']:n for n in json.loads(Path('work/nyc-hamilton-live.json').read_bytes())['nodes']}
    stations={s['plan_index']:s for s in state['stations']}
    express={t['track_ref']:t for t in state['hamilton_express_tracks']}
    ends={'1':(stations[18]['east_secondary'],stations[19]['west_secondary']),
          '2':(stations[18]['east_primary'],stations[19]['west_primary']),
          '3':(state['seventh_tracks']['3']['south_endpoint'],express['3']['start']),
          '4':(state['seventh_tracks']['4']['south_endpoint'],express['4']['frontier'])}
    scale=sources[6]['scale'];corridors=[];routes={}
    for ref,(start_id,end_id) in ends.items():
        depth=-2 if ref in ['1','2'] else -3
        start,end=nodes[start_id],nodes[end_id]
        assert start['depth']==end['depth']==depth
        route,route_ways,gaps=route_between(list(ways.values()),ref,start,end)
        routes[ref]=route
        chain=[0.0]
        for a,b in zip(route,route[1:]):chain.append(chain[-1]+distance(a,b)*scale)
        assert all(int(w['tags'].get('level',w['tags'].get('layer',depth)))==depth for w in route_ways)
        points=[dict(x=start['x'],y=start['y'],depth=depth,reason='native_endpoint')]
        points += [dict(**p,depth=depth,reason='source_curve') for p,d in zip(route,chain) if 25<d<chain[-1]-25]
        points.append(dict(x=end['x'],y=end['y'],depth=depth,reason='native_endpoint'))
        corridors.append(dict(track_ref=ref,start_node_id=start_id,end_node_id=end_id,
                              from_station='15th Street–Prospect Park' if ref in ['1','2'] else '7th Avenue',
                              source_length_metres=chain[-1],source_projection_gaps_world_metres=gaps,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in route_ways)),
                              points=simplify(points,tolerance=5),stage='candidate_native_curves_pending'))
    align_local_controls(corridors, routes, scale)
    return dict(to_station='Fort Hamilton Parkway',corridors=corridors,
                adaptations=['Local tracks remain at -2, express bypass at -3.',
                             'Express tracks bypass 15th Street and have no Fort Hamilton platforms.'],
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__=='__main__':
    result=prepare()
    Path('data/nyc_hamilton_corridors.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(ref=c['track_ref'],length=c['source_length_metres'],points=len(c['points'])) for c in result['corridors']]))
