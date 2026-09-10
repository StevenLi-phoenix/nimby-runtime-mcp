"""Build the geographic 36-station route through the persistent MCP client.

Run only in the dedicated empty world. Checkpoints contain native IDs; they must
not be reused after loading an older save. No save parsing or editing is used.
"""
import json
import math
import sys
from pathlib import Path
from session_call import call

ROOT=Path(__file__).resolve().parent
CHECKPOINT=ROOT/'work'/'line1-built.json'

def distance(a,b): return math.hypot(a['x']-b['x'],a['y']-b['y'])

def simplify(points,tolerance=8):
    if len(points)<3: return points
    a,b=points[0],points[-1];dx=b['x']-a['x'];dy=b['y']-a['y'];length=dx*dx+dy*dy
    deviations=[]
    for p in points[1:-1]:
        t=max(0,min(1,((p['x']-a['x'])*dx+(p['y']-a['y'])*dy)/length)) if length else 0
        deviations.append(math.hypot(p['x']-a['x']-t*dx,p['y']-a['y']-t*dy))
    index=max(range(len(deviations)),key=deviations.__getitem__)+1
    if deviations[index-1]<=tolerance and all(p.get('depth')==a.get('depth') for p in points):return [a,b]
    if deviations[index-1]<=tolerance:
        index=next((i for i in range(1,len(points)-1) if points[i]['depth']!=a['depth']),index)
    return simplify(points[:index+1],tolerance)[:-1]+simplify(points[index:],tolerance)

def run():
    if CHECKPOINT.exists():raise RuntimeError('Checkpoint exists; inspect it before resuming. Never duplicate construction.')
    plan=json.loads((ROOT/'data'/'line1_plan.json').read_text(encoding='utf-8'))
    state={'status':'building','plan':plan['scope'],'stations':[],'corridors':[],'turnbacks':[]}
    def save():CHECKPOINT.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    call('set_simulation_speed',speed=0)
    state['runtime']=call('runtime_status');save()
    for s in plan['stations']:
        # 140m platform leaves 20m clearance for the 120m consist.
        a={k:s[k]+(s['start'][k]-s[k])*7/6 for k in ['x','y']}
        b={k:s[k]+(s['end'][k]-s[k])*7/6 for k in ['x','y']}
        result=call('create_platform',start_x=a['x'],start_y=a['y'],end_x=b['x'],end_y=b['y'],depth=s['depth'])
        nodes=result['nodes']; platforms=[n for n in nodes if n['station_id']!='0']
        if len(platforms)!=4:raise RuntimeError(f'Unexpected platform nodes: {result}')
        byid={n['id']:n for n in platforms}
        p0=min(platforms,key=lambda n:distance(n,a))
        p1=byid[p0['next']]
        p2=next(n for n in platforms if n['id'] not in [p0['id'],p1['id']] and n['next'] in byid)
        p3=byid[p2['next']]
        record={**s,'native_station':p0['station_id'],'west_stop':p0['id'],'east_stop':p2['id'],
                'west_primary':p0['previous'],'east_primary':p1['next'],
                'west_secondary':p3['next'],'east_secondary':p2['previous'],'platform_nodes':[n['id'] for n in platforms]}
        state['stations'].append(record);save()
        call('rename_station',station_id=record['native_station'],name=s['name'])
        print(f"Station {len(state['stations'])}/36: {s['name']}",flush=True)
    route=plan['route'];chain=[0.0]
    for a,b in zip(route,route[1:]):chain.append(chain[-1]+distance(a,b))
    for first,second in zip(state['stations'],state['stations'][1:]):
        start=call('get_track_node',node_id=first['east_primary'])
        end=call('get_track_node',node_id=second['west_primary'])
        scale=1/math.cos(math.radians(first['latitude']))
        margin=160*scale
        points=[start]+[p for p,c in zip(route,chain) if first['chainage']+margin<c<second['chainage']-margin]+[end]
        points=simplify(points)
        current=start;created=[]
        for p in points[1:-1]:
            if distance(current,p)<40:continue
            result=call('extend_track',node_id=current['id'],end_x=p['x'],end_y=p['y'],depth=p['depth'])
            candidates=[n for n in result['nodes'] if n['id']!=current['id']]
            current=min(candidates,key=lambda n:distance(n,p))
            created.extend(n['id'] for n in candidates)
        result=call('connect_track_endpoints',start_node_id=current['id'],end_node_id=end['id'],dual=True)
        state['corridors'].append({'from':first['name'],'to':second['name'],'nodes':created,'connected':result});save()
        print(f"Corridor {len(state['corridors'])}/35: {first['name']} — {second['name']}",flush=True)
    # Both termini get 600m tails and native crossovers. Trains reverse at the
    # tail ends, then reach the opposite platform before starting the next trip.
    for s,side,sign in [(state['stations'][0],'west',-1),(state['stations'][-1],'east',1)]:
        start=call('get_track_node',node_id=s[f'{side}_primary'])
        paired=call('get_track_node',node_id=s[f'{side}_secondary'])
        dx=s['end']['x']-s['start']['x'];dy=s['end']['y']-s['start']['y'];length=math.hypot(dx,dy)
        scale=1/math.cos(math.radians(s['latitude']))
        x=start['x']+sign*dx/length*600*scale;y=start['y']+sign*dy/length*600*scale
        result=call('extend_track',node_id=start['id'],end_x=x,end_y=y,depth=s['depth'])
        ends=[n for n in result['nodes'] if n['id']!=start['id']]
        primary=min(ends,key=lambda n:math.hypot(n['x']-x,n['y']-y));secondary=next(n for n in ends if n['id']!=primary['id'])
        # Edge IDs denote the node whose previous edge is used.
        primary_edge=primary['id'] if primary['previous']!='0' else start['id']
        secondary_edge=secondary['id'] if secondary['previous']!='0' else paired['id']
        branch=call('create_track_branch',start_edge_id=primary_edge,start_position=.35,end_edge_id=secondary_edge,end_position=.35,depth=s['depth'])
        state['turnbacks'].append({'station':s['name'],'tail_nodes':ends,'branch':branch});save()
    if '--blueprints-only' in sys.argv:
        state['status']='blueprints-awaiting-budget-check';save()
        print('Blueprints ready; inspect normal construction cost before building.',flush=True)
        return
    verification=[i for s in state['stations'] for i in s['platform_nodes']]
    verification += [n['id'] for t in state['turnbacks'] for n in t['branch']['nodes']]
    state['build']=call('build_all_blueprints',verify_node_ids=verification);save()
    state['line']=call('create_line')['line'];save()
    line_id=state['line']['id']
    call('set_line_name',line_id=line_id,name='北京地铁1号线八通线',code='bj-1')
    for s in state['stations']:call('add_line_stop',line_id=line_id,platform_node_id=s['east_stop'])
    for s in reversed(state['stations']):call('add_line_stop',line_id=line_id,platform_node_id=s['west_stop'])
    state['line']=call('get_line',line_id=line_id);state['status']='built-awaiting-path-validation';save()
    print('Infrastructure and 72 directed stops ready; validate routing before fleet purchase.',flush=True)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run()
