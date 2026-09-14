"""Prepare West End approaches from surveyed source and live leads."""
import json
from pathlib import Path
from prepare_nyc_g_corridors import simplify


def prepare():
    survey = json.loads(Path('data/nyc_ninth_fort_survey.json').read_bytes())
    nodes = {n['id']: n for n in json.loads(Path('work/nyc-ninth-fort-live.json').read_bytes())['nodes']}
    survey['corridors'].insert(1,json.loads(Path('data/nyc_ninth_fort_center_clipped.json').read_bytes()))
    corridors = []
    for source in survey['corridors']:
        route = source['source_route']
        end = source['length_metres']
        profile = [(0,-1),(30,-1),(100,0),(170,1),(240,2),(end,2)]
        def at(distance, depth):
            a, b = next((a,b) for a,b in zip(route,route[1:])
                        if a['metres'] <= distance <= b['metres'])
            f = (distance-a['metres'])/(b['metres']-a['metres'])
            return dict(x=a['x']+f*(b['x']-a['x']),
                        y=a['y']+f*(b['y']-a['y']), metres=distance, depth=depth)
        points = []
        for (a, za), (b, zb) in zip(profile, profile[1:]):
            middle = [dict(x=q['x'], y=q['y'], metres=q['metres'], depth=za)
                      for q in route if a+10 < q['metres'] < b-10] if za == zb else []
            points += simplify([at(a,za)]+middle+[at(b,zb)], tolerance=2)[:-1]
        points.append(at(end,2))
        for q, key in [(points[0],'start_node_id'), (points[-1],'end_node_id')]:
            n = nodes[source[key]]
            assert '0' in [n['previous'],n['next']]
            q.update(x=n['x'], y=n['y'], depth=n['depth'])
        corridors.append(dict(track_ref=source['track_ref'],
                              start_node_id=source['start_node_id'], end_node_id=source['end_node_id'],
                              points=points, depth_profile=profile, source_length_metres=end))
    return dict(scale=survey['scale'], corridors=corridors,
                source='data/nyc_ninth_fort_survey.json',
                stage='candidate_native_geometry_and_crossing_audit_pending',
                vertical_inference='Expand source -1 to +2 transition into three successive native grade steps; audit parallel ramps and all crossings before construction.',
                supporting_source='https://www.nycsubway.org/wiki/BMT_West_End_Line',
                pending=['Audit native curves, spacing and grade crossings before selected construction.',
                         'Yard and unused lower-level tracks remain deferred.'])


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_ninth_fort_corridors.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print([dict(ref=c['track_ref'], points=len(c['points']), length_metres=c['source_length_metres'])
           for c in result['corridors']])
