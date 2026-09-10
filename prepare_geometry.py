"""Prepare a continuous WGS84/World-Mercator route from OSM relation 1667140."""
import json
import math
from pathlib import Path

R=6378137.0
EXPECTED='苹果园 古城 八角游乐园 八宝山 玉泉路 五棵松 万寿路 公主坟 军事博物馆 木樨地 南礼士路 复兴门 西单 天安门西 天安门东 王府井 东单 建国门 永安里 国贸 大望路 四惠 四惠东 高碑店 传媒大学 双桥 管庄 八里桥 通州北苑 果园 九棵树 梨园 临河里 土桥 花庄 环球度假区'.split()

def project(n):
    lat=math.radians(n['lat'])
    return [R*math.radians(n['lon']),R*math.log(math.tan(math.pi/4+lat/2))]

def run():
    raw=json.loads(Path('work/osm-line1-full.json').read_text(encoding='utf-8'))
    elements={(e['type'],e['id']):e for e in raw['elements']}
    rel=elements['relation',1667140]
    route=[]
    for m in rel['members']:
        if m['type']!='way' or m['role']=='inactive':continue
        w=elements['way',m['ref']]
        ids=w['nodes'][:]
        if route:
            if route[-1]['osm_id']==ids[-1]:ids.reverse()
            if route[-1]['osm_id']!=ids[0]:raise ValueError(f'Disconnected OSM way {w["id"]}')
            ids=ids[1:]
        depth=1 if 'bridge' in w.get('tags',{}) else -1 if w.get('tags',{}).get('tunnel')=='yes' else 0
        for i in ids:
            n=elements['node',i];x,y=project(n)
            route.append({'osm_id':i,'x':x,'y':y,'latitude':n['lat'],'longitude':n['lon'],'depth':depth})
    cumulative=[0.0]
    for a,b in zip(route,route[1:]):cumulative.append(cumulative[-1]+math.hypot(a['x']-b['x'],a['y']-b['y']))
    def at(s):
        s=max(0,min(cumulative[-1],s))
        for i in range(len(route)-1):
            if cumulative[i+1]>=s:
                t=(s-cumulative[i])/(cumulative[i+1]-cumulative[i]);a,b=route[i:i+2]
                return {'x':a['x']+(b['x']-a['x'])*t,'y':a['y']+(b['y']-a['y'])*t}
        return {k:route[-1][k] for k in ['x','y']}
    stations=[]
    for m in rel['members']:
        if m['type']!='node' or 'stop' not in m['role']:continue
        n=elements['node',m['ref']];name=n.get('tags',{}).get('name','').replace('（1号线）','')
        if name not in EXPECTED:continue
        x,y=project(n)
        index=min(range(len(route)),key=lambda i:math.hypot(route[i]['x']-x,route[i]['y']-y))
        error=math.hypot(route[index]['x']-x,route[index]['y']-y)
        if error>30:raise ValueError(f'Station {name} is off route by {error} world metres')
        chainage=cumulative[index];scale=1/math.cos(math.radians(n['lat']))
        a,b=at(chainage-100),at(chainage+100);dx=b['x']-a['x'];dy=b['y']-a['y'];length=math.hypot(dx,dy)
        tangent=[dx/length,dy/length];half=60*scale
        stations.append({'name':name,'osm_id':n['id'],'latitude':n['lat'],'longitude':n['lon'],
                         'x':x,'y':y,'depth':route[index]['depth'],'chainage':chainage,
                         'platform_length_metres':120,'start':{'x':x-half*tangent[0],'y':y-half*tangent[1]},
                         'end':{'x':x+half*tangent[0],'y':y+half*tangent[1]},'osm_role':m['role']})
    stations.sort(key=lambda s:s['chainage'])
    if [s['name'] for s in stations]!=EXPECTED:raise ValueError('Station order differs from complete 36-station scope')
    result={'source':'https://www.openstreetmap.org/relation/1667140',
            'attribution':'© OpenStreetMap contributors, ODbL 1.0',
            'scope':'苹果园—环球度假区，含暂时停用的八角游乐园；不含福寿岭及支线',
            'coordinate_system':'WGS84 projected to spherical Web Mercator (R=6378137)',
            'stations':stations,'route':route}
    Path('data').mkdir(exist_ok=True)
    Path('data/line1_plan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'stations':len(stations),'route_points':len(route),'world_length':cumulative[-1]},indent=2))

if __name__=='__main__':run()
