import json
from pathlib import Path

from django.test import TestCase

from home import test_versioned_derive as fixtures
from home.character_engine import derive, magias_concedidas
from home.content_versions import create_revision, seal_ruleset
from home.models import (TbEssencia, TbMagia, TbPersonagemEscolha, TbPersonagemMagia,
                         TbPersonagemTalento, TbTalento, TbTracoracial)
from home.tag_engine.library import Library
from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class
from home.versioned_conditions import snapshot_conditions
from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
from home.versioned_library import snapshot_library
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_spells import snapshot_spells
from home.views import _innate_spell_uses, _magias_sheet_info, _sync_magias_concedidas


class TalentInnateMaterializationTests(TestCase):
    def setUp(self):
        fixtures.VersionedDeriveTests.setUp(self)
        self.talent = TbTalento.objects.create(
            nome='Innate gift', slug='innate-gift', descricao='', tags_json=[
                'cast{spell:pinned_spell, without{slot}, uses{pb, reset:long_rest}}'])
        self.selection = TbPersonagemTalento.objects.create(
            id_personagem=self.person, id_talento=self.talent,
            categoria='origem', nivel=1, nome=self.talent.nome)

    def seal(self):
        return seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(),
            snapshot_mundane_items(), snapshot_spells(), snapshot_conditions(),
            snapshot_library(raw=Library(prefer_db=False).raw)],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)

    def test_materializes_innate_cast_without_changing_class_knowledge(self):
        ruleset = self.seal()
        for pinned in (None, ruleset):
            with self.subTest(pinned=pinned is not None):
                self.assertEqual(magias_concedidas(self.person, ruleset=pinned)['concedidas'], [])
                _sync_magias_concedidas(self.person, ruleset=pinned)
                _sync_magias_concedidas(self.person, ruleset=pinned)
                managed = TbPersonagemMagia.objects.get(
                    id_personagem=self.person, sempre_preparada=True)
                self.assertEqual(managed.origem, self.talent.nome)
                sheet = _magias_sheet_info(
                    self.person, derive(self.person, ruleset=pinned), [], ruleset=pinned)
                row = next(r for r in sheet['lista'] if r['id'] == managed.pk)
                self.assertEqual(row['innate_max'], 2)
                self.assertTrue(row['innate_without_slot'])
                self.assertTrue(row['innate_key'])
        self.selection.delete()
        _sync_magias_concedidas(self.person)
        self.assertFalse(TbPersonagemMagia.objects.filter(
            id_personagem=self.person, sempre_preparada=True).exists())
        self.assertTrue(TbPersonagemMagia.objects.filter(pk=self.choice.pk).exists())

    def test_only_selected_branch_and_unlocked_level_are_materialized(self):
        self.talent.tags_json = [
            'match(gift){yes:cast{spell:pinned_spell, without{slot}, uses{1, reset:long_rest}}, default:}',
            'requires:lvl{5} cast{spell:pinned_spell, without{slot}, uses{3, reset:long_rest}}']
        self.talent.save()
        ficha = derive(self.person)
        self.assertEqual(_innate_spell_uses(self.person, ficha), {})
        choice = TbPersonagemEscolha.objects.create(
            id_personagem=self.person, tipo='gift', valor='yes', slot=0)
        self.assertEqual(_innate_spell_uses(self.person, ficha)[
            (self.talent.nome, self.spell.slug)]['maximo'], 1)
        _sync_magias_concedidas(self.person)
        choice.delete()
        _sync_magias_concedidas(self.person)
        self.assertFalse(TbPersonagemMagia.objects.filter(
            id_personagem=self.person, sempre_preparada=True).exists())

    def test_selected_spell_cast_resolves_validated_grants_from_its_source(self):
        self.spell.classes = self.cl.nome
        self.spell.save()
        self.talent.tags_json = [
            'spell_selection:pinned-derive{nivel:1, qtd:1}',
            'cast{spell:spell_selection, modifiers{without{slot}}}, resource_cost:1/long_rest']
        self.talent.save()
        ruleset = self.seal()
        for pinned in (None, ruleset):
            with self.subTest(pinned=pinned is not None):
                self.assertEqual(_innate_spell_uses(self.person, ruleset=pinned), {})
                selection = TbPersonagemEscolha.objects.create(
                    id_personagem=self.person, tipo='magia-concedida',
                    origem=self.talent.nome, slot=0, valor=self.spell.slug)
                uses = _innate_spell_uses(self.person, ruleset=pinned)
                self.assertEqual(set(uses), {(self.talent.nome, self.spell.slug)})
                self.assertEqual(uses[(self.talent.nome, self.spell.slug)]['maximo'], 1)
                _sync_magias_concedidas(self.person, ruleset=pinned)
                self.assertEqual(TbPersonagemMagia.objects.filter(
                    id_personagem=self.person, sempre_preparada=True).count(), 1)
                selection.delete()
                _sync_magias_concedidas(self.person, ruleset=pinned)
                self.assertFalse(TbPersonagemMagia.objects.filter(
                    id_personagem=self.person, sempre_preparada=True).exists())

    def test_unresolved_selection_never_borrows_another_sources_spell(self):
        self.feature.tags_json = ['spell:pinned-spell']
        self.feature.save()
        self.talent.tags_json = [
            'cast{spell:spell_selection, without{slot}, uses{1, reset:long_rest}}']
        self.talent.save()
        self.assertEqual(_innate_spell_uses(self.person, ruleset=self.seal()), {})

    def test_catalog_talent_fixed_and_selected_spells_reach_sheet(self):
        records = json.loads((Path(__file__).parent / 'fixtures/conteudo.json').read_text(
            encoding='utf-8'))
        fields = next(row['fields'] for row in records
                      if row['model'] == 'home.tbtalento'
                      and row['fields']['slug'] == 'tocado-pelo-feerico')
        self.talent.nome = fields['nome']
        self.talent.tags_json = fields['tags_json']
        self.talent.save()
        fixed = TbMagia.objects.create(
            nome='Passo Nebuloso', slug='passo-nebuloso', nivel=2, escola='conjuracao')
        chosen = TbMagia.objects.create(
            nome='Escolha elegivel', slug='escolha-elegivel', nivel=1, escola='adivinhacao')
        ruleset = self.seal()
        pending = magias_concedidas(self.person, ruleset=ruleset)['pendentes']
        self.assertEqual(len(pending), 1)
        self.assertIn(chosen.slug, pending[0]['opcoes'])
        choice = TbPersonagemEscolha.objects.create(
            id_personagem=self.person, tipo='magia-concedida', origem=self.talent.nome,
            slot=pending[0]['slot'], valor=chosen.slug)
        self.talent.tags_json = []
        self.talent.save()
        self.assertEqual(_sync_magias_concedidas(self.person, ruleset=ruleset), 0)
        sheet = _magias_sheet_info(
            self.person, derive(self.person, ruleset=ruleset), [], ruleset=ruleset)
        rows = {r['slug']: r for r in sheet['lista'] if r['origem'] == fields['nome']}
        self.assertEqual(set(rows), {fixed.slug, chosen.slug})
        for row in rows.values():
            self.assertTrue(row['sempre_preparada'])
            self.assertTrue(row['innate_without_slot'])
            self.assertEqual(row['innate_max'], 1)
        choice.delete()
        _sync_magias_concedidas(self.person, ruleset=ruleset)
        managed = TbPersonagemMagia.objects.filter(
            id_personagem=self.person, sempre_preparada=True)
        self.assertEqual(list(managed.values_list('id_magia_id', flat=True)), [fixed.pk])

    def test_draconic_imperfect_wings_grants_feather_fall_on_sheet(self):
        records = json.loads((Path(__file__).parent / 'fixtures/conteudo.json').read_text(
            encoding='utf-8'))
        fields = next(row['fields'] for row in records
                      if row['model'] == 'home.tbtracoracial' and row['pk'] == 2285)
        essence = TbEssencia.objects.create(nome='Draconica', slug='draconica')
        trait = TbTracoracial.objects.create(
            id_essencia=essence, nome=fields['nome'], descricao=fields['descricao'],
            nivel_requisito=fields['nivel_requisito'], talento_racial=True,
            pre_requisito=fields['pre_requisito'], tags_json=fields['tags_json'])
        self.selection.delete()
        self.person.id_essencia = essence
        self.person.nivel = 4
        self.person.save()
        self.pc.nivel = 4
        self.pc.save()
        TbPersonagemEscolha.objects.create(
            id_personagem=self.person, tipo='alento', valor='vento', slot=0)
        racial = TbPersonagemTalento.objects.create(
            id_personagem=self.person, categoria='racial', nivel=1, nome=trait.nome)
        spell = TbMagia.objects.create(nome='Queda Suave', slug='queda-suave', nivel=1)
        ruleset = self.seal()
        for pinned in (None, ruleset):
            with self.subTest(pinned=pinned is not None):
                self.assertEqual(magias_concedidas(self.person, ruleset=pinned)['concedidas'], [])
                _sync_magias_concedidas(self.person, ruleset=pinned)
                _sync_magias_concedidas(self.person, ruleset=pinned)
                managed = TbPersonagemMagia.objects.get(
                    id_personagem=self.person, id_magia=spell, sempre_preparada=True)
                self.assertEqual(managed.origem, trait.nome)
                sheet = _magias_sheet_info(
                    self.person, derive(self.person, ruleset=pinned), [], ruleset=pinned)
                row = next(r for r in sheet['lista'] if r['id'] == managed.pk)
                self.assertEqual(row['innate_max'], 1)
                self.assertEqual(row['innate_reset'], 'long_rest')
                self.assertTrue(row['innate_without_slot'])
        racial.delete()
        _sync_magias_concedidas(self.person, ruleset=ruleset)
        self.assertFalse(TbPersonagemMagia.objects.filter(
            id_personagem=self.person, id_magia=spell).exists())
        self.assertTrue(TbPersonagemMagia.objects.filter(pk=self.choice.pk).exists())
