"""Plan the two stacked side platforms at Fifth Avenue/53rd Street."""
import json
import math
from pathlib import Path
from prepare_nyc_culver import centroid, nearest


def prepare():
    source = json.loads(Path('data/nyc_rockefeller_source.json').read_bytes())
    stop = json.loads(Path('data/nyc_f_plan.json').read_bytes())['directions']['to_coney_island']['stations'][12]
    scale = math.cos(math.radians(stop['latitude']))
    ways = {w['osm_way_id']: w for w in source['ways']}
    platforms = []
    for footprint_id, track_id, depth in [(908245242, 759735516, -2), (908245243, 819186609, -3)]:
        footprint, rail = ways[footprint_id], ways[track_id]
        assert int(footprint['tags']['level']) == int(rail['tags']['level']) == depth
        local = [{k:p[k]-stop[k] for k in ['x','y']} for p in footprint['points']]
        c = centroid(local)
        center = {k:c[k]+stop[k] for k in c}
        gap, q, (tx, ty) = nearest(rail['points'], center)
        if tx > 0:
            tx, ty = -tx, -ty
        offsets = [(-(p['x']-q['x'])*ty+(p['y']-q['y'])*tx)*scale for p in footprint['points']]
        lo, hi = min(offsets), max(offsets)
        assert lo > 1.4 or hi < -1.4, (lo, hi)
        platforms.append(dict(source_platform_way=footprint_id, source_track_way=track_id,
                              track_ref=rail['tags']['railway:track_ref'], depth=depth,
                              center=q, axis=dict(x=tx,y=ty), source_side_bounds_metres=[lo,hi],
                              points=[dict(x=q['x']+d*tx/scale,y=q['y']+d*ty/scale,depth=depth)
                                      for d in [-120,-70,70,120]]))
    return dict(name='5th Avenue/53rd Street',plan_index=12,scale=scale,platforms=platforms,
                center={k:sum(p['center'][k] for p in platforms)/2 for k in ['x','y']},
                platform_length_metres=140,source='data/nyc_rockefeller_source.json',
                pending=['Create separate single-track platforms and unify station ownership.',
                         'Verify side-building placement and both native layers before building.',
                         'Connect the Sixth Avenue junction and Lexington Avenue approaches.'])


if __name__ == '__main__':
    p = prepare()
    Path('data/nyc_fifth_53rd_stacked.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(p))
