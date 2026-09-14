"""Reserve separate F/Q station-after relays without yard connections."""
import json
from pathlib import Path


def prepare():
    state = json.loads(Path('work/nyc-f-built.json').read_bytes())
    layout = json.loads(Path('data/nyc_coney_four_islands.json').read_bytes())
    live = json.loads(Path('work/nyc-coney-relay-live.json').read_bytes())
    survey = json.loads(Path('work/nyc-coney-relay-survey.json').read_bytes())
    nodes = {n['id']: n for n in live['nodes']}
    assert all(n['id'] in nodes for n in survey['nodes']), 'Unrecorded nearby tracks'
    scale = layout['scale']
    tx, ty = (-layout['southbound_axis'][k] for k in ['x', 'y'])
    relays = []
    for service, index in [('F', 1), ('Q', 2)]:
        island = state['coney_islands'][index]
        tracks = []
        for key in ['west_primary', 'west_secondary']:
            n = nodes[island[key]]
            assert not n['blueprint'] and n['depth'] == 2
            assert n['station_id'] == '0' and '0' in [n['previous'], n['next']]
            # Existing leads extend 50 m beyond the platform. ReBP and shorten
            # them to 3 m, leaving 47 m to climb before future approach crossings.
            points = [dict(x=n['x']+tx*d/scale, y=n['y']+ty*d/scale,
                           depth=2 if d == -47 else 3, metres=d)
                      for d in [-47, 0, 100, 220, 340]]
            tracks.append(dict(role=key, start_node_id=n['id'], points=points,
                               rebuild_existing_lead_required=True,
                               original_endpoint={k:n[k] for k in ['x', 'y', 'depth']}))
        relays.append(dict(service=service, tracks=tracks,
                           crossover=dict(from_role='west_secondary', from_metres=180,
                                          to_role='west_primary', to_metres=120,
                                          clear_length_beyond_branch_metres=160),
                           train_length_metres=120))
    return dict(station='Coney Island–Stillwell Avenue', relays=relays, scale=scale,
                outward_tangent=dict(x=tx, y=ty),
                adaptation='Northern +3 station-after relays are a game adaptation, not surveyed real terminal trackwork. Shortened +2 leads rise before crossing future +2 approaches. No yard or depot links.',
                reserved_other_islands=[0, 3],
                stage='candidate_native_geometry_pending',
                pending=['Verify the untagged West End source segment level from connected geometry.',
                         'ReBP four non-platform leads and verify the +2 to +3 ramps before source crossings.',
                         'Inspect native curves, crossover positions, and clearance before building.',
                         'Verify arrival platform, reversal beyond crossover, and departure platform in operation.'])


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_coney_relays.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(relays=len(result['relays']), stage=result['stage'])))
