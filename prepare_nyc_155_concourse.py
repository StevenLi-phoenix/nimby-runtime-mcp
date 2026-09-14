"""Prepare 155th Street Concourse side platforms and its center through track."""
import json
import math
from pathlib import Path
from prepare_nyc_culver import centroid, nearest
from shapely.geometry import Polygon, LineString


def prepare():
    source=json.loads(Path('data/nyc_harlem_source.json').read_bytes())
    stop=json.loads(Path('data/nyc_d_plan.json').read_bytes())['directions']['to_coney_island']['stations'][10]
    footprints=[w for w in source['ways'] if w['osm_way_id'] in [676096998,676096999]]
    assert len(footprints)==2
    centers=[]
    for w in footprints:
        c=centroid([{k:q[k]-stop[k] for k in ['x','y']} for q in w['points']]);centers.append({k:c[k]+stop[k] for k in c})
    center={k:sum(c[k] for c in centers)/2 for k in ['x','y']};scale=math.cos(math.radians(stop['latitude']))
    ways=[w for w in source['ways'] if w['tags'].get('name')=='IND Concourse Line' and w['tags'].get('level')=='-2']
    reference=min(ways,key=lambda w:nearest(w['points'],center)[0]);_,_,(tx,ty)=nearest(reference['points'],center)
    if ty>0:tx,ty=-tx,-ty
    def offset(q):return (-(q['x']-center['x'])*ty+(q['y']-center['y'])*tx)*scale
    tracks=[]
    for w in ways:
        for a,b in zip(w['points'],w['points'][1:]):
            da=(a['x']-center['x'])*tx+(a['y']-center['y'])*ty;db=(b['x']-center['x'])*tx+(b['y']-center['y'])*ty
            if abs(db-da)<1e-9 or not 0<=-da/(db-da)<1:continue
            q={k:a[k]-da/(db-da)*(b[k]-a[k]) for k in ['x','y']}
            if abs(offset(q))>35:continue
            ref=w['tags']['railway:track_ref']
            tracks.append(dict(source_way_id=w['osm_way_id'],track_ref=ref,role='local' if ref in ['1','2'] else 'express',
                               depth=-2,offset_metres=offset(q),points=[dict(x=q['x']+tx*d/scale,y=q['y']+ty*d/scale,depth=-2)
                                                                       for d in [-120,-70,70,120]],**q))
    tracks.sort(key=lambda t:t['offset_metres']);assert {t['track_ref'] for t in tracks}=={'1','2','3-4'} and len(tracks)==3
    # Longer straight center leads cross the curved south approach of track 1.
    middle=next(t for t in tracks if t['track_ref']=='3-4')
    middle['points'][0]=dict(middle['points'][1]);middle['points'][-1]=dict(middle['points'][-2])
    middle['through_track_length_metres']=140
    platforms=[]
    for w,c in zip(footprints,centers):
        t=min(tracks,key=lambda t:abs(t['offset_metres']-offset(c)));assert t['role']=='local'
        polygon=Polygon([(((q['x']-center['x'])*tx+(q['y']-center['y'])*ty)*scale,offset(q)) for q in w['points']])
        section=polygon.intersection(LineString([(0,-40),(0,40)]));assert section.geom_type=='LineString'
        lo,hi=section.bounds[1],section.bounds[3];original=[lo,hi]
        if offset(c)<t['offset_metres']:hi=min(hi,t['offset_metres']-1.525)
        else:lo=max(lo,t['offset_metres']+1.525)
        assert hi-lo>2
        platforms.append(dict(track_ref=t['track_ref'],platform_way=w['osm_way_id'],source_lateral_bounds_metres=original,
                              track_offset_metres=t['offset_metres'],native_lateral_bounds_metres=[lo,hi],native_width_metres=hi-lo))
    assert min(b['offset_metres']-a['offset_metres'] for a,b in zip(tracks,tracks[1:]))>3.5
    return dict(name='155th Street',center=center,scale=scale,southbound_axis=dict(x=tx,y=ty),tracks=tracks,platforms=platforms,
                source='data/nyc_harlem_source.json',attribution=source['attribution'],stage='native_platform_candidate_pending')


if __name__=='__main__':
    p=prepare();Path('data/nyc_155_concourse_platforms.json').write_text(json.dumps(p,indent=2)+'\n')
    print(json.dumps(dict(tracks=[dict(ref=t['track_ref'],way=t['source_way_id'],offset=t['offset_metres']) for t in p['tracks']],platforms=p['platforms'])))
