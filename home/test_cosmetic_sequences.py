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

    def rig(self, raw):
        return next(layer for layer in raw['layers'] if layer.get('parts')
                    and layer.get('sequence', {}).get('backdrop', 0) > 0)

    def test_sequence_survives_validation_and_template_serialization(self):
        package = self.parse(self.raw)
        self.assertIsNotNone(package)
        expected = self.rig(self.raw)
        layer = next(layer for layer in package['banner'] if layer.get('parts')
                     and layer.get('sequence', {}).get('backdrop', 0) > 0)
        self.assertEqual(layer['sequence']['columns'], 1)
        self.assertEqual(layer['sequence'], expected['sequence'])
        self.assertEqual(len(layer['parts']), len(expected['parts']))
        self.assertNotIn('mask_url', layer)
        for pose, source in zip(layer['parts'], expected['parts']):
            self.assertTrue(pose['url'].endswith('/' + source['file']))
            self.assertEqual(pose['sequence'], source['sequence'])
            self.assertEqual(pose['placement'], source['placement'])
        self.assertTrue(all(f['frame'] == 0 for f in layer['sequence']['frames']))
        html = get_template('home/partials/_cosmetic_preview.html').render({'layers': package['banner'], 'slot': 'banner'})
        self.assertIn('data-cosmetic-parts=', html)
        self.assertIn('data-cosmetic-sequence="{&quot;columns&quot;:1', html)
        self.assertNotIn('data-cosmetic-sequence="{"columns"', html)

    def test_numeric_timeline_rejects_malformed_or_unsafe_input(self):
        seq = self.rig(self.raw)['sequence']
        invalid = [None, [], {}, dict(seq, columns=True), dict(seq, columns=0),
                   dict(seq, columns=9), dict(seq, duration=float('nan')),
                   dict(seq, duration=.5), dict(seq, delay=5), dict(seq, backdrop=1),
                   dict(seq, backdrop='url(x)'), dict(seq, extra='code'),
                   dict(seq, frames=[]), dict(seq, frames=seq['frames'] * 3)]
        for index, field, value in ((0, 'at', .01), (-1, 'at', .99), (3, 'at', .13),
                                    (0, 'frame', True), (0, 'frame', 7),
                                    (0, 'opacity', float('inf')), (0, 'opacity', -1),
                                    (0, 'shift', 26), (0, 'shift', float('nan'))):
            bad = copy.deepcopy(seq)
            bad['frames'][index][field] = value
            invalid.append(bad)
        for sequence in invalid:
            raw = copy.deepcopy(self.raw)
            self.rig(raw)['sequence'] = sequence
            with self.subTest(sequence=sequence):
                self.assertIsNone(self.parse(raw))

    def test_atlas_cannot_be_attached_to_avatars_or_conflicting_motions(self):
        for change in ({'slot': 'avatar'}, {'motion': 'drift'}, {'sprite': 'open'}):
            raw = copy.deepcopy(self.raw)
            self.rig(raw).update(change)
            with self.subTest(change=change):
                self.assertIsNone(self.parse(raw))

    def test_unrelated_layers_stay_ordinary_static_media(self):
        package = self.parse(self.raw)
        self.assertTrue(all('sequence' not in layer for layer in package['banner'][:3]))
        self.assertEqual(package['banner'][2]['motion'], 'none')
        candles = package['banner'][3:6]
        self.assertEqual([layer['motion'] for layer in candles], ['none', 'none', 'none'])
        self.assertEqual(len({layer['url'] for layer in candles}), 3)
        self.assertEqual(len({layer['sequence']['duration'] for layer in candles}), 3)
        self.assertEqual([len(layer['parts']) for layer in candles], [1, 2, 3])
        for layer in candles:
            self.assertEqual(layer['sequence']['columns'], 1)
            self.assertEqual(layer['sequence']['backdrop'], 0)
            self.assertTrue(all(frame['opacity'] == 1 and 'x' in frame and 'y' in frame for frame in layer['sequence']['frames']))
            for flame in layer['parts']:
                self.assertEqual(flame['sequence']['columns'], 4)
                self.assertEqual(flame['sequence']['rows'], 3)
                self.assertEqual({frame['frame'] for frame in flame['sequence']['frames']}, set(range(12)))
        raw = copy.deepcopy(self.raw)
        raw['slug'] = 'efeito-arbitrary-sequence'
        self.assertIsNotNone(self.parse(raw))
