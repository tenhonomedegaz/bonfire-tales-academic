from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .cosmetics import catalog_options, cosmetic_allowed, invalidate_cosmetic_cache
from .models import (TbClasse, TbConquista, TbConquistaNotificacao, TbCosmetico,
                     TbPersonagem, TbPersonagemClasse, TbUsuarioConquista,
                     TbUsuarioCosmetico)
from .rank_cosmetic_rewards import rank_unlock_metadata, sync_rank_cosmetics


seed = import_module('home.migrations.0164_rank_cosmetic_rewards')


class RankCosmeticRewardsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed.seed_rank_rewards(apps, SimpleNamespace(connection=connection))
        # Freeze the 0164 two-frame fixture even when the database has later data migrations.
        themes = list(TbCosmetico.objects.filter(slug__startswith='tema-rank-'))
        for rule in TbConquista.objects.filter(slug__startswith='elo-'):
            rule.recompensas_extras.remove(*themes)
        cls.klass = TbClasse.objects.create(nome='Rank test class', slug='rank-test-class')

    def setUp(self):
        invalidate_cosmetic_cache()
        self.owner = get_user_model().objects.create_user('rank-frame-owner')

    def tearDown(self):
        invalidate_cosmetic_cache()

    def character(self, level=1, adventures=0, **kwargs):
        character = TbPersonagem.objects.create(
            dono=self.owner, nome='Real rank character', nivel=level,
            aventuras=adventures, **kwargs)
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=self.klass, nivel=level, principal=True)
        return character

    def inventory(self):
        return TbUsuarioCosmetico.objects.filter(user=self.owner)

    def test_seed_is_idempotent_preserves_keys_inventory_and_art(self):
        self.character()
        cosmetic = TbCosmetico.objects.get(slug='moldura-elo-obsidiana-aberta')
        grant = self.inventory().get(cosmetico=cosmetic)
        cosmetic.asset_url = '/preserved-art.png'
        cosmetic.ativo = False
        cosmetic.definicao_json['art'] = 'preserved'
        cosmetic.save()
        seed.seed_rank_rewards(apps, SimpleNamespace(connection=connection))
        seed.seed_rank_rewards(apps, SimpleNamespace(connection=connection))
        cosmetic.refresh_from_db()
        self.assertEqual(TbCosmetico.objects.filter(slug__startswith='moldura-elo-').count(), 14)
        self.assertEqual(TbConquista.objects.filter(slug__startswith='elo-').count(), 7)
        self.assertEqual(cosmetic.asset_url, '/preserved-art.png')
        self.assertEqual(cosmetic.definicao_json['art'], 'preserved')
        self.assertFalse(cosmetic.ativo)
        self.assertEqual(self.inventory().get(cosmetico=cosmetic).pk, grant.pk)
        from .character_engine import aventuras_para_nivel, rank_por_nivel
        from .conquistas import recompensa_ids_da_conquista, regra_rank_valida
        for key, name, level, adventures in seed.RANKS:
            rule = TbConquista.objects.get(slug=f'elo-{key}')
            self.assertTrue(regra_rank_valida(rule.criterio_json))
            rule.full_clean()
            self.assertEqual(len(recompensa_ids_da_conquista(rule)), 2)
            self.assertEqual(rank_por_nivel(level), name)
            self.assertEqual(aventuras_para_nivel(level), adventures)

    def test_plain_or_invalid_character_does_not_unlock(self):
        character = TbPersonagem.objects.create(
            dono=self.owner, nome='No class', nivel=20, aventuras=200)
        self.assertEqual(sync_rank_cosmetics(self.owner), 0)
        row = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=self.klass, nivel=19, principal=True)
        self.assertFalse(self.inventory().exists())
        row.nivel = 20
        row.principal = False
        row.save()
        self.assertFalse(self.inventory().exists())

    def test_each_rank_grants_both_variants_and_all_preceding_ranks(self):
        for index, (_, _, level, adventures) in enumerate(seed.RANKS):
            with self.subTest(level=level):
                self.character(min(level, 20), adventures, publico=False, arquivado=True)
                self.assertEqual(self.inventory().count(), (index + 1) * 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=self.owner).count(), 7)
        self.assertEqual(TbConquistaNotificacao.objects.filter(concessao__user=self.owner).count(), 7)
        self.assertFalse(TbCosmetico.objects.filter(slug__contains='lenda').exists())

    def test_adventure_thresholds_and_diamante_do_not_require_character_level_21(self):
        character = self.character(20, 139)
        self.assertEqual(self.inventory().count(), 10)
        for adventures, expected in ((140, 12), (159, 12), (160, 14), (200, 14)):
            TbPersonagem.objects.filter(pk=character.pk).update(aventuras=adventures)
            catalog_options(self.owner, 'frame', 'perfil')
            self.assertEqual(self.inventory().count(), expected)
        character.refresh_from_db()
        self.assertEqual(character.nivel, 20)

    def test_adventures_without_the_required_build_level_do_not_unlock_higher_rank(self):
        self.character(1, 160)
        self.assertEqual(self.inventory().count(), 2)

    def test_legacy_queryset_updates_are_reconciled_by_both_ownership_apis(self):
        character = self.character()
        TbPersonagem.objects.filter(pk=character.pk).update(nivel=5, aventuras=9)
        character.classes.update(nivel=5)
        self.assertTrue(cosmetic_allowed(self.owner, 'frame', 'elo-ametista-aberta', 'perfil'))
        TbPersonagem.objects.filter(pk=character.pk).update(nivel=9, aventuras=28)
        character.classes.update(nivel=9)
        options = {item['key']: item for item in catalog_options(self.owner, 'frame', 'ficha')}
        self.assertEqual(options['elo-topazio-fechada']['estado'], 'possui')
        self.assertEqual(self.inventory().count(), 6)

    def test_durable_rewards_survive_downgrade_archive_delete_and_level_reassessment(self):
        character = self.character(20, 160)
        baseline = set(self.inventory().values_list('pk', flat=True))
        TbPersonagem.objects.filter(pk=character.pk).update(nivel=1, aventuras=0, arquivado=True)
        character.classes.update(nivel=1)
        from .conquistas import avaliar_nivel_personagem
        avaliar_nivel_personagem(self.owner)
        character.delete()
        avaliar_nivel_personagem(self.owner)
        self.assertTrue(cosmetic_allowed(self.owner, 'frame', 'elo-diamante-fechada'))
        self.assertEqual(set(self.inventory().values_list('pk', flat=True)), baseline)
        self.assertFalse(self.inventory().filter(suspenso_em__isnull=False).exists())

    def test_staff_suspensions_and_revocations_are_not_reactivated(self):
        self.character(20, 160)
        suspended = self.inventory().get(cosmetico__slug='moldura-elo-diamante-aberta')
        now = timezone.now()
        suspended.suspenso_em = now
        suspended.origem = 'staff'
        suspended.save()
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista__slug='elo-rubi')
        grant.revogada_em = now
        grant.save()
        self.inventory().filter(cosmetico__slug__contains='elo-rubi-').update(suspenso_em=now)
        from .conquistas import avaliar_nivel_personagem
        avaliar_nivel_personagem(self.owner)
        self.assertFalse(cosmetic_allowed(self.owner, 'frame', 'elo-diamante-aberta'))
        options = {item['key']: item for item in catalog_options(self.owner, 'frame')}
        self.assertEqual(options['elo-rubi-fechada']['estado'], 'bloqueado')
        suspended.refresh_from_db()
        grant.refresh_from_db()
        self.assertEqual(suspended.suspenso_em, now)
        self.assertEqual(suspended.origem, 'staff')
        self.assertEqual(grant.revogada_em, now)

    def test_preview_rollback_leaves_no_inventory_grants_or_notifications(self):
        with transaction.atomic():
            self.character(20, 160)
            self.assertEqual(self.inventory().count(), 14)
            self.assertTrue(cosmetic_allowed(self.owner, 'frame', 'elo-diamante-aberta'))
            transaction.set_rollback(True)
        self.assertFalse(self.inventory().exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.owner).exists())
        self.assertFalse(TbConquistaNotificacao.objects.filter(concessao__user=self.owner).exists())
        self.assertFalse(cosmetic_allowed(self.owner, 'frame', 'elo-diamante-aberta'))

    def test_multiple_classes_require_consistent_levels_and_one_primary(self):
        character = TbPersonagem.objects.create(
            dono=self.owner, nome='Multiclass', nivel=5, aventuras=9)
        TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=self.klass, nivel=3, principal=True)
        self.assertFalse(self.inventory().exists())
        other = TbPersonagemClasse.objects.create(
            id_personagem=character, id_classe=self.klass, nivel=2, principal=True)
        self.assertFalse(self.inventory().exists())
        other.principal = False
        other.save()
        self.assertEqual(self.inventory().count(), 4)

    def test_requirement_metadata_and_anonymous_access_never_grant(self):
        options = {item['key']: item for item in catalog_options(None, 'frame', 'perfil')}
        diamond = options['elo-diamante-aberta']
        self.assertEqual(diamond['estado'], 'bloqueado')
        self.assertEqual(diamond['requisito'],
                         'alcance lvl 20 e o patamar Epic Boon com um personagem pra liberar')
        self.assertEqual(diamond['unlock_hint'], diamond['requisito'])
        self.assertEqual(diamond['desbloqueio']['min_adventures'], 160)
        self.assertIsNone(diamond['preco'])
        self.assertEqual(diamond['class'], 'frame-elo')
        self.assertEqual(options['elo-ametista-fechada']['requisito'],
                         'alcance lvl 5 com um personagem pra liberar')
        self.assertFalse(self.inventory().exists())
        for invalid in (None, [], {'desbloqueio': {'rank': {}}}):
            self.assertEqual(rank_unlock_metadata(invalid), ({}, ''))

    def test_backfill_is_idempotent_and_preserves_suspensions(self):
        with patch('home.rank_cosmetic_rewards.sync_rank_cosmetics'):
            self.character(20, 160, publico=False, arquivado=True)
            invalid = TbPersonagem.objects.create(
                dono=get_user_model().objects.create_user('rank-invalid-legacy'),
                nome='Missing build', nivel=20, aventuras=200)
        self.assertFalse(self.inventory().exists())
        editor = SimpleNamespace(connection=connection)
        seed.backfill_rank_rewards(apps, editor)
        inventory = self.inventory().first()
        now = timezone.now()
        inventory.suspenso_em = now
        inventory.save()
        baseline = set(self.inventory().values_list('pk', flat=True))
        seed.backfill_rank_rewards(apps, editor)
        self.assertEqual(set(self.inventory().values_list('pk', flat=True)), baseline)
        inventory.refresh_from_db()
        self.assertEqual(inventory.suspenso_em, now)
        self.assertFalse(TbUsuarioCosmetico.objects.filter(user_id=invalid.dono_id).exists())

    def test_permanent_progress_survives_deletion_without_changing_legacy_rules(self):
        from .conquistas import conquistas_do_usuario, ranks_verificaveis
        self.assertNotIn('Diamante', ranks_verificaveis())
        self.assertEqual(ranks_verificaveis(permanentes=True)['Diamante'], 21)
        character = self.character(20, 160)
        character.delete()
        obtained = {item['slug']: item for item in conquistas_do_usuario(self.owner)['obtidas']}
        self.assertEqual(obtained['elo-diamante']['progresso_rank'], {'atual': 21, 'alvo': 21})

    def test_owned_preview_and_selector_query_budget(self):
        from .cosmetics import get_catalog
        self.character(20, 160)
        get_catalog('moldura')
        keys = [f'elo-{key}-{variant}' for key, _, _, _ in seed.RANKS
                for variant in ('aberta', 'fechada')]
        with CaptureQueriesContext(connection) as preview:
            for key in keys:
                self.assertTrue(cosmetic_allowed(self.owner, 'frame', key))
        with CaptureQueriesContext(connection) as selector:
            catalog_options(self.owner, 'frame')
        self.assertEqual(len(preview), 14)
        self.assertLessEqual(len(selector), 11)
        for queries in (preview, selector):
            self.assertFalse(any('TB_Personagem' in query['sql'] for query in queries))
            self.assertFalse(any(query['sql'].lstrip().upper().startswith(
                ('INSERT ', 'UPDATE ', 'DELETE ')) for query in queries))

    def test_automatic_frame_renderer_respects_staff_suspension(self):
        from django.template.loader import render_to_string
        from .ranks import character_rank
        character = self.character()
        context = {'rank':character_rank(character),'owner':self.owner}
        template = 'home/partials/_rank_frame.html'
        self.assertIn('rank-obsidiana-v3.png',render_to_string(template,context))
        self.inventory().filter(cosmetico__slug='moldura-elo-obsidiana-aberta').update(
            suspenso_em=timezone.now())
        self.assertNotIn('<img',render_to_string(template,context))

    def test_automatic_frame_renderer_does_not_grant_to_invalid_build(self):
        from django.template.loader import render_to_string
        from .ranks import character_rank
        character = TbPersonagem.objects.create(dono=self.owner,nome='No valid build',
            aventuras=160,nivel=20)
        html = render_to_string('home/partials/_rank_frame.html',{
            'rank':character_rank(character),'owner':self.owner})
        self.assertNotIn('<img',html)
        self.assertFalse(self.inventory().exists())
