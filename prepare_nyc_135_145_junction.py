"""Trace shared OSM node topology for the 135th–145th Street IND junction."""
import heapq
import json
import math
from collections import defaultdict
from pathlib import Path


def prepare():
    source = json.loads(Path('data/nyc_harlem_source.json').read_bytes())
    station = json.loads(Path('data/nyc_145_cross_sections.json').read_bytes())
    ways = {w['osm_way_id']: w for w in source['ways']}
    points = {i: p for w in source['ways'] for i, p in zip(w['node_ids'], w['points'])}
    graph = defaultdict(list)
    for w in source['ways']:
        tags = w['tags']
        if tags.get('railway') != 'subway' or not tags.get('name', '').startswith('IND ') or tags.get('service'):
            continue
        for a, b in zip(w['node_ids'], w['node_ids'][1:]):
            distance = math.hypot(points[a]['x']-points[b]['x'], points[a]['y']-points[b]['y'])
            graph[a].append((b, distance, w['osm_way_id']))
            graph[b].append((a, distance, w['osm_way_id']))
    starts = {}
    for ref, way_id in [('1', 813746959), ('2', 813746964), ('3', 813746961), ('4', 813746962)]:
        w = ways[way_id]
        starts[ref] = max([w['node_ids'][0], w['node_ids'][-1]], key=lambda i: points[i]['y'])

    def trace(start, end):
        queue = [(0, start)]; costs = {start: 0}; previous = {}
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != costs[node]:
                continue
            if node == end:
                path = [node]; edge_ways = []
                while node != start:
                    node, way = previous[node]; path.append(node); edge_ways.append(way)
                return distance, path[::-1], edge_ways[::-1]
            for neighbor, length, way in graph[node]:
                candidate = distance+length
                if candidate < costs.get(neighbor, float('inf')):
                    costs[neighbor] = candidate; previous[neighbor] = (node, way)
                    heapq.heappush(queue, (candidate, neighbor))
        return None

    routes = []
    for level in station['levels']:
        for track in level['tracks']:
            w = ways[track['source_way_id']]
            end = min([w['node_ids'][0], w['node_ids'][-1]], key=lambda i: points[i]['y'])
            candidates = [(trace(start, end), ref) for ref, start in starts.items()]
            candidates = [(v, ref) for v, ref in candidates if v is not None]
            assert candidates, track
            (distance, nodes, edges), ref = min(candidates, key=lambda pair: pair[0][0])
            runs = []
            for a, b, way in zip(nodes, nodes[1:], edges):
                if not runs or runs[-1]['way_id'] != way:
                    runs.append(dict(way_id=way, tags=ways[way]['tags'], node_ids=[a]))
                runs[-1]['node_ids'].append(b)
            routes.append(dict(start_track_ref=ref, target_way_id=w['osm_way_id'], target_track_ref=w['tags']['railway:track_ref'],
                               target_depth=level['depth'], length_metres=distance*station['scale'],
                               source_node_ids=nodes, segments=runs))
    used = {i for route in routes for i in route['source_node_ids']}
    junctions = [dict(node_id=i, **points[i], neighbors=[dict(node_id=n, way_id=w) for n, _, w in graph[i]])
                 for i in sorted(used) if len(graph[i]) > 2]
    return dict(source='data/nyc_harlem_source.json', attribution=source['attribution'], scale=station['scale'],
                routes=routes, junctions=junctions,
                scope='Main-track graph between source boundaries; native station approach clipping remains pending.',
                stage='source_topology_survey_native_junction_geometry_pending',
                exclusions='Service sidings, yards and crossover ways excluded from these main-route traces.')


if __name__ == '__main__':
    result = prepare()
    Path('data/nyc_135_145_junction_survey.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps([dict(start=r['start_track_ref'], target=r['target_track_ref'], depth=r['target_depth'],
                           ways=[s['way_id'] for s in r['segments']], length_metres=r['length_metres']) for r in result['routes']]))
    print('junctions', len(result['junctions']))
