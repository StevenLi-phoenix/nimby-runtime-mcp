"""Prepare Concourse branch candidates from resolved native fork positions."""
import json
from pathlib import Path
from shapely.geometry import LineString


def prepare():
    source=json.loads(Path('data/nyc_145_concourse_branches.json').read_bytes())
    forks=json.loads(Path('work/nyc-145-concourse-forks.json').read_bytes())
    net=json.loads(Path('work/nyc-145-concourse-before.json').read_bytes());nodes={n['id']:n for n in net['nodes']}
    branches=[];scale=source['scale']
    for branch in source['branches']:
        fork=next(f for f in forks if f['target_way_id']==branch['target_way_id'])
        coords=[]
        for segment in branch['segments']:coords.extend(segment['points'] if not coords else segment['points'][1:])
        line=LineString(coords);total=line.length*scale;end=nodes[branch['end_node_id']]
        assert len(branch['depth_boundaries'])==1
        boundary=branch['depth_boundaries'][0]['chainage_metres']
        cuts=[0,total,boundary-20,boundary+20]
        cuts.extend(d for d in range(25,int(total),25) if min(abs(d-z) for z in cuts)>10)
        cuts.sort();points=[];start=line.interpolate(0);finish=line.interpolate(line.length)
        for d in cuts:
            q=line.interpolate(d/scale);fa=max(0,1-d/60);fa=fa*fa*(3-2*fa);fb=max(0,1-(total-d)/100);fb=fb*fb*(3-2*fb)
            points.append(dict(x=q.x+fa*(fork['x']-start.x)+fb*(end['x']-finish.x),
                               y=q.y+fa*(fork['y']-start.y)+fb*(end['y']-finish.y),
                               depth=-2 if d<boundary else -3,chainage_metres=d))
        branches.append(dict(target_way_id=branch['target_way_id'],source_junction_node_id=branch['source_junction_node_id'],
                             fork=fork,end_node_id=end['id'],points=points,source_boundary_metres=boundary))
    return dict(source='data/nyc_145_concourse_branches.json',attribution=source['attribution'],scale=scale,branches=branches,
                stage='candidate_crossing_and_curve_review_pending')


if __name__=='__main__':
    p=prepare();Path('data/nyc_145_concourse_native.json').write_text(json.dumps(p,indent=2)+'\n')
    print(json.dumps([dict(target=b['target_way_id'],points=len(b['points']),boundary=b['source_boundary_metres']) for b in p['branches']]))
