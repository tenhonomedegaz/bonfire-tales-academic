from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from home.gestao.requests import act_on_request, create_request
from home.gestao.training import apply_training, preview_training
from home.market_services import register_completed_training, start_training, TRAINING_COST_PC
from home.models import TbIdioma, TbItemMundano, TbPersonagem, TbPersonagemTreinamento
from home.portal_models import PortalActivity


class ManagementTrainingTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user('training-owner')
        self.reviewer = users.objects.create_user('training-reviewer', is_staff=False)
        self.other = users.objects.create_user('training-other')
        self.reviewer.user_permissions.add(*Permission.objects.filter(
            codename__in=['review_portal_ficha', 'register_management_training']))
        self.language = TbIdioma.objects.create(nome='Idioma comprovado', slug='idioma-comprovado')
        self.tool = TbItemMundano.objects.create(nome='Ferramenta comprovada', slug='ferramenta-comprovada',
                                                categoria='ferramenta')
        self.person = TbPersonagem.objects.create(dono=self.owner, nome='Ficha de treinamento',
            carteira_pc=30000, braseiros=7, aventuras=40, nivel=5)
        self.task = create_request(actor=self.owner, request_id=uuid4(), queue='ficha',
            title='Treino antigo comprovado', description='Conferir registro legado antes do cadastro.',
            character_id=self.person.pk)
        self.task = act_on_request(actor=self.reviewer, task_id=self.task.pk,
            request_id=uuid4(), version=1, action='start', note='Conferencia assumida pela equipe.')

    def preview(self, **changes):
        data = dict(actor=self.reviewer, task_id=self.task.pk, token='idioma:idioma-comprovado',
                    reason='Treinamento antigo validado.', evidence='Registro aprovado pela equipe em planilha.')
        data.update(changes)
        return preview_training(**data)

    def apply(self, preview=None, **changes):
        data = dict(actor=self.reviewer, task_id=self.task.pk, ticket=(preview or self.preview())['ticket'])
        data.update(changes)
        return apply_training(**data)

    def test_preview_apply_replay_and_finish_preserve_balances_and_paid_catalog(self):
        for token in ('idioma:idioma-comprovado', 'ferramenta:ferramenta-comprovada'):
            with self.subTest(token=token):
                preview = self.preview(token=token, finish=token.startswith('ferramenta'))
                count = self.person.proficiencias.count()
                receipt = self.apply(preview)
                self.assertEqual(self.apply(preview).pk, receipt.pk)
                self.assertEqual(self.person.proficiencias.count(), count + 1)
                self.assertEqual(receipt.after['charged_pc'], 0)
                self.assertTrue(receipt.after['created'])
        self.person.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual((self.person.carteira_pc, self.person.braseiros,
                          self.person.aventuras, self.person.nivel), (30000, 7, 40, 5))
        self.assertEqual(self.task.status, 'done')
        self.assertFalse(self.person.treinamentos_mercado.exists())
        self.assertFalse(self.person.transacoes.exists())
        self.assertEqual(self.task.activities.filter(action='training').count(), 2)
        self.assertFalse(self.reviewer.is_staff)

    def test_permissions_task_identity_assignment_and_tampering(self):
        with self.assertRaises(PermissionDenied):
            self.preview(actor=self.owner)
        preview = self.preview()
        with self.assertRaises(PermissionDenied):
            self.apply(preview, actor=self.other)
        with self.assertRaises(PermissionDenied):
            self.apply(preview, task_id=self.task.pk + 100)
        with self.assertRaises(ValidationError):
            self.apply(preview, ticket=preview['ticket'] + 'corrupt')
        self.task.assignee = self.other
        self.task.save(update_fields=['assignee'])
        with self.assertRaises(PermissionDenied):
            self.apply(preview)
        self.assertFalse(self.person.proficiencias.exists())

    def test_stale_character_catalog_or_task_invalidates_confirmation(self):
        preview = self.preview()
        self.language.nome = 'Nome alterado'
        self.language.save(update_fields=['nome'])
        with self.assertRaises(ValidationError):
            self.apply(preview)
        preview = self.preview()
        self.person.proficiencias.create(tipo='ferramenta', nome='Outra ferramenta', origem='Antecedente')
        with self.assertRaises(ValidationError):
            self.apply(preview)
        preview = self.preview()
        self.task.version += 1
        self.task.save(update_fields=['version'])
        with self.assertRaises(ValidationError):
            self.apply(preview)
        self.assertFalse(self.person.proficiencias.filter(tipo='idioma').exists())

    def test_paid_training_is_not_completed_cancelled_or_refunded_by_legacy_record(self):
        paid = TbPersonagemTreinamento.objects.create(id_personagem=self.person, tipo='idioma',
            nome=self.language.nome, conclui_em=timezone.now() + timedelta(days=10))
        with self.assertRaises(ValidationError):
            self.preview()
        with self.assertRaises(ValidationError):
            register_completed_training(self.person, 'idioma:idioma-comprovado')
        paid.refresh_from_db()
        self.person.refresh_from_db()
        self.assertEqual(paid.status, 'ativo')
        self.assertEqual(self.person.carteira_pc, 30000)
        self.assertFalse(self.person.proficiencias.exists())

    def test_existing_independent_proficiency_is_preserved_without_duplication(self):
        existing = self.person.proficiencias.create(tipo='idioma', nome=self.language.nome, origem='Antecedente')
        preview = self.preview()
        self.assertTrue(preview['already_known'])
        receipt = self.apply(preview)
        self.assertFalse(receipt.after['created'])
        existing.refresh_from_db()
        self.assertEqual(existing.origem, 'Antecedente')
        self.assertEqual(self.person.proficiencias.count(), 1)

    def test_audit_failure_rolls_back_character_and_request(self):
        preview = self.preview(finish=True)
        with patch.object(PortalActivity.objects, 'create', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.apply(preview)
        self.task.refresh_from_db()
        self.assertEqual((self.task.status, self.task.version), ('reviewing', 2))
        self.assertFalse(self.person.proficiencias.exists())

    def test_http_preview_csrf_confirm_and_replay_without_technical_staff_flag(self):
        url = reverse('gestao:request_training', args=[self.task.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.reviewer)
        detail = self.client.get(reverse('gestao:request_detail', args=[self.task.pk]))
        self.assertContains(detail, url)
        response = self.client.post(url, {'action': 'preview', 'token': 'idioma:idioma-comprovado',
            'reason': 'Treino anterior comprovado.', 'evidence': 'Documento validado pela equipe.', 'finish': 'on'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.person.proficiencias.exists())
        ticket = response.context['preview']['ticket']
        for _ in range(2):
            self.assertEqual(self.client.post(url, {'action': 'confirm', 'ticket': ticket}).status_code, 302)
        self.assertEqual(self.person.proficiencias.count(), 1)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.reviewer)
        self.assertEqual(csrf.post(url, {'action': 'confirm', 'ticket': ticket}).status_code, 403)

    def test_new_training_in_market_still_charges_and_waits(self):
        row, outcome = start_training(self.person, 'idioma:idioma-comprovado')
        self.assertEqual(outcome, 'treinamento_iniciado')
        self.assertEqual(row.status, 'ativo')
        self.person.refresh_from_db()
        self.assertEqual(self.person.carteira_pc, 30000 - TRAINING_COST_PC)
        self.assertFalse(self.person.proficiencias.exists())

    def test_operator_can_open_case_from_person_without_impersonating_its_owner(self):
        self.reviewer.user_permissions.add(Permission.objects.get(codename='view_management_people'))
        self.client.force_login(self.reviewer)
        page = self.client.get(reverse('gestao:person', args=[self.owner.pk]))
        url = reverse('gestao:training_case', args=[self.person.pk])
        self.assertContains(page, url)
        response = self.client.get(url)
        operation = response.context['form'].initial['request_id']
        from home.portal_models import PortalRequest
        count = PortalRequest.objects.count()
        data = {'request_id': operation, 'reason': 'Regularizar aprendizado de campanha anterior.'}
        first = self.client.post(url, data)
        second = self.client.post(url, data)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.url, second.url)
        self.assertEqual(PortalRequest.objects.count(), count + 1)
        task = PortalRequest.objects.get(request_id=operation)
        self.assertEqual(task.requester_id, self.owner.pk)
        self.assertEqual(task.assignee_id, self.reviewer.pk)
        self.assertEqual(task.activities.get(action='create').actor_id, self.reviewer.pk)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('gestao:request_detail', args=[task.pk])).status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_open_case_is_denied_when_archived_and_service_rejects_forged_beneficiary(self):
        self.reviewer.user_permissions.add(Permission.objects.get(codename='view_management_people'))
        self.client.force_login(self.reviewer)
        self.person.arquivado = True
        self.person.save(update_fields=['arquivado'])
        self.assertEqual(self.client.get(reverse('gestao:training_case', args=[self.person.pk])).status_code, 404)
        with self.assertRaises(PermissionDenied):
            create_request(actor=self.reviewer, request_id=uuid4(), queue='ficha',
                title='Pedido invalido', description='Nao vincular outra pessoa.',
                character_id=self.person.pk, requester_id=self.other.pk)

    def test_legacy_staff_endpoint_reuses_the_same_completed_training_service(self):
        legacy = get_user_model().objects.create_user('legacy-staff', is_staff=True)
        self.client.force_login(legacy)
        route = reverse('personagem_treinamento', args=[self.person.pk])
        response = self.client.post(route, {'treinamento': 'idioma:idioma-comprovado'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('treinamento=ok', response.url)
        response = self.client.post(route, {'treinamento': 'idioma:idioma-comprovado'})
        self.assertIn('treinamento=invalido', response.url)
        self.assertEqual(self.person.proficiencias.count(), 1)
        self.person.refresh_from_db()
        self.assertEqual(self.person.carteira_pc, 30000)
