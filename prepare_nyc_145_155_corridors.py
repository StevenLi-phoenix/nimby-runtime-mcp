"""Prepare three Concourse corridors using live station endpoints and source curves."""
import json
from pathlib import Path
from shapely.geometry import LineString


def prepare(survey_path='data/nyc_concourse145_155_survey.json', network_path='work/nyc-concourse145-155-live.json'):
    p=json.loads(Path(survey_path).read_bytes())
    net=json.loads(Path(network_path).read_bytes());ns={n['id']:n for n in net['nodes']};scale=p['scale'];corridors=[]
    for c in p['corridors']:
        shared=[]
        for a,b in zip(c['segments'],c['segments'][1:]):
            common=set(a['source_node_ids'])&set(b['source_node_ids']);assert len(common)==1
            shared.append(next(iter(common)))
        changes=[a['to_metres'] for a,b in zip(c['segments'],c['segments'][1:]) if a['depth']!=b['depth']]
        assert len(changes)==1;boundary=changes[0]
        line=LineString([(q['x'],q['y']) for q in c['source_points']]);total=line.length*scale
        cuts=[0,total,boundary-35,boundary+35]
        cuts.extend(d for d in range(40,int(total),40) if min(abs(d-z) for z in cuts)>15)
        cuts.sort();a=ns[c['start_node_id']];b=ns[c['end_node_id']];start=line.interpolate(0);end=line.interpolate(line.length);points=[]
        for d in cuts:
            q=line.interpolate(d/scale);fa=max(0,1-d/100);fa=fa*fa*(3-2*fa);fb=max(0,1-(total-d)/200);fb=fb*fb*(3-2*fb)
            points.append(dict(x=q.x+fa*(a['x']-start.x)+fb*(b['x']-end.x),y=q.y+fa*(a['y']-start.y)+fb*(b['y']-end.y),
                               depth=-3 if d<boundary else -2,chainage_metres=d))
        corridors.append(dict(track_ref=c['track_ref'],start_node_id=a['id'],end_node_id=b['id'],points=points,
                              source_way_ids=[s['way'] for s in c['segments']],source_shared_node_ids=shared,source_boundary_metres=boundary))
    lines={c['track_ref']:LineString([(q['x'],q['y']) for q in c['points']]) for c in corridors}
    gaps={a+' / '+b:lines[a].distance(lines[b])*scale for a,b in [('1','3-4'),('3-4','2')]}
    return dict(source='data/nyc_concourse145_155_survey.json',attribution=p['attribution'],scale=scale,corridors=corridors,
                candidate_gaps=gaps,endpoint_blend_metres=dict(start=100,end=200),stage='candidate_native_curve_review_pending')


if __name__=='__main__':
    p=prepare();Path('data/nyc_concourse145_155_corridors.json').write_text(json.dumps(p,indent=2)+'\n')
    print(json.dumps(dict(gaps=p['candidate_gaps'],points=[len(c['points']) for c in p['corridors']],shared=[c['source_shared_node_ids'] for c in p['corridors']])))
