"""Plan four through tracks between Sutphin Boulevard and Briarwood; yard links excluded."""
import json
from pathlib import Path
from prepare_nyc_carroll_smith import route_between, distance
from prepare_nyc_g_corridors import simplify


def prepare():
    s = json.loads(Path('work/nyc-f-built.json').read_bytes())
    ns = {n['id']: n for n in json.loads(Path('work/nyc-sutphin-all-built.json').read_bytes())['nodes']}
    source_path = 'data/nyc_sutphin_briarwood_source.json'
    source = json.loads(Path(source_path).read_bytes())
    scale = json.loads(Path('data/nyc_sutphin_side_platforms.json').read_bytes())['scale']
    local = s['sutphin_platform_groups'][0]
    express = {e['track_ref']: e for e in s['sutphin_express_tracks']}
    pairs = [('1', local['east_secondary'], s['briarwood_platform_groups'][0]['west_secondary']),
             ('3', express['3']['east'], next(e['west'] for e in s['briarwood_express_tracks'] if e['track_ref']=='3')),
             ('4', express['4']['east'], next(e['west'] for e in s['briarwood_express_tracks'] if e['track_ref']=='4')),
             ('2', local['east_primary'], s['briarwood_platform_groups'][0]['west_primary'])]
    eligible = [dict(w, tags=dict(w['tags'], name='IND Culver Line')) for w in source['ways'] if w['tags'].get('name') == 'IND Queens Boulevard Line' and w['tags'].get('service') != 'yard']
    corridors = []
    for ref, start, end in pairs:
        assert all('0' in [ns[i]['previous'], ns[i]['next']] for i in [start, end])
        route, ways, gaps = route_between(eligible, ref, ns[start], ns[end])
        depths = [int(w['tags'].get('level', w['tags'].get('layer', -2))) for w in ways]
        assert set(depths) <= {-2, -1}, depths
        chain = [0.0]
        for a, b in zip(route, route[1:]):
            chain.append(chain[-1]+distance(a, b)*scale)
        transitions = [i for i in range(1,len(depths)) if depths[i]!=depths[i-1]]
        assert len(transitions)==2 and [depths[0],depths[transitions[0]],depths[-1]]==[-2,-1,-2]
        up, down = [chain[i] for i in transitions]
        profile = [(0,-2),(up-100,-2),(up,-1),(down,-1),(down+80,-2),(chain[-1],-2)]
        assert all(a[0]<b[0] for a,b in zip(profile,profile[1:]))
        def at(d,depth):
            i=next(i for i in range(len(chain)-1) if chain[i]<=d<=chain[i+1])
            f=(d-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),
                        y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']),depth=depth,metres=d)
        points=[]
        for (a,da),(b,db) in zip(profile,profile[1:]):
            if da!=db:
                # Native integer layers: explicit ramp endpoint controls.
                section=[at(a,da),at(b,db)]
            else:
                section=[at(a,da)]+[dict(q,depth=da,metres=d) for q,d in zip(route,chain) if a+10<d<b-10]+[at(b,db)]
                section=simplify(section,tolerance=1)
            points+=section[:-1]
        points.append(at(chain[-1],-2))
        for q, i in [(points[0], start), (points[-1], end)]:
            q.update(x=ns[i]['x'], y=ns[i]['y'], depth=ns[i]['depth'])
        corridors.append(dict(track_ref=ref, start_node_id=start, end_node_id=end, points=points,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in ways)),
                              depth_profile=profile, source_length_metres=chain[-1], source_projection_gaps_world_metres=gaps,
                              source_layer_segments=[dict(start_metres=chain[i],end_metres=chain[i+1],depth=d,source_way_id=ways[i]['osm_way_id']) for i,d in enumerate(depths)]))
    return dict(source=source_path, scale=scale, corridors=corridors,
                stage='candidate_native_curves_pending',
                pending=['Audit native ramp clearances, crossings and station approaches before building.',
                         'Keep yard tracks and yard access unbuilt.'])


if __name__ == '__main__':
    p = prepare()
    Path('data/nyc_sutphin_briarwood_corridors.json').write_text(json.dumps(p, indent=2)+'\n')
    print(json.dumps([dict(ref=c['track_ref'], length=c['source_length_metres'], points=len(c['points']), gaps=c['source_projection_gaps_world_metres']) for c in p['corridors']]))
