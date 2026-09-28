from types import SimpleNamespace as NS
from django.test import TestCase
from home.models import TbItemMagico
from home.content_versions import seal_ruleset
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_items import snapshot_magic_items
from home.character_engine import _features_de_itens


class VersionedItemsTests(TestCase):
    def setUp(self):
        self.item = TbItemMagico.objects.create(nome='Ring', slug='frozen-ring', slot='dedos',
            requer_sintonizacao=True, tags_json=['ca:+1'], preco='12.50')
        self.ruleset = seal_ruleset([snapshot_magic_items()], evaluator_version=EVALUATOR,
                                    vocabulary_version=VOCABULARY)
        self.entry = NS(id_item_magico_id=self.item.pk, equipado=True, sintonizado=True, nome='My ring')
        self.person = NS(inventario=NS(all=lambda: [self.entry]))

    def read(self):
        return _features_de_itens(self.person, ruleset=self.ruleset)

    def test_frozen_effect_and_live_equipment_state(self):
        self.item.tags_json = ['ca:+9']
        self.item.slot = 'pocao'
        self.item.save()
        self.assertEqual(self.read()[0][2].tags_json, ['ca:+1'])
        self.assertEqual(self.read()[0][1], 'My ring')
        self.entry.sintonizado = False
        self.assertEqual(self.read(), [])
        self.entry.sintonizado = True
        self.entry.equipado = False
        self.assertEqual(self.read(), [])
        self.entry.equipado = True
        self.item.delete()
        self.assertEqual(len(self.read()), 1)

    def test_missing_identity_refuses_current_catalog_substitution(self):
        self.entry.id_item_magico_id = 999999
        with self.assertRaisesMessage(ValueError, 'Magic item absent'):
            self.read()

    def test_consumable_never_grants_equipped_effect(self):
        self.item.slot = 'pocao'
        self.item.save()
        self.ruleset = seal_ruleset([snapshot_magic_items()], evaluator_version=EVALUATOR,
                                    vocabulary_version=VOCABULARY)
        self.assertEqual(self.read(), [])

    def test_armor_calculation_uses_frozen_catalog_and_preserves_inventory(self):
        from home.versioned_items import snapshot_mundane_items
        from home.character_engine import _armadura_equipada
        self.item.slot = 'escudo'
        self.item.tags_json = ['ca:+3']
        self.item.save()
        self.ruleset = seal_ruleset([snapshot_magic_items(), snapshot_mundane_items()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.entry.id_item_mundano_id = None
        self.entry.tags_json = []
        self.entry.id_item_magico = self.item
        self.entry.id_item_mundano = None
        class Inventory:
            def __init__(self, entry): self.entry = entry
            def filter(self, **kw): return self
            def select_related(self, *args): return self
            def __iter__(self): return iter([self.entry] if self.entry.equipado else [])
        self.person.inventario = Inventory(self.entry)
        old = _armadura_equipada(self.person, 2)
        self.assertEqual(old['escudo_bonus'], 3)
        self.assertEqual(_armadura_equipada(self.person, 2, ruleset=self.ruleset), old)
        self.item.tags_json = ['ca:+9']
        self.item.save()
        self.assertEqual(_armadura_equipada(self.person, 2)['escudo_bonus'], 9)
        self.assertEqual(_armadura_equipada(self.person, 2, ruleset=self.ruleset), old)
        self.assertIs(self.entry.id_item_magico, self.item)
        self.assertEqual(self.entry.tags_json, [])
        self.entry.equipado = False
        self.assertFalse(_armadura_equipada(self.person, 2, ruleset=self.ruleset)['tem_escudo'])

    def test_equipment_copy_refuses_missing_catalog_identity(self):
        from home.versioned_items import snapshot_mundane_items, resolved_inventory
        self.ruleset = seal_ruleset([snapshot_magic_items(), snapshot_mundane_items()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.entry.tags_json = []
        self.entry.id_item_mundano_id = 999999
        with self.assertRaisesMessage(ValueError, 'Equipment identity absent'):
            resolved_inventory(self.ruleset, [self.entry])

    def test_weapon_damage_and_proficiency_use_frozen_catalogs(self):
        from home.models import TbItemMundano
        from home.versioned_items import snapshot_mundane_items
        from home.character_engine import _perfis_de_armas
        weapon = TbItemMundano.objects.create(nome='Frozen blade', slug='frozen-blade',
            categoria='arma', subcategoria='arma_simples')
        self.item.slot = 'arma'
        self.item.tags_json = ['dmg:1d8(cortante)']
        self.item.save()
        self.ruleset = seal_ruleset([snapshot_magic_items(), snapshot_mundane_items()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.entry.nome = weapon.nome
        self.entry.id_item_mundano_id = None
        self.entry.tags_json = []
        self.entry.id_item_magico = self.item
        class Inventory:
            def all(inner): return [self.entry]
            def select_related(inner, *args): return inner
        self.person.inventario = Inventory()
        def read(ruleset=None):
            return _perfis_de_armas(self.person, {'FOR': {'mod': 3}, 'DES': {'mod': 1}},
                2, {}, {'Armas Simples'}, [], ruleset=ruleset)
        before = read()
        self.assertEqual(before[0][0]['bonus_ataque'], 5)
        self.assertEqual(before[0][0]['dado'], '1d8')
        self.assertEqual(read(self.ruleset), before)
        weapon.subcategoria = 'arma_marcial_dist'
        weapon.save()
        self.item.tags_json = ['dmg:2d12(fogo)']
        self.item.save()
        self.assertNotEqual(read(), before)
        self.assertEqual(read(self.ruleset), before)
        from home.character_engine import _ataques
        result = _ataques({'ataque_dado': {}, 'ataque_attr': {}, 'n_ataques': 1},
            {'FOR': {'mod': 3}, 'DES': {'mod': 1}}, 2, personagem=self.person,
            prof_armas={'Armas Simples'}, ruleset=self.ruleset)
        self.assertEqual(result['perfis'], before[0])
        self.entry.equipado = False
        self.assertEqual(read(self.ruleset), ([], []))
