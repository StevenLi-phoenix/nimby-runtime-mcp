"""Create a reviewable NYC service inventory from an OSM JSON snapshot.

This is discovery data, not a construction plan or proof of operation.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def prepare(path):
    raw = path.read_bytes()
    source = json.loads(raw)
    if source.get('remark'):
        raise ValueError(f"Incomplete Overpass response: {source['remark']}")
    services = []
    for relation in source['elements']:
        tags = relation.get('tags', {})
        if relation['type'] != 'relation' or tags.get('route_master') != 'subway':
            continue
        services.append({
            'osm_relation_id': relation['id'],
            'osm_version': relation.get('version'),
            'source_tags': tags,
            'routes': [member for member in relation.get('members', [])
                       if member['type'] == 'relation'],
            'status': 'discovered_requires_operator_and_geometry_validation',
        })
    if not services:
        raise ValueError('No subway route masters found; refuse an empty inventory')
    return {
        'scope': 'New York City Subway: full network, shared infrastructure and service patterns',
        'stage': 'discovery_only',
        'operator_reference': 'https://www.mta.info/map/5256',
        'discovery_index': 'https://wiki.openstreetmap.org/wiki/New_York_City_Subway',
        'source_url': 'https://api.openstreetmap.org/api/0.6/relations.json?relations=' + ','.join(str(s['osm_relation_id']) for s in services),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'source_timestamp': source.get('osm3s', {}).get('timestamp_osm_base'),
        'fetched_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
        'attribution': '© OpenStreetMap contributors; https://www.openstreetmap.org/copyright',
        'services': sorted(services, key=lambda item: (item['source_tags'].get('ref', ''), item['osm_relation_id'])),
        'construction_gates': [
            'Match operator map and distinguish regular, express, branch and night patterns',
            'Fetch route geometry; validate ordered stops and continuous track graph',
            'Deduplicate shared physical ways before creating infrastructure',
            'Check local/express tracks, junctions, bridge/tunnel layers and interchange station ownership',
            'Read current world and preserve player changes before every construction batch',
            'Verify native construction, complete round trips and terminal reversals',
        ],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/nyc_network_inventory.json'))
    args = parser.parse_args()
    inventory = prepare(args.snapshot)
    args.output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'services': len(inventory['services']), 'output': str(args.output)}))
