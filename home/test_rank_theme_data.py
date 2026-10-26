from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .conquistas import recompensa_ids_da_conquista
from .cosmetics import catalog_options, cosmetic_allowed, get_catalog, invalidate_cosmetic_cache
from .models import (TbClasse, TbConquista, TbConquistaNotificacao, TbCosmetico,
                     TbPersonagem, TbPersonagemClasse, TbUsuarioConquista, TbUsuarioCosmetico)


v1 = import_module('home.migrations.0164_rank_cosmetic_rewards')
v2 = import_module('home.migrations.0165_rank_themes')


class RankThemeDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Start each test at the data contract before 0165, on either test runner.
        TbCosmetico.objects.filter(slug__startswith='tema-rank-').delete()
        v1.seed_rank_rewards(apps, SimpleNamespace(connection=connection))
        cls.klass = TbClasse.objects.create(nome='Rank theme class', slug='rank-theme-class')

    def setUp(self):
        invalidate_cosmetic_cache()
        self.addCleanup(invalidate_cosmetic_cache)
        self.owner = get_user_model().objects.create_user('rank-theme-owner')
        self.editor = SimpleNamespace(connection=connection)

    def apply_data(self):
        v2.seed_rank_themes(apps, self.editor)
        v2.backfill_rank_themes(apps, self.editor)
        invalidate_cosmetic_cache()

    def character(self, level=20, adventures=160):
        character = TbPersonagem.objects.create(
            dono=self.owner, nome='Private archived rank theme hero', nivel=level,
            aventuras=adventures, publico=False, arquivado=True)
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=self.klass, nivel=level, principal=True)
        return character

    def test_labels_and_theme_contract_without_changing_rules_frames_or_sales(self):
        rules = {rule.slug: (rule.pk, rule.criterio_json, rule.recompensa_id)
                 for rule in TbConquista.objects.filter(slug__startswith='elo-')}
        frames = {frame.slug: (frame.pk, frame.definicao_json, frame.css_class)
                  for frame in TbCosmetico.objects.filter(slug__startswith='moldura-elo-')}
        sales = [TbCosmetico.objects.create(
            slug=slug, nome='Sale gallery', tipo='tema', origem='loja_braseiro',
            ativo=False, preco=None) for slug in ('tema-test-moon', 'tema-test-halloween')]
        self.apply_data()
        self.assertEqual(TbConquista.objects.filter(slug__startswith='elo-').count(), 7)
        self.assertEqual(TbCosmetico.objects.filter(slug__startswith='tema-rank-').count(), 7)
        for key, name, level, adventures, motif, _, _ in v2.RANK_THEMES:
            rule = TbConquista.objects.get(slug=f'elo-{key}')
            theme = TbCosmetico.objects.get(slug=f'tema-rank-{key}')
            self.assertEqual((rule.pk, rule.criterio_json, rule.recompensa_id), rules[rule.slug])
            self.assertEqual(rule.nome, f'Rank {name}')
            self.assertEqual(len(recompensa_ids_da_conquista(rule)), 3)
            self.assertEqual(theme.nome, f'Rank {name}')
            self.assertEqual((theme.tipo, theme.origem, theme.escopo, theme.css_class),
                             ('tema', 'conquista', 'ambos', 'theme-data'))
            self.assertTrue(theme.ativo)
            self.assertIsNone(theme.preco)
            definition = theme.definicao_json
            self.assertEqual(definition['motif'], motif)
            self.assertEqual(definition['particula'], 'nenhuma')
            self.assertEqual(definition['vel'], 'lenta')
            self.assertFalse(definition['glow'])
            self.assertEqual(definition['desbloqueio']['min_level'], min(level, 20))
            self.assertEqual(definition['desbloqueio']['min_adventures'], adventures)
            for color in ('accent', 'accent2', 'surface', 'deep'):
                self.assertRegex(definition[color], r'^#[0-9a-fA-F]{6}$')
            for variant in ('aberta', 'fechada'):
                frame = TbCosmetico.objects.get(slug=f'moldura-elo-{key}-{variant}')
                self.assertEqual((frame.pk, frame.definicao_json, frame.css_class), frames[frame.slug])
                self.assertEqual(frame.nome, f'Moldura Rank {name} - {variant}')
        for sale in sales:
            sale.refresh_from_db()
            self.assertEqual(sale.origem, 'loja_braseiro')
            self.assertFalse(sale.ativo)
            self.assertIsNone(sale.preco)

    def test_existing_custom_theme_and_inventory_suspension_are_preserved(self):
        self.character()
        theme = TbCosmetico.objects.create(
            slug='tema-rank-obsidiana', nome='Custom name', tipo='tema',
            origem='conquista', ativo=False, asset_url='/custom.png',
            definicao_json={'accent': '#112233', 'motif': 'runes', 'custom': 'keep'})
        now = timezone.now()
        owned = TbUsuarioCosmetico.objects.create(
            user=self.owner, cosmetico=theme, origem='staff', suspenso_em=now)
        self.apply_data()
        self.apply_data()
        theme.refresh_from_db()
        owned.refresh_from_db()
        self.assertEqual(TbCosmetico.objects.get(slug=theme.slug).pk, theme.pk)
        self.assertEqual(theme.nome, 'Custom name')
        self.assertEqual(theme.asset_url, '/custom.png')
        self.assertFalse(theme.ativo)
        self.assertEqual(theme.definicao_json['accent'], '#112233')
        self.assertEqual(theme.definicao_json['motif'], 'runes')
        self.assertEqual(theme.definicao_json['custom'], 'keep')
        self.assertTrue(theme.definicao_json['desbloqueio']['permanent'])
        self.assertEqual(owned.suspenso_em, now)
        self.assertEqual(owned.origem, 'staff')
        self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'rank-obsidiana'))

    def test_deleted_character_gets_seven_extra_rewards_without_duplicate_grants(self):
        character = self.character()
        old_inventory = set(TbUsuarioCosmetico.objects.filter(user=self.owner).values_list('pk', flat=True))
        old_grants = set(TbUsuarioConquista.objects.filter(user=self.owner).values_list('pk', flat=True))
        old_notices = set(TbConquistaNotificacao.objects.filter(
            concessao__user=self.owner).values_list('pk', flat=True))
        self.assertEqual(len(old_inventory), 14)
        character.delete()
        self.apply_data()
        self.apply_data()
        inventory = set(TbUsuarioCosmetico.objects.filter(user=self.owner).values_list('pk', flat=True))
        self.assertEqual(len(inventory), 21)
        self.assertTrue(old_inventory <= inventory)
        self.assertEqual(set(TbUsuarioConquista.objects.filter(
            user=self.owner).values_list('pk', flat=True)), old_grants)
        self.assertEqual(set(TbConquistaNotificacao.objects.filter(
            concessao__user=self.owner).values_list('pk', flat=True)), old_notices)

    def test_revoked_achievement_is_not_reactivated_and_invalid_build_gets_nothing(self):
        character = self.character()
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista__slug='elo-diamante')
        grant.revogada_em = timezone.now()
        grant.save()
        character.delete()
        self.apply_data()
        self.assertFalse(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico__slug='tema-rank-diamante').exists())
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=self.owner).count(), 20)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        other = get_user_model().objects.create_user('rank-theme-invalid')
        TbPersonagem.objects.create(dono=other, nome='No class', nivel=20, aventuras=200)
        self.apply_data()
        self.assertFalse(TbUsuarioCosmetico.objects.filter(user=other).exists())

    def test_theme_scope_unlock_hint_queryset_sync_and_cost(self):
        self.apply_data()
        character = self.character(1, 0)
        self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'rank-diamante'))
        TbPersonagem.objects.filter(pk=character.pk).update(nivel=20, aventuras=160)
        character.classes.update(nivel=20)
        self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'rank-diamante', 'ficha'))
        self.assertTrue(cosmetic_allowed(self.owner, 'theme', 'rank-diamante', 'perfil'))
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=self.owner).count(), 21)
        options = {item['key']: item for item in catalog_options(self.owner, 'theme')}
        self.assertEqual(options['rank-diamante']['estado'], 'possui')
        self.assertEqual(options['rank-diamante']['unlock_hint'],
                         'alcance lvl 20 e o patamar Epic Boon com um personagem pra liberar')
        get_catalog('tema')
        with CaptureQueriesContext(connection) as queries:
            for key, *_ in v2.RANK_THEMES:
                self.assertTrue(cosmetic_allowed(self.owner, 'theme', f'rank-{key}'))
        self.assertEqual(len(queries), 7)
        self.assertFalse(any('TB_Personagem' in query['sql'] for query in queries))
        theme = TbCosmetico.objects.get(slug='tema-rank-diamante')
        theme.escopo = 'perfil'
        theme.save()
        self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'rank-diamante', 'ficha'))

    def test_temporary_build_rolls_back_all_three_rewards(self):
        self.apply_data()
        with transaction.atomic():
            self.character(1, 0)
            self.assertEqual(TbUsuarioCosmetico.objects.filter(user=self.owner).count(), 3)
            transaction.set_rollback(True)
        self.assertFalse(TbUsuarioCosmetico.objects.filter(user=self.owner).exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.owner).exists())
        self.assertFalse(cosmetic_allowed(self.owner, 'theme', 'rank-obsidiana'))
