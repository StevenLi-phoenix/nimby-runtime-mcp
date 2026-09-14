"""Plan the Smith or 4th Avenue four-track station span from its OSM cross-section."""
import argparse
import hashlib
import json
from pathlib import Path


def prepare(plan_index=15):
    raw = Path('data/nyc_culver_cross_sections.json').read_bytes()
    assert plan_index in (15, 16)
    source = json.loads(raw)['stations'][plan_index-13]
    assert source['plan_index'] == plan_index
    by = {c['track_ref']: c for c in source['cross_section']}
    assert set(by) == {'1', '2', '3', '4'}
    source_depth = 4 if plan_index == 15 else 2
    native_depth = min(source_depth, 3)
    assert all(c['source_depth'] == source_depth for c in by.values())
    tangent = source['southbound_tangent']
    tracks = []
    for ref in ['1', '2', '3', '4']:
        center = by[ref]
        points = [dict(x=center['x']+d*tangent['x']/source['scale'],
                       y=center['y']+d*tangent['y']/source['scale'], depth=native_depth)
                  for d in [-120, -70, 0, 70, 120]]
        tracks.append(dict(track_ref=ref, source_way_id=center['osm_way_id'],
                           role='local_platform' if ref in ['1', '2'] else 'express_no_platform',
                           points=points))
    return dict(station=source['name'], plan_index=plan_index,
                source='data/nyc_culver_cross_sections.json', source_sha256=hashlib.sha256(raw).hexdigest(),
                platform_length_metres=140, track_spacing_metres=by['2']['offset_metres']-by['1']['offset_metres'],
                primary_ref='2', secondary_ref='1', paired_side='right',
                source_depth=source_depth, native_depth=native_depth, tracks=tracks,
                adaptations=[('Source +4 mapped to highest supported native +3.' if plan_index == 15
                              else 'Source +2 retained; BMT Fourth Avenue tracks are separately underground at -1.'),
                             'Straight parallel station span; retain source bends in onward approaches.'],
                stage='candidate_station_span_native_and_corridor_audit_pending',
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan-index', type=int, choices=[15, 16], default=15)
    args = parser.parse_args()
    result = prepare(args.plan_index)
    name = 'smith' if args.plan_index == 15 else 'fourth'
    Path(f'data/nyc_{name}_four_tracks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
