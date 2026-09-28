"""Integração DB do sync com fixture mínima; execução reservada ao coordenador."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import serializers
from django.test import TestCase

from home import deploy_sync
from home.magic_workshop import resolve_spell_token, spell_token
from home.models import TbBestiario, TbMagia, TbPersonagem, TbPersonagemItem, TbPersonagemMagia


class BattleFamiliarCatalogSyncTests(TestCase):
    def setUp(self):
        # Isola apenas os arquivos operacionais; ORM, transações e sync são reais.
        for name in ('_load_content_deletions', '_load_content_renames'):
            patcher = patch.object(deploy_sync, name, return_value={})
            patcher.start()
            self.addCleanup(patcher.stop)
        self.legacy = TbMagia.objects.create(
            nome='Tradução anterior', nome_ingles='Battle Familiar',
            slug='battle-familiar-legado-sync', nivel=2, descricao='Texto anterior')
        owner = get_user_model().objects.create_user(username='battle-sync-owner')
        self.person = TbPersonagem.objects.create(dono=owner, nome='Conjurador')
        self.acquired = TbPersonagemMagia.objects.create(
            id_personagem=self.person, id_magia=self.legacy, nome='Nome adquirido',
            nivel=2, origem='Mago', preparada=True, sempre_preparada=True)
        self.token = spell_token(self.legacy)
        self.component = TbPersonagemItem.objects.create(
            id_personagem=self.person, nome='Diamante vinculado', qtd=1,
            tags_json=['spell_component{spell:%s, kind:focus, cost_po:25}' % self.token])
        self.scroll = TbPersonagemItem.objects.create(
            id_personagem=self.person, nome='Pergaminho adquirido', qtd=2,
            tags_json=['spell_scroll{spell:%s, level:2, save_dc:13, attack_bonus:5}'
                       % self.token, 'consumable'])
        self.find = TbMagia.objects.create(
            nome='Encontrar Familiar', nome_ingles='Find Familiar',
            slug='find-familiar-controle-sync', nivel=1)
        self.target = TbMagia(
            pk=900001, nome='Familiar de Batalha', nome_ingles='Battle Familiar',
            slug='familiar-de-batalha', nivel=2, descricao='Texto atualizado',
            classes='Druida, Bruxo, Mago', classes_slugs=['druida', 'mistico', 'mago'],
            tags_json=['log_castable'])

    def sync(self, *objects):
        return deploy_sync.sincronizar_conteudo(serializers.serialize('json', objects))

    def snapshot(self):
        return serializers.serialize('json', [
            *TbMagia.objects.order_by('pk'), *TbPersonagem.objects.order_by('pk'),
            *TbPersonagemMagia.objects.order_by('pk'),
            *TbPersonagemItem.objects.order_by('pk')])

    def assert_rejected(self, message, *objects):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, message):
            self.sync(*(objects or [self.target]))
        self.assertEqual(self.snapshot(), before)

    def test_english_identity_preserves_pk_slug_owned_spell_item_token_and_repeat(self):
        before_acquired = serializers.serialize('json', [self.acquired])
        before_component = serializers.serialize('json', [self.component])
        before_scroll = serializers.serialize('json', [self.scroll])
        before_find = serializers.serialize('json', [self.find])
        original_pk, original_slug = self.legacy.pk, self.legacy.slug
        count = TbMagia.objects.count()
        report = self.sync(self.target)
        self.legacy.refresh_from_db()
        self.acquired.refresh_from_db()
        self.find.refresh_from_db()
        self.assertEqual((self.legacy.pk, self.legacy.slug), (original_pk, original_slug))
        self.assertEqual(self.legacy.nome_ingles, 'Battle Familiar')
        self.assertEqual(self.legacy.descricao, 'Texto atualizado')
        self.assertEqual(self.acquired.id_magia_id, self.legacy.pk)
        self.assertEqual(serializers.serialize('json', [self.acquired]), before_acquired)
        self.assertEqual(serializers.serialize('json', [self.find]), before_find)
        self.assertEqual(TbMagia.objects.count(), count)
        self.component.refresh_from_db()
        self.scroll.refresh_from_db()
        self.assertEqual(serializers.serialize('json', [self.component]), before_component)
        self.assertEqual(serializers.serialize('json', [self.scroll]), before_scroll)
        self.assertEqual(resolve_spell_token(self.token).pk, original_pk)
        self.assertEqual(report['renames'], [])
        self.assertFalse(TbMagia.objects.filter(slug=self.target.slug).exists())
        self.assertTrue(report['mem_ok'])
        after_first = self.snapshot()
        second = self.sync(self.target)
        self.assertEqual(self.snapshot(), after_first)
        self.assertEqual(second['renames'], [])
        self.assertIn(('TbMagia', 1, 0), second['pass1'])

    def test_english_identity_is_case_and_space_insensitive(self):
        self.legacy.nome_ingles = '  BATTLE FAMILIAR  '
        self.legacy.save(update_fields=['nome_ingles'])
        self.sync(self.target)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.slug, 'battle-familiar-legado-sync')
        self.assertEqual(self.legacy.nome_ingles, 'Battle Familiar')

    def test_new_identity_inserts_once_without_using_fixture_pk(self):
        self.acquired.delete()
        self.legacy.delete()
        count = TbMagia.objects.count()
        self.sync(self.target)
        created = TbMagia.objects.get(slug=self.target.slug)
        self.sync(self.target)
        self.assertEqual(TbMagia.objects.count(), count + 1)
        self.assertEqual(TbMagia.objects.get(slug=self.target.slug).pk, created.pk)
        self.assertNotEqual(created.pk, self.target.pk)

    def test_duplicate_database_english_identity_rejected(self):
        TbMagia.objects.create(nome='Outra tradução', nome_ingles=' BATTLE FAMILIAR ',
                               slug='battle-duplicate-sync')
        self.assert_rejected('identidade EN duplicada no banco')

    def test_target_slug_owned_by_find_familiar_rejected(self):
        self.find.slug = self.target.slug
        self.find.save(update_fields=['slug'])
        self.assert_rejected('colisão de slug')

    def test_target_slug_with_unknown_english_identity_rejected(self):
        TbMagia.objects.create(nome='Registro sem identidade', slug=self.target.slug)
        self.assert_rejected('colisão de slug')

    def test_duplicate_fixture_english_identity_rejected(self):
        duplicate = TbMagia(pk=900002, nome='Duplicata', nome_ingles=' battle familiar ',
                            slug='duplicate-in-fixture')
        self.assert_rejected('identidade EN duplicada no fixture', self.target, duplicate)

    def test_other_fixture_record_cannot_reclaim_old_or_target_slug(self):
        for slug in (self.legacy.slug, self.target.slug):
            other = TbMagia(pk=900003, nome='Outra magia', nome_ingles='Other Spell', slug=slug)
            for objects in ((other, self.target), (self.target, other)):
                with self.subTest(slug=slug, first=objects[0].nome_ingles):
                    self.assert_rejected('disputa o slug', *objects)

    def test_configured_rename_collision_rejected(self):
        with patch.object(deploy_sync, '_load_content_renames', return_value={
                'TbMagia': {self.find.slug: self.target.slug}}):
            self.assert_rejected('colisão de slug')

    def test_conflicting_rename_destinations_rejected(self):
        for source in (self.legacy.slug, self.target.slug):
            with self.subTest(source=source), patch.object(
                    deploy_sync, '_load_content_renames', return_value={
                        'TbMagia': {source: 'outro-destino'}}):
                self.assert_rejected('outro destino|outro rename')

    def test_matching_configured_rename_does_not_change_live_spell_token(self):
        with patch.object(deploy_sync, '_load_content_renames', return_value={
                'TbMagia': {self.legacy.slug: self.target.slug}}):
            report = self.sync(self.target)
        self.legacy.refresh_from_db()
        self.assertEqual(self.legacy.slug, 'battle-familiar-legado-sync')
        self.assertEqual(report['renames'], [])

    def test_later_sync_failure_rolls_back_content_and_acquired_spells(self):
        invalid = TbBestiario(pk=900004, nome='Inválido', slug='invalid-battle-sync',
                             comunidade=True)
        self.assert_rejected('comunitário', self.target, invalid)
        self.assertFalse(TbBestiario.objects.filter(slug=invalid.slug).exists())

    def test_unrelated_spells_keep_existing_slug_based_policy(self):
        # Não transforma EN em chave genérica para todas as magias.
        other = TbMagia(pk=900005, nome='Find Familiar alternativo',
                        nome_ingles='Find Familiar', slug='find-familiar-outro-sync')
        count = TbMagia.objects.count()
        self.sync(other)
        self.assertEqual(TbMagia.objects.count(), count + 1)
        self.find.refresh_from_db()
        self.assertEqual(self.find.slug, 'find-familiar-controle-sync')
