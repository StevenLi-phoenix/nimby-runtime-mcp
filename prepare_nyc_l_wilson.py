"""Keep both Wilson approach tracks independent at their source layers."""
import json
from pathlib import Path

from prepare_nyc_l_corridors import offset, simplify


def prepare():
    plan = json.loads(Path('data/nyc_l_plan.json').read_text(encoding='utf-8'))
    state = json.loads(Path('work/nyc-l-built.json').read_text(encoding='utf-8'))
    live = json.loads(Path('work/nyc-l-live-topology.json').read_text(encoding='utf-8'))
    nodes = {n['id']: n for n in live['nodes']}
    stations = {s['plan_index']: s for s in state['stations']}
    paths = []
    for direction, rail in [('to_canarsie', 'secondary'), ('to_manhattan', 'primary')]:
        source = plan['directions'][direction]
        route, segments = source['route'], source['segments']
        if direction == 'to_manhattan':
            total = route[-1]['chainage']
            route = [dict(p, chainage=total-p['chainage']) for p in reversed(route)]
            segments = list(reversed(segments))
        def chain_at(point):
            result = []
            for a,b in zip(route, route[1:]):
                d,t = offset(point,a,b)
                result.append((d,a['chainage']+t*(b['chainage']-a['chainage'])))
            return min(result)[1]
        for index in (14,15):
            a,b = stations[index],stations[index+1]
            start,end = nodes[a['east_'+rail]],nodes[b['west_'+rail]]
            s0,s1 = chain_at(start),chain_at(end)
            assert s0<s1
            points = [dict(x=start['x'],y=start['y'],depth=start['depth'],reason='live_endpoint')]
            for j,p in enumerate(route):
                if s0+40<p['chainage']<s1-40:
                    dep=segments[min(j,len(segments)-1)]['candidate_depth']
                    previous=segments[max(0,j-1)]['candidate_depth']
                    points.append(dict(x=p['x'],y=p['y'],depth=dep,source_node_id=p['osm_node_id'],
                                       reason='layer_boundary' if dep!=previous else 'geometry'))
            points.append(dict(x=end['x'],y=end['y'],depth=end['depth'],reason='live_endpoint'))
            anchors=[0]+[i for i,p in enumerate(points[1:-1],1) if p['reason']=='layer_boundary']+[len(points)-1]
            kept=[]
            for lo,hi in zip(anchors,anchors[1:]):
                kept.extend(simplify(points[lo:hi+1])[:-1])
            kept.append(points[-1])
            paths.append(dict(key=f'{index}-{rail}',corridor=index,direction=direction,
                              start_node_id=start['id'],end_node_id=end['id'],points=kept))
    return dict(source='data/nyc_l_plan.json',status='independent_single_track_candidates',paths=paths)


if __name__=='__main__':
    result=prepare()
    Path('data/nyc_l_wilson.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(key=p['key'],depths=[q['depth'] for q in p['points']]) for p in result['paths']]))
