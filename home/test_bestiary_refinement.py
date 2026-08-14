from django.test import SimpleTestCase

from home.management.commands.importar_bestiario_csv import _split_secao, _traduz_feature
from home.management.commands.refinar_bestiario_descricoes import (
    _merge_block,
    _normalize_translated_text,
    _protect_measurements,
    _restore_measurements,
)


class BestiarySectionParserTests(SimpleTestCase):
    def test_sentence_in_new_paragraph_stays_in_previous_action(self):
        text = (
            'Multiattack. The creature makes one Bite attack and one\n\n'
            'Claw attack.\n\n'
            'Bite. Melee Weapon Attack: +5 to hit.'
        )

        blocks = _split_secao(text, {})

        self.assertEqual([block['name_en'] for block in blocks], ['Multiattack', 'Bite'])
        self.assertIn('Claw attack.', blocks[0]['entries_en'][0])

    def test_complete_sentence_does_not_become_an_action_name(self):
        text = (
            'Multiattack. The creature makes three Chain attacks.\n\n'
            'It can teleport after one of these attacks.\n\n'
            'Chain. Melee Weapon Attack: +6 to hit.'
        )

        blocks = _split_secao(text, {})

        self.assertEqual([block['name_en'] for block in blocks], ['Multiattack', 'Chain'])
        self.assertIn('It can teleport', blocks[0]['entries_en'][0])

    def test_feature_suffix_is_preserved_and_localized(self):
        self.assertEqual(
            _traduz_feature('Legendary Resistance (3/Day)'),
            'Resistencia Lendaria (3/Dia)',
        )


class _FakeTranslator:
    def translate(self, value):
        return {
            'Teleport': 'teletransporte',
            'Official text.': 'Texto oficial.',
        }.get(value, '')


class BestiaryFeatureNameTests(SimpleTestCase):
    def test_untranslated_imported_name_is_localized(self):
        result = _merge_block(
            {'name': 'Teleport', 'entries': ['Texto antigo.']},
            {'name_en': 'Teleport', 'name': 'Teleport', 'entries_en': ['Official text.']},
            _FakeTranslator(),
        )

        self.assertEqual(result['name'], 'Teletransporte')

    def test_manually_reviewed_name_is_preserved(self):
        result = _merge_block(
            {'name': 'Passo pelo Véu', 'entries': ['Texto antigo.']},
            {'name_en': 'Teleport', 'name': 'Teleport', 'entries_en': ['Official text.']},
            _FakeTranslator(),
        )

        self.assertEqual(result['name'], 'Passo pelo Véu')

    def test_hybrid_imported_suffix_can_be_retranslated(self):
        class SuffixTranslator:
            def translate(self, value):
                return 'Resistência Lendária (3/Dia ou 4/Dia no Covil)'

        result = _merge_block(
            {'name': 'Resistencia Lendaria (3/Dia, or 4/Dia in Lair)', 'entries': ['Texto.']},
            {
                'name_en': 'Legendary Resistance (3/Day, or 4/Day in Lair)',
                'name': 'Resistencia Lendaria (3/Dia, or 4/Dia in Lair)',
                'entries_en': ['Official text.'],
            },
            SuffixTranslator(),
        )

        self.assertEqual(result['name'], 'Resistência Lendária (3/Dia ou 4/Dia no Covil)')


class BestiaryMeasurementTests(SimpleTestCase):
    def test_feet_are_presented_in_meters_and_feet(self):
        protected, values = _protect_measurements('reach 5 ft. and range 120 feet')
        restored = _restore_measurements(protected, values)

        self.assertEqual(restored, 'reach 1,5 m [5 pés] and range 36 m [120 pés]')

    def test_old_cached_measurement_is_normalized(self):
        self.assertEqual(
            _normalize_translated_text('alcance de 36,5 m [120 pes]'),
            'alcance de 36 m [120 pés]',
        )
