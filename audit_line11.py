"""Partitioned live Line 11 curve, crossing and build audit."""
import json
from pathlib import Path
from session_call import call
from audit_crossings import native_crossings
from audit_line4 import curve_metrics

def run():
    stations=json.loads(Path('work/line11-built.json').read_text(encoding='utf-8'))['stations']
    network=call('get_track_network',seed_node_ids=[s['west_stop'] for s in stations]);ids={n['id'] for n in network['nodes']}
    assert len(ids)<5000
    existing={}
    for line_id in ['1125899906842625','1125899906973697','1125899907039233','1125899907104769','1125899907170305','1125899907301377','1125899907366913','1125899907432449','1125899907497985','1125899907563521','1125899907629057','1125899907694593','1125899907760129','1125899907825665','1125899907891201','1125899907956737','1125899908022273','1125899908087809','1125899908153345','1125899908218881','1125899908284417','1125899908349953']:
        line=call('get_line',line_id=line_id)
        part=call('get_track_network',seed_node_ids=[line['stops'][0]['node_id']])
        assert len(part['nodes'])<5000
        existing.update((n['id'],n) for n in part['nodes'])
    # Separate queries avoid truncating a growing world at the 5000-node limit.
    extra=call('get_track_network',seed_node_ids=['281475074031617'])
    existing.update((n['id'],n) for n in extra['nodes'])
    assert ids.isdisjoint(existing),'Unexpected cross-line topological connection'
    world=list(existing.values())+network['nodes']
    hits=native_crossings(world)
    cross=[h for h in hits if (h['a'] in ids)!=(h['b'] in ids)]
    metrics=[m for n in network['nodes'] if (m:=curve_metrics(n))]
    flags=[m for m in metrics if not m['junction'] and not m['platform'] and ((m['stretch'] or 0)>1.12 or (m['min_radius_world'] is not None and m['min_radius_world']<200))]
    by={n['id']:n for n in network['nodes']}
    station_issues=[dict(station=s['name'],node=i) for s in stations for i in s['platform_nodes'] if by[i]['station_id']!=s['native_station'] or by[i]['depth']!=s['depth']]
    assert all(b['depth']==n['depth'] for n in network['nodes'] for b in n['buildings'])
    result=dict(runtime=call('runtime_status'),network=network,existing_nodes=list(existing.values()),crossline=cross,internal_crossings=[h for h in hits if h['a'] in ids and h['b'] in ids],metrics=metrics,curve_flags=flags,station_issues=station_issues,checks=call('get_track_build_checks',node_ids=list(ids)))
    Path('work/line11-curve-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(nodes=len(ids),existing_nodes=len(existing),crossline=cross,curve_flags=flags,station_issues=station_issues,checks=result['checks']),ensure_ascii=True))

if __name__=='__main__':run()
