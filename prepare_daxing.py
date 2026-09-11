"""Extract only the Daxing extension; existing Line 4 is a live connection anchor."""
import argparse
import bisect
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from prepare_geometry import project
from prepare_line4 import source_depth

EXPECTED = '天宫院 生物医药基地 义和庄 黄村火车站 黄村西大街 清源路 枣园 高米店南 高米店北 西红门 新宫 公益西桥'.split()


def prepare(path):
    content = path.read_bytes()
    objects = {(e['type'], e['id']): e for e in json.loads(content)['elements']}
    relation = objects['relation', 2083779]
    ways = [objects['way', m['ref']] for m in relation['members']
            if m['type'] == 'way' and m['role'] == '']
    assert all(w.get('tags', {}).get('railway') == 'subway' for w in ways)
    edges = {frozenset((a, b)): w for w in ways for a, b in zip(w['nodes'], w['nodes'][1:])}
    ids = list(ways[0]['nodes'])
    if ids[-1] not in (ways[1]['nodes'][0], ways[1]['nodes'][-1]):
        ids.reverse()
    for way in ways[1:]:
        part = list(way['nodes'])
        if part[-1] == ids[-1]:
            part.reverse()
        if part[0] != ids[-1]:
            raise ValueError(f"Disconnected OSM way {way['id']}")
        ids.extend(part[1:])
    all_stops = [objects['node', m['ref']] for m in relation['members']
                 if m['type'] == 'node' and m['role'].startswith('stop')]
    stops = [n for n in all_stops if n.get('tags', {}).get('name') in EXPECTED]
    assert [n['tags']['name'] for n in stops] == list(reversed(EXPECTED))
    stops.reverse()
    if ids.index(stops[0]['id']) > ids.index(stops[-1]['id']):
        ids.reverse()
    ids = ids[ids.index(stops[0]['id']):ids.index(stops[-1]['id'])+1]
    route, chain, segments = [], [], []
    for nid in ids:
        x, y = project(objects['node', nid])
        chain.append(0 if not route else chain[-1]+math.hypot(x-route[-1]['x'], y-route[-1]['y']))
        route.append(dict(osm_id=nid, x=x, y=y))
    for i, (a, b) in enumerate(zip(ids, ids[1:])):
        way = edges[frozenset((a, b))]
        assert way.get('tags', {}).get('service') is None, 'Exclude depot and storage tracks'
        depth = source_depth(way.get('tags', {}))
        route[i].update(depth=depth, source_way=way['id'])
        if segments and segments[-1]['source_way'] == way['id']:
            segments[-1].update(end_index=i+1, end_chainage=chain[i+1])
        else:
            segments.append(dict(source_way=way['id'], source_tags=way.get('tags', {}), depth=depth,
                                 start_index=i, end_index=i+1, start_chainage=chain[i], end_chainage=chain[i+1]))
    route[-1].update(depth=route[-2]['depth'], source_way=route[-2]['source_way'])

    def at(s):
        s = max(0, min(chain[-1], s))
        i = min(len(chain)-2, max(0, bisect.bisect_right(chain, s)-1))
        f = (s-chain[i])/(chain[i+1]-chain[i])
        return {k: route[i][k]*(1-f)+route[i+1][k]*f for k in ('x', 'y')}

    stations = []
    for node in stops:
        idx = ids.index(node['id']); s = chain[idx]
        a, b = at(s-100), at(s+100)
        dx, dy = b['x']-a['x'], b['y']-a['y']
        length = math.hypot(dx, dy); half = 70/math.cos(math.radians(node['lat']))
        x, y = project(node)
        stations.append(dict(name=node['tags']['name'], osm_name=node['tags']['name'], osm_id=node['id'],
            latitude=node['lat'], longitude=node['lon'], x=x, y=y, chainage=s,
            depth=route[idx]['depth'], source_depth=route[idx]['depth'], platform_length_metres=140,
            start=dict(x=x-half*dx/length, y=y-half*dy/length),
            end=dict(x=x+half*dx/length, y=y+half*dy/length),
            reuse_existing=node['tags']['name']=='公益西桥'))
    assert [s['name'] for s in stations] == EXPECTED
    assert [s['name'] for s in stations if s['depth'] == 1] == ['西红门']
    assert all(a['chainage'] < b['chainage'] for a, b in zip(stations, stations[1:]))
    return dict(source='https://api.openstreetmap.org/api/0.6/relation/2083779/full.json',
        attribution='© OpenStreetMap contributors, ODbL 1.0', source_sha256=hashlib.sha256(content).hexdigest(),
        relation_version=relation['version'], prepared_at=datetime.now(timezone.utc).isoformat(),
        projection='EPSG:3857; R=6378137', category='metro', track_type='Medium speed', closed=False,
        scope='大兴线11座新站，天宫院—新宫，接既有公益西桥；与既有4号线贯通运营',
        official_scope='https://www.mtr.bj.cn/service/line/line-4.html',
        existing_line_code='bj-4', color='#008E9C', excluded_scope=['车辆段', '联络线', '库线'],
        world_length=chain[-1], stations=stations, route=route, source_segments=segments,
        required_boundary_indices=sorted({i for segment in segments for i in (segment['start_index'], segment['end_index'])}),
        construction_ready=False, remaining_checks=['读取公益西桥实时端点，不重建该站', '沿现有站后端点接续',
            '西红门高架与桥隧过渡', '车站盘点与跨线交叉', '曲线平顺及建造检查', '天宫院站后折返'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot', type=Path)
    plan = prepare(parser.parse_args().snapshot)
    Path('data/daxing_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(new_stations=11, reused_stations=1, points=len(plan['route']), world_length=plan['world_length'])))
