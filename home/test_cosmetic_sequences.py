"""Validated atlas choreography is presentation data, independent of item names."""
import copy
import json

from django.template.loader import get_template
from django.test import SimpleTestCase

from .cosmetic_packages import PACKAGE_ROOT, parse_package


class CosmeticSequenceTests(SimpleTestCase):
    def setUp(self):
        self.raw = json.loads((PACKAGE_ROOT / 'efeito-vigilia-das-lanternas.json').read_text(encoding='utf-8'))

    def parse(self, raw):
        return parse_package(raw, raw['slug'], 'efeito')

    def test_sequence_survives_validation_and_template_serialization(self):
        package = self.parse(self.raw)
        self.assertIsNotNone(package)
        layer = package['banner'][-1]
        self.assertEqual(layer['sequence']['columns'], 3)
        self.assertEqual(layer['sequence']['duration'], 18)
        self.assertEqual({frame['frame'] for frame in layer['sequence']['frames']}, {0, 1, 2})
        html = get_template('home/partials/_cosmetic_preview.html').render({'layers': package['banner'], 'slot': 'banner'})
        self.assertIn('data-cosmetic-sequence="{&quot;columns&quot;:3', html)
        self.assertNotIn('data-cosmetic-sequence="{"columns"', html)

    def test_numeric_timeline_rejects_malformed_or_unsafe_input(self):
        seq = self.raw['layers'][-1]['sequence']
        invalid = [None, [], {}, dict(seq, columns=True), dict(seq, columns=1),
                   dict(seq, columns=9), dict(seq, duration=float('nan')),
                   dict(seq, duration=1), dict(seq, delay=5), dict(seq, backdrop=1),
                   dict(seq, backdrop='url(x)'), dict(seq, extra='code'),
                   dict(seq, frames=[]), dict(seq, frames=seq['frames'] * 3)]
        for index, field, value in ((0, 'at', .01), (-1, 'at', .99), (3, 'at', .13),
                                    (0, 'frame', True), (0, 'frame', 3),
                                    (0, 'opacity', float('inf')), (0, 'opacity', -1)):
            bad = copy.deepcopy(seq)
            bad['frames'][index][field] = value
            invalid.append(bad)
        for sequence in invalid:
            raw = copy.deepcopy(self.raw)
            raw['layers'][-1]['sequence'] = sequence
            with self.subTest(sequence=sequence):
                self.assertIsNone(self.parse(raw))

    def test_atlas_cannot_be_attached_to_avatars_or_conflicting_motions(self):
        for change in ({'slot': 'avatar'}, {'motion': 'float'}, {'sprite': 'open'}):
            raw = copy.deepcopy(self.raw)
            raw['layers'][-1].update(change)
            with self.subTest(change=change):
                self.assertIsNone(self.parse(raw))

    def test_unrelated_layers_stay_ordinary_static_media(self):
        package = self.parse(self.raw)
        self.assertTrue(all('sequence' not in layer for layer in package['banner'][:-1]))
        self.assertEqual(package['banner'][2]['motion'], 'none')
        self.assertEqual([layer['motion'] for layer in package['banner'][3:6]], ['float', 'float', 'pulse'])
        raw = copy.deepcopy(self.raw)
        raw['slug'] = 'efeito-arbitrary-sequence'
        self.assertIsNotNone(self.parse(raw))
