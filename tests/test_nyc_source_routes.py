import unittest
from prepare_nyc_carroll_smith import distance, route_between


class SourceProjectionTests(unittest.TestCase):
    def test_two_projections_on_one_segment_do_not_detour_via_source_endpoint(self):
        for reverse in [False, True]:
            points=[{'x':0,'y':0},{'x':100,'y':0}]
            ids=[1,2]
            if reverse:
                points.reverse()
                ids.reverse()
            way={'osm_way_id':1,'tags':{'name':'IND Culver Line','railway:track_ref':'3-4'},
                 'node_ids':ids,'points':points}
            path,ways,gaps=route_between([way],'3-4',{'x':20,'y':1},{'x':80,'y':-1})
            self.assertAlmostEqual(sum(distance(a,b) for a,b in zip(path,path[1:])),60)
            self.assertEqual([p['x'] for p in path],[20,80])
            self.assertEqual(gaps,[1,1])
            self.assertEqual([w['osm_way_id'] for w in ways],[1])
