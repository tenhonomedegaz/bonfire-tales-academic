import unittest
from copy import deepcopy

from home.vtt_lab_spatial import distance_units, measure_tokens


def fp(x, y, z=0, w=1, h=1, height=1):
    return {'pos': {'x': x, 'y': y, 'z': z}, 'sizeCells': {'w': w, 'h': h, 'z': height}}


class SpatialTests(unittest.TestCase):
    def test_existing_metric_semantics_include_height_and_floor_sqrt(self):
        origin, target = fp(0, 0), fp(3, 4, 2)
        self.assertEqual(distance_units('manhattan3d', origin, target), 9)
        self.assertEqual(distance_units('chebyshev3d', origin, target), 4)
        self.assertEqual(distance_units('euclidean-round', origin, target), 5)
        self.assertEqual(distance_units('alt-5-10-5', origin, target), 10)

    def test_footprint_overlap_symmetry_and_translation(self):
        for metric in ('manhattan3d', 'chebyshev3d', 'euclidean-round', 'alt-5-10-5'):
            a, b = fp(-3, 2, -1, 3, 2, 2), fp(4, 3, 2, 2, 2, 2)
            distance = distance_units(metric, a, b)
            self.assertEqual(distance, distance_units(metric, b, a))
            for shape in (a, b):
                for axis in shape['pos']:
                    shape['pos'][axis] += 30
            self.assertEqual(distance, distance_units(metric, a, b))
            self.assertEqual(distance_units(metric, fp(0, 0, w=3, h=3), fp(1, 1)), 0)

    def test_bad_metrics_boolean_float_and_dimensions_are_rejected(self):
        for metric, a in [('unknown', fp(0, 0)), ('manhattan3d', fp(True, 0)),
                          ('manhattan3d', fp(1.0, 0)), ('manhattan3d', fp(0, 0, w=0))]:
            with self.assertRaises(ValueError):
                distance_units(metric, a, fp(3, 4))

    def test_measurement_is_read_only_and_does_not_claim_path_or_los(self):
        state = {'board': {'cell_meters': 1.5}, 'tokens': [
            {'id': 'a', 'x': 0, 'y': 0, 'z': 0}, {'id': 'b', 'x': 3, 'y': 4, 'z': 2}]}
        before = deepcopy(state)
        result = measure_tokens(state, 'a', 'b')
        self.assertEqual(result['meters'], 13.5)
        self.assertFalse(result['path_validated'])
        self.assertFalse(result['line_of_sight_validated'])
        self.assertEqual(state, before)
        with self.assertRaises(ValueError):
            measure_tokens(state, 'a', 'foreign')
