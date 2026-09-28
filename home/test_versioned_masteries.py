from types import SimpleNamespace as NS
from django.test import TestCase
from home.models import TbItemMundano, TbOpcaojogo
from home.content_versions import seal_ruleset
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_items import snapshot_mundane_items
from home.versioned_options import snapshot_options
from home.character_engine import _maestrias_armas, _mapa_maestria_por_arma


class VersionedMasteriesTests(TestCase):
    def setUp(self):
        self.weapon = TbItemMundano.objects.create(nome='Pinned blade', slug='pinned-blade',
            categoria='arma', subcategoria='arma_simples',
            tags_json=['maestrias{pinned_sap}', 'dmg:1d6(cortante)'])
        self.mastery = TbOpcaojogo.objects.create(nome='Pinned sap', slug='pinned-sap',
            tipo='Maestria de Arma', descricao='Original effect')
        self.ruleset = seal_ruleset([snapshot_mundane_items(), snapshot_options()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.choice = NS(valor='pinned-blade|pinned_sap')
        self.person = NS(escolhas=NS(filter=lambda **kw: NS(order_by=lambda *args: [self.choice])))

    def read(self, ruleset=None):
        return _maestrias_armas(self.person, ruleset=ruleset)

    def test_preserves_mastery_and_attack_mapping_after_catalog_changes(self):
        before = self.read()
        self.assertEqual(before[0]['maestria']['efeito'], 'Original effect')
        self.assertEqual(self.read(self.ruleset), before)
        self.weapon.tags_json = []
        self.weapon.nome = 'Changed blade'
        self.weapon.save()
        self.mastery.descricao = 'Changed effect'
        self.mastery.save()
        self.assertNotEqual(self.read(), before)
        frozen = self.read(self.ruleset)
        self.assertEqual(frozen, before)
        self.assertEqual(_mapa_maestria_por_arma(frozen), _mapa_maestria_por_arma(before))
        self.weapon.delete()
        self.mastery.delete()
        self.assertEqual(self.read(self.ruleset), before)

    def test_live_choice_and_legacy_pending_state_are_preserved(self):
        self.choice.valor = 'pinned-blade'
        result = self.read(self.ruleset)[0]
        self.assertTrue(result['maestria_pendente'])
        self.assertIsNone(result['maestria'])
        self.assertEqual(len(result['maestrias_disponiveis']), 1)
        self.choice.valor = 'pinned-blade|not-offered'
        self.assertTrue(self.read(self.ruleset)[0]['maestria_pendente'])
        self.choice.valor = 'pinned-blade|pinned_sap'
        self.assertFalse(self.read(self.ruleset)[0]['maestria_pendente'])

    def test_incomplete_frozen_catalog_refuses_mutable_fallback(self):
        self.choice.valor = 'unknown-weapon|pinned_sap'
        with self.assertRaisesMessage(ValueError, 'Mastery weapon absent'):
            self.read(self.ruleset)
        self.assertFalse(self.read()[0]['encontrada'])
        self.choice.valor = 'pinned-blade|pinned_sap'
        self.mastery.delete()
        incomplete = seal_ruleset([snapshot_mundane_items(), snapshot_options()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        TbOpcaojogo.objects.create(nome='Replacement', slug='pinned-sap', tipo='Maestria de Arma')
        with self.assertRaisesMessage(ValueError, 'Weapon mastery absent'):
            self.read(incomplete)
