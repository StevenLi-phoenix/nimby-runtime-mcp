"""Validate a directed NYC subway source against an explicit operator station mapping."""
import bisect
from datetime import datetime, timezone
import hashlib
import json
import math

from prepare_geometry import project

def source_depth(tags):
    level = int(tags.get('level', tags.get('layer', '0')))
    if tags.get('tunnel') == 'yes':
        level = min(level, -1)
    if tags.get('bridge') == 'yes':
        level = max(level, 1)
    return level


def direction(path, relation_id, reverse, *, route_ref, osm_stations, mta_stations):
    raw = path.read_bytes()
    objects = {(e['type'], e['id']): e for e in json.loads(raw)['elements']}
    relation = objects['relation', relation_id]
    if relation['tags'].get('route') != 'subway' or relation['tags'].get('ref') != route_ref:
        raise ValueError('Unexpected source route')
    ways = [objects['way', m['ref']] for m in relation['members']
            if m['type'] == 'way' and m['role'] in ('', 'forward', 'backward')]
    stops = [objects[m['type'], m['ref']] for m in relation['members']
             if m['role'].startswith('stop')]
    expected = osm_stations[::-1] if reverse else osm_stations
    if [s.get('tags', {}).get('name') for s in stops] != expected:
        raise ValueError('Complete ordered station list differs from expected MTA mapping')
    ids, edge_ways = [], []
    for i, way in enumerate(ways):
        if way.get('tags', {}).get('railway') != 'subway':
            raise ValueError(f"Non-subway track way {way['id']}")
        nodes = way['nodes'][:]
        if not ids:
            following = set(ways[1]['nodes'][::len(ways[1]['nodes']) - 1])
            if nodes[-1] not in following and nodes[0] in following:
                nodes.reverse()
            ids = [nodes[0]]
        if nodes[-1] == ids[-1]:
            nodes.reverse()
        if nodes[0] != ids[-1]:
            raise ValueError(f"Disconnected way {way['id']} after {ids[-1]}")
        ids.extend(nodes[1:])
        edge_ways.extend([way['id']] * (len(nodes) - 1))
    if len(ids) != len(set(ids)):
        raise ValueError('Repeated track nodes require branch/loop analysis')
    indices = [ids.index(s['id']) for s in stops]
    if indices != sorted(indices):
        raise ValueError('Stops do not follow track direction')
    route, chain = [], []
    for node_id in ids:
        node = objects['node', node_id]
        x, y = project(node)
        chain.append(chain[-1] + math.hypot(x-route[-1]['x'], y-route[-1]['y']) if route else 0.0)
        route.append(dict(osm_node_id=node_id, x=x, y=y,
                          latitude=node['lat'], longitude=node['lon'], chainage=chain[-1]))
    def interpolate(s):
        i = max(0, min(len(chain)-2, bisect.bisect_right(chain, s)-1))
        f = (s-chain[i])/(chain[i+1]-chain[i])
        return {k: route[i][k] + f*(route[i+1][k]-route[i][k]) for k in ('x', 'y')}
    stations = []
    for stop, index in zip(stops, indices):
        s = chain[index]
        a, b = interpolate(s-60), interpolate(s+60)
        dx, dy = b['x']-a['x'], b['y']-a['y']
        norm = math.hypot(dx, dy)
        half = 70/math.cos(math.radians(stop['lat']))
        way = objects['way', edge_ways[min(index, len(edge_ways)-1)]]
        depth = source_depth(way['tags'])
        incident = sorted({edge_ways[j] for j in (index-1, index) if 0 <= j < len(edge_ways)})
        incident_depths = sorted({source_depth(objects['way', wid]['tags']) for wid in incident})
        point = route[index]
        stations.append(dict(name=stop['tags']['name'],
            mta_name=mta_stations[osm_stations.index(stop['tags']['name'])],
            **point, platform_length_metres=140, source_way_id=way['id'],
            source_depth=depth, candidate_depth=max(-3, min(3, depth)),
            incident_source_way_ids=incident, incident_source_depths=incident_depths,
            layer_boundary_review_required=len(incident_depths) > 1,
            start=dict(x=point['x']-half*dx/norm, y=point['y']-half*dy/norm),
            end=dict(x=point['x']+half*dx/norm, y=point['y']+half*dy/norm)))
    segments = []
    for i, wid in enumerate(edge_ways):
        tags = objects['way', wid]['tags']
        segments.append(dict(from_node_id=ids[i], to_node_id=ids[i+1],
                             source_way_id=wid, source_depth=source_depth(tags),
                             candidate_depth=max(-3, min(3, source_depth(tags)))))
    return dict(relation_id=relation_id, source_url=f'https://api.openstreetmap.org/api/0.6/relation/{relation_id}/full.json',
        source_sha256=hashlib.sha256(raw).hexdigest(), source_version=relation['version'],
        fetched_at=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        source_tags=relation['tags'], stations=stations, route=route, segments=segments,
        ways=[dict(osm_way_id=w['id'], tags=w['tags']) for w in ways],
        world_length=chain[-1], actual_length_metres=sum((chain[i+1]-chain[i])*math.cos(math.radians(route[i]['latitude'])) for i in range(len(chain)-1)),
        validation=dict(ordered_stations_match=True, connected_track_chain=True,
                        station_count=len(stations), unique_track_nodes=len(ids)))

