from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from .bestiary_false_casts import repair_false_casts, strip_false_casts
from .management.commands.importar_bestiario_csv import _split_secao
from .models import TbBestiario


def sleep_trait():
    return {'name_en': 'Unusual Nature', 'name': 'Natureza Incomum',
            'entries_en': ["The shard doesn't require air, food, drink, or sleep."],
            'entries': ['O fragmento não requer ar, comida, bebida ou sono.'],
            'tags': ['cast{spell:sono}'],
            'spell_refs': [{'slug': 'sono', 'name': 'Sono'}]}


class FalseCastRulesTests(SimpleTestCase):
    def test_damage_resistance_is_not_the_cantrip(self):
        damage = {'name_en': 'Confer Fire Resistance',
                  'entries_en': ['The nightmare can grant Resistance to Fire damage to a rider.'],
                  'tags': ['cast{spell:resistencia}', 'damage{fire}'],
                  'spell_refs': [{'slug': 'resistencia'}]}
        fixed, slugs = strip_false_casts(damage)
        self.assertEqual(slugs, frozenset({'resistencia'}))
        self.assertEqual(fixed['tags'], ['damage{fire}'])
        self.assertNotIn('spell_refs', fixed)

    def test_resistance_spell_and_other_spells_survive(self):
        spellcasting = {'name_en': 'Spellcasting',
                        'entries_en': ['Cantrips (at will): guidance, resistance'],
                        'tags': ['cast{spell:resistencia}']}
        self.assertEqual(strip_false_casts(spellcasting), (spellcasting, frozenset()))
        actual = {'name_en': 'Resistance', 'entries_en': ['The mage casts Resistance.'],
                  'tags': ['cast{spell:resistencia}']}
        self.assertEqual(strip_false_casts(actual), (actual, frozenset()))
        mixed = {'name_en': 'Inhabit Object',
                 'entries_en': ['The shard can cast spells. The rider gains resistance to psychic damage.'],
                 'tags': ['cast{spell:resistencia}', 'cast{spell:voo}']}
        fixed, slugs = strip_false_casts(mixed)
        self.assertEqual(slugs, frozenset({'resistencia'}))
        self.assertEqual(fixed['tags'], ['cast{spell:voo}'])

    def test_import_parser_keeps_damage_resistance_prose_without_spell_reference(self):
        catalog = [{'en_lower': 'resistance', 'slug': 'resistencia',
                    'name_en': 'Resistance', 'name_pt': 'Resistência', 'resolved': True}]
        blocks = _split_secao(
            'Confer Fire Resistance. The nightmare can grant Resistance to Fire damage to a rider.\n'
            'Spellcasting. Cantrips (at will): guidance, resistance.', catalog)
        self.assertEqual(len(blocks), 2)
        self.assertNotIn('spell_refs', blocks[0])
        self.assertEqual(blocks[1]['spell_refs'][0]['slug'], 'resistencia')

    def test_sleep_immunity_is_not_spellcasting_but_other_text_is_preserved(self):
        original = sleep_trait()
        fixed, slugs = strip_false_casts(original)
        self.assertEqual(slugs, frozenset({'sono'}))
        self.assertNotIn('tags', fixed)
        self.assertNotIn('spell_refs', fixed)
        self.assertEqual(fixed['entries'], original['entries'])
        self.assertEqual(original['tags'], ['cast{spell:sono}'])

    def test_real_cast_and_unrelated_trait_are_unchanged(self):
        cast = {'name_en': 'Spellcasting', 'entries_en': ['The mage casts Sleep.'],
                'tags': ['cast{spell:sono}'], 'spell_refs': [{'slug': 'sono'}]}
        self.assertEqual(strip_false_casts(cast), (cast, frozenset()))
        no_match = {**sleep_trait(), 'entries_en': ['The shard casts Sleep.']}
        self.assertEqual(strip_false_casts(no_match), (no_match, frozenset()))

    def test_import_parser_omits_false_cast_but_keeps_actual_spell(self):
        catalog = [{'en_lower': 'sleep', 'slug': 'sono', 'name_en': 'Sleep',
                    'name_pt': 'Sono', 'resolved': True}]
        blocks = _split_secao(
            "Unusual Nature. The shard doesn't require air, food, drink, or sleep.\n"
            'Spellcasting. The shard casts Sleep.', catalog)
        self.assertEqual(len(blocks), 2)
        self.assertNotIn('tags', blocks[0])
        self.assertNotIn('spell_refs', blocks[0])
        self.assertEqual(blocks[1]['tags'], ['cast{spell:sono}'])

    def test_shared_reference_survives_when_other_feature_casts(self):
        trait = sleep_trait()
        spell = {'name_en': 'Spellcasting', 'entries_en': ['The mage casts Sleep.'],
                 'tags': ['cast{spell:sono}'], 'spell_refs': [{'slug': 'sono'}]}
        statblock = {'traits': [trait], 'actions': [spell], 'tags': ['cast{spell:sono}'],
                     'spell_refs': [{'slug': 'sono'}]}
        fixed, tags, description, edits = repair_false_casts(
            statblock, ['cast{spell:sono}'], '#### Magias referenciadas\n- `spell:sono` - Sono\n')
        self.assertEqual(len(edits), 1)
        self.assertEqual(fixed['actions'], [spell])
        self.assertEqual(fixed['spell_refs'], [{'slug': 'sono'}])
        self.assertEqual(tags, ['cast{spell:sono}'])
        self.assertIn('spell:sono', description)


class FalseCastCommandTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.report = Path(self.folder.name) / 'review.json'
        trait = sleep_trait()
        self.before = {'traits': [trait], 'tags': ['cast{spell:sono}'],
                       'spell_refs': [{'slug': 'sono'}]}
        self.creatures = [TbBestiario.objects.create(
            nome=f'Criatura {pk}', slug=f'false-cast-{pk}', pk=pk,
            statblock_json=deepcopy(self.before), tags_json=['cast{spell:sono}'],
            descricao_markdown='#### Magias referenciadas\n- `spell:sono` - Sono\n\n#### Traços\n- Natureza Incomum\n',
            imagem_url='/imagem-propria.png', comunidade=False,
        ) for pk in (6111, 6112)]

    def preview(self):
        call_command('reparar_bestiario_falsas_conjuracoes', output=str(self.report))

    def apply(self):
        call_command('reparar_bestiario_falsas_conjuracoes', manifest=str(self.report), apply=True)

    def test_preview_apply_replay_and_unrelated_fields(self):
        self.preview()
        self.assertEqual(self.creatures[0].statblock_json, self.before)
        report = json.loads(self.report.read_text(encoding='utf-8'))
        self.assertEqual(len(report['rows']), 2)
        self.apply()
        self.apply()
        for creature in self.creatures:
            creature.refresh_from_db()
            self.assertEqual(creature.statblock_json['traits'][0]['entries'],
                             self.before['traits'][0]['entries'])
            self.assertEqual(creature.statblock_json['tags'], [])
            self.assertEqual(creature.statblock_json['spell_refs'], [])
            self.assertEqual(creature.tags_json, [])
            self.assertNotIn('spell:sono', creature.descricao_markdown)
            self.assertEqual(creature.imagem_url, '/imagem-propria.png')

    def test_second_row_change_rolls_back_first(self):
        self.preview()
        second = self.creatures[1]
        second.statblock_json = {**second.statblock_json, 'manual_note': 'edição posterior'}
        second.save(update_fields=['statblock_json'])
        with self.assertRaisesMessage(CommandError, 'Criatura mudou desde a prévia'):
            self.apply()
        self.creatures[0].refresh_from_db()
        self.assertEqual(self.creatures[0].statblock_json, self.before)

    def test_community_or_tampered_report_is_rejected(self):
        self.preview()
        self.creatures[1].comunidade = True
        self.creatures[1].save(update_fields=['comunidade'])
        with self.assertRaisesMessage(CommandError, 'Identidade ou autoria divergente'):
            self.apply()
        self.creatures[1].comunidade = False
        self.creatures[1].save(update_fields=['comunidade'])
        report = json.loads(self.report.read_text(encoding='utf-8'))
        report['rows'][1]['edits'][0]['removed_spell_slugs'] = ['outra-magia']
        self.report.write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaisesMessage(CommandError, 'Reparo diverge da prévia'):
            self.apply()
        self.creatures[0].refresh_from_db()
        self.assertEqual(self.creatures[0].statblock_json, self.before)
