from copy import deepcopy
from pathlib import Path
from django.test import TestCase
from django.urls import reverse
from .hunter_rework import catalog
from .ranger_reference import extract_reference
from .spellcasting import class_spellcasting_contract, slot_table_at, max_spell_level_at
from .versioned_classes import resolved_classes
from .character_engine import derive
from .hunter_spell_preparation import panel, save_spells
from .models import TbRecursoclasse, TbMagia


class HunterSpellProgressionTests(TestCase):
    def setUp(self):
        from .test_hunter_spell_preparation import HunterSpellPreparationTests
        HunterSpellPreparationTests.setUp(self)
        self.data['spellcasting_progression'] = catalog()['spellcasting_progression']
        TbMagia.objects.filter(nome_ingles="Hunter's Mark").update(classes=self.cl.nome)
        self.bind(self.data)

    def test_creator_offers_two_choices_in_addition_to_fixed_mark(self):
        from .views import _classe_conjuracao
        for ability in ('int', 'wis'):
            choices = _classe_conjuracao(self.cl, ruleset=self.ruleset, ability=ability)
            self.assertEqual(choices['magias_n'], 2)
            self.assertEqual(choices['ability'], ability)
            self.assertNotIn("Hunter's Mark", [m['nome_ingles'] for m in choices['magias_nv1']])

    def test_twenty_levels_match_reference_with_either_ability(self):
        source = Path(__file__).resolve().parent.parent / 'ref/Classes Reworkadas' / catalog()['source_file']
        reference = extract_reference(source)['progression']
        for ability in ('int', 'wis'):
            self.profile.ability = ability
            self.profile.save()
            pc = resolved_classes(self.ruleset, [self.pc])[0]
            for row in reference:
                with self.subTest(ability=ability, level=row['level']):
                    contract = class_spellcasting_contract(pc.id_classe, level=row['level'], ruleset=self.ruleset)
                    self.assertEqual(contract['ability'], ability)
                    self.assertEqual(contract['spell_limit'], {'kind': 'fixed', 'value': str(row['prepared_spells'])})
                    slots = slot_table_at(pc.id_classe, level=row['level'], ruleset=self.ruleset)
                    self.assertEqual(slots, dict(enumerate(row['slots'], 1)))
                    self.assertEqual(max_spell_level_at(contract, pc.id_classe, level=row['level'], ruleset=self.ruleset),
                                     max(circle for circle, count in slots.items() if count))

    def test_first_level_sheet_spend_rest_and_preparation_use_table(self):
        self.pc.nivel = 1
        self.pc.id_subclasse = None
        self.pc.save()
        self.person.nivel = 1
        self.person.save()
        sheet_url = reverse('hunter_sheet', args=[self.person.pk])
        response = self.client.get(sheet_url)
        self.assertEqual(response.status_code, 200)
        slot = next(s for s in response.context['spell_slots'] if s['nivel'] == 1)
        self.assertEqual(slot['total'], 2)
        self.assertEqual(panel(self.profile, derive(self.person, ruleset=self.ruleset))['limite'], 2)
        with self.assertRaises(ValueError):
            save_spells(character_id=self.person.pk, owner_id=self.user.pk,
                selected=[s.slug for s in self.spells[:3]], expected_version=0)
        response = self.client.post(reverse('personagem_usar_slot_magia', args=[self.person.pk]),
            {'nivel': 1, 'acao': 'gastar', 'operation_id': slot['gastar_operation_id'],
             'expected_version': slot['version']}, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['slot']['atual'], 1)
        self.client.post(reverse('personagem_descansar', args=[self.person.pk]), {'tipo': 'longo'})
        slot = next(s for s in self.client.get(sheet_url).context['spell_slots'] if s['nivel'] == 1)
        self.assertEqual((slot['atual'], slot['total']), (2, 2))

    def test_old_revision_and_live_tables_remain_independent(self):
        current = self.ruleset
        self.data.pop('spellcasting_progression')
        TbRecursoclasse.objects.create(id_classe=self.cl, nome='Legacy slots', slug='1o',
            tipo='table-only', valores_json={'1': '8'})
        self.bind(self.data)
        self.assertEqual(slot_table_at(self.cl, level=1, ruleset=self.ruleset)[1], 8)
        self.assertEqual(slot_table_at(self.cl, level=1)[1], 8)
        self.assertEqual(slot_table_at(self.cl, level=1, ruleset=current)[1], 2)
        self.cl.tags_json = []
        self.cl.save()
        self.assertEqual(class_spellcasting_contract(self.cl, level=1, ruleset=current)['spell_limit']['value'], '2')
        self.data = deepcopy(catalog())
        self.data['progression'].pop()
        self.bind(self.data)
        with self.assertRaisesMessage(ValueError, 'Incomplete Hunter'):
            slot_table_at(self.cl, level=1, ruleset=self.ruleset)
