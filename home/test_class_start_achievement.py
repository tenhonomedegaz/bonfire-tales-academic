import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse

from home.badges import perfil_badges_batch
from home.conquistas import conceder_conquista, conquistas_do_usuario
from home.models import (TbClasse, TbConquista, TbCosmetico, TbEventoConquista,
                         TbPersonagem, TbPersonagemClasse, TbUsuarioConquista,
                         TbUsuarioCosmetico)
from home.test_criador import _CriadorBase


class ClassStartAchievementTests(_CriadorBase):
    def test_private_class_achievement_is_hidden_from_public_profile(self):
        rule = self._rule()
        rule.nome = 'Conquista da classe oculta QA'
        rule.save(update_fields=['nome'])
        user = self._novo_usuario('private-class-achievement', staff=True)
        created = self._post_criar(user, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        self.assertFalse(character.publico)
        self.assertEqual(conquistas_do_usuario(user, pode_ver_privados=False)['total'], 0)

        url = reverse('public_profile', args=[user.username])
        self.client.logout()
        self.assertNotContains(self.client.get(url), rule.nome)
        self.assertNotContains(self.client.get(url), rule.recompensa.nome)
        self.assertNotIn(rule.recompensa.slug, [badge['slug'] for badge in
                         perfil_badges_batch([user])[user.pk]['badges']])
        self.client.force_login(user)
        self.assertContains(self.client.get(url), rule.nome)
        moderator = get_user_model().objects.create_superuser(
            'class-achievement-moderator', 'class-achievement@example.invalid', 'x')
        self.client.force_login(moderator)
        self.assertContains(self.client.get(url), rule.nome)

        character.publico = True
        character.save(update_fields=['publico'])
        self.client.logout()
        self.assertContains(self.client.get(url), rule.nome)
        self.assertContains(self.client.get(url), rule.recompensa.nome)
        self.assertIn(rule.recompensa.slug, [badge['slug'] for badge in
                      perfil_badges_batch([user])[user.pk]['badges']])
        character.arquivado = True
        character.save(update_fields=['arquivado'])
        self.assertNotContains(self.client.get(url), rule.nome)
        self.assertNotContains(self.client.get(url), rule.recompensa.nome)

    def _rule(self, slug='guerreiro'):
        definition = {'schema_version': 1, 'metric': 'class_started',
                      'scope': 'account', 'filters': {'class_slug': slug},
                      'operator': 'gte', 'target': 1}
        badge = TbCosmetico.objects.create(slug='badge-inicio-classe',
                                           nome='Início de classe', tipo='badge',
                                           origem='conquista')
        rule = TbConquista(slug='inicio-classe', nome='Início de classe',
                          criterio='automatico', criterio_json=definition,
                          recompensa=badge)
        rule.full_clean()
        rule.save()
        return rule

    def test_confirmed_level_one_creation_records_class_once(self):
        rule = self._rule()
        user = self._novo_usuario('class-start-owner', staff=True)
        payload = self._payload('guerreiro')
        self.client.force_login(user)
        preview = self.client.post(reverse('criar_personagem_preview'),
                                   data=json.dumps(payload), content_type='application/json')
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(TbEventoConquista.objects.filter(conta=user).exists())
        created = self._post_criar(user, payload)
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        event = TbEventoConquista.objects.get(agregado_id=character.pk)
        self.assertEqual(event.payload_json, {
            'initial_class_id': TbClasse.objects.get(slug='guerreiro').pk,
            'initial_class_slug': 'guerreiro', 'initial_level': 1,
            'first_character': True})
        grant = TbUsuarioConquista.objects.get(user=user, conquista=rule)
        self.assertEqual(grant.evidencia_json['evento_id'], str(event.pk))
        self.assertEqual(grant.evidencia_json['initial_class_id'],
                         event.payload_json['initial_class_id'])
        self.assertEqual(grant.definicao_json, rule.criterio_json)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(user=user,
                                                          cosmetico=rule.recompensa).exists())
        again = self._post_criar(user, {**payload, 'nome': 'Outro guerreiro'})
        self.assertTrue(again.json()['ok'], again.content)
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user,
                                                           conquista=rule).count(), 1)
        self.assertEqual(TbEventoConquista.objects.filter(conta=user).count(), 2)

    def test_replay_uses_creation_snapshot_after_class_changes(self):
        user = self._novo_usuario('class-start-replay', staff=True)
        created = self._post_criar(user, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        event = TbEventoConquista.objects.get(agregado_id=character.pk)
        TbPersonagemClasse.objects.filter(id_personagem=character, principal=True).update(
            id_classe=TbClasse.objects.get(slug='barbaro'))
        rule = self._rule('guerreiro')
        output = StringIO()
        call_command('reprocessar_inicio_classe', user_id=user.pk, stdout=output)
        self.assertIn('concessoes=1', output.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user,
                                                           conquista=rule).exists())
        call_command('reprocessar_inicio_classe', apply=True, user_id=user.pk,
                     stdout=StringIO())
        call_command('reprocessar_inicio_classe', apply=True, user_id=user.pk,
                     stdout=StringIO())
        grant = TbUsuarioConquista.objects.get(user=user, conquista=rule)
        self.assertEqual(grant.evidencia_json['evento_id'], str(event.pk))
        self.assertEqual(grant.evidencia_json['initial_class_slug'], 'guerreiro')
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user,
                                                           conquista=rule).count(), 1)

    def test_legacy_event_without_snapshot_does_not_infer_current_class(self):
        user = self._novo_usuario('class-start-legacy', staff=True)
        created = self._post_criar(user, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        event = TbEventoConquista.objects.get(agregado_id=created.json()['id'])
        event.payload_json = {}
        event.save(update_fields=['payload_json'])
        rule = self._rule()
        output = StringIO()
        call_command('reprocessar_inicio_classe', apply=True, user_id=user.pk,
                     stdout=output)
        self.assertIn('sem_snapshot=1', output.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user,
                                                           conquista=rule).exists())

    def test_replay_preserves_class_start_after_character_link_is_removed(self):
        user = self._novo_usuario('class-start-archived', staff=True)
        created = self._post_criar(user, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        event = TbEventoConquista.objects.get(agregado_id=created.json()['id'])
        event.personagem = None
        event.save(update_fields=['personagem'])
        rule = self._rule('guerreiro')

        preview = StringIO()
        call_command('reprocessar_inicio_classe', user_id=user.pk, stdout=preview)
        self.assertIn('concessoes=1', preview.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user, conquista=rule).exists())

        call_command('reprocessar_inicio_classe', apply=True, user_id=user.pk,
                     stdout=StringIO())
        grant = TbUsuarioConquista.objects.get(user=user, conquista=rule)
        self.assertEqual(grant.evidencia_json['evento_id'], str(event.pk))
        self.assertEqual(grant.evidencia_json['initial_class_slug'], 'guerreiro')
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=user, cosmetico=rule.recompensa).exists())

        call_command('reprocessar_inicio_classe', apply=True, user_id=user.pk,
                     stdout=StringIO())
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user,
                                                           conquista=rule).count(), 1)

    def test_other_class_does_not_award_and_manual_grant_keeps_origin(self):
        rule = self._rule('guerreiro')
        user = self._novo_usuario('class-start-manual-owner', staff=True)
        staff = self._novo_usuario('class-start-manual-staff', staff=True)
        self.assertTrue(conceder_conquista(user, rule, por=staff))
        grant = TbUsuarioConquista.objects.get(user=user, conquista=rule)
        self.assertEqual(grant.concedida_por_id, staff.pk)
        created = self._post_criar(user, self._payload('barbaro'))
        self.assertTrue(created.json()['ok'], created.content)
        call_command('reprocessar_inicio_classe', apply=True, user_id=user.pk,
                     stdout=StringIO())
        grant.refresh_from_db()
        self.assertEqual(grant.concedida_por_id, staff.pk)
        self.assertEqual(grant.evidencia_json, {})
        self.assertEqual(TbUsuarioConquista.objects.filter(user=user,
                                                           conquista=rule).count(), 1)

    def test_invalid_slug_and_failed_award_do_not_persist_creation(self):
        rule = self._rule()
        rule.criterio_json = {**rule.criterio_json,
                              'filters': {'class_slug': 'Guerreiro'}}
        with self.assertRaises(ValidationError):
            rule.full_clean()
        rule.criterio_json = {**rule.criterio_json,
                              'filters': {'class_slug': 'guerreiro'}}
        user = self._novo_usuario('class-start-failure', staff=True)
        with patch('home.conquistas.conceder_conquista',
                   side_effect=RuntimeError('award unavailable')):
            response = self._post_criar(user, self._payload('guerreiro'))
        self.assertEqual(response.status_code, 500)
        self.assertFalse(TbPersonagem.objects.filter(dono=user).exists())
        self.assertFalse(TbEventoConquista.objects.filter(conta=user).exists())
