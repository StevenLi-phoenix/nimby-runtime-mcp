"""Plan the curved local-only Culver segment; express tracks remain on their bypass."""
import json
from pathlib import Path

from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import simplify


def prepare():
    state=json.loads(Path('work/nyc-g-built.json').read_bytes())
    source=json.loads(Path('data/nyc_culver_cross_sections.json').read_bytes())['stations']
    ways={w['osm_way_id']:w for s in source for w in s['source_rails']}
    nodes={n['id']:n for n in json.loads(Path('work/nyc-seventh-fifteenth-live.json').read_bytes())['nodes']}
    station=next(s for s in state['stations'] if s['plan_index']==18)
    scale=source[5]['scale'];corridors=[]
    for ref in ['1','2']:
        start_id=state['seventh_tracks'][ref]['south_endpoint']
        end_id=station['west_secondary' if ref=='1' else 'west_primary']
        start,end=nodes[start_id],nodes[end_id]
        route,route_ways,gaps=route_between(list(ways.values()),ref,start,end)
        chain=[0.0]
        for a,b in zip(route,route[1:]):chain.append(chain[-1]+distance(a,b)*scale)
        boundary=next(chain[i] for i,w in enumerate(route_ways) if w['tags'].get('level',w['tags'].get('layer'))=='-2')
        assert 80<boundary<chain[-1]
        anchors=[(0,-3),(boundary-80,-3),(boundary,-2),(chain[-1],-2)]
        def at(position,depth):
            i=next(i for i in range(len(chain)-1) if chain[i]<=position<=chain[i+1])
            f=(position-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),
                        y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']),
                        depth=depth,chainage_metres=position,reason='layer_anchor')
        points=[]
        for (a,depth),(b,next_depth) in zip(anchors,anchors[1:]):
            segment=[at(a,depth)]+[dict(**p,depth=depth,chainage_metres=d,reason='source_curve')
                                     for p,d in zip(route,chain) if a+15<d<b-15]+[at(b,next_depth)]
            points += simplify(segment,tolerance=4)[:-1]
        points.append(at(chain[-1],-2))
        for p,n in [(points[0],start),(points[-1],end)]:p.update(x=n['x'],y=n['y'],depth=n['depth'],reason='native_endpoint')
        corridors.append(dict(track_ref=ref,start_node_id=start_id,end_node_id=end_id,points=points,
                              source_length_metres=chain[-1],source_projection_gaps_world_metres=gaps,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in route_ways)),
                              stage='candidate_native_curves_pending'))
    return dict(from_station='7th Avenue',to_station='15th Street–Prospect Park',corridors=corridors,
                adaptations=['Preserve the local route bend; B3/B4 follow a separate express bypass.',
                             'Transition from -3 to source -2 over 80m before the source layer boundary.'],
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__=='__main__':
    result=prepare()
    Path('data/nyc_seventh_fifteenth_corridors.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(ref=c['track_ref'],points=len(c['points']),length=c['source_length_metres']) for c in result['corridors']]))
