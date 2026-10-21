"""Aceite local da progressão de nível baseada em revisão canônica."""
import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from home.admin import TbConquistaAdmin
from home.conquista_admin_form import ConquistaAdminForm
from home.character_history import capture_build, register_revision
from home.conquistas import (avaliar_nivel_personagem, conceder_conquista,
                            conquistas_do_usuario, registrar_fato_level_up)
from home.event_deliveries import (LEVEL_CONSUMER, process_level_delivery,
                                   reserve_level_delivery)
from home.models import (TbConquista, TbConquistaNotificacao, TbCosmetico,
                         TbEntregaEventoConquista, TbPersonagem,
                         TbPersonagemRevisao, TbEventoConquista,
                         TbUsuarioConquista, TbTransacaoMestre,
                         UserProfile)
from home.test_criador import _CriadorBase
from home.permissions import limite_detalhe, is_rank_esmeralda


class LevelAchievementTests(_CriadorBase):
    def test_level_thirteen_slot_is_proven_once_and_survives_character_deletion(self):
        owner = self._novo_usuario('slot-level-thirteen-owner')
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        primary = character.classes.get(principal=True)
        primary.nivel = 12
        primary.save(update_fields=['nivel'])
        character.nivel = 12
        character.save(update_fields=['nivel', 'atualizado_em'])
        avaliar_nivel_personagem(owner)
        self.assertFalse(is_rank_esmeralda(owner))

        snapshot = capture_build(character)
        primary.nivel = 13
        primary.save(update_fields=['nivel'])
        character.nivel = 13
        character.save(update_fields=['nivel', 'atualizado_em'])
        revision = register_revision(
            character, tipo='level_up', snapshot=snapshot, user=owner,
            nivel_antes=12, nivel_depois=13)
        marker = TbEventoConquista.objects.get(
            conta=owner, tipo='rank_slot_13_granted')
        self.assertEqual(marker.agregado_id, revision.pk)
        self.assertEqual(marker.payload_json['threshold'], 13)
        self.assertTrue(is_rank_esmeralda(owner))
        with (patch('home.permissions.is_colaborador', return_value=False),
              patch('home.permissions.is_mestre_ouro', return_value=False)):
            self.assertEqual(limite_detalhe(owner)['total'], 2)
        owner.email = 'esmeralda@example.invalid'
        owner.save(update_fields=['email'])
        with (patch('home.models.TbEventoConquista.objects.filter',
                    side_effect=RuntimeError('site event table unavailable')),
              patch('home.models.BotMember.objects.filter') as bot_member,
              patch('home.models.BotCharacterLog.objects.filter') as bot_rank):
            bot_member.return_value.values_list.return_value = ['discord-id']
            bot_rank.return_value.exists.return_value = True
            self.assertTrue(is_rank_esmeralda(owner))

        avaliar_nivel_personagem(owner)
        self.assertEqual(TbEventoConquista.objects.filter(
            conta=owner, tipo='rank_slot_13_granted').count(), 1)
        character.delete()
        marker.refresh_from_db()
        self.assertIsNone(marker.personagem_id)
        self.assertTrue(is_rank_esmeralda(owner))

    def test_legacy_level_thirteen_reconciliation_grants_only_proven_slot_once(self):
        owner = self._novo_usuario('legacy-level-thirteen-owner')
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        primary = character.classes.get(principal=True)
        primary.nivel = 12
        primary.save(update_fields=['nivel'])
        character.nivel = 12
        character.save(update_fields=['nivel', 'atualizado_em'])
        snapshot = capture_build(character)
        primary.nivel = 13
        primary.save(update_fields=['nivel'])
        character.nivel = 13
        character.save(update_fields=['nivel', 'atualizado_em'])
        register_revision(character, tipo='level_up', snapshot=snapshot, user=owner,
                          nivel_antes=12, nivel_depois=13)
        TbEventoConquista.objects.filter(
            conta=owner, tipo='rank_slot_13_granted').delete()
        profile, _ = UserProfile.objects.get_or_create(user=owner)
        profile.moedas_mestragem = 7000
        profile.save(update_fields=['moedas_mestragem'])
        ledger_before = TbTransacaoMestre.objects.filter(mestre=owner).count()

        unproven_owner = self._novo_usuario('unproven-level-thirteen-owner')
        unproven_created = self._post_criar(unproven_owner, self._payload('guerreiro'))
        self.assertTrue(unproven_created.json()['ok'], unproven_created.content)
        unproven = TbPersonagem.objects.get(pk=unproven_created.json()['id'])
        unproven.nivel = 13
        unproven.save(update_fields=['nivel', 'atualizado_em'])

        self.assertFalse(TbEventoConquista.objects.filter(
            conta=owner, tipo='rank_slot_13_granted').exists())

        output = StringIO()
        call_command('reconcile_redesign_c_esmeralda', apply=True,
                     confirm='G01-C-LEVEL13', stdout=output)
        applied = json.loads(output.getvalue())
        self.assertEqual(applied['granted_user_ids'], [owner.pk])
        self.assertTrue(is_rank_esmeralda(owner))
        self.assertFalse(is_rank_esmeralda(unproven_owner))

        output = StringIO()
        call_command('reconcile_redesign_c_esmeralda', apply=True,
                     confirm='G01-C-LEVEL13', stdout=output)
        self.assertEqual(json.loads(output.getvalue())['granted_user_ids'], [])
        self.assertEqual(TbEventoConquista.objects.filter(
            conta=owner, tipo='rank_slot_13_granted').count(), 1)
        profile.refresh_from_db()
        self.assertEqual(profile.moedas_mestragem, 7000)
        self.assertEqual(TbTransacaoMestre.objects.filter(mestre=owner).count(),
                         ledger_before)

    def test_level_delivery_replays_milestone_and_reversal_once(self):
        owner = self._novo_usuario('level-delivery-owner')
        rule = TbConquista.objects.create(
            slug='level-delivery-rule', nome='Nível recuperável', ativo=False,
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 2})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        snapshot = capture_build(character)
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        revision = register_revision(
            character, tipo='level_up', snapshot=snapshot, user=owner,
            nivel_antes=1, nivel_depois=2)
        delivery = TbEntregaEventoConquista.objects.get(
            evento__tipo='character_level_up', consumidor=LEVEL_CONSUMER)
        self.assertEqual(delivery.estado, 'pendente')
        rule.ativo = True
        rule.save(update_fields=['ativo'])
        preview = StringIO()
        call_command('processar_entregas_nivel', user_id=owner.pk, stdout=preview)
        self.assertIn('fatos=1 entregas=1', preview.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=owner,
                                                          conquista=rule).exists())
        call_command('processar_entregas_nivel', apply=True,
                     user_id=owner.pk, stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'concluida')
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule, revogada_em__isnull=True).count(), 1)
        call_command('processar_entregas_nivel', apply=True,
                     user_id=owner.pk, stdout=StringIO())
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule).count(), 1)

        self.client.force_login(owner)
        self.assertEqual(self.client.post(reverse('personagem_reverter_revisao',
            args=[character.pk, revision.pk])).status_code, 302)
        reversed_delivery = TbEntregaEventoConquista.objects.get(
            evento__tipo='character_level_reverted', consumidor=LEVEL_CONSUMER)
        self.assertEqual(reversed_delivery.estado, 'pendente')
        call_command('processar_entregas_nivel', apply=True,
                     user_id=owner.pk, stdout=StringIO())
        reversed_delivery.refresh_from_db()
        self.assertEqual(reversed_delivery.estado, 'concluida')
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule, revogada_em__isnull=True).count(), 0)

    def test_level_delivery_failure_after_grant_rolls_back_and_retries(self):
        owner = self._novo_usuario('level-delivery-retry-owner')
        rule = TbConquista.objects.create(
            slug='level-delivery-retry-rule', nome='Nível retentável', ativo=False,
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 2})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        snapshot = capture_build(character)
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        register_revision(character, tipo='level_up', snapshot=snapshot, user=owner,
                          nivel_antes=1, nivel_depois=2)
        rule.ativo = True
        rule.save(update_fields=['ativo'])
        delivery = TbEntregaEventoConquista.objects.get(
            evento__tipo='character_level_up', consumidor=LEVEL_CONSUMER)

        def fail_after_award(user):
            avaliar_nivel_personagem(user)
            raise RuntimeError('falha de teste após concessão')

        with patch('home.event_deliveries.avaliar_nivel_personagem',
                   side_effect=fail_after_award):
            call_command('processar_entregas_nivel', apply=True,
                         user_id=owner.pk, stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'pendente')
        self.assertEqual(delivery.ultimo_erro, 'RuntimeError')
        self.assertFalse(TbUsuarioConquista.objects.filter(user=owner,
                                                          conquista=rule).exists())
        TbEntregaEventoConquista.objects.filter(pk=delivery.pk).update(
            proxima_tentativa_em=timezone.now() - timedelta(seconds=1))
        call_command('processar_entregas_nivel', apply=True,
                     user_id=owner.pk, stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'concluida')
        self.assertEqual(delivery.tentativas, 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule).count(), 1)

    def test_reviewed_level_delivery_resumes_only_its_own_account(self):
        owner = self._novo_usuario('level-delivery-review-owner')
        rule = TbConquista.objects.create(
            slug='level-delivery-review-rule', nome='Nível em revisão', ativo=False,
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 2})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        snapshot = capture_build(character)
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        register_revision(character, tipo='level_up', snapshot=snapshot, user=owner,
                          nivel_antes=1, nivel_depois=2)
        rule.ativo = True
        rule.save(update_fields=['ativo'])
        delivery = TbEntregaEventoConquista.objects.get(consumidor=LEVEL_CONSUMER)
        reservation = reserve_level_delivery(user_id=owner.pk)
        with patch('home.event_deliveries.avaliar_nivel_personagem',
                   side_effect=RuntimeError('falha de teste')):
            self.assertFalse(process_level_delivery(*reservation, max_attempts=1))
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'revisao')
        preview = StringIO()
        call_command('processar_entregas_nivel', resume_review_id=delivery.pk,
                     stdout=preview)
        self.assertIn('estado=revisao tentativas=1', preview.getvalue())
        call_command('processar_entregas_nivel', apply=True,
                     resume_review_id=delivery.pk, stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'concluida')
        self.assertEqual(delivery.tentativas, 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule).count(), 1)

    def test_admin_recovers_contiguous_historical_rank_facts(self):
        owner = self._novo_usuario('rank-history-owner')
        rule = TbConquista.objects.create(
            slug='rank-history-ametista', nome='Ametista histórica QA',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'rank_reached',
                'scope': 'account', 'filters': {'rank': 'Ametista'},
                'operator': 'gte', 'target': 1})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        primary = character.classes.get(principal=True)
        revisions = []
        for level in range(2, 7):
            snapshot = capture_build(character)
            primary.nivel = level
            primary.save(update_fields=['nivel'])
            character.nivel = level
            character.save(update_fields=['nivel', 'atualizado_em'])
            revisions.append(TbPersonagemRevisao.objects.create(
                id_personagem=character, tipo='level_up', snapshot_json=snapshot,
                nivel_antes=level - 1, nivel_depois=level, criado_por=owner))
        administrator = TbConquistaAdmin(TbConquista, admin.site)
        request = RequestFactory().post('/admin/home/tbconquista/')
        with patch.object(administrator, 'message_user') as notification:
            administrator.reprocessar_nivel(request, TbConquista.objects.filter(pk=rule.pk))
            administrator.reprocessar_nivel(request, TbConquista.objects.filter(pk=rule.pk))
        self.assertIn('5 fato(s) recuperado(s)', notification.call_args_list[0].args[1])
        self.assertIn('0 fato(s) recuperado(s)', notification.call_args_list[1].args[1])
        self.assertEqual(TbEventoConquista.objects.filter(
            origem='site', tipo='character_level_up',
            agregado_id__in=[revision.pk for revision in revisions]).count(), 5)
        grant = TbUsuarioConquista.objects.get(user=owner, conquista=rule)
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['nivel'], 6)
        self.assertEqual(TbConquistaNotificacao.objects.filter(concessao=grant).count(), 1)

    def test_admin_recovers_only_verifiable_missing_level_fact(self):
        owner = self._novo_usuario('level-legacy-owner')
        rule = TbConquista.objects.create(
            slug='level-legacy-rule', nome='Nível histórico QA',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 2})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        snapshot = capture_build(character)
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        revision = TbPersonagemRevisao.objects.create(
            id_personagem=character, tipo='level_up', snapshot_json=snapshot,
            nivel_antes=1, nivel_depois=2, criado_por=owner)
        self.assertFalse(TbEventoConquista.objects.filter(agregado_id=revision.pk,
                         tipo='character_level_up').exists())
        administrator = TbConquistaAdmin(TbConquista, admin.site)
        request = RequestFactory().post('/admin/home/tbconquista/')
        with patch.object(administrator, 'message_user') as notification:
            administrator.reprocessar_nivel(request, TbConquista.objects.filter(pk=rule.pk))
            administrator.reprocessar_nivel(request, TbConquista.objects.filter(pk=rule.pk))
        self.assertIn('1 fato(s) recuperado(s)', notification.call_args_list[0].args[1])
        self.assertEqual(TbEventoConquista.objects.filter(
            agregado_id=revision.pk, tipo='character_level_up').count(), 1)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule, revogada_em__isnull=True).count(), 1)
        self.assertEqual(TbConquistaNotificacao.objects.filter(
            concessao__user=owner, concessao__conquista=rule).count(), 1)

        revision.revertida = True
        revision.save(update_fields=['revertida'])
        TbEventoConquista.objects.filter(
            agregado_id=revision.pk, tipo='character_level_up').delete()
        with patch.object(administrator, 'message_user'):
            administrator.reprocessar_nivel(request, TbConquista.objects.filter(pk=rule.pk))
        self.assertFalse(TbEventoConquista.objects.filter(
            agregado_id=revision.pk, tipo='character_level_up').exists())

    def test_admin_does_not_invent_level_fact_without_valid_snapshot(self):
        owner = self._novo_usuario('level-unproven-owner')
        rule = TbConquista.objects.create(
            slug='level-unproven-rule', nome='Nível não comprovado QA',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 2})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        revision = TbPersonagemRevisao.objects.create(
            id_personagem=character, tipo='level_up', snapshot_json={},
            nivel_antes=1, nivel_depois=2, criado_por=owner)
        administrator = TbConquistaAdmin(TbConquista, admin.site)
        with patch.object(administrator, 'message_user') as notification:
            administrator.reprocessar_nivel(
                RequestFactory().post('/admin/home/tbconquista/'),
                TbConquista.objects.filter(pk=rule.pk))
        self.assertIn('1 revisão(ões) sem prova suficiente', notification.call_args.args[1])
        self.assertFalse(TbEventoConquista.objects.filter(
            agregado_id=revision.pk, tipo='character_level_up').exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=owner, conquista=rule).exists())
        revision.snapshot_json = ['estrutura inválida']
        revision.save(update_fields=['snapshot_json'])
        with patch.object(administrator, 'message_user') as notification:
            administrator.reprocessar_nivel(
                RequestFactory().post('/admin/home/tbconquista/'),
                TbConquista.objects.filter(pk=rule.pk))
        self.assertIn('1 revisão(ões) sem prova suficiente', notification.call_args.args[1])
        self.assertFalse(TbEventoConquista.objects.filter(
            agregado_id=revision.pk, tipo='character_level_up').exists())

    def test_rank_milestone_uses_verified_level_and_private_character(self):
        owner = self._novo_usuario('rank-milestone-owner')
        badge = TbCosmetico.objects.create(
            slug='rank-ametista-badge', nome='Badge Ametista QA',
            tipo='badge', origem='conquista')
        form = ConquistaAdminForm(data={
            'slug': 'rank-ametista-qa', 'nome': 'Rank Ametista QA',
            'criterio': 'automatico', 'criterio_json': '{}', 'ativo': 'on',
            'ordem': '0', 'metrica_assistida': 'rank_reached',
            'rank_alvo': 'Ametista', 'recompensa': badge.pk,
        })
        self.assertTrue(form.is_valid(), form.errors)
        rule = form.save()
        self.assertEqual(rule.criterio_json['filters']['rank'], 'Ametista')
        self.assertEqual(ConquistaAdminForm(instance=rule).fields['rank_alvo'].initial,
                         'Ametista')
        administrator = get_user_model().objects.create_superuser(
            'rank-admin-qa', 'rank-admin-qa@example.invalid', 'x')
        self.client.force_login(administrator)
        self.assertContains(self.client.get(reverse(
            'admin:home_tbconquista_change', args=[rule.pk])), 'rank_alvo')
        self.assertFalse(ConquistaAdminForm(data={
            'slug': 'rank-epico-qa', 'nome': 'Rank épico QA',
            'criterio': 'automatico', 'criterio_json': '{}', 'ativo': 'on',
            'ordem': '0', 'metrica_assistida': 'rank_reached',
            'rank_alvo': 'Ascendido',
        }).is_valid())

        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        primary = character.classes.get(principal=True)
        for level in range(2, 6):
            snapshot = capture_build(character)
            primary.nivel = level
            primary.save(update_fields=['nivel'])
            character.nivel = level
            character.save(update_fields=['nivel', 'atualizado_em'])
            register_revision(character, tipo='level_up', snapshot=snapshot,
                              user=owner, nivel_antes=level - 1, nivel_depois=level)
        grant = TbUsuarioConquista.objects.get(user=owner, conquista=rule)
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['personagem_id'], character.pk)
        self.assertEqual(grant.evidencia_json['nivel'], 5)
        own = next(item for item in conquistas_do_usuario(owner)['obtidas']
                   if item['slug'] == rule.slug)
        self.assertEqual(own['progresso_rank'], {'atual': 5, 'alvo': 5})
        self.client.force_login(owner)
        self.assertContains(self.client.get(reverse('profile')),
                            'Maior nível comprovado: 5')
        self.assertContains(self.client.get(reverse('profile')),
                            str(grant.evidencia_json['evento_id']))

        public_url = reverse('public_profile', args=[owner.username])
        self.client.logout()
        self.assertNotContains(self.client.get(public_url), rule.nome)
        self.assertNotContains(self.client.get(public_url),
                               str(grant.evidencia_json['evento_id']))
        character.publico = True
        character.save(update_fields=['publico'])
        self.assertContains(self.client.get(public_url), rule.nome)
        self.assertNotContains(self.client.get(public_url),
                               str(grant.evidencia_json['evento_id']))
        character.publico = False
        character.save(update_fields=['publico'])

        primary.nivel = 4
        primary.save(update_fields=['nivel'])
        character.nivel = 4
        character.save(update_fields=['nivel', 'atualizado_em'])
        avaliar_nivel_personagem(owner)
        grant.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(next(item['progresso_rank']['atual']
                              for item in conquistas_do_usuario(owner)['obtidas']
                              if item['slug'] == rule.slug), 5)

        revision = TbPersonagemRevisao.objects.get(
            id_personagem=character, nivel_depois=5, tipo='level_up')
        revision.revertida = True
        revision.save(update_fields=['revertida'])
        avaliar_nivel_personagem(owner)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        blocked = next(item for item in conquistas_do_usuario(owner)['bloqueadas']
                       if item['slug'] == rule.slug)
        self.assertEqual(blocked['progresso_rank'], {'atual': 4, 'alvo': 5})

        revision.revertida = False
        revision.save(update_fields=['revertida'])
        primary.nivel = 5
        primary.save(update_fields=['nivel'])
        character.nivel = 5
        character.save(update_fields=['nivel', 'atualizado_em'])
        avaliar_nivel_personagem(owner)
        grant.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule).count(), 1)

        # A ficha histórica arquivada sustenta o marco; outra ficha pública
        # permite exibi-lo sem revelar a origem privada.
        character.arquivado = True
        character.save(update_fields=['arquivado'])
        second_payload = self._payload('guerreiro')
        second_payload['nome'] = 'Segundo rank QA'
        second_created = self._post_criar(owner, second_payload)
        self.assertTrue(second_created.json()['ok'], second_created.content)
        second = TbPersonagem.objects.get(pk=second_created.json()['id'])
        second_class = second.classes.get(principal=True)
        for level in range(2, 6):
            snapshot = capture_build(second)
            second_class.nivel = level
            second_class.save(update_fields=['nivel'])
            second.nivel = level
            second.save(update_fields=['nivel', 'atualizado_em'])
            register_revision(second, tipo='level_up', snapshot=snapshot,
                              user=owner, nivel_antes=level - 1, nivel_depois=level)
        second.publico = True
        second.save(update_fields=['publico'])
        grant.refresh_from_db()
        self.assertEqual(grant.evidencia_json['personagem_ids'],
                         sorted([character.pk, second.pk]))
        self.client.logout()
        self.assertContains(self.client.get(public_url), rule.nome)
        second.publico = False
        second.save(update_fields=['publico'])
        self.assertNotContains(self.client.get(public_url), rule.nome)

        # Um marco cadastrado depois do level-up entra pelo reprocessamento do admin.
        late = TbConquista.objects.create(
            slug='rank-ametista-tardio-qa', nome='Ametista tardia QA',
            criterio='automatico', criterio_json=rule.criterio_json)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=owner, conquista=late).exists())
        model_admin = TbConquistaAdmin(TbConquista, admin.site)
        with patch.object(model_admin, 'message_user') as notification:
            model_admin.reprocessar_nivel(
                RequestFactory().post('/admin/home/tbconquista/'),
                TbConquista.objects.filter(pk=late.pk))
        notification.assert_called_once()
        self.assertTrue(TbUsuarioConquista.objects.filter(
            user=owner, conquista=late, revogada_em__isnull=True).exists())

    def test_level_twenty_single_class_requires_canonical_unmixed_history(self):
        owner = self._novo_usuario('level-pure-owner')
        base = {'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'operator': 'gte', 'target': 20}
        pure = TbConquista.objects.create(
            slug='level-twenty-pure-qa', nome='Nível 20 sem multiclasse QA',
            criterio='automatico', criterio_json={
                **base, 'filters': {'class_slug': 'guerreiro', 'single_class': True}})
        ordinary = TbConquista.objects.create(
            slug='level-twenty-ordinary-qa', nome='Nível 20 guerreiro QA',
            criterio='automatico', criterio_json={
                **base, 'filters': {'class_slug': 'guerreiro'}})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        for level in range(2, 21):
            snapshot = capture_build(character)
            primary = character.classes.get(principal=True)
            primary.nivel = level
            primary.save(update_fields=['nivel'])
            character.nivel = level
            character.save(update_fields=['nivel', 'atualizado_em'])
            register_revision(character, tipo='level_up', snapshot=snapshot,
                              user=owner, nivel_antes=level - 1,
                              nivel_depois=level)
        grants = TbUsuarioConquista.objects.filter(
            user=owner, revogada_em__isnull=True,
            conquista__in=[pure, ordinary])
        self.assertEqual(grants.count(), 2)
        self.assertEqual(next(item['progresso_nivel']['atual']
                              for item in conquistas_do_usuario(owner)['obtidas']
                              if item['slug'] == pure.slug), 20)
        profile_url = reverse('public_profile', args=[owner.username])
        self.client.logout()
        self.assertNotContains(self.client.get(profile_url), pure.nome)
        character.publico = True
        character.save(update_fields=['publico'])
        self.assertContains(self.client.get(profile_url), pure.nome)
        character.publico = False
        character.save(update_fields=['publico'])

        # Sem uma subida intermediária, o último nível não prova classe única.
        revision = TbPersonagemRevisao.objects.get(
            id_personagem=character, nivel_antes=2, tipo='level_up')
        revision.tipo = 'nivel_1'
        revision.save(update_fields=['tipo'])
        avaliar_nivel_personagem(owner)
        self.assertIsNotNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=pure).revogada_em)
        self.assertIsNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=ordinary).revogada_em)
        revision.tipo = 'level_up'
        revision.save(update_fields=['tipo'])
        avaliar_nivel_personagem(owner)
        self.assertIsNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=pure).revogada_em)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=pure).count(), 1)

        event = TbEventoConquista.objects.get(
            tipo='character_level_up', agregado_id=revision.pk)
        event.versao_payload = 2
        event.save(update_fields=['versao_payload'])
        avaliar_nivel_personagem(owner)
        self.assertIsNotNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=pure).revogada_em)
        event.versao_payload = 1
        event.save(update_fields=['versao_payload'])
        avaliar_nivel_personagem(owner)
        self.assertIsNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=pure).revogada_em)

        # Um snapshot histórico multiclasses invalida só o marco sem multiclasse.
        snapshot = revision.snapshot_json
        snapshot['classes'].append({**snapshot['classes'][0], 'principal': False})
        revision.snapshot_json = snapshot
        revision.save(update_fields=['snapshot_json'])
        avaliar_nivel_personagem(owner)
        self.assertIsNotNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=pure).revogada_em)
        self.assertIsNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=ordinary).revogada_em)
        self.assertEqual(next(item['progresso_nivel']['atual']
                              for item in conquistas_do_usuario(owner)['bloqueadas']
                              if item['slug'] == pure.slug), 0)

        snapshot['classes'].pop()
        revision.snapshot_json = snapshot
        revision.save(update_fields=['snapshot_json'])
        avaliar_nivel_personagem(owner)
        self.assertIsNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=pure).revogada_em)
        event = TbEventoConquista.objects.get(
            tipo='character_level_up', agregado_id=revision.pk)
        payload = event.payload_json
        payload['classes_after'].append({**payload['classes_after'][0],
                                         'principal': False})
        event.payload_json = payload
        event.save(update_fields=['payload_json'])
        avaliar_nivel_personagem(owner)
        self.assertIsNotNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=pure).revogada_em)
        self.assertIsNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=ordinary).revogada_em)

    def test_private_level_milestone_and_rewards_follow_character_visibility(self):
        owner = self._novo_usuario('level-private-owner')
        badge = TbCosmetico.objects.create(
            slug='level-private-badge', nome='Badge de nivel privado QA',
            tipo='badge', origem='conquista')
        frame = TbCosmetico.objects.create(
            slug='moldura-level-private-frame', nome='Moldura de nivel privado QA',
            tipo='moldura', origem='conquista', escopo='perfil',
            css_class='frame-level-private-qa')
        definition = {'schema_version': 1, 'metric': 'character_level',
                      'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                      'operator': 'gte', 'target': 2}
        badge_rule = TbConquista.objects.create(
            slug='level-private-badge-rule', nome='Marco privado de guerreiro QA',
            criterio='automatico', criterio_json=definition, recompensa=badge)
        TbConquista.objects.create(
            slug='level-private-frame-rule', nome='Marco de moldura privada QA',
            criterio='automatico', criterio_json=definition, recompensa=frame)
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        snapshot = capture_build(character)
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        register_revision(character, tipo='level_up', snapshot=snapshot, user=owner,
                          nivel_antes=1, nivel_depois=2)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, revogada_em__isnull=True,
            conquista__criterio_json__metric='character_level').count(), 2)
        profile = UserProfile.objects.get(user=owner)
        profile.avatar_frame = 'level-private-frame'
        profile.save(update_fields=['avatar_frame'])
        url = reverse('public_profile', args=[owner.username])

        self.client.logout()
        visitor = self.client.get(url)
        for private_text in (badge_rule.nome, badge.nome, frame.slug, frame.css_class):
            self.assertNotContains(visitor, private_text)
        badge_grant = TbUsuarioConquista.objects.get(user=owner, conquista=badge_rule)
        self.assertNotContains(visitor, str(badge_grant.evidencia_json['evento_id']))
        self.client.force_login(owner)
        own_page = self.client.get(url)
        self.assertContains(own_page, badge_rule.nome)
        self.assertContains(own_page, frame.css_class)
        self.assertContains(own_page, str(badge_grant.evidencia_json['evento_id']))
        editor = self.client.get(reverse('profile'))
        self.assertNotIn(badge_rule.nome, str(editor.context['preview_conquistas']))
        self.assertEqual(editor.context['preview_appearance']['frame_key'], 'none')
        self.assertNotIn(badge.slug, [row['slug'] for row in editor.context['preview_badges']])
        self.assertEqual(editor.context['preview_personagens'], [])
        preview = self.client.post(reverse('perfil_preview'), {
            'profile_theme': 'bonfire', 'avatar_frame': 'level-private-frame',
            'profile_effect': 'none',
        })
        self.assertEqual(preview.status_code, 200)
        for private_text in (badge_rule.nome, badge.nome, frame.slug, frame.css_class,
                             str(badge_grant.evidencia_json['evento_id'])):
            self.assertNotIn(private_text, preview.json()['html'])
        moderator = get_user_model().objects.create_superuser(
            'level-private-moderator', 'level-private-moderator@example.invalid', 'x')
        self.client.force_login(moderator)
        self.assertContains(self.client.get(url), badge_rule.nome)
        self.client.logout()

        character.publico = True
        character.save(update_fields=['publico'])
        public_page = self.client.get(url)
        self.assertContains(public_page, badge_rule.nome)
        self.assertContains(public_page, badge.nome)
        self.assertContains(public_page, frame.css_class)
        self.client.force_login(owner)
        public_preview = self.client.post(reverse('perfil_preview'), {
            'profile_theme': 'bonfire', 'avatar_frame': 'level-private-frame',
            'profile_effect': 'none',
        })
        self.assertIn(badge_rule.nome, public_preview.json()['html'])
        self.assertIn(frame.css_class, public_preview.json()['html'])
        self.client.logout()
        character.arquivado = True
        character.save(update_fields=['arquivado'])
        archived_page = self.client.get(url)
        for private_text in (badge_rule.nome, badge.nome, frame.slug, frame.css_class):
            self.assertNotContains(archived_page, private_text)

        independent = TbConquista.objects.create(
            slug='level-badge-independent-qa', nome='Conquista publica independente QA',
            criterio='manual', recompensa=badge)
        conceder_conquista(owner, independent)
        shared_page = self.client.get(url)
        self.assertNotContains(shared_page, badge_rule.nome)
        self.assertContains(shared_page, badge.nome)
        self.assertNotContains(shared_page, frame.css_class)

    def test_replay_de_nivel_antigo_preserva_marco_atual_sem_duplicar_aviso(self):
        owner = self._novo_usuario('level-replay-owner')
        rule = TbConquista.objects.create(
            slug='level-three-replay-test', nome='Marco fictício de nível 3',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 3})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        revisions = []
        for level in (2, 3):
            snapshot = capture_build(character)
            primary = character.classes.get(principal=True)
            primary.nivel = level
            primary.save(update_fields=['nivel'])
            character.nivel = level
            character.save(update_fields=['nivel', 'atualizado_em'])
            revisions.append(register_revision(
                character, tipo='level_up', snapshot=snapshot, user=owner,
                nivel_antes=level - 1, nivel_depois=level))

        first_event = TbEventoConquista.objects.get(
            tipo='character_level_up', agregado_id=revisions[0].pk)
        self.assertEqual(registrar_fato_level_up(revisions[0]).pk, first_event.pk)
        self.assertEqual(first_event.payload_json['level_after'], 2)
        grant = TbUsuarioConquista.objects.get(user=owner, conquista=rule)
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['agregado_id'], revisions[1].pk)
        self.assertEqual(TbConquistaNotificacao.objects.filter(
            concessao__user=owner, concessao__conquista=rule).count(), 1)

    def test_level_rule_grants_once_and_reversal_removes_private_progress(self):
        owner = self._novo_usuario('level-achievement-owner')
        other = self._novo_usuario('level-achievement-other')
        rule = TbConquista.objects.create(
            slug='level-two-test', nome='Marco fictício de nível 2',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'character_level',
                'scope': 'account', 'filters': {'class_slug': 'guerreiro'},
                'operator': 'gte', 'target': 2})
        created = self._post_criar(owner, self._payload('guerreiro'))
        self.assertTrue(created.json()['ok'], created.content)
        character = TbPersonagem.objects.get(pk=created.json()['id'])
        self.client.force_login(owner)
        self.assertContains(self.client.get(reverse('profile')),
                            'Nível atual comprovado: 0')

        snapshot = capture_build(character)
        primary = character.classes.get(principal=True)
        primary.nivel = 2
        primary.save(update_fields=['nivel'])
        character.nivel = 2
        character.save(update_fields=['nivel', 'atualizado_em'])
        revision = register_revision(
            character, tipo='level_up', snapshot=snapshot, user=owner,
            nivel_antes=1, nivel_depois=2)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=owner, conquista=rule, revogada_em__isnull=True).count(), 1)
        self.assertEqual(TbConquistaNotificacao.objects.filter(
            concessao__user=owner, concessao__conquista=rule).count(), 1)
        self.assertContains(self.client.get(reverse('profile')),
                            'Nível atual comprovado: 2')
        self.assertContains(self.client.get(reverse('conquista_notificacoes')),
                            rule.nome)
        registrar_fato_level_up(revision)
        self.assertEqual(TbConquistaNotificacao.objects.filter(
            concessao__user=owner, concessao__conquista=rule).count(), 1)

        later_rule = TbConquista.objects.create(
            slug='level-two-later', nome='Marco retroativo fictício',
            criterio='automatico', criterio_json=rule.criterio_json)
        admin_url = reverse('admin:home_tbconquista_changelist')
        action = {'action': 'reprocessar_nivel',
                  '_selected_action': [str(later_rule.pk)]}
        self.assertNotEqual(self.client.post(admin_url, action).status_code, 200)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=owner, conquista=later_rule).exists())
        staff = get_user_model().objects.create_superuser(
            'level-achievement-admin', 'level-admin@example.invalid', 'x')
        self.client.force_login(staff)
        self.assertEqual(self.client.post(admin_url, action).status_code, 302)
        self.assertTrue(TbUsuarioConquista.objects.filter(
            user=owner, conquista=later_rule, revogada_em__isnull=True).exists())

        self.client.force_login(other)
        denied = self.client.post(reverse('personagem_reverter_revisao',
                                          args=[character.pk, revision.pk]))
        self.assertNotEqual(denied.status_code, 302)
        self.assertNotContains(self.client.get(reverse('conquista_notificacoes')),
                               rule.nome)
        self.client.force_login(owner)
        reversed_response = self.client.post(reverse('personagem_reverter_revisao',
                                                    args=[character.pk, revision.pk]))
        self.assertEqual(reversed_response.status_code, 302)
        grant = TbUsuarioConquista.objects.get(user=owner, conquista=rule)
        self.assertIsNotNone(grant.revogada_em)
        self.assertIsNotNone(TbUsuarioConquista.objects.get(
            user=owner, conquista=later_rule).revogada_em)
        self.assertNotContains(self.client.get(reverse('conquista_notificacoes')),
                               rule.nome)
