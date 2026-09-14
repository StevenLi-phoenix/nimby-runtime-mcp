"""Prepare weekday F geometry and identify source tracks shared with G."""
import argparse
import json
from pathlib import Path

from prepare_nyc_direction import direction

OSM_STATIONS = [
    'Jamaica–179th Street', '169th Street', 'Parsons Boulevard', 'Sutphin Boulevard',
    'Briarwood', 'Kew Gardens–Union Turnpike', '75th Avenue', 'Forest Hills–71st Avenue',
    'Jackson Heights–Roosevelt Avenue', 'Queens Plaza', 'Court Square–23rd Street',
    '53rd Street–Lexington Avenue', '53rd Street–5th Avenue',
    '47th–50th Streets–Rockefeller Center', '42nd Street–Bryant Park',
    '34th Street–Herald Square', '23rd Street', '14th Street',
    'West 4th Street–Washington Square', 'Broadway–Lafayette Street', '2nd Avenue',
    'Delancey Street', 'East Broadway', 'York Street', 'Jay Street–MetroTech',
    'Bergen Street', 'Carroll Street', 'Smith–9th Streets', '4th Avenue', '7th Avenue',
    '15th Street–Prospect Park', 'Fort Hamilton Parkway', 'Church Avenue',
    'Ditmas Avenue', '18th Avenue', 'Avenue I', 'Bay Parkway', 'Avenue N', 'Avenue P',
    'Kings Highway', 'Avenue U', 'Avenue X', 'Neptune Avenue',
    'West 8th Street–New York Aquarium', 'Coney Island–Stillwell Avenue',
]
MTA_STATIONS = [
    'Jamaica-179 St', '169 St', 'Parsons Blvd', 'Sutphin Blvd', 'Briarwood',
    'Kew Gardens-Union Tpke', '75 Av', 'Forest Hills-71 Av', 'Jackson Hts-Roosevelt Av',
    'Queens Plaza', 'Court Sq-23 St', 'Lexington Av/53 St', '5 Av/53 St',
    '47-50 Sts Rockefeller Ctr', '42 St-Bryant Pk', '34 St-Herald Sq', '23 St', '14 St',
    'W 4 St-Washington Sq', 'Broadway-Lafayette St', '2 Av', 'Delancey St-Essex St',
    'East Broadway', 'York St', 'Jay St-MetroTech', 'Bergen St', 'Carroll St',
    'Smith-9 Sts', '4 Av-9 St', '7 Av', '15 St-Prospect Park', 'Fort Hamilton Pkwy',
    'Church Av', 'Ditmas Av', '18 Av', 'Avenue I', 'Bay Pkwy', 'Avenue N', 'Avenue P',
    'Kings Hwy', 'Avenue U', 'Avenue X', 'Neptune Av', 'W 8 St-NY Aquarium',
    'Coney Island-Stillwell Av',
]


def prepare(south, north):
    dirs = {
        key: direction(path, rid, reverse, route_ref='F',
                       osm_stations=OSM_STATIONS, mta_stations=MTA_STATIONS)
        for key, path, rid, reverse in [
            ('to_coney_island', south, 9753683, False),
            ('to_jamaica', north, 366772, True)]
    }
    g = json.loads(Path('data/nyc_g_plan.json').read_text(encoding='utf-8'))
    shared = []
    for fk, gk in [('to_coney_island', 'to_church'), ('to_jamaica', 'to_court_square')]:
        f, gs = dirs[fk], g['directions'][gk]
        f_nodes = {p['osm_node_id'] for p in f['route']}
        shared.append(dict(f_direction=fk, g_direction=gk,
                           source_way_ids=sorted({w['osm_way_id'] for w in f['ways']} &
                                                 {w['osm_way_id'] for w in gs['ways']}),
                           source_node_ids=sorted(f_nodes & {p['osm_node_id'] for p in gs['route']}),
                           stations=[dict(name=s['name'], g_source_node_id=s['osm_node_id'],
                                          identical_f_stop=any(t['osm_node_id']==s['osm_node_id'] for t in f['stations']))
                                     for s in gs['stations'] if s['name'] in OSM_STATIONS[25:33]]))
    return dict(name='New York City Subway F', code='nyc-f', closed=False,
                stage='weekday_source_geometry_verified_not_built',
                operator_reference='https://www.mta.info/maps/subway-line-maps/f-line',
                attribution=g['attribution'], projection=g['projection'], track_type='Medium speed',
                directions=dirs, g_shared_geometry=shared,
                pending=['Retain G shared local tracks and stations; do not duplicate them.',
                         'Audit express tracks, grade-separated junctions and Church Avenue turnback.',
                         'Verify other shared corridors and time-dependent service variants.',
                         'Survey live world, build remaining infrastructure and verify operation.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('south', type=Path)
    parser.add_argument('north', type=Path)
    args = parser.parse_args()
    plan = prepare(args.south, args.north)
    Path('data/nyc_f_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: v['validation'] for k,v in plan['directions'].items()}))
    print(json.dumps([{**s, 'source_node_ids':len(s['source_node_ids'])} for s in plan['g_shared_geometry']],ensure_ascii=True))
