"""Clip Grand-Atlantic source to native leads and retain explicit bridge ramps."""
import json,math
from pathlib import Path
from prepare_nyc_g_corridors import simplify

def prepare():
    survey=json.loads(Path('data/nyc_grand_atlantic_grade_survey.json').read_bytes())
    state=json.loads(Path('work/nyc-d-built.json').read_bytes())
    ns={n['id']:n for n in json.loads(Path('work/nyc-grand-atlantic-live.json').read_bytes())['nodes']}
    g=state['grand_platform_groups'][0];islands=state['atlantic_fourth_islands'];out=[]
    pairs=[('3',g['east_secondary'],islands[0]['west_primary']),('4',g['east_primary'],islands[1]['west_secondary'])]
    for c,(ref,a,b) in zip(survey['corridors'],pairs):
        route=c['route'];chain=c['chainage_metres']
        def project(n):
            hits=[]
            for i,(u,v) in enumerate(zip(route,route[1:])):
                dx,dy=v['x']-u['x'],v['y']-u['y'];den=dx*dx+dy*dy
                if not den:continue
                f=max(0,min(1,((n['x']-u['x'])*dx+(n['y']-u['y'])*dy)/den))
                hits.append((math.hypot(n['x']-u['x']-f*dx,n['y']-u['y']-f*dy),chain[i]+f*(chain[i+1]-chain[i])))
            return min(hits)
        ga,lo=project(ns[a]);gb,hi=project(ns[b]);assert max(ga,gb)<40 and lo<hi
        bridge=next(r for r in c['source_layers'] if r['depth']==2);bs,be=bridge['start_metres'],bridge['end_metres'];deep=c['source_layers'][-1]['start_metres']
        profile=[(lo,-2),(bs-240,-2),(bs-160,-1),(bs-80,0),(bs,1),(bs+100,2),(be-100,2),(be,1),(be+80,0),(be+160,-1),(be+240,-2),(deep-80,-2),(deep,-3),(hi,-3)]
        assert all(x[0]<y[0] for x,y in zip(profile,profile[1:])),profile
        def at(d,z):
            i=next(i for i in range(len(chain)-1) if chain[i]<=d<=chain[i+1]);f=(d-chain[i])/(chain[i+1]-chain[i])
            return dict(x=route[i]['x']+f*(route[i+1]['x']-route[i]['x']),y=route[i]['y']+f*(route[i+1]['y']-route[i]['y']),depth=z,metres=d-lo)
        points=[]
        for (u,zu),(v,zv) in zip(profile,profile[1:]):
            section=[at(u,zu)]+([dict(x=q['x'],y=q['y'],depth=zu,metres=d-lo) for q,d in zip(route,chain) if u+10<d<v-10] if zu==zv else [])+[at(v,zv)]
            points+=simplify(section,tolerance=2)[:-1]
        points.append(at(hi,-3))
        for q,i in [(points[0],a),(points[-1],b)]:
            assert '0' in [ns[i]['previous'],ns[i]['next']];q.update(x=ns[i]['x'],y=ns[i]['y'],depth=ns[i]['depth'])
        out.append(dict(track_ref=ref,start_node_id=a,end_node_id=b,points=points,depth_profile=[(d-lo,z) for d,z in profile],source_projection_gaps_world_metres=[ga,gb],source_length_metres=hi-lo,source_station_offsets_metres=[lo,hi]))
    return dict(corridors=out,source='data/nyc_grand_atlantic_grade_survey.json',stage='candidate_crossings_and_native_geometry_pending',pending=['Fetch parallel Manhattan Bridge and Brooklyn junction source tracks, including Q/N and DeKalb approaches.','Audit riverbank and bridge ramp crossing clearance before native creation.','Check native curves, grade changes and protected objects before selected build.'])

if __name__=='__main__':
    p=prepare();Path('data/nyc_grand_atlantic_corridors.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf-8');print([{k:c[k] for k in ['track_ref','source_length_metres','source_projection_gaps_world_metres']}|{'points':len(c['points'])} for c in p['corridors']])
