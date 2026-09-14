"""Connect Jay Street F platforms to the existing Bergen mainline interfaces."""
import json
from pathlib import Path
from prepare_nyc_carroll_smith import route_between, distance
from prepare_nyc_g_corridors import simplify


def prepare():
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    g = json.loads(Path('work/nyc-g-built.json').read_bytes())
    source = json.loads(Path('data/nyc_jay_street_source.json').read_bytes())
    nodes = {n['id']:n for n in json.loads(Path('work/nyc-jay-bergen-live.json').read_bytes())['nodes']}
    scale = json.loads(Path('data/nyc_jay_street_islands.json').read_bytes())['scale']
    corridors = []
    for ref, index, key in [('1', 0, 'east_secondary'), ('2', 1, 'east_primary')]:
        a = state['jay_islands'][index][key]
        b = next(t['f_open_endpoint'] for t in g['hoyt_bergen_merge']['tracks'] if t['track_ref'] == ref)
        assert all('0' in [nodes[i]['previous'], nodes[i]['next']] for i in [a,b])
        route, ways, gaps = route_between(source['ways'], ref, nodes[a], nodes[b])
        depths = [int(w['tags'].get('level',w['tags'].get('layer',-1))) for w in ways]
        assert set(depths) <= {-1,-2}, depths
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
        for p,n in [(points[0],nodes[a]),(points[-1],nodes[b])]:
            p.update(x=n['x'],y=n['y'],depth=n['depth'])
        corridors.append(dict(track_ref=ref,start_node_id=a,end_node_id=b,points=points,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in ways)),
                              source_length_metres=chain[-1],source_projection_gaps_world_metres=gaps,
                              source_layer_segments=[dict(start_metres=chain[i],end_metres=chain[i+1],depth=d) for i,d in enumerate(depths)]))
    return dict(corridors=corridors,scale=scale,source='data/nyc_jay_street_source.json',
                stage='candidate_native_curves_and_crossing_audit_pending',
                pending=['Check crossings against existing G and future A/C/R tracks.',
                         'Inspect native curves and layer transitions before building.'])


if __name__=='__main__':
    result=prepare()
    Path('data/nyc_jay_bergen_corridors.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([dict(ref=c['track_ref'],length=c['source_length_metres'],points=len(c['points']),depths=[p['depth'] for p in c['points']]) for c in result['corridors']]))
