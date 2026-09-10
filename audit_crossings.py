"""Conservative straight-segment crossing audit of runtime node snapshots.

Native track curves and junction conflict blocks still require in-game verification.
"""
import json
from pathlib import Path


def native_crossings(nodes):
    """Intersect native tessellated node curves; depths are native node layers."""
    def cross(a, b):
        return a[0]*b[1]-a[1]*b[0]
    bounds = {}
    for n in nodes:
        if len(n.get('curve', [])) < 2:
            continue
        xs, ys = zip(*n['curve'])
        bounds[n['id']] = min(xs), min(ys), max(xs), max(ys)
    hits = []
    for i, a in enumerate(nodes):
        if a['id'] not in bounds:
            continue
        ab = bounds[a['id']]
        for b in nodes[i+1:]:
            if b['id'] not in bounds or a['depth'] != b['depth']:
                continue
            bb = bounds[b['id']]
            if ab[2] < bb[0] or bb[2] < ab[0] or ab[3] < bb[1] or bb[3] < ab[1]:
                continue
            # Shared route junctions are connections rather than crossings.
            if b['id'] in [a['previous'], a['next'], a.get('branch_parent')]:
                continue
            if a['id'] in [b['previous'], b['next'], b.get('branch_parent')]:
                continue
            found = False
            for p, q in zip(a['curve'], a['curve'][1:]):
                r = q[0]-p[0], q[1]-p[1]
                for u, v in zip(b['curve'], b['curve'][1:]):
                    s = v[0]-u[0], v[1]-u[1]
                    den = cross(r, s)
                    if abs(den) < 1e-9:
                        continue
                    z = u[0]-p[0], u[1]-p[1]
                    t, w = cross(z, s)/den, cross(z, r)/den
                    if 1e-5 < t < 1-1e-5 and 1e-5 < w < 1-1e-5:
                        hits.append({'a': a['id'], 'b': b['id'], 'x': p[0]+t*r[0], 'y': p[1]+t*r[1], 'depth': a['depth']})
                        found = True
                        break
                if found:
                    break
    return hits


def crossings(nodes):
    ns = {n['id']: n for n in nodes}
    edges = sorted({tuple(sorted((n['id'], n[k]))) for n in nodes
                    for k in ['previous', 'next'] if n[k] in ns})
    def cross(a, b):
        return a[0]*b[1]-a[1]*b[0]
    hits = []
    for i, (ai, bi) in enumerate(edges):
        a, b = ns[ai], ns[bi]
        r = (b['x']-a['x'], b['y']-a['y'])
        for ci, di in edges[i+1:]:
            if len({ai, bi, ci, di}) < 4:
                continue
            c, d = ns[ci], ns[di]
            s = (d['x']-c['x'], d['y']-c['y'])
            den = cross(r, s)
            if abs(den) < 1e-9:
                continue
            q = (c['x']-a['x'], c['y']-a['y'])
            t, u = cross(q, s)/den, cross(q, r)/den
            if 1e-6 < t < 1-1e-6 and 1e-6 < u < 1-1e-6:
                za = a['depth']+t*(b['depth']-a['depth'])
                zb = c['depth']+u*(d['depth']-c['depth'])
                if abs(za-zb) < .9:
                    hits.append({'a': [ai, bi], 'b': [ci, di],
                                 'x': a['x']+t*r[0], 'y': a['y']+t*r[1],
                                 'depth': [za, zb]})
    return hits


if __name__ == '__main__':
    nodes = {n['id']: n for f in ['work/live-network.json', 'work/fuxingmen-live-before.json']
             for n in json.loads(Path(f).read_text(encoding='utf-8'))['nodes']}
    hits = crossings(list(nodes.values()))
    print(json.dumps(hits, indent=2))
