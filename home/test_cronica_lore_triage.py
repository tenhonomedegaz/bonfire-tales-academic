"""Staff triage and Loremaster decisions stay separate in Chronicle review."""

import json
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from home.models import TbCronica
from home.views import _cronica_author_snapshot, _cronica_pending_snapshot


class CronicaLoreTriageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.author = users.objects.create_user('lore-author')
        cls.staff = users.objects.create_user('lore-staff', is_staff=True)
        cls.loremaster = users.objects.create_user('lore-master', is_staff=True)
        cls.generic = users.objects.create_user('lore-generic', is_staff=True)
        cls.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='triage_tbcronica',
        ))
        cls.loremaster.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbcronica',
        ))
        cls.story = TbCronica.objects.create(
            titulo='Relato em análise', slug='relato-em-analise',
            conteudo_markdown='Texto original', autor=cls.author, status='pendente',
        )

    def decision(self, action, *, feedback='', snapshot=None, revision=None):
        payload = {'action': action, 'feedback': feedback}
        if snapshot is not None:
            payload['expected_snapshot'] = snapshot
        if revision is not None:
            payload['expected_revision'] = revision
        return self.client.post(
            reverse('cronica_review_action', args=[self.story.pk]),
            json.dumps(payload), content_type='application/json',
        )

    def test_staff_forwards_with_reason_and_only_loremaster_can_decide(self):
        snapshot = _cronica_pending_snapshot(self.story)
        self.client.force_login(self.staff)
        queue = self.client.get(reverse('cronicas_review'))
        self.assertContains(queue, 'Encaminhar ao Loremaster')
        self.assertNotContains(queue, 'Devolver ao autor')
        self.assertEqual(self.decision('encaminhar', snapshot=snapshot).status_code, 400)
        self.assertEqual(self.decision('encaminhar', feedback='Dúvida sobre a cronologia', snapshot=snapshot).status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'pendente')
        self.assertEqual(self.story.revisao_edicao['triagem_lore']['motivo'], 'Dúvida sobre a cronologia')
        self.assertContains(self.client.get(reverse('cronicas_review')), 'Dúvida sobre a cronologia')
        self.assertEqual(self.decision('encaminhar', feedback='Outro motivo', snapshot=snapshot).status_code, 409)
        self.assertEqual(self.decision('aprovar', snapshot=snapshot).status_code, 403)
        self.assertEqual(self.decision('reprovar', feedback='Vetada', snapshot=snapshot).status_code, 403)
        self.assertNotEqual(self.client.get(reverse('admin:index')).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('cronica_detail', args=[self.story.slug])).status_code, 404)

        self.client.force_login(self.loremaster)
        self.assertContains(self.client.get(reverse('cronicas_review')), 'Dúvida sobre a cronologia')
        self.assertEqual(self.decision('aprovar', snapshot=snapshot).status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'aprovada')
        self.assertEqual(self.story.revisao_edicao, {})
        self.assertEqual(self.story.revisado_por_id, self.loremaster.pk)
        self.assertEqual(LogEntry.objects.filter(object_id=str(self.story.pk)).count(), 2)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[self.story.slug])), 'Texto original')

    def test_staff_can_approve_routine_lore_but_generic_staff_cannot(self):
        snapshot = _cronica_pending_snapshot(self.story)
        self.client.force_login(self.generic)
        self.assertEqual(self.client.get(reverse('cronicas_review')).status_code, 403)
        self.assertEqual(self.decision('aprovar', snapshot=snapshot).status_code, 403)
        self.client.force_login(self.staff)
        listing = self.client.get(reverse('mundo_cronicas'))
        self.assertContains(listing, reverse('cronicas_review'))
        self.assertEqual(self.decision('reprovar', feedback='Não posso vetar', snapshot=snapshot).status_code, 403)
        self.assertEqual(self.decision('aprovar', snapshot=snapshot).status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.status, 'aprovada')
        self.assertEqual(self.story.revisado_por_id, self.staff.pk)

    def test_forwarding_audit_failure_rolls_back_the_referral(self):
        self.client.force_login(self.staff)
        with patch('django.contrib.admin.models.LogEntry.objects.create',
                   side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.decision('encaminhar', feedback='Conferir a origem',
                              snapshot=_cronica_pending_snapshot(self.story))
        self.story.refresh_from_db()
        self.assertEqual(self.story.revisao_edicao, {})
        self.assertEqual(self.story.status, 'pendente')

    def test_author_change_after_forwarding_still_requires_loremaster(self):
        snapshot = _cronica_pending_snapshot(self.story)
        self.client.force_login(self.staff)
        self.assertEqual(self.decision('encaminhar', feedback='Verificar data da batalha', snapshot=snapshot).status_code, 200)
        self.story.refresh_from_db()
        self.client.force_login(self.author)
        edit = self.client.post(reverse('cronica_edit', args=[self.story.slug]), json.dumps({
            'conteudo_markdown': 'Texto corrigido',
            'expected_edit': _cronica_author_snapshot(self.story),
        }), content_type='application/json')
        self.assertEqual(edit.status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.revisao_edicao['triagem_lore']['motivo'], 'Verificar data da batalha')
        self.client.force_login(self.staff)
        self.assertEqual(self.decision('aprovar', snapshot=snapshot).status_code, 409)
        fresh_snapshot = _cronica_pending_snapshot(self.story)
        self.assertEqual(self.decision('aprovar', snapshot=fresh_snapshot).status_code, 403)
        self.client.force_login(self.loremaster)
        self.assertEqual(self.decision('aprovar', snapshot=fresh_snapshot).status_code, 200)
        self.client.logout()
        self.assertContains(self.client.get(reverse('cronica_detail', args=[self.story.slug])), 'Texto corrigido')

    def test_forwarded_revision_keeps_public_text_until_loremaster_decides(self):
        self.story.status = 'aprovada'
        self.story.save(update_fields=['status'])
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(reverse('cronica_edit', args=[self.story.slug]), json.dumps({
            'conteudo_markdown': 'Nova versão privada',
            'expected_edit': _cronica_author_snapshot(self.story),
        }), content_type='application/json').status_code, 200)
        self.story.refresh_from_db()
        revision = self.story.revisao_edicao['submetida_em']
        self.client.force_login(self.staff)
        self.assertEqual(self.decision('encaminhar', feedback='Dúvida sobre a região', revision=revision).status_code, 200)
        self.assertEqual(self.decision('aprovar', revision=revision).status_code, 403)
        self.story.refresh_from_db()
        self.client.force_login(self.author)
        self.assertEqual(self.client.post(reverse('cronica_edit', args=[self.story.slug]), json.dumps({
            'conteudo_markdown': 'Versão corrigida ainda privada',
            'expected_edit': _cronica_author_snapshot(self.story),
        }), content_type='application/json').status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.revisao_edicao['triagem_lore']['motivo'], 'Dúvida sobre a região')
        revision = self.story.revisao_edicao['submetida_em']
        self.client.force_login(self.staff)
        self.assertEqual(self.decision('aprovar', revision=revision).status_code, 403)
        self.client.logout()
        page = self.client.get(reverse('cronica_detail', args=[self.story.slug]))
        self.assertContains(page, 'Texto original')
        self.assertNotContains(page, 'Versão corrigida ainda privada')
        self.assertNotContains(page, 'Dúvida sobre a região')

        self.client.force_login(self.loremaster)
        self.assertEqual(self.decision('reprovar', feedback='Ajuste a localização', revision=revision).status_code, 200)
        self.story.refresh_from_db()
        self.assertEqual(self.story.conteudo_markdown, 'Texto original')
        self.assertEqual(self.story.revisao_edicao['estado'], 'reprovada')
        self.assertNotIn('triagem_lore', self.story.revisao_edicao)
