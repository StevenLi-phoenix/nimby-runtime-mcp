"""Prepare both L train directions, preserving source layer differences."""
import argparse
import json
from pathlib import Path

from prepare_nyc_direction import direction as read_direction

OSM_STATIONS = [
    '8th Avenue', '6th Avenue', 'Union Square', '3rd Avenue', '1st Avenue',
    'Bedford Avenue', 'Lorimer Street', 'Graham Avenue', 'Grand Street',
    'Montrose Avenue', 'Morgan Avenue', 'Jefferson Street', 'DeKalb Avenue',
    'Myrtle–Wyckoff Avenues', 'Halsey Street', 'Wilson Avenue',
    'Bushwick Avenue–Aberdeen Street', 'Broadway Junction', 'Atlantic Avenue',
    'Sutter Avenue', 'Livonia Avenue', 'New Lots Avenue', 'East 105th Street',
    'Canarsie–Rockaway Parkway',
]
MTA_STATIONS = [
    '8 Av', '6 Av', '14 St-Union Sq', '3 Av', '1 Av', 'Bedford Av',
    'Lorimer St', 'Graham Av', 'Grand St', 'Montrose Av', 'Morgan Av',
    'Jefferson St', 'DeKalb Av', 'Myrtle-Wyckoff Avs', 'Halsey St',
    'Wilson Av', 'Bushwick Av-Aberdeen St', 'Broadway Junction', 'Atlantic Av',
    'Sutter Av', 'Livonia Av', 'New Lots Av', 'East 105 St', 'Canarsie-Rockaway Pkwy',
]


def direction(path, relation_id, reverse):
    return read_direction(path, relation_id, reverse, route_ref='L',
                          osm_stations=OSM_STATIONS, mta_stations=MTA_STATIONS)


def prepare(south_path, north_path):
    south = direction(south_path, 366763, False)
    north = direction(north_path, 9716996, True)
    differences = []
    for s, n in zip(south['stations'], reversed(north['stations'])):
        if s['incident_source_depths'] != n['incident_source_depths']:
            differences.append(dict(name=s['name'], south_depths=s['incident_source_depths'], north_depths=n['incident_source_depths'],
                                    boundary_ambiguity=s['layer_boundary_review_required'] or n['layer_boundary_review_required']))
    return dict(name='New York City Subway L', code='nyc-l', closed=False,
        stage='source_geometry_verified_construction_layout_pending',
        track_type='Medium speed', projection='EPSG:3857, R=6378137',
        operator_reference='https://www.mta.info/maps/subway-line-maps/l-line',
        attribution='© OpenStreetMap contributors; https://www.openstreetmap.org/copyright',
        directions=dict(to_canarsie=south, to_manhattan=north),
        directional_station_layer_differences=differences,
        adaptations=['140 m platforms with 120 m six-car substitute fleet.',
                     'Source depth -4 has candidate -3 within the native range; interchange crossings require review before construction.'],
        pending=['Design shared station ownership for future interchange lines.',
                 'Preserve the Wilson Avenue directional layer difference.',
                 'Review curves, layer transitions and both station-after terminal turnbacks.',
                 'Survey current game before creating any blueprint.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('south', type=Path)
    parser.add_argument('north', type=Path)
    args = parser.parse_args()
    plan = prepare(args.south, args.north)
    Path('data/nyc_l_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v['validation'] for k, v in plan['directions'].items()}))
    print(json.dumps(plan['directional_station_layer_differences']))
