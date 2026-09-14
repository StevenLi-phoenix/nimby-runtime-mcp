"""Plan Avenue I's two outside platforms and the separate center through rail."""
import json
from pathlib import Path


def prepare(plan_index=35, source_path='data/nyc_south_culver_source.json'):
    source=json.loads(Path(source_path).read_bytes())
    s=next(s for s in source['stations'] if s['plan_index']==plan_index)
    assert s['layout']=='two_side_platforms'
    refs={c['track_ref']:c for c in s['cross_section']};t=s['southbound_tangent'];scale=s['scale']
    tracks=[]
    for ref in ['1','3-4','2']:
        c=refs[ref]
        tracks.append(dict(track_ref=ref,source_way_id=c['osm_way_id'],role='center_through_no_platform' if ref=='3-4' else 'local_platform',
                           points=[dict(x=c['x']+d*t['x']/scale,y=c['y']+d*t['y']/scale,depth=2) for d in [-120,-70,0,70,120]]))
    return dict(plan_index=plan_index,station=s['name'],center=s['center'],scale=scale,southbound_tangent=t,native_depth=2,
                platform_length_metres=140,primary_ref='2',secondary_ref='1',tracks=tracks,
                track_spacing_metres=refs['2']['offset_metres']-refs['1']['offset_metres'],
                source=source_path,operator_reference='https://www.mta.info/maps/subway-line-maps/f-line',
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__=='__main__':
    result=prepare();Path('data/nyc_avenue_i_three_tracks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
