import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from home.ranger_reference import checksum, compare_fixture, extract_reference, write_draft


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'ref/Classes Reworkadas/Caçador in Bonfire Tales RPG _ World Anvil.html'


class RangerReferenceTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = extract_reference(SOURCE)

    def test_full_progression_and_order_milestones(self):
        rows = self.reference['progression']
        self.assertEqual([(rows[n - 1]['hunter_die']) for n in (1, 5, 11, 17)],
                         ['d6', 'd8', 'd10', 'd12'])
        self.assertEqual(rows[0]['slots'], [2, 0, 0, 0, 0])
        self.assertEqual(rows[-1]['slots'], [4, 3, 3, 3, 2])
        for order in self.reference['orders']:
            levels = {e['level'] for e in self.reference['entries']
                      if e['owner'] == order and e['level'] is not None}
            self.assertEqual(levels, {3, 6, 10, 14, 18}, order)
        # A class feature following the final order must not belong to that order.
        instinct = next(e for e in self.reference['entries'] if e['name'] == 'Instinto de Caçador')
        self.assertEqual(instinct['owner'], '')

    def test_fighting_style_and_secrets_retain_nested_source_content(self):
        entries = self.reference['entries']
        style = next(e for e in entries if e['name'] == 'Estilo de Luta')
        self.assertEqual(style['parent'], 'Nível 2: Preparos de Caçada')
        self.assertIn('substituir', style['text'])
        degrees = [e for e in entries if e['title'].startswith('Segredos de ')]
        self.assertEqual(len(degrees), 12)
        grenade = next(e for e in entries if e['name'] == 'Granada de Luz')
        self.assertIn('1º Grau', grenade['parent'])
        self.assertIn('Aprimoramento', grenade['text'])

    def test_checksum_is_deterministic_and_changes_with_content(self):
        self.assertEqual(extract_reference(SOURCE), self.reference)
        draft = copy.deepcopy(self.reference)
        expected = draft.pop('checksum')
        self.assertEqual(checksum(draft), expected)
        draft['entries'][0]['text'] += ' changed'
        self.assertNotEqual(checksum(draft), expected)
        self.assertFalse(draft['activation_ready'])

    def test_baseline_preserves_ids_payloads_and_requires_review(self):
        comparison = compare_fixture(self.reference, ROOT / 'home/fixtures/conteudo.json')
        self.assertTrue(comparison['features'])
        for row in comparison['features']:
            self.assertIsInstance(row['legacy_id'], int)
            self.assertEqual(checksum(row['baseline_payload']), row['baseline_checksum'])
            self.assertIn(row['action'], ('review-effects', 'manual-mapping-required'))

    def test_existing_artifact_is_never_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'draft.json'
            write_draft(path, self.reference)
            with self.assertRaises(FileExistsError):
                write_draft(path, {'replaced': True})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), self.reference)

    def test_missing_source_sections_fail_closed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'incomplete.html'
            path.write_text('<div class="user-css-vignette"></div>', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'progression'):
                extract_reference(path)
