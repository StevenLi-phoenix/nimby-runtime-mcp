"""Keep four Culver through tracks and reserve a separate lower G relay."""
import json
import math
from pathlib import Path
from prepare_nyc_carroll_smith import route_between,distance


def prepare():
    state=json.loads(Path('work/nyc-g-built.json').read_bytes())
    live=json.loads(Path('work/nyc-church-relay-live.json').read_bytes())
    nodes={n['id']:n for n in live['nodes']}
    source=json.loads(Path('data/nyc_church_relay_source.json').read_bytes())
    station=json.loads(Path('data/nyc_culver_cross_sections.json').read_bytes())['stations'][7]
    scale=station['scale'];t=station['southbound_tangent'];tracks=[]
    for ref in ['1','3','4','2']:
        start=nodes[state['church_tracks'][ref]['south_endpoint']]
        assert start['depth']==-2 and '0' in [start['previous'],start['next']]
        estimate={k:start[k]+t[k]*250/scale for k in ['x','y']}
        route,ways,gaps=route_between(source['ways'],ref,start,estimate)
        assert all(w['tags'].get('level',w['tags'].get('layer'))=='-2' for w in ways)
        chain=[0.0]
        for a,b in zip(route,route[1:]):chain.append(chain[-1]+distance(a,b)*scale)
        def at(d):
            i=next(i for i in range(len(chain)-1) if chain[i]<=d<=chain[i+1])
            f=(d-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),
                        y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']),depth=-2,metres=d)
        points=[dict(x=start['x'],y=start['y'],depth=-2,metres=0)]+[at(d) for d in [80,160,chain[-1]]]
        tracks.append(dict(track_ref=ref,start_node_id=start['id'],points=points,
                           source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in ways)),source_projection_gaps_world_metres=gaps))
    return dict(station='Church Avenue',through_tracks=tracks,scale=scale,southbound_tangent=t,
                relay=dict(arrival_ref='1',departure_ref='2',branch_metres=60,
                           lower_control_metres=[140,260,450],depth=-3,outward_offset_metres=3,
                           crossover_arrival_metres=290,crossover_departure_metres=230),
                reference='https://www.mta.info/document/10191',
                source_limitation='MTA confirms tail tracks south of Church; the OSM snapshot contains only four through tracks. Lower relay shape is a game adaptation, not surveyed tail-track geometry.',
                scope='Four short through-track continuations and two G reversal tracks. No depot, yard storage fan, or yard links.',
                stage='native_through_tracks_and_relay_pending')


if __name__=='__main__':
    result=prepare();Path('data/nyc_church_relay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
