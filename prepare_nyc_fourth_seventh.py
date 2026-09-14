"""Plan four Culver tracks between the built viaduct and 7th Avenue islands."""
import hashlib
import json
from pathlib import Path

from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import simplify


def prepare():
    raw = Path('data/nyc_culver_cross_sections.json').read_bytes()
    sources = json.loads(raw)['stations']
    ways = {r['osm_way_id']:r for station in sources for r in station['source_rails']}
    state = json.loads(Path('work/nyc-g-built.json').read_bytes())
    live = json.loads(Path('work/nyc-fourth-seventh-live.json').read_bytes())
    nodes = {n['id']:n for n in live['nodes']}
    fourth = next(s for s in state['stations'] if s['plan_index']==16)
    express = {t['track_ref']:t for t in state['fourth_express_tracks']}
    starts = {'1':fourth['east_secondary'], '2':fourth['east_primary'],
              '3':express['3']['frontier'], '4':express['4']['start']}
    scale = sources[4]['scale']
    corridors=[]
    for ref,start_id in starts.items():
        end_id=state['seventh_tracks'][ref]['north_endpoint']
        start,end=nodes[start_id],nodes[end_id]
        route,route_ways,gaps=route_between(list(ways.values()),ref,start,end)
        chain=[0.0]
        for a,b in zip(route,route[1:]):chain.append(chain[-1]+distance(a,b)*scale)
        assert chain[-1]>360 and start['depth']==2 and end['depth']==-3
        anchors=[(0,2),(60,0),(120,-1),(180,-2),(240,-3),(300,-3),(chain[-1],-3)]
        def at(position,depth):
            i=next(i for i in range(len(chain)-1) if chain[i]<=position<=chain[i+1])
            f=(position-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),
                        y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']),
                        chainage_metres=position,depth=depth,reason='transition_anchor')
        points=[]
        for (a,depth),(b,next_depth) in zip(anchors,anchors[1:]):
            part=[at(a,depth)]
            part += [dict(**p,depth=depth,chainage_metres=d,reason='source_curve')
                     for p,d in zip(route,chain) if a+15<d<b-15]
            part.append(at(b,next_depth))
            points += simplify(part,tolerance=5)[:-1]
        points.append(at(chain[-1],-3))
        for p,n in [(points[0],start),(points[-1],end)]:
            p.update(x=n['x'],y=n['y'],depth=n['depth'],reason='native_endpoint')
        corridors.append(dict(track_ref=ref,start_node_id=start_id,end_node_id=end_id,points=points,
                              source_length_metres=chain[-1],source_projection_gaps_world_metres=gaps,
                              fully_tunnelled_source_chainage_metres=next(chain[i] for i,w in enumerate(route_ways) if w['tags'].get('tunnel')=='yes'),
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in route_ways)),
                              stage='candidate_native_curves_pending'))
    return dict(from_station='4th Avenue',to_station='7th Avenue',corridors=corridors,
                source_sha256=hashlib.sha256(raw).hexdigest(),
                adaptations=['Preserve built +2 viaduct endpoints and new -3 station endpoints.',
                             'Place the ground anchor 60m from the existing endpoint, before the fully tunnelled source; reach -3 at 240m.',
                             'The earlier ground anchor at 120m lay inside the source tunnel and conflicted with a road; preserve the source tunnel crossing.',
                             'Source levels describe relative layers, not measured vertical grades.'],
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__=='__main__':
    result=prepare()
    Path('data/nyc_fourth_seventh_corridors.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(ref=c['track_ref'],points=len(c['points']),length=c['source_length_metres']) for c in result['corridors']]))
