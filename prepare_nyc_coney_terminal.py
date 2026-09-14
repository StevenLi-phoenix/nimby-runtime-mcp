"""Extract Coney Island's eight-track cross-section and four platform footprints."""
import json,math
from pathlib import Path
from prepare_nyc_culver import centroid
from prepare_nyc_direction import source_depth

def prepare():
 source=json.loads(Path('data/nyc_coney_culver_source.json').read_bytes());stop=json.loads(Path('data/nyc_f_plan.json').read_bytes())['directions']['to_coney_island']['stations'][44];scale=math.cos(math.radians(stop['latitude']));platforms=[]
 for wid in [427044488,427044493,792754806,792754814]:
  w=next(w for w in source['ways'] if w['osm_way_id']==wid);c=centroid([{k:p[k]-stop[k] for k in ['x','y']} for p in w['points']]);platforms.append(dict(source_way_id=wid,center={k:c[k]+stop[k] for k in ['x','y']},footprint=w))
 center={k:sum(p['center'][k] for p in platforms)/4 for k in ['x','y']}
 # Station tracks run near north/south; use the long footprint axis rather than
 # F's sharply turning approach tangent at its stop marker.
 pts=platforms[0]['footprint']['points'];a=max(pts,key=lambda p:p['y']);b=min(pts,key=lambda p:p['y']);dx,dy=b['x']-a['x'],b['y']-a['y'];length=math.hypot(dx,dy);tx,ty=dx/length,dy/length;cross=[]
 for w in source['ways']:
  if w['tags'].get('railway')!='subway' or source_depth(w['tags'])!=2:continue
  for a,b in zip(w['points'],w['points'][1:]):
   da=(a['x']-center['x'])*tx+(a['y']-center['y'])*ty;db=(b['x']-center['x'])*tx+(b['y']-center['y'])*ty
   if abs(db-da)<1e-9 or not 0<=-da/(db-da)<=1:continue
   f=-da/(db-da);q={k:a[k]+f*(b[k]-a[k]) for k in ['x','y']};off=(-(q['x']-center['x'])*ty+(q['y']-center['y'])*tx)*scale
   if abs(off)<55:cross.append(dict(source_way_id=w['osm_way_id'],track_ref=w['tags'].get('railway:track_ref'),line_name=w['tags'].get('name'),offset_metres=off,**q))
 cross.sort(key=lambda c:c['offset_metres']);assert len(cross)==8,cross
 for p in platforms:p['offset_metres']=(-(p['center']['x']-center['x'])*ty+(p['center']['y']-center['y'])*tx)*scale
 platforms.sort(key=lambda p:p['offset_metres'])
 islands=[]
 for p in platforms:
  left=max((c for c in cross if c['offset_metres']<p['offset_metres']),key=lambda c:c['offset_metres']);right=min((c for c in cross if c['offset_metres']>p['offset_metres']),key=lambda c:c['offset_metres'])
  islands.append(dict(platform_way_id=p['source_way_id'],track_refs=[left['track_ref'],right['track_ref']],source_track_ways=[left['source_way_id'],right['source_way_id']],track_spacing_metres=right['offset_metres']-left['offset_metres']))
 return dict(name='Coney Island–Stillwell Avenue',plan_index=44,center=center,scale=scale,southbound_axis=dict(x=tx,y=ty),cross_section=cross,islands=islands,platforms=platforms,source='data/nyc_coney_culver_source.json',stage='source_cross_section_only_native_terminal_plan_pending',pending=['Verify service-to-platform mapping using operator data.','Plan arrival-platform to station-after relay to departure-platform paths, preserving four islands/eight physical tracks.','Do not add yard or depot links.'])
if __name__=='__main__':
 p=prepare();Path('data/nyc_coney_terminal_source.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:p[k] for k in ['center','cross_section','islands']}))
