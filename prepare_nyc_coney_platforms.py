"""Prepare Coney Island four-island platform tracks; approaches remain separate."""
import json
from pathlib import Path

def prepare():
 s=json.loads(Path('data/nyc_coney_terminal_source.json').read_bytes());by={c['source_way_id']:c for c in s['cross_section']};tx,ty=s['southbound_axis'].values();scale=s['scale'];islands=[]
 for island in s['islands']:
  tracks=[]
  for wid in island['source_track_ways']:
   c=by[wid];tracks.append(dict(**c,points=[dict(x=c['x']+d*tx/scale,y=c['y']+d*ty/scale,depth=2) for d in [-120,-70,70,120]]))
  islands.append(dict(**island,tracks=tracks,island_width_metres=island['track_spacing_metres']-3.05))
 return dict(name=s['name'],plan_index=44,center=s['center'],scale=scale,southbound_axis=s['southbound_axis'],islands=islands,platform_length_metres=140,depth=2,source='data/nyc_coney_terminal_source.json',stage='platform_candidate_native_audit_pending',pending=['Native station/platform geometry audit','Source approach and service direction mapping','Station-after relay paths and fleet-length clearance','Full line operating verification'])
if __name__=='__main__':
 p=prepare();Path('data/nyc_coney_four_islands.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print([(i['track_refs'],i['island_width_metres']) for i in p['islands']])
