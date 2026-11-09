from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from home.gestao.character_profile import apply_profile, edit_token, preview_profile
from home.gestao.requests import open_character_case
from home.models import TbClasse, TbPersonagem, TbPersonagemClasse
from home.portal_models import PortalActivity, PortalRequest


class CharacterProfileCorrectionTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user('profile-owner')
        self.operator = users.objects.create_user('profile-operator', is_staff=False)
        self.other = users.objects.create_user('profile-other')
        self.operator.user_permissions.add(*Permission.objects.filter(codename__in=[
            'view_management_people', 'review_portal_ficha', 'correct_management_character_profile']))
        self.person = TbPersonagem.objects.create(dono=self.owner, nome='Nome anterior', nivel=5,
            forca=16, aventuras=30, carteira_pc=34567, braseiros=11, publico=False,
            ficha_theme='arcane', foto_frame='rank-ametista', historia='Historia preservada.',
            notas_jogador='Nota de mesa anterior.')
        self.person_class = TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=TbClasse.objects.create(nome='Classe de teste', slug='classe-profile'), nivel=5, principal=True)
        self.task = open_character_case(actor=self.operator, character_id=self.person.pk,
            purpose='profile', request_id=uuid4(), reason='Corrigir informacao enviada pelo dono.')

    def preview(self, **changes):
        self.task.refresh_from_db()
        self.task.character.refresh_from_db()
        data = dict(actor=self.operator, task_id=self.task.pk, base_token=edit_token(self.operator, self.task),
            changes={'nome': 'Nome corrigido'}, reason='Correcao solicitada pelo dono.',
            evidence='Mensagem do dono no atendimento.')
        data.update(changes)
        return preview_profile(**data)

    def apply(self, preview=None, **changes):
        data = dict(actor=self.operator, task_id=self.task.pk, ticket=(preview or self.preview())['ticket'])
        data.update(changes)
        return apply_profile(**data)

    def test_preview_confirm_replay_preserves_mechanics_cosmetics_and_privacy(self):
        preview = self.preview(changes={'nome': 'Nome corrigido', 'anotacoes': 'Lore revisada.'}, finish=True)
        self.person.refresh_from_db()
        self.assertEqual(self.person.nome, 'Nome anterior')
        self.assertEqual([row['label'] for row in preview['rows']], ['Nome do personagem', 'Anotações de lore'])
        receipt = self.apply(preview)
        self.assertEqual(self.apply(preview).pk, receipt.pk)
        self.person.refresh_from_db()
        self.person_class.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual((self.person.nome, self.person.anotacoes), ('Nome corrigido', 'Lore revisada.'))
        self.assertEqual((self.person.nivel, self.person.forca, self.person.aventuras,
                          self.person.carteira_pc, self.person.braseiros), (5, 16, 30, 34567, 11))
        self.assertEqual((self.person.ficha_theme, self.person.foto_frame, self.person.publico),
                         ('arcane', 'rank-ametista', False))
        self.assertEqual(self.person.historia, 'Historia preservada.')
        self.assertEqual(self.person_class.nivel, 5)
        self.assertEqual(self.task.status, 'done')
        self.assertEqual(receipt.before['fields']['nome'], 'Nome anterior')
        self.assertEqual(self.task.activities.filter(action='profile').count(), 1)

    def test_forbidden_fields_missing_reason_and_empty_change_are_rejected(self):
        for key in ('nivel', 'dono_id', 'carteira_pc', 'id_raca_id', 'ficha_theme', 'publico', 'historia', 'tamanho'):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                self.preview(changes={key: 'Qualquer texto'})
        with self.assertRaises(ValidationError):
            self.preview(changes={'nome': ''})
        with self.assertRaises(ValidationError):
            self.preview(changes={'nome': self.person.nome})
        with self.assertRaises(ValidationError):
            self.preview(reason='')
        with self.assertRaises(ValidationError):
            self.preview(changes={'idade': 'x' * 31})
        self.assertFalse(self.task.activities.filter(action='profile').exists())

    def test_changed_data_since_form_open_and_since_preview_are_rejected(self):
        token = edit_token(self.operator, self.task)
        self.person.anotacoes = 'Editada pelo dono enquanto o formulario estava aberto.'
        self.person.save(update_fields=['anotacoes'])
        with self.assertRaises(ValidationError):
            self.preview(base_token=token)
        preview = self.preview()
        self.person.nome = 'Nome novo do dono'
        self.person.save(update_fields=['nome'])
        with self.assertRaises(ValidationError):
            self.apply(preview)
        self.person.refresh_from_db()
        self.assertEqual(self.person.nome, 'Nome novo do dono')

    def test_identity_assignment_revocation_and_tampering(self):
        preview = self.preview()
        with self.assertRaises(PermissionDenied):
            self.apply(preview, actor=self.other)
        with self.assertRaises(PermissionDenied):
            self.apply(preview, task_id=self.task.pk + 10)
        with self.assertRaises(ValidationError):
            self.apply(preview, ticket=preview['ticket'] + 'invalid')
        self.task.assignee = self.other
        self.task.save(update_fields=['assignee'])
        with self.assertRaises(PermissionDenied):
            self.apply(preview)
        self.task.assignee = self.operator
        self.task.save(update_fields=['assignee'])
        self.operator.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            self.apply(preview)

    def test_unrelated_cosmetic_changes_are_preserved_and_audit_failure_rolls_back(self):
        preview = self.preview()
        self.person.ficha_theme = 'bonfire'
        self.person.save(update_fields=['ficha_theme'])
        with patch.object(PortalActivity.objects, 'create', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.apply(preview)
        self.person.refresh_from_db()
        self.task.refresh_from_db()
        self.assertEqual(self.person.nome, 'Nome anterior')
        self.assertEqual(self.person.ficha_theme, 'bonfire')
        self.assertEqual(self.task.version, 2)

    def test_http_creation_preview_confirm_and_private_audit_visibility(self):
        self.client.force_login(self.operator)
        case_url = reverse('gestao:profile_case', args=[self.person.pk])
        self.assertContains(self.client.get(reverse('gestao:person', args=[self.owner.pk])), case_url)
        case = self.client.get(case_url)
        response = self.client.post(case_url, {'request_id': case.context['form'].initial['request_id'],
            'reason': 'Corrigir nota solicitada pelo dono.'})
        self.assertEqual(response.status_code, 302)
        url = response.url
        page = self.client.get(url)
        form = page.context['form']
        data = {key: form.initial.get(key, '') for key in form.fields}
        data.update(action='preview', notas_jogador='Nota corrigida confidencial.',
            reason='Correcao solicitada pelo dono.', evidence='Referencia validada pela equipe.', finish='on')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        ticket = response.context['preview']['ticket']
        for _ in range(2):
            response = self.client.post(url, {'action': 'confirm', 'ticket': ticket})
            self.assertEqual(response.status_code, 302)
        detail_url = response.url
        self.assertContains(self.client.get(detail_url), 'Nota corrigida confidencial.')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(detail_url), 'Nota de mesa anterior.')
        self.other.user_permissions.add(Permission.objects.get(codename='review_portal_ficha'))
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(detail_url), 'Nota corrigida confidencial.')
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.operator)
        self.assertEqual(csrf.post(url, {'action': 'confirm', 'ticket': ticket}).status_code, 403)

    def test_long_text_confirmation_and_escaping(self):
        self.client.force_login(self.operator)
        url = reverse('gestao:request_profile', args=[self.task.pk])
        page = self.client.get(url)
        data = {key: page.context['form'].initial.get(key, '') for key in page.context['form'].fields}
        data.update(action='preview', aparencia='<script>alert(1)</script>' + 'Texto ' * 700,
            reason='Ajuste de descricao aprovado.', evidence='Documento enviado pelo dono.')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        ticket = response.context['preview']['ticket']
        self.assertEqual(self.client.post(url, {'action': 'confirm', 'ticket': ticket}).status_code, 302)
        self.person.refresh_from_db()
        self.assertTrue(self.person.aparencia.startswith('<script>'))
