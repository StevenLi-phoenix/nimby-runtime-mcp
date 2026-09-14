"""Extract Avenue I--Kings Highway source without replacing built northern plans."""
import argparse
import json
from pathlib import Path
from prepare_nyc_south_culver import prepare
from prepare_nyc_avenue_i import prepare as prepare_side_station


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('snapshot',type=Path)
    args=parser.parse_args()
    specs=[(36,{427044484,427044485},{'1','2','3-4'}),
           (37,{427044449,427044450},{'1','2','3-4'}),
           (38,{427044451,427044452},{'1','2','3-4'}),
           (39,{427044494,427044495},{'1','2','3-4'})]
    source,_=prepare(args.snapshot,specs,'https://api.openstreetmap.org/api/0.6/map.json?bbox=-73.980,40.601,-73.968,40.626')
    Path('data/nyc_mid_culver_source.json').write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for index,key in [(36,'bay_parkway'),(37,'avenue_n'),(38,'avenue_p')]:
        candidate=prepare_side_station(index,'data/nyc_mid_culver_source.json')
        Path(f'data/nyc_{key}_three_tracks.json').write_text(json.dumps(candidate,indent=2)+'\n')
    print(json.dumps([dict(name=s['name'],layout=s['layout'],cross_section=s['cross_section']) for s in source['stations']]))


if __name__=='__main__':main()
