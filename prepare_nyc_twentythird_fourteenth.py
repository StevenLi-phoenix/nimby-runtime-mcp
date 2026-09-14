"""Plan the Sixth Avenue connection from 23rd Street to 14th Street."""
import json
from pathlib import Path
from prepare_nyc_carroll_smith import route_between, distance
from prepare_nyc_g_corridors import simplify


def prepare():
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    source = json.loads(Path('data/nyc_twentythird_source.json').read_bytes())
    nodes = {n['id']:n for n in json.loads(Path('work/nyc-twentythird-fourteenth-live.json').read_bytes())['nodes']}
    scale = json.loads(Path('data/nyc_twentythird_side_platforms.json').read_bytes())['scale']
    corridors = []
    for ref, index, key in [('1', 0, 'east_secondary'), ('2', 1, 'east_primary')]:
        a = state['twentythird_platform_groups'][0][key]
        b = state['fourteenth_platform_groups'][0]['west_secondary' if ref == '1' else 'west_primary']
        assert all('0' in [nodes[i]['previous'], nodes[i]['next']] for i in [a,b])
        eligible = [dict(w,tags=dict(w['tags'],name='IND Culver Line')) for w in source['ways'] if w['tags'].get('name') in ['IND Culver Line','IND Sixth Avenue Line']]; route, ways, gaps = route_between(eligible, ref, nodes[a], nodes[b])
        depths = [int(w['tags'].get('level',w['tags'].get('layer',-1))) for w in ways]
        assert set(depths) <= {-4,-3,-2,-1}, depths; source_depths = depths[:]; depths = [max(-3,d) for d in depths]
        chain = [0.0]
        for u,v in zip(route,route[1:]):
            chain.append(chain[-1]+distance(u,v)*scale)
        # Keep explicit controls at every source layer boundary when simplifying.
        cuts = [0]+[i for i in range(1,len(depths)) if depths[i]!=depths[i-1]]+[len(route)-1]
        points = []
        for start,end in zip(cuts,cuts[1:]):
            section = [dict(route[i],depth=depths[start],metres=chain[i]) for i in range(start,end+1)]
            points += simplify(section,tolerance=2)[:-1]
        points.append(dict(route[-1],depth=depths[-1],metres=chain[-1]))
        if len(points) == 2:
            interior=[]
            for fraction in [1/3,2/3]:
                d=chain[-1]*fraction
                i=next(i for i in range(len(chain)-1) if chain[i]<=d<=chain[i+1])
                f=(d-chain[i])/(chain[i+1]-chain[i])
                interior.append(dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),
                                     y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']),
                                     depth=depths[i],metres=d))
            points=points[:1]+interior+points[-1:]
        for p,n in [(points[0],nodes[a]),(points[-1],nodes[b])]:
            p.update(x=n['x'],y=n['y'],depth=n['depth'])
        corridors.append(dict(track_ref=ref,start_node_id=a,end_node_id=b,points=points,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in ways)),
                              source_length_metres=chain[-1],source_projection_gaps_world_metres=gaps,
                              source_layer_segments=[dict(start_metres=chain[i],end_metres=chain[i+1],depth=d) for i,d in enumerate(source_depths)]))
    return dict(corridors=corridors,scale=scale,source='data/nyc_twentythird_source.json',
                stage='candidate_native_curves_and_crossing_audit_pending',
                adaptation='Source -1 to -2 levels retained; original depths remain in source_layer_segments.',
                pending=['Check source tunnel crossings and station approach curves.',
                         'Inspect native curves and layer transitions before building.'])


if __name__=='__main__':
    result=prepare()
    Path('data/nyc_twentythird_fourteenth_corridors.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([dict(ref=c['track_ref'],length=c['source_length_metres'],points=len(c['points']),depths=[p['depth'] for p in c['points']]) for c in result['corridors']]))



