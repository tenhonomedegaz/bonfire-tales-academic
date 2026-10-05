import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.conquistas import (
    conceder_conquista, conceder_conquista_em_massa, registrar_criacao_personagem,
)
from home.deploy_sync import MEMORY_MODELS
from home.models import (
    TbConquista, TbConquistaNotificacao, TbCosmetico, TbEventoConquista, TbPersonagem,
    TbUsuarioConquista, TbUsuarioCosmetico,
)
from home.test_criador import _CriadorBase


RULE = {'schema_version': 1, 'metric': 'characters_created',
        'scope': 'account', 'operator': 'gte', 'target': 1}


class AchievementGrantAtomicTests(TestCase):
    def test_mass_grant_rolls_back_every_recipient_on_reward_failure(self):
        users = [get_user_model().objects.create_user(f'atomic-batch-{i}') for i in range(2)]
        badge = TbCosmetico.objects.create(
            slug='badge-atomic-batch', nome='Badge de lote',
            tipo='badge', origem='conquista',
        )
        rule = TbConquista.objects.create(
            slug='atomic-batch', nome='Conquista de lote',
            criterio='manual', recompensa=badge,
        )
        original = TbUsuarioCosmetico.objects.get_or_create
        calls = 0

        def fail_second_reward(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('inventario indisponivel')
            return original(*args, **kwargs)

        with patch.object(TbUsuarioCosmetico.objects, 'get_or_create',
                          side_effect=fail_second_reward):
            with self.assertRaises(RuntimeError):
                conceder_conquista_em_massa(users, rule)
        self.assertEqual(TbUsuarioConquista.objects.filter(conquista=rule).count(), 0)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(cosmetico=badge).count(), 0)

        self.assertEqual(conceder_conquista_em_massa(users, rule), (2, 0))
        self.assertEqual(conceder_conquista_em_massa(users, rule), (0, 2))
        self.assertEqual(TbUsuarioConquista.objects.filter(conquista=rule).count(), 2)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(cosmetico=badge).count(), 2)

    def test_admin_batch_rolls_back_all_achievements_on_reward_failure(self):
        admin_user = get_user_model().objects.create_superuser(
            'atomic-admin', 'atomic-admin@example.invalid', 'password',
        )
        user = get_user_model().objects.create_user('atomic-admin-recipient')
        badge = TbCosmetico.objects.create(
            slug='badge-atomic-admin', nome='Badge de admin',
            tipo='badge', origem='conquista',
        )
        first = TbConquista.objects.create(
            slug='atomic-admin-first', nome='Primeira conquista', criterio='manual',
        )
        second = TbConquista.objects.create(
            slug='atomic-admin-second', nome='Segunda conquista',
            criterio='manual', recompensa=badge,
        )
        self.client.force_login(admin_user)
        payload = {
            'action': 'conceder_a_usuarios', 'confirmar': '1',
            'select_across': '0', '_selected_action': [first.pk, second.pk],
            'usernames': user.username,
        }
        url = reverse('admin:home_tbconquista_changelist')
        with patch.object(TbUsuarioCosmetico.objects, 'get_or_create',
                          side_effect=RuntimeError('inventario indisponivel')):
            with self.assertRaises(RuntimeError):
                self.client.post(url, payload)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user).count(), 0)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=user, cosmetico=badge).count(), 0)

        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user).count(), 2)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=user, cosmetico=badge).count(), 1)

    def test_reward_failure_rolls_back_new_grant_and_reactivation(self):
        user = get_user_model().objects.create_user('atomic-achievement-owner')
        badge = TbCosmetico.objects.create(
            slug='badge-atomic-achievement', nome='Badge atômico',
            tipo='badge', origem='conquista',
        )
        rule = TbConquista.objects.create(
            slug='atomic-achievement', nome='Conquista atômica',
            criterio='manual', recompensa=badge,
        )
        with patch.object(TbUsuarioCosmetico.objects, 'get_or_create',
                          side_effect=RuntimeError('inventário indisponível')):
            with self.assertRaises(RuntimeError):
                conceder_conquista(user, rule)
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user, conquista=rule).exists())

        self.assertTrue(conceder_conquista(user, rule))
        grant = TbUsuarioConquista.objects.get(user=user, conquista=rule)
        possession = TbUsuarioCosmetico.objects.get(user=user, cosmetico=badge)
        grant.revogada_em = timezone.now()
        grant.save(update_fields=['revogada_em'])
        possession.suspenso_em = timezone.now()
        possession.save(update_fields=['suspenso_em'])
        with patch.object(TbUsuarioCosmetico.objects, 'get_or_create',
                          side_effect=RuntimeError('inventário indisponível')):
            with self.assertRaises(RuntimeError):
                conceder_conquista(user, rule)
        grant.refresh_from_db()
        possession.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertIsNotNone(possession.suspenso_em)


