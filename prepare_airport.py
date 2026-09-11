"""Prepare both complete Capital Airport Express paths, including terminal reversals."""
import hashlib
import json
import math
import os
from pathlib import Path

from prepare_geometry import project

EXPECTED = {
    2062998: ['北新桥', '东直门', '三元桥', '首都机场3号航站楼', '首都机场2号航站楼'],
    2062999: ['首都机场2号航站楼', '三元桥', '东直门', '北新桥'],
}


def prepare_path(rid):
    path = Path(os.environ['TEMP'], f'nimby-osm-airport-{rid}.json')
    content = path.read_bytes()
    raw = json.loads(content)
    elements = {(e['type'], e['id']): e for e in raw['elements']}
    relation = elements['relation', rid]
    ways = [elements['way', m['ref']] for m in relation['members']
            if m['type'] == 'way' and m['role'] == '']
    ids, edges = [], []
    for i, way in enumerate(ways):
        part = way['nodes'][:]
        if not ids:
            if part[0] in ways[i + 1]['nodes']:
                part.reverse()
        elif ids[-1] == part[-1]:
            part.reverse()
        assert not ids or ids[-1] == part[0], f'Disconnected way {way["id"]}'
        tags = way['tags']
        assert tags.get('railway') == 'subway'
        assert tags.get('service') in (None, 'crossover'), 'Exclude depot/storage tracks'
        depth = -1 if tags.get('tunnel') == 'yes' else 1 if tags.get('bridge') else 0
        edges.extend(dict(osm_way=way['id'], depth=depth, source_tags=tags,
                          from_osm=a, to_osm=b) for a, b in zip(part, part[1:]))
        ids.extend(part if not ids else part[1:])
    route, chainage = [], 0.0
    for i, node_id in enumerate(ids):
        n = elements['node', node_id]
        x, y = project(n)
        if route:
            chainage += math.hypot(x-route[-1]['x'], y-route[-1]['y'])
        route.append(dict(osm_id=node_id, x=x, y=y, chainage=chainage))
    stops = []
    last = -1
    for m in relation['members']:
        if m['type'] != 'node' or m['role'] != 'stop':
            continue
        n = elements['node', m['ref']]
        index = ids.index(n['id'], last + 1)
        last = index
        stops.append(dict(name=n['tags']['name'], osm_id=n['id'], route_index=index,
                          latitude=n['lat'], longitude=n['lon'], **{k: route[index][k] for k in ['x', 'y', 'chainage']}))
    assert [s['name'] for s in stops] == EXPECTED[rid]
    assert len(edges) == len(route)-1
    return dict(source=f'https://www.openstreetmap.org/relation/{rid}',
                source_sha256=hashlib.sha256(content).hexdigest(), relation_version=relation['version'],
                route=route, edges=edges, stops=stops, world_length=chainage)


def run():
    outbound, inbound = [prepare_path(r) for r in EXPECTED]
    existing = json.loads(Path('work/airport-existing-world.json').read_text(encoding='utf-8'))
    inventory = existing['inventory']['stations']
    stations = []
    for stop in outbound['stops']:
        i = stop['route_index']
        # At T3 the source doubles back on its station approach. Use arrival tangent.
        route = outbound['route']
        a, b = (route[i-1], route[i]) if i else (route[0], route[1])
        dx, dy = b['x']-a['x'], b['y']-a['y']
        norm = math.hypot(dx, dy)
        half = 70/math.cos(math.radians(stop['latitude']))
        depth = 1 if stop['name'] == '首都机场3号航站楼' else -1
        matches = [s for s in inventory if s['name'] == stop['name']]
        assert len(matches) <= 1
        if matches:
            # Separate airport platforms from existing underground cross-lines.
            depth = -2
        stations.append(dict(**stop, depth=depth, platform_length_metres=140,
                             interchange_station_id=matches[0]['id'] if matches else None,
                             start=dict(x=stop['x']-half*dx/norm, y=stop['y']-half*dy/norm),
                             end=dict(x=stop['x']+half*dx/norm, y=stop['y']+half*dy/norm)))
    result = dict(scope='首都机场线最新完整5站，含北新桥延伸；T3、T2站内折返',
                  attribution='© OpenStreetMap contributors, ODbL 1.0',
                  official_scope='https://www.bcia.com.cn/dtjcx.html',
                  projection='EPSG:3857, spherical Web Mercator metres',
                  layer_policy='保留桥隧类别；OSM layer 是相对叠放，映射为游戏 -1/0/1，既有换乘交叉使用 -2',
                  stations=stations, outbound=outbound, inbound=inbound,
                  operating_order=EXPECTED[2062998]+EXPECTED[2062999][1:],
                  terminal_reversals=['首都机场3号航站楼', '首都机场2号航站楼', '北新桥'])
    Path('data/airport_plan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(stations=len(stations), outbound_points=len(outbound['route']),
                          inbound_points=len(inbound['route'])), ensure_ascii=False))


if __name__ == '__main__':
    run()
