"""Trace B3 to B1 and B4 to the single Ditmas center rail without inventing a fourth rail."""
import json
from pathlib import Path
from prepare_nyc_carroll_smith import distance, route_between
from prepare_nyc_g_corridors import simplify


def prepare():
    source=json.loads(Path('data/nyc_south_culver_source.json').read_bytes())
    g=json.loads(Path('work/nyc-g-built.json').read_bytes())
    f=json.loads(Path('work/nyc-f-built.json').read_bytes())
    nodes={n['id']:n for n in json.loads(Path('work/nyc-ditmas-merge-live.json').read_bytes())['nodes']}
    starts={t['track_ref']:t['frontier'] for t in g['church_relay']['through_tracks']}
    scale=source['stations'][0]['scale'];corridors=[]
    for ref,connector in [('3',426574735),('4',426574738)]:
        # Only the named connecting way is included in this route graph; retain
        # original source tags in the source artifact, not the temporary graph.
        ways=[dict(w,tags=dict(w['tags'],**{'railway:track_ref':ref})) if w['osm_way_id']==connector else w for w in source['ways']]
        start=nodes[starts[ref]]
        end=f['ditmas_b3_merge_candidate'] if ref=='3' else nodes[f['ditmas_center_track']['north_endpoint']]
        route,rways,gaps=route_between(ways,ref,start,end)
        chain=[0.0]
        for a,b in zip(route,route[1:]):chain.append(chain[-1]+distance(a,b)*scale)
        portal=next(chain[i] for i,w in enumerate(rways) if w['tags'].get('tunnel')!='yes')
        bridge=next(chain[i] for i,w in enumerate(rways) if w['tags'].get('bridge')=='yes')
        junction=next(chain[i] for i,w in enumerate(rways) if w['osm_way_id']==connector)
        anchors=[(0,-2),(portal,-1),(portal+45,0),(bridge,1),(bridge+50,2),(junction,2),(chain[-1],2)]
        assert all(a[0]<b[0] for a,b in zip(anchors,anchors[1:])),anchors
        def at(d,depth):
            i=next(i for i in range(len(chain)-1) if chain[i]<=d<=chain[i+1]);v=(d-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+v*(route[i+1]['x']-route[i]['x']),y=route[i]['y']+v*(route[i+1]['y']-route[i]['y']),depth=depth,chainage_metres=d)
        points=[]
        for (a,d),(b,e) in zip(anchors,anchors[1:]):
            segment=[at(a,d)]+[dict(**p,depth=d,chainage_metres=c) for p,c in zip(route,chain) if a+20<c<b-20]+[at(b,e)]
            points+=simplify(segment,tolerance=2)[:-1]
        points.append(at(chain[-1],2))
        for p,n in [(points[0],start),(points[-1],end)]:p.update(x=n['x'],y=n['y'],depth=n['depth'])
        target={k:end[k] for k in ['edge_id','position','depth']} if ref=='3' else {'id':end['id']}
        corridors.append(dict(track_ref=ref,start_node_id=start['id'],end=target,points=points,
                              source_way_ids=list(dict.fromkeys(w['osm_way_id'] for w in rways)),
                              source_projection_gaps_world_metres=gaps,source_length_metres=chain[-1],
                              portal_metres=portal,bridge_metres=bridge,crossover_origin_metres=junction))
    return dict(corridors=corridors,scale=scale,source='data/nyc_south_culver_source.json',
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright',
                scope='B3 merge into B1 and B4 connection to center; source crossovers need subsequent native sampling.',
                stage='candidate_native_geometry_audit_pending')


if __name__=='__main__':
    result=prepare();Path('data/nyc_ditmas_merge.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
