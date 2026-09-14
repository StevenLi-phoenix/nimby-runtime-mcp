"""Plan 7th Avenue's two islands, each between its local and express track."""
import hashlib
import argparse
import json
from pathlib import Path


def prepare(plan_index=17):
    assert plan_index in (17, 20)
    raw = Path('data/nyc_culver_cross_sections.json').read_bytes()
    source = json.loads(raw)['stations'][plan_index-13]
    assert source['plan_index'] == plan_index
    refs = {c['track_ref']: c for c in source['cross_section']}
    tangent, scale = source['southbound_tangent'], source['scale']
    islands = []
    for primary, secondary in [('3', '1'), ('2', '4')]:
        center = refs[primary]
        spacing = center['offset_metres']-refs[secondary]['offset_metres']
        assert 5 < spacing < 12
        clearance = 1.825 if plan_index == 17 else 1.525
        islands.append(dict(primary_ref=primary, secondary_ref=secondary, spacing_metres=spacing,
                            start={k: center[k]-tangent[k]*70/scale for k in ['x', 'y']},
                            end={k: center[k]+tangent[k]*70/scale for k in ['x', 'y']},
                            surface_offsets=[-spacing/2, -clearance],
                            roof_offsets=[-spacing/2, -clearance]))
    return dict(station=source['name'], plan_index=plan_index, depth=-3 if plan_index == 17 else -2, islands=islands,
                source_sha256=hashlib.sha256(raw).hexdigest(), platform_length_metres=140,
                layout='Four platform tracks, two islands; B1/B3 and B4/B2 share an island.',
                adaptations=['Existing native surface and roof buildings form two meeting halves per island.',
                             'No footprint extensions or external walk links are used for station membership.'],
                stage='native_layout_pending',
                attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan-index', type=int, choices=[17,20], default=17)
    index = parser.parse_args().plan_index
    result = prepare(index)
    key = 'seventh' if index == 17 else 'church'
    Path(f'data/nyc_{key}_islands.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True))
