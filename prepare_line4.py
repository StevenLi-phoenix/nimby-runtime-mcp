"""Validate Line 4 geometry and preserve source bridge/tunnel boundaries."""
import argparse
import bisect
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from prepare_geometry import project

EXPECTED = '公益西桥 角门西 马家堡 北京南站 陶然亭 菜市口 宣武门 西单 灵境胡同 西四 平安里 新街口 西直门 动物园 国家图书馆 魏公村 人民大学 海淀黄庄 中关村 北京大学东门 圆明园 西苑 北宫门 安河桥北'.split()


def source_depth(tags):
    layer = int(tags.get('layer', '0'))
    if tags.get('tunnel') not in (None, 'no', 'building_passage'):
        return -1
    if tags.get('bridge') not in (None, 'no') or layer > 0:
        return 1
    return 0


def prepare(path, survey_path=None):
    content = path.read_bytes()
    raw = json.loads(content)
    objects = {(e['type'], e['id']): e for e in raw['elements']}
    relation = objects['relation', 2082917]
    ways = [objects['way', m['ref']] for m in relation['members']
            if m['type'] == 'way' and m['role'] == '']
    assert all(w.get('tags', {}).get('railway') == 'subway' for w in ways)
    terminal_stops = [m['ref'] for m in relation['members']
                      if m['type'] == 'node' and m['role'].startswith('stop')]
    # The public Gongyixiqiao short-turn platform is tagged siding in OSM.
    # Retain that route-member platform track, not unrelated storage tracks.
    assert all(w.get('tags', {}).get('service') in (None, 'crossover') or
               (w.get('tags', {}).get('service') == 'siding' and
                terminal_stops[0] in w['nodes']) for w in ways)
    edge_sources = {}
    for way in ways:
        for a, b in zip(way['nodes'], way['nodes'][1:]):
            edge_sources[frozenset((a, b))] = way
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
    stops = [objects['node', m['ref']] for m in relation['members']
             if m['type'] == 'node' and m['role'].startswith('stop')]
    normalize = lambda name: name
    if [normalize(n['tags']['name']) for n in stops] == list(reversed(EXPECTED)):
        stops.reverse()
    if [normalize(n['tags']['name']) for n in stops] != EXPECTED:
        raise ValueError('Unexpected Line 4 station order')
    if ids.index(stops[0]['id']) > ids.index(stops[-1]['id']):
        ids.reverse()
    route, chain = [], []
    for node_id in ids:
        n = objects['node', node_id]
        x, y = project(n)
        chain.append(0 if not route else chain[-1] + math.hypot(x-route[-1]['x'], y-route[-1]['y']))
        route.append(dict(osm_id=node_id, x=x, y=y, depth=-1))
    segments = []
    for i, (a, b) in enumerate(zip(ids, ids[1:])):
        way = edge_sources[frozenset((a, b))]
        depth = source_depth(way.get('tags', {}))
        route[i]['depth'] = depth
        route[i]['source_way'] = way['id']
        if segments and segments[-1]['source_way'] == way['id']:
            segments[-1]['end_chainage'] = chain[i+1]
            segments[-1]['end_index'] = i+1
        else:
            segments.append(dict(source_way=way['id'], depth=depth,
                                 source_tags=way.get('tags', {}), start_index=i, end_index=i+1,
                                 start_chainage=chain[i], end_chainage=chain[i+1]))
    route[-1]['depth'] = route[-2]['depth']
    route[-1]['source_way'] = route[-2]['source_way']

    def at(s):
        s = max(0, min(chain[-1], s))
        i = min(len(chain)-2, max(0, bisect.bisect_right(chain, s)-1))
        f = (s-chain[i])/(chain[i+1]-chain[i])
        return {k: route[i][k]*(1-f)+route[i+1][k]*f for k in ('x', 'y')}

    stations = []
    for n in stops:
        s = chain[ids.index(n['id'])]
        a, b = at(s-100), at(s+100)
        dx, dy = b['x']-a['x'], b['y']-a['y']
        length = math.hypot(dx, dy)
        half = 70/math.cos(math.radians(n['lat']))
        x, y = project(n)
        station_depth = route[ids.index(n['id'])]['depth']
        stations.append(dict(name=normalize(n['tags']['name']), osm_name=n['tags']['name'],
                             osm_id=n['id'], latitude=n['lat'], longitude=n['lon'], x=x, y=y,
                             depth=station_depth, chainage=s, platform_length_metres=140,
                             start=dict(x=x-half*dx/length, y=y-half*dy/length),
                             end=dict(x=x+half*dx/length, y=y+half*dy/length)))
    assert all(a['chainage'] < b['chainage'] for a, b in zip(stations, stations[1:]))
    if survey_path:
        survey = json.loads(survey_path.read_text(encoding='utf-8'))
        live = {s['name']: s for s in survey['stations']}
        for station in stations:
            current = live[station['name']]
            assert len(current['matches']) <= 1
            station['source_depth'] = station['depth']
            if current['matches']:
                match = current['matches'][0]
                station['interchange_station_id'] = match['id']
                occupied = {n['depth'] for n in current['nearby']['nodes']
                            if n['station_id'] == match['id']}
                assert occupied, 'Matched station has no nearby platforms'
                if station['depth'] in occupied:
                    assert station['depth'] < 0, 'Surface interchange requires individual design'
                    station['depth'] = next(d for d in (-1, -2, -3) if d not in occupied)
                station['existing_platform_depths'] = sorted(occupied)
    return dict(source='https://api.openstreetmap.org/api/0.6/relation/2082917/full.json',
                attribution='© OpenStreetMap contributors, ODbL 1.0',
                source_sha256=hashlib.sha256(content).hexdigest(), relation_version=relation['version'],
                prepared_at=datetime.now(timezone.utc).isoformat(),
                projection='EPSG:3857; R=6378137', category='metro', track_type='Medium speed',
                scope='北京地铁4号线公益西桥—安河桥北，24站；按顺序先建设4号线，大兴线随后接续',
                excluded_scope=['车辆段', '联络线', '库线'],
                official_scope='https://www.mtr.bj.cn/service/line/line-4.html',
                code='bj-4', color='#008E9C',
                closed=False, world_length=chain[-1], stations=stations, route=route,
                source_segments=segments,
                elevation_policy='OSM桥隧类别映射为地下-1/地面0/高架1；换乘层级须实时审计后确定；保留源layer用于交叉复核；密集控制点平顺优先',
                required_boundary_indices=sorted({i for s in segments for i in (s['start_index'], s['end_index'])}),
                construction_ready=False,
                remaining_checks=['实时既有轨道相交审计', '终点折返进路', '换乘位置及距离', '原生预算及全局蓝图盘点'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--survey', type=Path)
    args = parser.parse_args()
    plan = prepare(args.snapshot, args.survey)
    Path('data/line4_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(stations=len(plan['stations']), points=len(plan['route']), world_length=plan['world_length'])))
