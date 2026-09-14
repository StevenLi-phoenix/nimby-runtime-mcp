"""Clip Concourse approaches to their shared main-track source junctions."""
import json
from pathlib import Path
from shapely.geometry import LineString, Point
from shapely.ops import substring


def prepare():
    p=json.loads(Path('data/nyc_135_145_approach_survey.json').read_bytes())
    topo=json.loads(Path('data/nyc_135_145_junction_survey.json').read_bytes())
    junctions={j['node_id']:j for j in topo['junctions']}
    starts={677322262:6424622730,677322261:6422236785,677322260:6424622717}
    branches=[]
    for route in p['routes']:
        if route['end_depth']!=-3:continue
        source_id=starts[route['target_way_id']];j=junctions[source_id];point=Point(j['x'],j['y'])
        segments=[];started=False
        for segment in route['segments']:
            line=LineString(segment['points'])
            if not started:
                if line.distance(point)>.001:continue
                position=line.project(point)
                if line.length-position<.001:continue
                line=substring(line,position,line.length);started=True
            segments.append(dict(way_id=segment['way_id'],depth=segment['depth'],points=list(line.coords)))
        assert segments and segments[0]['depth']==-2 and segments[-1]['depth']==-3
        assert Point(segments[0]['points'][0]).distance(point)<.001
        assert all(Point(a['points'][-1]).distance(Point(b['points'][0]))<.001 for a,b in zip(segments,segments[1:]))
        distances=[];total=0;previous=segments[0]['depth']
        for segment in segments:
            if segment['depth']!=previous:distances.append(dict(chainage_metres=total,from_depth=previous,to_depth=segment['depth']))
            total+=LineString(segment['points']).length*p['scale'];previous=segment['depth']
        branches.append(dict(source_junction_node_id=source_id,start_track_ref=route['start_track_ref'],
                             end_node_id=route['end_node_id'],target_way_id=route['target_way_id'],
                             segments=segments,length_metres=total,depth_boundaries=distances))
    assert len(branches)==3
    return dict(source='data/nyc_135_145_approach_survey.json',attribution=p['attribution'],scale=p['scale'],branches=branches,
                stage='source_branches_clipped_native_parent_curve_alignment_pending',
                pending=['Resolve native branch positions from live main-track curves.',
                         'Audit source and native crossings against upper tracks and all three branches.'])


if __name__=='__main__':
    p=prepare();Path('data/nyc_145_concourse_branches.json').write_text(json.dumps(p,indent=2)+'\n')
    print(json.dumps([{k:v for k,v in b.items() if k!='segments'} for b in p['branches']]))
