from django.test import TestCase
from home.test_versioned_derive import VersionedDeriveTests as Fixtures
from home.models import TbOpcaojogo, TbTalento, TbPersonagemEscolha, TbPersonagemTalento, TbPersonagemMagia
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items
from home.versioned_spells import snapshot_spells
from home.views import _sync_magias_concedidas


class VersionedSyncTests(TestCase):
    def setUp(self):
        Fixtures.setUp(self)
        self.option = TbOpcaojogo.objects.create(nome='Old option', slug='sync-option', tipo='Style')
        self.talent = TbTalento.objects.create(nome='Old talent', slug='sync-talent', descricao='')
        self.feature.tags_json = ['spell_selection:pinned-derive{nivel:1, qtd:1}',
            'grant:opcao:style:sync-option', 'grant:talento{sync-talent, without{asi}}']
        self.feature.save()
        self.spell.classes = self.cl.nome
        self.spell.save()
        self.ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        TbPersonagemEscolha.objects.create(id_personagem=self.person, tipo='magia-concedida',
            origem=self.feature.nome, slot=0, valor=self.spell.slug)

    def test_sync_uses_frozen_identity_and_metadata_without_duplicates(self):
        self.spell.slug = 'renamed-spell'
        self.spell.nome = 'New spell'
        self.spell.save()
        self.option.slug = 'renamed-option'
        self.option.save()
        self.talent.nome = 'New talent'
        self.talent.save()
        self.feature.tags_json = []
        self.feature.save()
        for _ in range(2):
            self.assertEqual(_sync_magias_concedidas(self.person, ruleset=self.ruleset), 0)
        granted = TbPersonagemMagia.objects.get(id_personagem=self.person, sempre_preparada=True)
        self.assertEqual((granted.id_magia_id, granted.nome, granted.nivel),
                         (self.spell.pk, 'Old spell', 1))
        self.assertEqual(TbPersonagemEscolha.objects.get(tipo='grant-opcao', id_personagem=self.person).valor, 'sync-option')
        self.assertEqual(TbPersonagemTalento.objects.get(id_personagem=self.person, categoria='concedido').nome, 'Old talent')
        self.choice.refresh_from_db()
        self.assertEqual(self.choice.nome, 'My spell')
        self.assertTrue(self.choice.preparada)
        self.pc.nivel = 0
        self.pc.save()
        _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        self.assertFalse(TbPersonagemMagia.objects.filter(id_personagem=self.person, sempre_preparada=True).exists())
        self.assertFalse(TbPersonagemEscolha.objects.filter(id_personagem=self.person, tipo='grant-opcao').exists())
        self.assertFalse(TbPersonagemTalento.objects.filter(id_personagem=self.person, categoria='concedido').exists())
        self.assertTrue(TbPersonagemMagia.objects.filter(pk=self.choice.pk).exists())

    def test_missing_fixed_identity_rolls_back_spell_materialization(self):
        self.option.delete()
        with self.assertRaisesMessage(ValueError, 'Granted option identity unavailable'):
            _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        self.assertFalse(TbPersonagemMagia.objects.filter(id_personagem=self.person, sempre_preparada=True).exists())
        self.assertTrue(TbPersonagemMagia.objects.filter(pk=self.choice.pk).exists())
