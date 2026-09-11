import math
import unittest

from track_tangents import calculate_tangents


def control(i, x, y, previous='0', next='0', **extra):
    return dict(id=i, x=x, y=y, previous=previous, next=next,
                blueprint=True, station_id='0', **extra)


class TangentTests(unittest.TestCase):
    def test_short_transition_does_not_bend_long_span(self):
        nodes = [control('1', -1000, 0), control('2', 0, 0, '1', '3'), control('3', 0, 10)]
        p = calculate_tangents(nodes, ['2'])['points'][0]
        self.assertAlmostEqual(p['dx'], 1)
        self.assertAlmostEqual(p['dy'], 0)
        self.assertEqual((p['x'], p['y']), (0, 0))

    def test_comparable_spans_use_unit_vector_bisector(self):
        nodes = [control('1', -20, 0), control('2', 0, 0, '1', '3'), control('3', 0, 10)]
        p = calculate_tangents(nodes, ['2'])['points'][0]
        self.assertAlmostEqual(p['dx'], math.sqrt(.5))
        self.assertAlmostEqual(p['dy'], math.sqrt(.5))

    def test_pair_preserves_opposite_travel_orientation(self):
        nodes = [control('1', -100, 0), control('2', 0, 0, '1', '3'), control('3', 100, 20),
                 control('4', 100, 26), control('5', 0, 6, '4', '6'), control('6', -100, 6)]
        a, b = calculate_tangents(nodes, ['2', '5'], [['2', '5']])['points']
        self.assertAlmostEqual(a['dx'], -b['dx'])
        self.assertAlmostEqual(a['dy'], -b['dy'])

    def test_degenerate_or_unsafe_controls_are_rejected(self):
        for target, end in [(control('2', 0, 0, '1', '3'), (-10, 0)),
                            (control('2', 0, 0, '1', '3', branch_parent='9'), (10, 0)),
                            (control('2', 0, 0, '1'), (10, 0))]:
            with self.subTest(target=target, end=end), self.assertRaises(ValueError):
                calculate_tangents([control('1', -10, 0), target, control('3', *end)], ['2'])

    def test_widely_separated_tracks_are_not_paired(self):
        nodes = [control('1', -10, 0), control('2', 0, 0, '1', '3'), control('3', 10, 0),
                 control('4', -10, 50), control('5', 0, 50, '4', '6'), control('6', 10, 50)]
        with self.assertRaises(ValueError):
            calculate_tangents(nodes, ['2', '5'], [['2', '5']])
