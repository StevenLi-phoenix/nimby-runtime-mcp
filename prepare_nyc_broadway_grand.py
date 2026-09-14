"""Prepare explicit grade controls for Broadway-Lafayette to Grand Street."""
import json
from pathlib import Path
from prepare_nyc_g_corridors import simplify

def prepare():
    survey=json.loads(Path('data/nyc_broadway_grand_survey.json').read_bytes())
    live={n['id']:n for n in json.loads(Path('work/nyc-broadway-grand-live.json').read_bytes())['nodes']}
    out=[]
    for c in survey['corridors']:
        route=c['route'];chain=c['chainage_metres']
        profile=[(0,-3),(60,-3),(130,-2),(210,-1),(560,-1),(660,-2),(chain[-1],-2)]
        def at(d,z):
            i=next(i for i in range(len(chain)-1) if chain[i]<=d<=chain[i+1])
            f=(d-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']),depth=z,metres=d)
        points=[]
        for (a,za),(b,zb) in zip(profile,profile[1:]):
            section=[at(a,za)]+([dict(q,depth=za,metres=d) for q,d in zip(route,chain) if a+10<d<b-10] if za==zb else [])+[at(b,zb)]
            points+=simplify(section,tolerance=1)[:-1]
        points.append(at(chain[-1],-2))
        for q,key in [(points[0],'start_node_id'),(points[-1],'end_node_id')]:
            n=live[c[key]];assert '0' in [n['previous'],n['next']];q.update(x=n['x'],y=n['y'],depth=n['depth'])
        out.append(dict(track_ref=c['ref'],start_node_id=c['start_node_id'],end_node_id=c['end_node_id'],points=points,depth_profile=profile,source_way_ids=c['source_way_ids'],source_length_metres=c['length']))
    return dict(corridors=out,scale=survey['scale'],source='data/nyc_broadway_grand_source.json',stage='candidate_native_geometry_and_grade_clearance_pending',pending=['Verify native ramps remain above intermediate -2 crossings and below Nassau -1 crossings.','Inspect station approach curvature and mutual spacing before building.','Keep yard connections deferred.'])

if __name__=='__main__':
    p=prepare();Path('data/nyc_broadway_grand_corridors.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf-8');print([(c['track_ref'],len(c['points'])) for c in p['corridors']])
