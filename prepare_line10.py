"""Prepare the complete closed Line 10 route from live OSM relation data."""
import json
import os
import math
from pathlib import Path

from prepare_geometry import project

EXPECTED = '西局 泥洼 丰台站 首经贸 纪家庙 草桥 角门西 角门东 大红门 石榴庄 宋家庄 成寿寺 分钟寺 十里河 潘家园 劲松 双井 国贸 金台夕照 呼家楼 团结湖 农业展览馆 亮马桥 三元桥 太阳宫 芍药居 惠新西街南口 安贞门 北土城 健德门 牡丹园 西土城 知春路 知春里 海淀黄庄 苏州街 巴沟 火器营 长春桥 车道沟 慈寿寺 西钓鱼台 公主坟 莲花桥 六里桥'.split()


def run():
    raw = json.loads(Path(os.environ['TEMP'], 'nimby-osm-line10-1721075.json').read_text(encoding='utf-8'))
    elements = {(e['type'], e['id']): e for e in raw['elements']}
    rel = elements['relation', 1721075]
    ids = []
    for member in rel['members']:
        if member['type'] != 'way' or member['role'] != '':
            continue
        way = elements['way', member['ref']]
        assert way['tags'].get('railway') == 'subway' and way['tags'].get('tunnel') == 'yes'
        part = way['nodes'][:]
        if ids:
            if ids[-1] == part[-1]:
                part.reverse()
            assert ids[-1] == part[0], 'Disconnected source geometry'
            part = part[1:]
        ids.extend(part)
    assert ids[0] == ids[-1], 'Source route must close'
    route = []
    chain = [0.0]
    for node_id in ids:
        n = elements['node', node_id]
        x, y = project(n)
        route.append(dict(osm_id=node_id, x=x, y=y, depth=-1))
        if len(route) > 1:
            a, b = route[-2:]
            chain.append(chain[-1] + math.hypot(a['x']-b['x'], a['y']-b['y']))

    def at(s):
        s %= chain[-1]
        for i in range(len(chain)-1):
            if chain[i+1] >= s:
                t = (s-chain[i])/(chain[i+1]-chain[i])
                return {k: route[i][k]*(1-t)+route[i+1][k]*t for k in ('x', 'y')}
        raise AssertionError(s)

    stations = []
    seen = set()
    for member in rel['members']:
        if member['type'] != 'node' or member['role'] != 'stop' or member['ref'] in seen:
            continue
        seen.add(member['ref'])
        n = elements['node', member['ref']]
        index = ids.index(n['id'])
        x, y = project(n)
        s = chain[index]
        a, b = at(s-100), at(s+100)
        dx, dy = b['x']-a['x'], b['y']-a['y']
        length = math.hypot(dx, dy)
        half = 70/math.cos(math.radians(n['lat']))
        stations.append(dict(name=n['tags']['name'], osm_id=n['id'], latitude=n['lat'], longitude=n['lon'],
                             x=x, y=y, depth=-1, chainage=s, platform_length_metres=140,
                             start=dict(x=x-half*dx/length, y=y-half*dy/length),
                             end=dict(x=x+half*dx/length, y=y+half*dy/length)))
    assert [s['name'] for s in stations] == EXPECTED
    result = dict(source='https://www.openstreetmap.org/relation/1721075',
                  attribution='© OpenStreetMap contributors, ODbL 1.0',
                  scope='北京地铁10号线完整45站双线环线', closed=True,
                  world_length=chain[-1], stations=stations, route=route)
    Path('data/line10_plan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(stations=len(stations), points=len(route), world_length=chain[-1])))


if __name__ == '__main__':
    run()
