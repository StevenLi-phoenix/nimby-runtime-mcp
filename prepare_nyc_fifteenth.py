"""Plan the narrow source island at 15th Street–Prospect Park."""
import json
from pathlib import Path


def prepare():
    source=json.loads(Path('data/nyc_culver_cross_sections.json').read_bytes())['stations'][5]
    assert source['plan_index']==18 and len(source['platform_footprints'])==1
    refs={c['track_ref']:c for c in source['cross_section']}
    assert set(refs)=={'1','2'}
    center,tangent,scale=refs['2'],source['southbound_tangent'],source['scale']
    spacing=refs['2']['offset_metres']-refs['1']['offset_metres']
    return dict(station=source['name'],plan_index=18,depth=-2,primary_ref='2',secondary_ref='1',
                start={k:center[k]-tangent[k]*70/scale for k in ['x','y']},
                end={k:center[k]+tangent[k]*70/scale for k in ['x','y']},
                spacing_metres=spacing,surface_offsets=[-spacing/2,-1.525],
                island_width_metres=spacing-3.05,source_platform_id=904605003,
                layout='Two local platform tracks and one island; express tracks bypass this station.',
                stage='native_layout_pending',
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__=='__main__':
    result=prepare()
    Path('data/nyc_fifteenth_island.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
