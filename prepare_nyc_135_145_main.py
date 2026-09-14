"""Plan four shared main tracks with explicit source junction controls."""
import json
import math
from pathlib import Path
from shapely.geometry import LineString, Point


def prepare():
    survey = json.loads(Path('data/nyc_135_145_approach_survey.json').read_bytes())
    topology = json.loads(Path('data/nyc_135_145_junction_survey.json').read_bytes())
    network = json.loads(Path('work/nyc-135-145-live.json').read_bytes())
    nodes = {n['id']: n for n in network['nodes']}
    scale = survey['scale']; corridors = []
    for route in survey['routes']:
        if route['end_depth'] != -2:
            continue
        coordinates = []; boundaries = []; distance = 0
        for segment in route['segments']:
            if coordinates and segment['depth'] != previous_depth:
                boundaries.append(distance)
            coordinates.extend(segment['points'] if not coordinates else segment['points'][1:])
            distance += LineString(segment['points']).length*scale
            previous_depth = segment['depth']
        assert len(boundaries) == 1
        line = LineString(coordinates); total = line.length*scale; boundary = boundaries[0]
        junctions = [dict(node_id=j['node_id'], chainage_metres=line.project(Point(j['x'], j['y']))*scale)
                     for j in topology['junctions'] if line.distance(Point(j['x'], j['y']))*scale < .001]
        transition_half = min(35, boundary*.45, (total-boundary)*.45,
                              *[abs(j['chainage_metres']-boundary)*.45 for j in junctions])
        cuts = [0, total, boundary-transition_half, boundary+transition_half] + [j['chainage_metres'] for j in junctions]
        assert all(0 <= d <= total for d in cuts)
        cuts.extend(d for d in range(50, int(total), 50) if min(abs(d-z) for z in cuts) > 15)
        cuts = sorted(set(cuts)); a = nodes[route['start_node_id']]; b = nodes[route['end_node_id']]
        start = line.interpolate(0); end = line.interpolate(line.length); points = []
        for d in cuts:
            q = line.interpolate(d/scale)
            fa = max(0, 1-d/100); fa = fa*fa*(3-2*fa)
            fb = max(0, 1-(total-d)/100); fb = fb*fb*(3-2*fb)
            point = dict(x=q.x+fa*(a['x']-start.x)+fb*(b['x']-end.x),
                         y=q.y+fa*(a['y']-start.y)+fb*(b['y']-end.y),
                         depth=-1 if d < boundary else -2, chainage_metres=d)
            for junction in junctions:
                if abs(d-junction['chainage_metres']) < .001:
                    point['source_junction_node_id'] = junction['node_id']
            points.append(point)
        if route['start_track_ref'] == '1':
            # Native splines narrow the gap near the first Concourse fork.
            for index, shift in [(3, .15), (4, .30), (5, .30), (6, .15)]:
                a, b = points[index-1], points[index+1]
                dx, dy = b['x']-a['x'], b['y']-a['y']; length = math.hypot(dx, dy)
                points[index]['x'] -= dy/length*shift/scale
                points[index]['y'] += dx/length*shift/scale
        corridors.append(dict(track_ref=route['start_track_ref'],start_node_id=a['id'],end_node_id=b['id'],
                              source_way_ids=[s['way_id'] for s in route['segments']],points=points,
                              source_boundary_metres=boundary,junctions=junctions))
    lines = {c['track_ref']: LineString([(q['x'],q['y']) for q in c['points']]) for c in corridors}
    gaps = {a+'-'+b: lines[a].distance(lines[b])*scale for a,b in [('1','3'),('3','4'),('4','2')]}
    return dict(source='data/nyc_135_145_approach_survey.json', attribution=survey['attribution'],scale=scale,
                corridors=corridors,candidate_gaps=gaps,stage='candidate_native_curve_review_pending',
                pending='Concourse branches must attach to the three recorded shared junction controls.')


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_135_145_main_corridors.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(gaps=result['candidate_gaps'],tracks=[dict(ref=c['track_ref'],points=len(c['points']),
                           boundary=c['source_boundary_metres'],junctions=c['junctions']) for c in result['corridors']])))
