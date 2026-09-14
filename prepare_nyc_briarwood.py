"""Plan Briarwood Queens Boulevard side platforms."""
import json
import math
from pathlib import Path
from prepare_nyc_culver import centroid, nearest


def prepare():
    source=json.loads(Path('data/nyc_briarwood_source.json').read_bytes())
    stop=json.loads(Path('data/nyc_f_plan.json').read_bytes())['directions']['to_coney_island']['stations'][4]
    footprints=[w for w in source['ways'] if w['osm_way_id'] in [906716436,906716437]]
    assert len(footprints)==2
    centers=[]
    for w in footprints:
        c=centroid([{k:p[k]-stop[k] for k in ['x','y']} for p in w['points']])
        centers.append({k:c[k]+stop[k] for k in c})
    center={k:sum(c[k] for c in centers)/2 for k in ['x','y']}
    rails=[w for w in source['ways'] if w['tags'].get('name')=='IND Queens Boulevard Line' and w['tags'].get('level')=='-2']
    _,_,(tx,ty)=min((nearest(w['points'],center) for w in rails),key=lambda n:n[0])
    if tx>0:tx,ty=-tx,-ty
    scale=math.cos(math.radians(stop['latitude']))
    tracks=[]
    for ref in ['1','2']:
        candidates=[]
        for w in rails:
            if w['tags'].get('railway:track_ref')!=ref:continue
            for a,b in zip(w['points'],w['points'][1:]):
                da=(a['x']-center['x'])*tx+(a['y']-center['y'])*ty
                db=(b['x']-center['x'])*tx+(b['y']-center['y'])*ty
                if abs(db-da)<1e-9 or not 0<=-da/(db-da)<=1:continue
                q={k:a[k]-da/(db-da)*(b[k]-a[k]) for k in ['x','y']}
                candidates.append(dict(**q,source_way_id=w['osm_way_id']))
        q=min(candidates,key=lambda q:math.hypot(q['x']-center['x'],q['y']-center['y']))
        tracks.append(dict(track_ref=ref,**q,points=[dict(x=q['x']+d*tx/scale,y=q['y']+d*ty/scale,depth=-2) for d in [-120,-70,70,120]]))
    spacing=math.hypot(tracks[0]['x']-tracks[1]['x'],tracks[0]['y']-tracks[1]['y'])*scale
    assert 3<spacing<30
    return dict(name='Briarwood',plan_index=4,center=center,scale=scale,
                southbound_axis=dict(x=tx,y=ty),tracks=tracks,track_spacing_metres=spacing,
                platform_type='two side platforms',platform_length_metres=140,depth=-2,
                source_platforms=footprints,reserved_express_track_refs=['3','4'],
                reserved_express_depth=-2,source='data/nyc_briarwood_source.json',
                stage='candidate_native_creation_pending')


if __name__=='__main__':
    p=prepare();Path('data/nyc_briarwood_side_platforms.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(spacing=p['track_spacing_metres'],center=p['center'],tracks=[t['track_ref'] for t in p['tracks']])))
