from io import StringIO
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from home.conquista_admin_form import ConquistaAdminForm
from home.conquistas import (avaliar_aventuras_jogadas, avaliar_quests_categorizadas,
                            registrar_fato_aventura)
from home.event_deliveries import (ADVENTURE_CONSUMER, process_adventure_delivery,
                                   reserve_adventure_delivery)
from home.models import (TbClasse, TbConquista, TbCosmetico, TbEventoConquista,
                         TbEntregaEventoConquista, TbPersonagem, TbPersonagemAventura,
                         TbPersonagemClasse,
                         TbUsuarioConquista, TbUsuarioCosmetico)
from home.test_criador import _CriadorBase


class AdventuresAchievementTests(_CriadorBase):
    def setUp(self):
        super().setUp()
        self.owner = self._novo_usuario('adventures-achievement-owner')
        self.staff = self._novo_usuario('adventures-achievement-staff', staff=True)
        self.character = TbPersonagem.objects.create(
            dono=self.owner, nome='Aventureiro', nivel=1)
        TbPersonagemClasse.objects.create(
            id_personagem=self.character,
            id_classe=TbClasse.objects.get(slug='guerreiro'), nivel=1, principal=True)
        self.badge = TbCosmetico.objects.create(
            slug='badge-aventuras-qa', nome='Mesas verificadas QA',
            tipo='badge', origem='conquista')
        self.definition = {
            'schema_version': 1, 'metric': 'adventures_played',
            'scope': 'account', 'aggregate': 'sum',
            'filters': {'valid': True, 'origin': 'played_session'},
            'operator': 'gte', 'target': 3,
        }
        self.rule = TbConquista(
            slug='aventuras-verificadas-qa', nome='Aventuras verificadas QA',
            criterio='automatico', criterio_json=self.definition,
            recompensa=self.badge)
        self.rule.full_clean()
        self.rule.save()

    def launch(self, quantity):
        self.client.force_login(self.staff)
        return self.client.post(
            reverse('personagem_registrar_aventuras', args=[self.character.pk]), {
                'nome_aventura': 'Mesa verificada QA', 'aventuras': quantity,
                'mestre': self.staff.pk, 'data_missao': '2026-09-27',
            })

    def test_durable_adventure_delivery_replays_both_metrics_and_reversal(self):
        self.rule.ativo = False
        self.rule.save(update_fields=['ativo'])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(
            reverse('personagem_registrar_aventuras', args=[self.character.pk]), {
                'nome_aventura': 'Quest comprovada', 'aventuras': 3,
                'mestre': self.staff.pk, 'data_missao': '2026-09-27',
                'quest_category': 'bg_token',
            }).status_code, 302)
        quest = TbConquista.objects.create(
            slug='quest-delivery-bg', nome='Quest entregue', criterio='automatico',
            criterio_json={'schema_version': 1, 'metric': 'quests_completed',
                           'scope': 'account', 'filters': {'category': 'bg_token',
                                                          'valid': True},
                           'operator': 'gte', 'target': 1})
        self.rule.ativo = True
        self.rule.save(update_fields=['ativo'])
        event = TbEventoConquista.objects.get(tipo='adventure_recorded')
        delivery = TbEntregaEventoConquista.objects.get(
            evento=event, consumidor=ADVENTURE_CONSUMER)
        self.assertEqual(delivery.estado, 'pendente')
        preview = StringIO()
        call_command('processar_entregas_aventura', user_id=self.owner.pk,
                     stdout=preview)
        self.assertIn('fatos=1 entregas=1', preview.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.owner).exists())
        call_command('processar_entregas_aventura', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'concluida')
        self.assertEqual(set(TbUsuarioConquista.objects.filter(
            user=self.owner).values_list('conquista_id', flat=True)),
            {self.rule.pk, quest.pk})
        call_command('processar_entregas_aventura', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        self.assertEqual(TbUsuarioConquista.objects.filter(user=self.owner).count(), 2)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge).count(), 1)

        ledger = TbPersonagemAventura.objects.get(origem='mesa')
        self.assertEqual(self.client.post(reverse(
            'personagem_reverter_aventura', args=[self.character.pk, ledger.pk]
        )).status_code, 302)
        reversed_delivery = TbEntregaEventoConquista.objects.get(
            evento__tipo='adventure_reverted', consumidor=ADVENTURE_CONSUMER)
        self.assertEqual(reversed_delivery.estado, 'pendente')
        call_command('processar_entregas_aventura', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        reversed_delivery.refresh_from_db()
        self.assertEqual(reversed_delivery.estado, 'concluida')
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, revogada_em__isnull=True).count(), 0)

    def test_failed_delivery_rolls_back_grant_and_retries(self):
        self.rule.ativo = False
        self.rule.save(update_fields=['ativo'])
        self.assertEqual(self.launch(3).status_code, 302)
        self.rule.ativo = True
        self.rule.save(update_fields=['ativo'])
        delivery = TbEntregaEventoConquista.objects.get(
            evento__tipo='adventure_recorded', consumidor=ADVENTURE_CONSUMER)
        with patch('home.event_deliveries.avaliar_quests_categorizadas',
                   side_effect=RuntimeError('falha de teste')):
            call_command('processar_entregas_aventura', apply=True,
                         user_id=self.owner.pk, stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'pendente')
        self.assertEqual(delivery.ultimo_erro, 'RuntimeError')
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.owner).exists())
        TbEntregaEventoConquista.objects.filter(pk=delivery.pk).update(
            proxima_tentativa_em=timezone.now() - timedelta(seconds=1))
        call_command('processar_entregas_aventura', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'concluida')
        self.assertEqual(delivery.tentativas, 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).count(), 1)

    def test_reviewed_adventure_delivery_can_resume_its_own_account(self):
        self.rule.ativo = False
        self.rule.save(update_fields=['ativo'])
        self.assertEqual(self.launch(3).status_code, 302)
        self.rule.ativo = True
        self.rule.save(update_fields=['ativo'])
        delivery = TbEntregaEventoConquista.objects.get(
            evento__tipo='adventure_recorded', consumidor=ADVENTURE_CONSUMER)
        reservation = reserve_adventure_delivery(user_id=self.owner.pk)
        with patch('home.event_deliveries.avaliar_quests_categorizadas',
                   side_effect=RuntimeError('falha de teste')):
            self.assertFalse(process_adventure_delivery(*reservation, max_attempts=1))
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'revisao')
        preview = StringIO()
        call_command('processar_entregas_aventura', resume_review_id=delivery.pk,
                     stdout=preview)
        self.assertIn('estado=revisao tentativas=1', preview.getvalue())
        call_command('processar_entregas_aventura', apply=True,
                     resume_review_id=delivery.pk, stdout=StringIO())
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, 'concluida')
        self.assertEqual(delivery.tentativas, 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).count(), 1)

    def test_adventure_rule_requires_boolean_valid_before_awarding(self):
        malformed = {**self.definition,
                     'filters': {'valid': 1, 'origin': 'played_session'}}
        rule = TbConquista(
            slug='aventuras-filtro-invalido', nome='Filtro estrito',
            criterio='automatico', criterio_json=malformed)
        with self.assertRaises(ValidationError):
            rule.full_clean()
        rule.save()  # Uma definição legada ou importada também falha fechada no avaliador.
        self.assertEqual(self.launch(3).status_code, 302)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=rule).exists())
        rule.criterio_json = self.definition
        rule.full_clean()
        rule.save(update_fields=['criterio_json'])
        avaliar_aventuras_jogadas(self.owner)
        self.assertTrue(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=rule, revogada_em__isnull=True).exists())

    def test_admin_reprocesses_existing_adventure_and_quest_facts(self):
        self.rule.ativo = False
        self.rule.save(update_fields=['ativo'])
        self.client.force_login(self.staff)
        recorded = self.client.post(
            reverse('personagem_registrar_aventuras', args=[self.character.pk]), {
                'nome_aventura': 'Mesa antiga BG', 'aventuras': 3,
                'mestre': self.staff.pk, 'data_missao': '2026-09-27',
                'quest_category': 'bg_token',
            })
        self.assertEqual(recorded.status_code, 302)
        quest_rule = TbConquista.objects.create(
            slug='quest-antiga-bg', nome='Quest antiga BG', criterio='automatico',
            criterio_json={'schema_version': 1, 'metric': 'quests_completed',
                           'scope': 'account', 'filters': {'category': 'bg_token', 'valid': True},
                           'operator': 'gte', 'target': 1})
        self.rule.ativo = True
        self.rule.save(update_fields=['ativo'])
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.owner).exists())
        administrator = get_user_model().objects.create_superuser(
            'adventure-reprocess-admin', 'reprocess@example.invalid', 'x')
        self.client.force_login(administrator)
        admin_url = reverse('admin:home_tbconquista_changelist')
        manual_rule = TbConquista.objects.create(
            slug='manual-reprocess-guard', nome='Regra manual', criterio='manual')
        payload = {'action': 'reprocessar_aventuras_quests', 'select_across': '0',
                   '_selected_action': [manual_rule.pk]}
        self.assertEqual(self.client.post(admin_url, payload).status_code, 302)
        self.assertFalse(TbUsuarioConquista.objects.filter(user=self.owner).exists())
        payload['_selected_action'] = [quest_rule.pk]
        self.assertEqual(self.client.post(admin_url, payload).status_code, 302)
        grants = TbUsuarioConquista.objects.filter(user=self.owner)
        self.assertEqual(set(grants.values_list('conquista_id', flat=True)),
                         {self.rule.pk, quest_rule.pk})
        self.assertEqual(grants.get(conquista=self.rule).evidencia_json['total'], 3)
        self.assertEqual(grants.get(conquista=quest_rule).evidencia_json['categoria'], 'bg_token')
        self.assertEqual(self.client.post(admin_url, payload).status_code, 302)
        self.assertEqual(grants.count(), 2)
        self.assertEqual(TbEventoConquista.objects.filter(
            conta=self.owner, tipo='adventure_recorded').count(), 1)

        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('profile')), self.rule.nome)
        self.assertContains(self.client.get(reverse('profile')), quest_rule.nome)
        self.assertContains(self.client.get(reverse('conquista_notificacoes')),
                            quest_rule.nome)

    def test_staff_ledger_counts_units_once_and_reversal_removes_support(self):
        self.definition = {**self.definition, 'operator': 'gt', 'target': 2}
        self.rule.criterio_json = self.definition
        self.rule.full_clean()
        self.rule.save(update_fields=['criterio_json'])
        community = TbPersonagemAventura.objects.create(
            id_personagem=self.character, nome_aventura='Recompensa social QA',
            origem='recompensa_comunidade', qtd_aventuras=10)
        with self.assertRaises(ValueError):
            registrar_fato_aventura(community)
        self.assertEqual(self.launch(2).status_code, 302)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).exists())
        self.assertEqual(self.launch(1).status_code, 302)
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=self.rule)
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['total'], 3)
        self.assertEqual(len(grant.evidencia_json['lancamento_ids']), 2)
        self.assertEqual(grant.definicao_json, self.definition)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge, suspenso_em__isnull=True).count(), 1)

        ledger = TbPersonagemAventura.objects.filter(origem='mesa').order_by('pk').last()
        recorded = TbEventoConquista.objects.filter(tipo='adventure_recorded').count()
        registrar_fato_aventura(ledger)
        self.assertEqual(TbEventoConquista.objects.filter(
            tipo='adventure_recorded').count(), recorded)
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule, revogada_em__isnull=True).count(), 1)

        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse(
            'personagem_reverter_aventura', args=[self.character.pk, ledger.pk]
        )).status_code, 302)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge,
            suspenso_em__isnull=False).exists())

    def test_fact_must_identify_exact_ledger_character(self):
        other = TbPersonagem.objects.create(
            dono=self.owner, nome='Outro personagem', nivel=1)
        self.assertEqual(self.launch(3).status_code, 302)
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=self.rule)
        self.assertIsNone(grant.revogada_em)
        fact = TbEventoConquista.objects.get(tipo='adventure_recorded')
        fact.personagem = other
        fact.save(update_fields=['personagem'])
        avaliar_aventuras_jogadas(self.owner)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge,
            suspenso_em__isnull=False).exists())
        fact.personagem = self.character
        fact.save(update_fields=['personagem'])
        avaliar_aventuras_jogadas(self.owner)
        grant.refresh_from_db()
        self.assertIsNone(grant.revogada_em)
        self.assertEqual(grant.evidencia_json['total'], 3)

    def test_adventure_and_quest_replay_require_exact_fact_version_and_payload(self):
        quest_rule = TbConquista(
            slug='quest-exact-ledger-qa', nome='Quest com prova exata',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'quests_completed',
                'scope': 'account', 'filters': {'category': 'bg_token', 'valid': True},
                'operator': 'gte', 'target': 1}, recompensa=self.badge)
        quest_rule.full_clean()
        quest_rule.save()
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('personagem_registrar_aventuras', args=[self.character.pk]), {
                'nome_aventura': 'Quest com prova exata', 'aventuras': 3,
                'mestre': self.staff.pk, 'data_missao': '2026-09-27',
                'quest_category': 'bg_token',
            })
        self.assertEqual(response.status_code, 302)
        fact = TbEventoConquista.objects.get(tipo='adventure_recorded')
        ledger = TbPersonagemAventura.objects.get(origem='mesa')
        original = dict(fact.payload_json)
        grants = TbUsuarioConquista.objects.filter(
            user=self.owner, conquista__in=[self.rule, quest_rule])
        self.assertEqual(grants.filter(revogada_em__isnull=True).count(), 2)

        for version, changes in ((2, {}), (1, {'ledger_id': float(ledger.pk)}),
                                 (1, {'quantidade': 3.0})):
            fact.versao_payload = version
            fact.payload_json = {**original, **changes}
            fact.save(update_fields=['versao_payload', 'payload_json'])
            with self.assertRaises(ValueError):
                registrar_fato_aventura(ledger, avaliar=False)
            avaliar_aventuras_jogadas(self.owner)
            avaliar_quests_categorizadas(self.owner)
            self.assertEqual(grants.filter(revogada_em__isnull=True).count(), 0)
            self.assertFalse(TbUsuarioCosmetico.objects.filter(
                user=self.owner, cosmetico=self.badge,
                suspenso_em__isnull=True).exists())

            fact.versao_payload = 1
            fact.payload_json = original.copy()
            fact.save(update_fields=['versao_payload', 'payload_json'])
            avaliar_aventuras_jogadas(self.owner)
            avaliar_quests_categorizadas(self.owner)
            self.assertEqual(grants.filter(revogada_em__isnull=True).count(), 2)
            self.assertEqual(grants.count(), 2)
            self.assertEqual(TbUsuarioCosmetico.objects.filter(
                user=self.owner, cosmetico=self.badge,
                suspenso_em__isnull=True).count(), 1)

    def test_admin_requires_explicit_comparator_and_threshold(self):
        admin = get_user_model().objects.create_superuser(
            'adventures-rule-admin', 'adventures-rule@example.invalid', 'x')
        self.client.force_login(admin)
        self.assertContains(self.client.get(reverse('admin:home_tbconquista_add')),
                            'Aventuras de mesa comprovadas')
        data = {'slug': 'adventures-assisted-qa', 'nome': 'Aventuras assistidas QA',
                'criterio': 'automatico', 'criterio_json': '{}', 'ativo': 'on',
                'ordem': '0',
                'metrica_assistida': 'adventures_played',
                'operador_unidades': 'gt', 'alvo_unidades': '3'}
        form = ConquistaAdminForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().criterio_json,
                         {**self.definition, 'operator': 'gt'})
        missing = ConquistaAdminForm(data={**data, 'slug': 'adventures-missing-qa',
                                          'alvo_unidades': ''})
        self.assertIn('alvo_unidades', missing.errors)
        invalid = TbConquista(slug='adventures-invalid-qa', nome='Inválida QA',
                              criterio='automatico', criterio_json={
                                  **self.definition, 'filters': {'valid': True}})
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_owner_sees_verified_progress_without_exposing_it_publicly(self):
        self.assertEqual(self.launch(2).status_code, 302)
        self.client.force_login(self.owner)
        editor = self.client.get(reverse('profile'))
        self.assertContains(editor, '2 comprovadas')
        self.assertContains(editor, 'meta: pelo menos 3')

        url = reverse('public_profile', args=[self.owner.username])
        self.assertContains(self.client.get(url), '2 comprovadas')
        self.client.logout()
        self.assertNotContains(self.client.get(url), '2 comprovadas')
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(url), '2 comprovadas')

    def test_legacy_explicit_ledger_can_be_previewed_and_replayed_once(self):
        ledger = TbPersonagemAventura.objects.create(
            id_personagem=self.character, nome_aventura='Mesa antiga QA',
            origem='mesa', qtd_aventuras=3)
        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', user_id=self.owner.pk,
                     stdout=output)
        self.assertIn('fatos_novos=1', output.getvalue())
        self.assertFalse(TbEventoConquista.objects.exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).exists())

        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=output)
        self.assertIn('fatos_novos=1', output.getvalue())
        self.assertEqual(TbEventoConquista.objects.filter(
            agregado_id=ledger.pk, tipo='adventure_recorded').count(), 1)
        self.assertEqual(TbUsuarioConquista.objects.get(
            user=self.owner, conquista=self.rule).evidencia_json['total'], 3)

        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=output)
        self.assertIn('fatos_novos=0', output.getvalue())
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).count(), 1)

    def test_replay_retains_previous_account_after_later_ledger_failure(self):
        second = self._novo_usuario('adventure-replay-recovery-2')
        other_character = TbPersonagem.objects.create(dono=second, nome='Outra mesa')
        first_ledger = TbPersonagemAventura.objects.create(
            id_personagem=self.character, nome_aventura='Primeira mesa',
            origem='mesa', qtd_aventuras=3)
        second_ledger = TbPersonagemAventura.objects.create(
            id_personagem=other_character, nome_aventura='Segunda mesa',
            origem='mesa', qtd_aventuras=3)

        def fail_second(ledger, **kwargs):
            if ledger.pk == second_ledger.pk:
                raise RuntimeError('segundo lancamento indisponivel')
            return registrar_fato_aventura(ledger, **kwargs)

        with patch('home.management.commands.reprocessar_aventuras_jogadas.registrar_fato_aventura',
                   side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, 'segundo lancamento indisponivel'):
                call_command('reprocessar_aventuras_jogadas', apply=True, stdout=StringIO())
        self.assertTrue(TbEventoConquista.objects.filter(agregado_id=first_ledger.pk).exists())
        self.assertFalse(TbEventoConquista.objects.filter(agregado_id=second_ledger.pk).exists())
        self.assertTrue(TbUsuarioConquista.objects.filter(user=self.owner,
                                                          conquista=self.rule).exists())
        self.assertFalse(TbUsuarioConquista.objects.filter(user=second,
                                                           conquista=self.rule).exists())

        call_command('reprocessar_aventuras_jogadas', apply=True, stdout=StringIO())
        self.assertEqual(TbEventoConquista.objects.filter(tipo='adventure_recorded').count(), 2)
        self.assertEqual(TbUsuarioConquista.objects.filter(conquista=self.rule).count(), 2)
        self.assertEqual(TbUsuarioCosmetico.objects.filter(cosmetico=self.badge).count(), 2)

    def test_replay_revokes_stale_grant_without_active_ledger(self):
        self.assertEqual(self.launch(3).status_code, 302)
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=self.rule)
        ledger = TbPersonagemAventura.objects.get(origem='mesa')
        ledger.revertido = True
        ledger.revertido_em = timezone.now()
        ledger.save(update_fields=['revertido', 'revertido_em'])

        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', user_id=self.owner.pk,
                     stdout=output)
        self.assertIn('lancamentos=0 fatos_novos=0 contas=1', output.getvalue())
        grant.refresh_from_db()
        self.assertIsNone(grant.revogada_em)

        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=output)
        self.assertIn('lancamentos=0 fatos_novos=0 contas=1', output.getvalue())
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge,
            suspenso_em__isnull=False).exists())

        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=self.rule).count(), 1)

    def test_staff_confirmed_quest_category_replays_and_reverses(self):
        administrator = get_user_model().objects.create_superuser(
            'quest-category-admin', 'quest-category@example.invalid', 'x')
        self.client.force_login(administrator)
        add_url = reverse('admin:home_tbconquista_add')
        self.assertContains(self.client.get(add_url), 'name="categoria_quest"')
        rule_data = {
            'slug': 'quest-bg-token-qa', 'nome': 'Quest BG/token QA',
            'criterio': 'automatico', 'criterio_json': '{}',
            'ordem': '0',
            'metrica_assistida': 'quests_completed',
            'categoria_quest': 'bg_token',
            'recompensa': self.badge.pk,
        }
        invalid = self.client.post(add_url, {**rule_data, 'categoria_quest': ''})
        self.assertContains(invalid, 'Selecione uma categoria confirmável.')
        self.assertFalse(TbConquista.objects.filter(slug='quest-bg-token-qa').exists())
        response = self.client.post(add_url, rule_data)
        self.assertEqual(response.status_code, 302, response.content[:500])
        quest_rule = TbConquista.objects.get(slug='quest-bg-token-qa')
        self.assertFalse(quest_rule.ativo)
        self.assertEqual(quest_rule.criterio_json['filters']['category'], 'bg_token')
        self.assertContains(self.client.get(reverse(
            'admin:home_tbconquista_change', args=[quest_rule.pk])),
            '<option value="bg_token" selected>BG/token</option>', html=True)
        url = reverse('personagem_registrar_aventuras', args=[self.character.pk])
        payload = {'nome_aventura': 'Quest BG confirmada', 'aventuras': 2,
                   'mestre': self.staff.pk, 'data_missao': '2026-09-27',
                   'quest_category': 'bg_token'}
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(url, {**payload, 'data_missao': ''}).status_code, 302)
        self.assertFalse(TbPersonagemAventura.objects.exists())
        self.assertEqual(self.client.post(url, payload).status_code, 302)
        ledger = TbPersonagemAventura.objects.get(origem='mesa')
        fact = TbEventoConquista.objects.get(tipo='adventure_recorded')
        self.assertEqual(ledger.detalhes_json['quest_confirmed_by'], self.staff.pk)
        self.assertEqual(fact.payload_json['quest_category'], 'bg_token')
        self.assertContains(self.client.get(reverse('editar_ficha', args=[self.character.pk])),
                            'Categoria confirmada: BG/token')
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=quest_rule).exists())

        quest_rule.ativo = True
        quest_rule.save(update_fields=['ativo'])
        output = StringIO()
        call_command('reprocessar_aventuras_jogadas', user_id=self.owner.pk,
                     stdout=output)
        self.assertIn('contas=1', output.getvalue())
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=quest_rule).exists())
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        grant = TbUsuarioConquista.objects.get(user=self.owner, conquista=quest_rule)
        self.assertEqual(grant.evidencia_json['lancamento_id'], ledger.pk)
        self.assertEqual(grant.definicao_json, quest_rule.criterio_json)
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        self.assertEqual(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=quest_rule).count(), 1)

        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('profile')), quest_rule.nome)
        self.assertContains(self.client.get(reverse('profile')), '1 quest comprovada')
        self.assertContains(self.client.get(reverse('conquista_notificacoes')),
                            quest_rule.nome)
        public_url = reverse('public_profile', args=[self.owner.username])
        self.client.logout()
        self.assertNotContains(self.client.get(public_url), '1 quest comprovada')

        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse(
            'personagem_reverter_aventura', args=[self.character.pk, ledger.pk]
        )).status_code, 302)
        grant.refresh_from_db()
        self.assertIsNotNone(grant.revogada_em)
        self.assertTrue(TbUsuarioCosmetico.objects.filter(
            user=self.owner, cosmetico=self.badge,
            suspenso_em__isnull=False).exists())
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('profile')), '0 quests comprovadas')

    def test_legacy_category_without_staff_confirmation_does_not_award(self):
        rule = TbConquista(
            slug='unverified-quest-bg', nome='Quest BG sem prova',
            criterio='automatico', criterio_json={
                'schema_version': 1, 'metric': 'quests_completed',
                'scope': 'account', 'filters': {'category': 'bg_token', 'valid': True},
                'operator': 'gte', 'target': 1})
        rule.full_clean()
        rule.save()
        TbPersonagemAventura.objects.create(
            id_personagem=self.character, nome_aventura='Legado ambíguo',
            origem='mesa', qtd_aventuras=1,
            detalhes_json={'quest_category': 'bg_token'})
        call_command('reprocessar_aventuras_jogadas', apply=True,
                     user_id=self.owner.pk, stdout=StringIO())
        self.assertEqual(TbEventoConquista.objects.filter(
            tipo='adventure_recorded').count(), 1)
        self.assertFalse(TbUsuarioConquista.objects.filter(
            user=self.owner, conquista=rule).exists())
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('profile')), '0 quests comprovadas')
