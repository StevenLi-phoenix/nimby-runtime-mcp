"""Plan source-connected outer Culver tracks across the Church portal."""
import json
from pathlib import Path

from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import simplify


def prepare():
    source = json.loads(Path('data/nyc_south_culver_source.json').read_bytes())
    g = json.loads(Path('work/nyc-g-built.json').read_bytes())
    f = json.loads(Path('work/nyc-f-built.json').read_bytes())
    nodes = {n['id']: n for n in json.loads(Path('work/nyc-church-ditmas-live.json').read_bytes())['nodes']}
    starts = {t['track_ref']: t['frontier'] for t in g['church_relay']['through_tracks']}
    station = next(s for s in f['stations'] if s['plan_index'] == 33)
    scale = source['stations'][0]['scale']
    corridors = []
    for ref, key in [('1', 'west_secondary'), ('2', 'west_primary')]:
        start, end = nodes[starts[ref]], nodes[station[key]]
        route, ways, gaps = route_between(source['ways'], ref, start, end)
        chain = [0.0]
        for a, b in zip(route, route[1:]):
            chain.append(chain[-1]+distance(a,b)*scale)
        portal = next(chain[i] for i,w in enumerate(ways) if w['tags'].get('tunnel') != 'yes')
        bridge = next(chain[i] for i,w in enumerate(ways) if w['tags'].get('bridge') == 'yes')
        anchors = [(0,-2),(portal,-1),(portal+45,0),(bridge,1),(bridge+50,2),(chain[-1],2)]
        assert all(a[0]<b[0] for a,b in zip(anchors,anchors[1:]))

        def at(d, depth):
            i = next(i for i in range(len(chain)-1) if chain[i]<=d<=chain[i+1])
            v = (d-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+v*(route[i+1]['x']-route[i]['x']),
                        y=route[i]['y']+v*(route[i+1]['y']-route[i]['y']),
                        depth=depth, chainage_metres=d, reason='layer_anchor')

        points=[]
        for (a, depth),(b, next_depth) in zip(anchors,anchors[1:]):
            candidates=[at(a,depth)]+[dict(**p,depth=depth,chainage_metres=d,reason='source_curve')
                                           for p,d in zip(route,chain) if a+20<d<b-20]+[at(b,next_depth)]
            points+=simplify(candidates,tolerance=2)[:-1]
        points.append(at(chain[-1],2))
        for p,n in [(points[0],start),(points[-1],end)]:
            p.update(x=n['x'],y=n['y'],depth=n['depth'],reason='existing_endpoint')
        corridors.append(dict(track_ref=ref,start_node_id=start['id'],end_node_id=end['id'],points=points,
                              source_length_metres=chain[-1],portal_chainage_metres=portal,
                              bridge_chainage_metres=bridge,source_projection_gaps_world_metres=gaps,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in ways))))
    return dict(corridors=corridors,scale=scale,stage='outer_tracks_candidate_native_audit_pending',
                source='data/nyc_south_culver_source.json',
                adaptations=['Monotonic -2,-1,0,+1,+2 across the unroofed source approach; relative layers are not surveyed gradients.',
                             'Keep existing station and G relay geometry.'],
                remaining_topology=['B3 joins B1 through OSM way 426574735.',
                                    'B4 joins the single center 3-4 rail through OSM way 426574738.',
                                    'Crossovers 194911406 and 194911409 remain to be constructed.'],
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__ == '__main__':
    result=prepare()
    Path('data/nyc_church_ditmas_corridors.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
