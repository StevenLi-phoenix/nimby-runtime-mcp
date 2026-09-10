"""Prepare the complete closed Line 2 route from live OSM relation data."""
import json
import math
from pathlib import Path

from prepare_geometry import project

EXPECTED = '西直门 车公庄 阜成门 复兴门 长椿街 宣武门 和平门 前门 崇文门 北京站 建国门 朝阳门 东四十条 东直门 雍和宫 安定门 鼓楼大街 积水潭'.split()


def run():
    raw = json.loads(Path('work/osm-line2-outer.json').read_text(encoding='utf-8'))
    elements = {(e['type'], e['id']): e for e in raw['elements']}
    rel = elements['relation', 1667237]
    ids = []
    for member in rel['members']:
        if member['type'] != 'way':
            continue
        part = elements['way', member['ref']]['nodes'][:]
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
    result = dict(source='https://www.openstreetmap.org/relation/1667237',
                  attribution='© OpenStreetMap contributors, ODbL 1.0',
                  scope='北京地铁2号线完整18站双线环线', closed=True,
                  world_length=chain[-1], stations=stations, route=route)
    Path('data/line2_plan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(stations=len(stations), points=len(route), world_length=chain[-1])))


if __name__ == '__main__':
    run()
