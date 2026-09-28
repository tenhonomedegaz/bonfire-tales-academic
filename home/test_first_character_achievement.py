import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from home.conquistas import conceder_conquista, registrar_criacao_personagem
from home.deploy_sync import MEMORY_MODELS
from home.models import (
    TbConquista, TbCosmetico, TbEventoConquista, TbPersonagem,
    TbUsuarioConquista, TbUsuarioCosmetico,
)
from home.test_criador import _CriadorBase


RULE = {'schema_version': 1, 'metric': 'characters_created',
        'scope': 'account', 'operator': 'gte', 'target': 1}


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
