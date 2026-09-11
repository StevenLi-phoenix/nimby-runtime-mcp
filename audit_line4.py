"""Read-only Line 4 blueprint and native curve audit; not a build authorization."""
import json
import math
from pathlib import Path

from audit_crossings import native_crossings
from session_call import call


def curve_metrics(node):
    points = node.get('curve', [])
    if len(points) < 2:
        return None
    length = sum(math.dist(a,b) for a,b in zip(points,points[1:]))
    chord = math.dist(points[0],points[-1])
    radii = []
    turns = []
    for a,b,c in zip(points,points[1:],points[2:]):
        u = b[0]-a[0],b[1]-a[1]
        v = c[0]-b[0],c[1]-b[1]
        cross = u[0]*v[1]-u[1]*v[0]
        if abs(cross) > 1e-6:
            radii.append(math.dist(a,b)*math.dist(b,c)*math.dist(a,c)/(2*abs(cross)))
            turns.append(1 if cross > 0 else -1)
    return dict(id=node['id'], x=node['x'], y=node['y'], length_world=length,
                stretch=length/chord if chord > 1e-6 else None,
                min_radius_world=min(radii) if radii else None,
                curvature_sign_changes=sum(a!=b for a,b in zip(turns,turns[1:])),
                junction=node.get('branch_parent','0')!='0' or bool(node.get('branches')),
                platform=node['station_id']!='0')


def run():
    stations = json.loads(Path('work/line4-built.json').read_text(encoding='utf-8'))['stations']
    network = call('get_track_network',seed_node_ids=[s['west_stop'] for s in stations])
    ids = {n['id'] for n in network['nodes']}
    lines = [call('get_line',line_id=i) for i in ['1125899906842625','1125899906973697',
             '1125899907039233','1125899907104769','1125899907170305','1125899907301377','1125899907366913']]
    world = call('get_track_network',seed_node_ids=[s['west_stop'] for s in stations]+[l['stops'][0]['node_id'] for l in lines])
    hits = native_crossings(world['nodes'])
    crossline = [h for h in hits if (h['a'] in ids)!=(h['b'] in ids)]
    metrics = [m for n in network['nodes'] if (m:=curve_metrics(n)) is not None]
    flags = [m for m in metrics if not m['junction'] and not m['platform'] and
             ((m['stretch'] or 0)>1.12 or (m['min_radius_world'] is not None and m['min_radius_world']<200))]
    byid = {n['id']:n for n in network['nodes']}
    station_issues = [dict(station=s['name'],node=n) for s in stations for n in s['nodes']
                      if n in byid and byid[n]['depth']!=s['depth']]
    result = dict(runtime=call('runtime_status'),network=network,world=world,
                  checks=call('get_track_build_checks',node_ids=list(ids)),
                  crossline_crossings=crossline,internal_crossings=[h for h in hits if h['a'] in ids and h['b'] in ids],
                  curve_flags=flags,curve_metrics=metrics,station_layer_issues=station_issues)
    Path('work/line4-curve-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(nodes=len(ids),world_nodes=len(world['nodes']),crossline=crossline,
         curve_flags=len(flags),station_layer_issues=station_issues,checks=result['checks']),ensure_ascii=True))


if __name__ == '__main__':
    run()
