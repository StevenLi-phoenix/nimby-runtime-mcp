"""Prepare the G corridor with explicit L interchange and F shared-track candidates."""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_nyc_direction import direction

OSM_STATIONS = [
    'Court Square', '21st Street', 'Greenpoint Avenue', 'Nassau Avenue',
    'Metropolitan Avenue', 'Broadway', 'Flushing Avenue',
    'Myrtle–Willoughby Avenues', 'Bedford–Nostrand Avenues', 'Classon Avenue',
    'Clinton–Washington Avenues', 'Fulton Street', 'Hoyt–Schermerhorn Streets',
    'Bergen Street', 'Carroll Street', 'Smith–9th Streets', '4th Avenue',
    '7th Avenue', '15th Street–Prospect Park', 'Fort Hamilton Parkway', 'Church Avenue',
]
MTA_STATIONS = [
    'Court Sq', '21 St', 'Greenpoint Av', 'Nassau Av', 'Metropolitan Av',
    'Broadway', 'Flushing Av', 'Myrtle Willoughby Avs', 'Bedford-Nostrand Avs',
    'Classon Av', 'Clinton-Washington Avs', 'Fulton St', 'Hoyt-Schermerhorn',
    'Bergen St', 'Carroll St', 'Smith-9 Sts', '4 Av-9 Sts', '7 Av',
    '15 St-Prospect Park', 'Fort Hamilton Pkwy', 'Church Av',
]


def prepare(south_path, north_path, route_index_path=Path('data/nyc_route_index.json')):
    directions = {
        key: direction(path, rid, reverse, route_ref='G',
                       osm_stations=OSM_STATIONS, mta_stations=MTA_STATIONS)
        for key, path, rid, reverse in [
            ('to_church', south_path, 9699111, False),
            ('to_court_square', north_path, 9699110, True)]
    }
    index_raw = route_index_path.read_bytes()
    f_members = {}
    for route in json.loads(index_raw)['routes']:
        if route['source_tags'].get('ref') != 'F':
            continue
        for member in route['ordered_track_candidates']:
            if member['type'] == 'way':
                f_members.setdefault(member['ref'], set()).add(route['osm_relation_id'])
    shared = []
    for key, source in directions.items():
        for way in source['ways']:
            wid = way['osm_way_id']
            if wid in f_members:
                shared.append(dict(direction=key, osm_way_id=wid,
                                   f_relation_ids=sorted(f_members[wid])))
    return dict(
        name='New York City Subway G', code='nyc-g', closed=False,
        stage='source_geometry_verified_construction_layout_pending',
        track_type='Medium speed', projection='EPSG:3857, R=6378137',
        operator_reference='https://www.mta.info/maps/subway-line-maps/g-line',
        attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright',
        directions=directions,
        shared_source_way_candidates=shared,
        route_index_sha256=hashlib.sha256(index_raw).hexdigest(),
        shared_source_limitation='Member identity only; verify F geometry, local/express assignments and junctions before construction.',
        interchange_requirements=[
            dict(station='Metropolitan Avenue', existing_line='nyc-l',
                 existing_station='Lorimer Street', method='shared station ownership'),
            dict(station='Court Square', future_lines=['E', 'F', '7']),
            dict(station='Hoyt–Schermerhorn Streets', future_lines=['A', 'C']),
            dict(station='4th Avenue', future_lines=['R']),
        ],
        shared_infrastructure=[dict(
            other_line='F', from_station='Bergen Street', to_station='Church Avenue',
            requirement='Build local tracks once; preserve separate express paths and branch connections.',
            geometry_audit_pending=True)],
        adaptations=['140 m platforms and 120 m six-car substitute fleet.',
                     'Metropolitan Avenue source -4 maps to candidate -3, below existing L at -2.',
                     'Smith–9th Streets source +4 maps to candidate +3; approach grades require review.'],
        pending=[
            'Survey the live world and preserve all existing stations and tracks.',
            'Audit both directions, source layers, curves and future express tracks.',
            'Design Church Avenue turnback without blocking the continuing F service.',
            'Design Court Square station-after turnback and future interchange crossings.',
            'Assign Metropolitan Avenue platforms to the existing Lorimer Street station.',
        ])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('south', type=Path)
    parser.add_argument('north', type=Path)
    args = parser.parse_args()
    plan = prepare(args.south, args.north)
    Path('data/nyc_g_plan.json').write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v['validation'] for k, v in plan['directions'].items()}))
