"""Extract Culver Avenue U/X source and independent three-track station candidates."""
import argparse,json
from pathlib import Path
from prepare_nyc_south_culver import prepare
from prepare_nyc_avenue_i import prepare as station_plan

def main():
 p=argparse.ArgumentParser();p.add_argument('snapshot',type=Path);a=p.parse_args()
 source,_=prepare(a.snapshot,[(40,{427044453,427044454},{'1','2','3-4'}),(41,{427044455,427044456},{'1','2','3-4'})], 'https://api.openstreetmap.org/api/0.6/map.json?bbox=-73.979,40.585,-73.968,40.604')
 target='data/nyc_lower_culver_source.json';Path(target).write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 for index,key in [(40,'avenue_u'),(41,'avenue_x')]:
  plan=station_plan(index,target);Path(f'data/nyc_{key}_three_tracks.json').write_text(json.dumps(plan,indent=2)+'\n')
 print(json.dumps([dict(name=s['name'],cross_section=s['cross_section']) for s in source['stations']]))
if __name__=='__main__':main()
