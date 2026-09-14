"""Index NYC route members without treating unverified ways as built tracks."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def prepare(inventory_path, snapshot_path):
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    raw = snapshot_path.read_bytes()
    snapshot = json.loads(raw)
    if snapshot.get('remark'):
        raise ValueError(snapshot['remark'])
    relations = {e['id']: e for e in snapshot['elements'] if e['type'] == 'relation'}
    parents = defaultdict(list)
    for service in inventory['services']:
        for child in service['routes']:
            parents[child['ref']].append(service['osm_relation_id'])
    missing = set(parents) - set(relations)
    if missing:
        raise ValueError(f'Missing route relations: {sorted(missing)}')
    routes, way_routes, issues = [], defaultdict(set), []
    for rid in sorted(parents):
        relation = relations[rid]
        tags = relation.get('tags', {})
        errors = []
        if tags.get('route') != 'subway':
            errors.append('route_tag_is_not_subway')
        if tags.get('network:wikidata') != 'Q7733':
            errors.append('network_requires_manual_validation')
        # Empty/forward/backward way roles are candidates until way tags and
        # continuous node geometry have been read. Platform polygons are excluded.
        ways = [m for m in relation['members'] if m['type'] == 'way'
                and m['role'] in ('', 'forward', 'backward')]
        stops = [m for m in relation['members'] if m['role'].startswith('stop')]
        if not ways or not stops:
            errors.append('missing_track_or_stop_members')
        for member in ways:
            way_routes[member['ref']].add(rid)
        routes.append(dict(osm_relation_id=rid, osm_version=relation.get('version'),
                           parent_master_ids=parents[rid], source_tags=tags,
                           ordered_stop_members=stops, ordered_track_candidates=ways,
                           issues=errors, geometry_verified=False))
        if errors:
            issues.append(dict(osm_relation_id=rid, issues=errors))
    shared = []
    for wid, route_ids in sorted(way_routes.items()):
        service_ids = sorted({p for rid in route_ids for p in parents[rid]})
        if len(service_ids) > 1:
            shared.append(dict(osm_way_id=wid, route_ids=sorted(route_ids),
                               master_ids=service_ids))
    return dict(stage='member_topology_only', inventory_source=inventory['source_url'],
                source_url='https://api.openstreetmap.org/api/0.6/relations.json?relations=' + ','.join(map(str, sorted(parents))),
                source_sha256=hashlib.sha256(raw).hexdigest(),
                attribution=inventory['attribution'], routes=routes,
                shared_track_candidates=shared, issues=issues,
                counts=dict(routes=len(routes), unique_track_candidates=len(way_routes),
                            shared_between_masters=len(shared), flagged_routes=len(issues)),
                limitations=['Shared IDs prove common source members, not complete physical track coverage.',
                             'Distinct way IDs may represent adjacent local/express tracks or opposite directions.',
                             'Station ownership, layer and junction connectivity need full geometry and live-world inspection.',
                             'Flagged source relations must not enter automatic construction.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--inventory', type=Path, default=Path('data/nyc_network_inventory.json'))
    parser.add_argument('--output', type=Path, default=Path('data/nyc_route_index.json'))
    args = parser.parse_args()
    result = prepare(args.inventory, args.snapshot)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['counts']))
    print(json.dumps(result['issues']))
