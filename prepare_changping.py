"""Validate Changping Line geometry and preserve source bridge/tunnel boundaries."""
import argparse
import bisect
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from prepare_geometry import project

EXPECTED = '昌平西山口 十三陵景区 昌平 昌平东关 北邵洼 南邵 沙河高教园 沙河 巩华城 朱辛庄 生命科学园 西二旗 清河 朱房北 清河小营桥 学知园 六道口 学院桥 西土城 蓟门桥'.split()


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
    relation = objects['relation', 2111424]
    ways = [objects['way', m['ref']] for m in relation['members']
            if m['type'] == 'way' and m['role'] == '']
    assert all(w.get('tags', {}).get('railway') == 'subway' for w in ways)
    assert all(w.get('tags', {}).get('service') in (None, 'crossover') for w in ways)
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
    supplement = json.loads(path.with_name('nimby-osm-changping-1350622.json').read_text(encoding='utf-8'))
    extra = next(e for e in supplement['elements'] if e['type']=='node' and e['id']==13161970243)
    assert extra['tags']['name']=='朱房北'
    if not any(n['tags']['name']=='朱房北' for n in stops):
        stops.insert(next(i for i,n in enumerate(stops) if n['tags']['name']=='清河站')+1,extra)
    normalize = lambda name: {'清河站':'清河'}.get(name,name)
    if [normalize(n['tags']['name']) for n in stops] == list(reversed(EXPECTED)):
        stops.reverse()
    if [normalize(n['tags']['name']) for n in stops] != EXPECTED:
        raise ValueError('Unexpected Changping Line station order')
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
        if n['id'] in ids:
            route_index=ids.index(n['id']);s=chain[route_index];center=project(n);offset=0
        else:
            px,py=project(n);candidates=[]
            for j,(u,v) in enumerate(zip(route,route[1:])):
                dx,dy=v['x']-u['x'],v['y']-u['y'];den=dx*dx+dy*dy
                f=max(0,min(1,((px-u['x'])*dx+(py-u['y'])*dy)/den)) if den else 0
                cx,cy=u['x']+f*dx,u['y']+f*dy
                candidates.append((math.hypot(px-cx,py-cy),j,f,cx,cy))
            offset,route_index,f,cx,cy=min(candidates);assert offset<150, 'Station source too far from mainline'
            s=chain[route_index]+f*(chain[route_index+1]-chain[route_index]);center=(cx,cy)
        a, b = at(s-100), at(s+100)
        dx, dy = b['x']-a['x'], b['y']-a['y']
        length = math.hypot(dx, dy)
        half = 70/math.cos(math.radians(n['lat']))
        x, y = center
        station_depth = route[route_index]['depth']
        stations.append(dict(name=normalize(n['tags']['name']), osm_name=n['tags']['name'],
                             osm_id=n['id'], source_projection_offset_world=offset, latitude=n['lat'], longitude=n['lon'], x=x, y=y,
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
                    if station['depth'] < 0:
                        station['depth'] = next(d for d in (-1, -2, -3) if d not in occupied)
                    else:
                        station['surface_interchange_review'] = 'Retain source elevation and parallel platform separation; audit live native crossings before building'
                station['existing_platform_depths'] = sorted(occupied)
    return dict(source='https://api.openstreetmap.org/api/0.6/relation/2111424/full.json',
                attribution='© OpenStreetMap contributors, ODbL 1.0',
                supplemental_station_source='https://www.openstreetmap.org/node/13161970243',
                supplemental_station_note='朱房北 omitted from route stop members; projected independent station node onto mainline; source coordinate retained as latitude/longitude',
                source_sha256=hashlib.sha256(content).hexdigest(), relation_version=relation['version'],
                prepared_at=datetime.now(timezone.utc).isoformat(),
                projection='EPSG:3857; R=6378137', category='metro', track_type='Medium speed',
                scope='北京地铁昌平线昌平西山口—蓟门桥，完整20站',
                excluded_scope=['车辆段', '联络线', '库线'],
                official_scope='https://www.bjsubway.com/station/xltcx/changping/2013-10-26/358.html',
                code='bj-cp', color='#D47DAA',
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
    Path('data/changping_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(stations=len(plan['stations']), points=len(plan['route']), world_length=plan['world_length'])))
