"""Prepare the complete Franklin Avenue Shuttle from an explicit OSM snapshot."""
import bisect
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from prepare_geometry import project

EXPECTED = ['Franklin Avenue', 'Park Place', 'Botanic Garden', 'Prospect Park']


def prepare(path):
    raw = path.read_bytes()
    objects = {(e['type'], e['id']): e for e in json.loads(raw)['elements']}
    relation = objects['relation', 6342928]
    ways = [objects['way', m['ref']] for m in relation['members']
            if m['type'] == 'way' and not m['role']]
    stops = [objects['node', m['ref']] for m in relation['members']
             if m['type'] == 'node' and m['role'] == 'stop']
    assert [n['tags']['name'] for n in stops] == EXPECTED
    ids = [stops[0]['id']]
    sources = []
    for way in ways:
        part = way['nodes'][:]
        if part[-1] == ids[-1]:
            part.reverse()
        assert part[0] == ids[-1], f"Disconnected way {way['id']}"
        ids.extend(part[1:])
        sources.extend([way] * (len(part)-1))
    assert ids[-1] == stops[-1]['id'] and len(ids) == len(set(ids))
    route, chain = [], [0.0]
    for i, node_id in enumerate(ids):
        node = objects['node', node_id]
        x, y = project(node)
        source = sources[min(i, len(sources)-1)]
        tags = source['tags']
        level = int(tags.get('level', tags.get('layer', '0')))
        depth = -1 if tags.get('tunnel') == 'yes' or level < 0 else 1 if tags.get('bridge') == 'yes' or level > 0 else 0
        if route:
            chain.append(chain[-1] + math.hypot(x-route[-1]['x'], y-route[-1]['y']))
        route.append(dict(osm_id=node_id, x=x, y=y, depth=depth,
                          chainage=chain[-1], source_way=source['id'], source_tags=tags))

    def at(s):
        i = min(len(route)-2, max(0, bisect.bisect_right(chain, s)-1))
        f = (s-chain[i])/(chain[i+1]-chain[i])
        return {k: route[i][k]*(1-f)+route[i+1][k]*f for k in ('x','y')}

    stations = []
    for node in stops:
        i = ids.index(node['id']); s = chain[i]
        a,b = at(s-60),at(s+60)
        dx,dy = b['x']-a['x'],b['y']-a['y']; length=math.hypot(dx,dy)
        x,y = project(node); half=70/math.cos(math.radians(node['lat']))
        stations.append(dict(name=node['tags']['name'], osm_id=node['id'],
            latitude=node['lat'], longitude=node['lon'], x=x,y=y,chainage=s,
            depth=route[i]['depth'],platform_length_metres=140,
            start=dict(x=x-half*dx/length,y=y-half*dy/length),
            end=dict(x=x+half*dx/length,y=y+half*dy/length)))
    return dict(name='NYC Franklin Avenue Shuttle',code='nyc-s',closed=False,
        source='https://api.openstreetmap.org/api/0.6/relation/6342928/full.json',
        source_version=relation['version'],source_sha256=hashlib.sha256(raw).hexdigest(),
        fetched_at=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
        attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright',
        projection='EPSG:3857, R=6378137',track_type='Medium speed',
        scope='Complete four-station service, double track and station-after turnbacks.',
        adaptations=['140 m platforms and Kayou 231 six-car substitute fleet.',
            'Double track replaces the real northern single track.',
            'Positive embankments and bridges use depth=1; below-grade level=-2 cuts and tunnels use depth=-1 because the game has no open-cut terrain interface.'],
        stations=stations,route=route,world_length=chain[-1])


if __name__ == '__main__':
    plan=prepare(Path(sys.argv[1]))
    Path('data/nyc_s_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(stations=plan['stations'],nodes=len(plan['route']),world_length=plan['world_length'])))