class FirstCharacterAchievementTests(_CriadorBase):
    def make_rule(self):
        badge = TbCosmetico.objects.create(slug='badge-primeira-ficha-teste',
            nome='Badge de teste', tipo='badge', origem='conquista')
        return TbConquista.objects.create(slug='primeira-ficha-teste',
            nome='Primeira ficha de teste', criterio='automatico',
            criterio_json=RULE, recompensa=badge)

    def test_real_creation_awards_once_with_event_and_reward(self):
        rule = self.make_rule()
        user = self._novo_usuario('first-achievement-owner', staff=True)
        manual = TbConquista.objects.create(slug='manual-preservada-teste',
            nome='Conquista manual de teste', criterio='manual')
        self.assertTrue(conceder_conquista(user, manual))
        payload = self._payload('guerreiro')
        self.client.force_login(user)
        preview = self.client.post(reverse('criar_personagem_preview'),
            data=json.dumps(payload), content_type='application/json')
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(TbEventoConquista.objects.count(), 0)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user, conquista=rule).count(), 0)

        first = self._post_criar(user, payload)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertTrue(first.json()['ok'])
        character = TbPersonagem.objects.get(pk=first.json()['id'])
        event = TbEventoConquista.objects.get(agregado_id=character.pk)
        grant = TbUsuarioConquista.objects.get(user=user, conquista=rule)
        self.assertEqual(event.conta_id, user.pk)
        notice = TbConquistaNotificacao.objects.get(concessao=grant)
        self.assertContains(self.client.get(reverse('conquista_notificacoes')), rule.nome)
        self.assertIsNone(notice.lida_em)
        self.assertEqual(event.chave_origem, f'personagem:{character.pk}:criado')
        self.assertEqual(grant.evidencia_json['evento_id'], str(event.pk))
        self.assertEqual(grant.definicao_json, RULE)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(user=user, cosmetico=rule.recompensa).exists())
        self.assertEqual(registrar_criacao_personagem(character).pk, event.pk)
        self.assertEqual(TbEventoConquista.objects.count(), 1)

        second = self._post_criar(user, {**payload, 'nome': 'Outro herói'})
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(TbEventoConquista.objects.count(), 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user, conquista=rule).count(), 1)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(user=user, cosmetico=rule.recompensa).count(), 1)
        self.assertTrue(TbUsuarioConquista.objects.filter(user=user, conquista=manual).exists())
        profile = self.client.get(reverse('public_profile', args=[user.username]))
        self.assertContains(profile, rule.nome)
        self.assertNotContains(profile, str(event.pk))
        auditor = get_user_model().objects.create_superuser(
            'achievement-auditor', 'auditor@example.invalid', 'x')
        self.client.force_login(auditor)
        audit = self.client.get(reverse('admin:home_tbeventoconquista_change', args=[event.pk]))
        self.assertContains(audit, event.chave_origem)
        grant_audit = self.client.get(reverse('admin:home_tbusuarioconquista_change', args=[grant.pk]))
        self.assertContains(grant_audit, str(event.pk))

    def test_preexisting_character_does_not_receive_false_first_award(self):
        rule = self.make_rule()
        user = self._novo_usuario('legacy-achievement-owner', staff=True)
        TbPersonagem.objects.create(dono=user, nome='Ficha anterior')
        created = self._post_criar(user, self._payload('guerreiro'))
        self.assertEqual(created.status_code, 200, created.content)
        self.assertEqual(TbEventoConquista.objects.count(), 1)
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user, conquista=rule).exists())

    def test_later_rule_replays_only_explicit_first_character_fact(self):
        user = self._novo_usuario('first-replay-owner', staff=True)
        self.client.force_login(user)
        first = self._post_criar(user, self._payload('guerreiro'))
        second = self._post_criar(user, {**self._payload('guerreiro'),
                                       'nome': 'Segundo herói'})
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        facts = list(TbEventoConquista.objects.filter(conta=user).order_by('ocorrido_em', 'agregado_id'))
        self.assertEqual([fact.payload_json['first_character'] for fact in facts], [True, False])
        rule = self.make_rule()
        output = StringIO()
        call_command('reprocessar_primeira_ficha', '--user-id', str(user.pk), stdout=output)
        self.assertIn('fatos=1 concessoes=1', output.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user, conquista=rule).exists())
        call_command('reprocessar_primeira_ficha', '--apply', '--user-id', str(user.pk), stdout=StringIO())
        grant = TbUsuarioConquista.objects.get(user=user, conquista=rule)
        self.assertEqual(grant.evidencia_json['evento_id'], str(facts[0].pk))
        self.assertEqual(grant.definicao_json, RULE)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(user=user, cosmetico=rule.recompensa).exists())
        self.assertTrue(TbConquistaNotificacao.objects.filter(concessao=grant).exists())
        output = StringIO()
        call_command('reprocessar_primeira_ficha', '--apply', '--user-id', str(user.pk), stdout=output)
        self.assertIn('concessoes=0', output.getvalue())
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user, conquista=rule).count(), 1)

    def test_legacy_fact_without_first_snapshot_is_not_replayed(self):
        user = self._novo_usuario('legacy-first-replay-owner', staff=True)
        TbEventoConquista.objects.create(
            origem='site', chave_origem='personagem:123:criado',
            tipo='character_created', conta=user, agregado_id=123,
            ocorrido_em=timezone.now(), payload_json={},
        )
        rule = self.make_rule()
        output = StringIO()
        call_command('reprocessar_primeira_ficha', '--apply', '--user-id', str(user.pk), stdout=output)
        self.assertIn('fatos=0 concessoes=0', output.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user, conquista=rule).exists())

    def test_failure_rolls_back_character_event_and_grant(self):
        self.make_rule()
        user = self._novo_usuario('rollback-achievement-owner', staff=True)
        with patch('home.conquistas.conceder_conquista', side_effect=RuntimeError('falha de teste')):
            response = self._post_criar(user, self._payload('guerreiro'))
        self.assertEqual(response.status_code, 500)
        self.assertFalse(TbPersonagem.objects.filter(dono=user).exists())
        self.assertFalse(TbEventoConquista.objects.filter(conta=user).exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user).exists())

    def test_unsupported_automatic_rule_is_rejected(self):
        rule = TbConquista(slug='invalida-teste', nome='Inválida', criterio='automatico',
                          criterio_json={'evento': 'aventuras', 'gte': 100})
        with self.assertRaises(ValidationError):
            rule.full_clean()
        legacy = TbConquista.objects.create(slug='legada-teste', nome='Legada',
            criterio='automatico', criterio_json={'evento': 'aventuras', 'gte': 100})
        legacy.nome = 'Legada ajustada'
        legacy.full_clean()
        self.assertIn('TbEventoConquista', MEMORY_MODELS)

    def test_inactive_rule_is_not_awarded(self):
        rule = self.make_rule()
        rule.ativo = False
        rule.save(update_fields=['ativo'])
        user = self._novo_usuario('inactive-achievement-owner', staff=True)
        response = self._post_criar(user, self._payload('guerreiro'))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(TbEventoConquista.objects.filter(conta=user).count(), 1)
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user, conquista=rule).exists())
