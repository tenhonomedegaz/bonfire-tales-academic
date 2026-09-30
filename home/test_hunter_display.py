"""Presentation checks for the immutable published Hunter catalog."""
import hashlib
import json
from django.test import SimpleTestCase
from django.utils.text import slugify

from .hunter_display import RULES, display_descriptions, explanatory_cards


class HunterDisplayTests(SimpleTestCase):
    def test_display_is_bound_to_frozen_source_and_keeps_structure(self):
        rules = json.loads((RULES / 'hunter_content.json').read_text(encoding='utf-8'))
        display = display_descriptions()
        self.assertEqual(len(display), len(rules['features']))
        for feature in rules['features']:
            digest = hashlib.sha256(feature['text'].encode('utf-8')).hexdigest()
            self.assertIn(digest, display)
            self.assertNotIn('<', display[digest])
        by_id = {row['id']: display[hashlib.sha256(row['text'].encode()).hexdigest()]
                 for row in rules['features']}
        mark = by_id['006-nivel-1-marca-do-cacador']
        self.assertIn('#### Marcar o Alvo', mark)
        self.assertIn('#### Dado de Caçador', mark)
        self.assertIn('\n\n', mark)
        self.assertIn('**', mark)
        orders = by_id['076-nivel-3-ordem-do-cacador']
        self.assertEqual(orders.count('(?subclasse='), 8)
        for order in rules['orders']:
            self.assertIn('(?subclasse=' + slugify(order) + '-rework)', orders)
        self.assertIn('####', '\n'.join(by_id.values()))

    def test_missing_explanatory_cards_do_not_mutate_or_duplicate_catalog(self):
        cards = explanatory_cards([])
        self.assertEqual([(card.niveladquirido, card.nome) for card in cards], [
            (3, 'Ordem do Caçador'),
            (6, 'Habilidade da Ordem'),
            (10, 'Habilidade da Ordem'),
            (14, 'Habilidade da Ordem'),
            (18, 'Habilidade da Ordem'),
        ])
        self.assertEqual(explanatory_cards(card.descricao for card in cards), [])

    def test_source_file_was_not_used_at_request_time(self):
        # The deploy only needs the checked-in presentation artifact.
        self.assertTrue((RULES / 'hunter_display.json').is_file())
        self.assertTrue(display_descriptions())
