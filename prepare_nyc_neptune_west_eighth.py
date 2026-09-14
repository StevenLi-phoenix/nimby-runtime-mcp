"""Plan three source-connected elevated tracks from Neptune Avenue to West 8th Street."""
import json
from pathlib import Path
from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import simplify


def prepare():
    f=json.loads(Path('work/nyc-f-built.json').read_bytes())
    source=json.loads(Path('data/nyc_coney_culver_source.json').read_bytes())
    nodes={n['id']:n for name in ['nyc-neptune-west-eighth-live'] for n in json.loads(Path('work/'+name+'.json').read_bytes())['nodes']}
    s={s['plan_index']:s for s in f['stations']}
    ends={'1':(s[42]['east_secondary'],s[43]['west_secondary']),
          '2':(s[42]['east_primary'],s[43]['west_primary'])}
    scale=json.loads(Path('data/nyc_west_eighth_stacked.json').read_bytes())['levels'][0]['scale'];corridors=[]
    for ref,(a,b) in ends.items():
        start,end=nodes[a],nodes[b];route,ways,gaps=route_between(source['ways'],ref,start,end)
        assert all(w['tags'].get('bridge')=='yes' and w['tags'].get('level')=='2' for w in ways)
        chain=[0.0]
        for u,v in zip(route,route[1:]):chain.append(chain[-1]+distance(u,v)*scale)
        def at(d):
            i=next(i for i in range(len(chain)-1) if chain[i]<=d<=chain[i+1]);t=(d-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+t*(route[i+1]['x']-route[i]['x']),y=route[i]['y']+t*(route[i+1]['y']-route[i]['y']),depth=2,chainage_metres=d)
        anchors=[0,80,160,chain[-1]];assert anchors==sorted(anchors)
        points=[]
        for u,v in zip(anchors,anchors[1:]):
            segment=[at(u)]+[dict(**p,depth=2,chainage_metres=d) for p,d in zip(route,chain) if u+15<d<v-15]+[at(v)]
            points+=simplify(segment,tolerance=1.5)[:-1]
        points.append(at(chain[-1]))
        for p,n in [(points[0],start),(points[-1],end)]:p.update(x=n['x'],y=n['y'],depth=n['depth'])
        corridors.append(dict(track_ref=ref,start_node_id=a,end_node_id=b,points=points,source_length_metres=chain[-1],
                              source_projection_gaps_world_metres=gaps,source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in ways))))
    return dict(corridors=corridors,scale=scale,source='data/nyc_coney_culver_source.json',
                stage='candidate_native_audit_pending',attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__=='__main__':
    result=prepare();Path('data/nyc_neptune_west_eighth_corridors.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
