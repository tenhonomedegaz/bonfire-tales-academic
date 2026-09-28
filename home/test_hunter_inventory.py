import json
from pathlib import Path

from django.test import SimpleTestCase

from .hunter_inventory import build_inventory, content_catalog
from .hunter_rework import catalog, level_features
from .ranger_reference import checksum


ROOT = Path(__file__).resolve().parent.parent


class HunterInventoryTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.saved = json.loads((ROOT / 'docs/hunter-release/inventory.json').read_text(encoding='utf-8'))
        cls.inventory = build_inventory(
            ROOT / 'ref/Classes Reworkadas' / catalog()['source_file'],
            ROOT / 'home/fixtures/conteudo.json',
            [ROOT / doc['path'] for doc in cls.saved['rule_documents']])

    def test_every_source_heading_and_old_feature_has_explicit_review_action(self):
        data = self.inventory
        self.assertEqual(data['coverage']['source_entries'], 211)
        self.assertEqual(data['coverage']['legacy_features'], 53)
        self.assertEqual(len(data['source_matrix']), len(data['reference']['entries']))
        self.assertTrue(all(not row['automatic_equivalence'] for row in data['source_matrix']))
        self.assertTrue(all(row['migration_action'].startswith('retain-legacy')
                            for row in data['baseline']['features']))
        for row in data['baseline_records']:
            original = {key: value for key, value in row.items() if key != 'checksum'}
            self.assertEqual(checksum(original), row['checksum'])
        self.assertFalse(data['activation_ready'])

    def test_published_text_catalog_matches_source_and_filters_all_orders(self):
        expected = content_catalog(self.inventory)
        saved = json.loads((ROOT / 'home/rules/hunter_content.json').read_text(encoding='utf-8'))
        self.assertEqual(saved, expected)
        for order in catalog()['orders']:
            for level in range(3, 21):
                actual = level_features(level, order['id'])
                self.assertEqual(actual, [f for f in expected['features']
                    if f['level'] <= level and f['order'] in ('', order['name'])])
            self.assertEqual({f['level'] for f in actual if f['order']}, {3, 6, 10, 14, 18})

    def test_subordinate_rules_retained_without_other_order_content(self):
        entries = self.inventory['reference']['entries']
        spellcasting = next(e for e in entries if e['name'] == 'Conjuração' and not e['owner'])
        self.assertIn('Inteligência', spellcasting['section_text'])
        self.assertIn('Sabedoria', spellcasting['section_text'])
        style = next(e for e in entries if e['name'] == 'Preparos de Caçada')
        self.assertIn('Estilo de Luta', style['section_text'])
        for feature in content_catalog(self.inventory)['features']:
            self.assertTrue(feature['text'], feature['name'])
            for order in self.inventory['reference']['orders']:
                if order != feature['order']:
                    self.assertNotIn('Nível 18:', feature['text'])
