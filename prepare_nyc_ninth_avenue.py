"""Plan Ninth Avenue's three West End tracks, excluding overlapping yard tracks."""
import json
from pathlib import Path


def prepare():
    survey = json.loads(Path('data/nyc_ninth_avenue_survey.json').read_bytes())
    scale = survey['scale']
    tx, ty = survey['axis']['x'], survey['axis']['y']
    rows = [r for r in survey['cross_section']
            if r['tags'].get('name') == 'BMT West End Line'
            and r['tags'].get('service') != 'yard']
    assert [r['tags']['railway:track_ref'] for r in rows] == ['2', '3-4', '1']
    tracks = []
    for r in rows:
        assert r['tags']['level'] == '-1'
        tracks.append(dict(track_ref=r['tags']['railway:track_ref'],
                           source_way_id=r['way'], offset_metres=r['offset'],
                           points=[dict(x=r['x']+d*tx/scale, y=r['y']+d*ty/scale,
                                        depth=-1) for d in [-120,-70,70,120]]))
    islands = []
    for a,b in zip(tracks,tracks[1:]):
        width = b['offset_metres']-a['offset_metres']-3.05
        assert width > 3
        islands.append(dict(track_refs=[a['track_ref'],b['track_ref']],
                            island_width_metres=width,
                            offset_min=a['offset_metres']+1.525,
                            offset_max=b['offset_metres']-1.525))
    return dict(name='9th Avenue', plan_index=23, center=survey['center'], scale=scale,
                southbound_axis=survey['axis'], depth=-1, platform_length_metres=140,
                tracks=tracks, islands=islands, source_platform_way_ids=[299892115,299892131],
                excluded_yard_way_ids=[r['way'] for r in survey['cross_section']
                                       if r['tags'].get('service') == 'yard'],
                source='data/nyc_ninth_avenue_source.json',
                stage='candidate_native_platform_geometry_pending',
                pending=['Create three physical platform tracks with two island footprints; do not duplicate the middle track.',
                         'Audit native station geometry and both approaches before selected construction.',
                         'Preserve yard and private platform infrastructure as deferred work.'])


if __name__ == '__main__':
    plan = prepare()
    Path('data/nyc_ninth_avenue_three_tracks.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(islands=plan['islands'], excluded_yard_way_ids=plan['excluded_yard_way_ids'])))
