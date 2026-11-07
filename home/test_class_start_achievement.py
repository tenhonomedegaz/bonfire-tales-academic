import json
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from home.badges import perfil_badges_batch
from home.conquistas import (conceder_conquista, conquistas_do_usuario,
                            visibilidade_inicio_classe)
from home.models import (AsaasCheckoutOrder, CosmeticCheckoutPurchase, TbClasse,
                         TbConquista, TbConquistaNotificacao, TbCosmetico,
                         TbEventoConquista, TbPersonagem, TbPersonagemClasse,
                         TbUsuarioConquista, TbUsuarioCosmetico)
from home.test_criador import _CriadorBase


class ClassStartAchievementTests(_CriadorBase):
    def test_registered_class_proof_is_visible_only_to_owner_and_staff(self):
        rule = self._rule()
        rule.descricao = 'Detalhes da classe conquistada.'
        rule.save(update_fields=['descricao'])
        owner = self._novo_usuario('class-proof-owner', staff=True)
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        fact = TbEventoConquista.objects.get(agregado_id=character.pk)
        url = reverse('public_profile', args=[owner.username])

        own_profile = self.client.get(reverse('profile'))
        self.assertContains(own_profile, str(fact.pk))
        self.assertContains(own_profile, '<details class="conquista-info">')
        self.assertContains(own_profile, rule.descricao)
        self.assertContains(self.client.get(url), str(fact.pk))
        self.assertContains(self.client.get(url), character.nome)
        self.client.logout()
        self.assertNotContains(self.client.get(url), str(fact.pk))
        self.assertNotContains(self.client.get(url), 'Provas das conquistas')
        self.assertNotContains(self.client.get(url), rule.descricao)

        character.publico = True
        character.save(update_fields=['publico'])
        self.assertContains(self.client.get(url), rule.nome)
        self.assertContains(self.client.get(url), rule.descricao)
        self.assertContains(self.client.get(url), '<details class="conquista-info">')
        self.assertNotContains(self.client.get(url), str(fact.pk))
        self.assertEqual(conquistas_do_usuario(
            owner, pode_ver_privados=False)['evidencias_privadas'], [])

        moderator = get_user_model().objects.create_superuser(
            'class-proof-moderator', 'class-proof-moderator@example.invalid', 'x')
        self.client.force_login(moderator)
        self.assertContains(self.client.get(url), str(fact.pk))

    def test_second_public_character_exposes_class_without_reawarding(self):
        rule = self._rule()
        owner = self._novo_usuario('second-public-class-owner', staff=True)
        first = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(first.json()['ok'], first.content)
        first_character = TbPersonagem.objects.get(pk=first.json()['id'])
        first_character.arquivado = True
        first_character.save(update_fields=['arquivado'])
        public_url = reverse('public_profile', args=[owner.username])
        self.client.logout()
        self.assertNotContains(self.client.get(public_url), rule.nome)

        second = self._post_criar(owner, {**self._payload('guerreiro'),
                                         'nome': 'Guerreiro público QA'})
        self.assertTrue(second.json()['ok'], second.content)
        second_character = TbPersonagem.objects.get(pk=second.json()['id'])
        grant = TbUsuarioConquista.objects.get(user=owner, conquista=rule)
        first_event_id = grant.evidencia_json['evento_id']
        self.assertEqual(grant.evidencia_json['personagem_ids'],
                         sorted([first_character.pk, second_character.pk]))
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule).count(), 1)
        self.assertEqual(TbConquistaNotificacao.objects.filter(concessao=grant).count(), 1)

        self.client.logout()
        second_character.publico = True
        second_character.save(update_fields=['publico'])
        self.assertContains(self.client.get(public_url), rule.nome)
        self.assertContains(self.client.get(public_url), rule.recompensa.nome)
        second_character.publico = False
        second_character.save(update_fields=['publico'])
        self.assertNotContains(self.client.get(public_url), rule.nome)

        call_command('reprocessar_inicio_classe', apply=True, user_id=owner.pk,
                     stdout=StringIO())
        grant.refresh_from_db()
        self.assertEqual(grant.evidencia_json['evento_id'], first_event_id)
        self.assertEqual(grant.evidencia_json['personagem_ids'],
                         sorted([first_character.pk, second_character.pk]))
        self.assertEqual(TbConquistaNotificacao.objects.filter(concessao=grant).count(), 1)

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

    def test_shared_badge_keeps_independent_achievement_right(self):
        rule = self._rule()
        rule.nome = 'Conquista da classe oculta QA'
        rule.save(update_fields=['nome'])
        user = self._novo_usuario('shared-class-badge', staff=True)
        created = self._post_criar(user, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        self.assertFalse(TbPersonagem.objects.get(pk=created.json()['id']).publico)
        url = reverse('public_profile', args=[user.username])
        self.client.logout()
        self.assertNotContains(self.client.get(url), rule.recompensa.nome)

        independent = TbConquista.objects.create(
            slug='shared-badge-independent', nome='Conquista independente QA',
            criterio='manual', recompensa=rule.recompensa)
        self.assertTrue(conceder_conquista(user, independent))
        self.assertNotIn(rule.recompensa.slug,
                         visibilidade_inicio_classe([user])[1][user.pk])
        self.assertNotContains(self.client.get(url), rule.nome)
        self.assertContains(self.client.get(url), rule.recompensa.nome)
        self.assertIn(rule.recompensa.slug, [badge['slug'] for badge in
                      perfil_badges_batch([user])[user.pk]['badges']])

    def test_private_class_does_not_hide_independently_purchased_badge(self):
        rule = self._rule()
        rule.nome = 'Conquista da classe oculta QA'
        rule.save(update_fields=['nome'])
        user = self._novo_usuario('purchased-class-badge', staff=True)
        created = self._post_criar(user, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        self.assertFalse(TbPersonagem.objects.get(pk=created.json()['id']).publico)
        order = AsaasCheckoutOrder.objects.create(
            user=user, email=user.email, product_code='cosmetic:' + rule.recompensa.slug,
            mode='single', amount=Decimal('12.34'))
        CosmeticCheckoutPurchase.objects.create(
            order=order, beneficiary=user, cosmetico=rule.recompensa,
            slug=rule.recompensa.slug, name=rule.recompensa.nome,
            granted_at=timezone.now())

        self.client.logout()
        url = reverse('public_profile', args=[user.username])
        self.assertNotContains(self.client.get(url), rule.nome)
        self.assertContains(self.client.get(url), rule.recompensa.nome)
        self.assertIn(rule.recompensa.slug, [badge['slug'] for badge in
                      perfil_badges_batch([user])[user.pk]['badges']])

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

    def test_replay_keeps_earlier_class_grant_when_later_fact_fails(self):
        from home.conquistas import avaliar_inicio_classe_evento

        first = self._novo_usuario('class-replay-recovery-1', staff=True)
        second = self._novo_usuario('class-replay-recovery-2', staff=True)
        for user in (first, second):
            response = self._post_criar(user, self._payload('guerreiro'))
            self.assertTrue(response.json()['ok'], response.content)
        rule = self._rule('guerreiro')
        calls = 0

        def fail_second(fact):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('segundo fato indisponivel')
            return avaliar_inicio_classe_evento(fact)

        with patch('home.management.commands.reprocessar_inicio_classe.avaliar_inicio_classe_evento',
                   side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, 'segundo fato indisponivel'):
                call_command('reprocessar_inicio_classe', apply=True, stdout=StringIO())
        self.assertTrue(TbUsuarioConquista.objects.filter(user=first, conquista=rule).exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=second, conquista=rule).exists())
        call_command('reprocessar_inicio_classe', apply=True, stdout=StringIO())
        self.assertEqual(TbUsuarioConquista.objects.filter(conquista=rule).count(), 2)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(cosmetico=rule.recompensa).count(), 2)

    def test_replay_preview_counts_same_class_only_once_without_writing(self):
        user = self._novo_usuario('class-replay-preview-count', staff=True)
        for name in ('Primeiro heroi', 'Segundo heroi'):
            response = self._post_criar(user, {**self._payload('guerreiro'), 'nome': name})
            self.assertTrue(response.json()['ok'], response.content)
        rule = self._rule('guerreiro')
        output = StringIO()
        call_command('reprocessar_inicio_classe', user_id=user.pk, stdout=output)
        self.assertIn('fatos=2 sem_snapshot=0 concessoes=1', output.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=user, conquista=rule).exists())
        self.assertFalse(TbUsuarioCosmetico.objects.filter(user=user,
                                                          cosmetico=rule.recompensa).exists())

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
