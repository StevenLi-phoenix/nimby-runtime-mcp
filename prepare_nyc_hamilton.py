"""Plan stacked local platforms and express tracks at Fort Hamilton Parkway."""
import json
from pathlib import Path


def prepare():
    s=json.loads(Path('data/nyc_culver_cross_sections.json').read_bytes())['stations'][6]
    refs={c['track_ref']:c for c in s['cross_section']}
    t,scale=s['southbound_tangent'],s['scale']
    tracks=[]
    for ref in ['1','2','3','4']:
        c=refs[ref];depth=-2 if ref in ['1','2'] else -3
        assert c['source_depth']==depth
        tracks.append(dict(track_ref=ref,depth=depth,source_way_id=c['osm_way_id'],
                           role='local_side_platform' if ref in ['1','2'] else 'express_no_platform',
                           points=[dict(x=c['x']+d*t['x']/scale,y=c['y']+d*t['y']/scale,depth=depth)
                                   for d in [-120,-70,0,70,120]]))
    return dict(station=s['name'],plan_index=19,tracks=tracks,
                local_spacing_metres=refs['2']['offset_metres']-refs['1']['offset_metres'],
                stage='native_station_and_corridor_audit_pending',
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__=='__main__':
    result=prepare()
    Path('data/nyc_hamilton_four_tracks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
