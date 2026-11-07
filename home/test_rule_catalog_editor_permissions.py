"""Talent and option editors honor their separate model permissions."""

import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbOpcaojogo, TbTalento


class RuleCatalogEditorPermissionTests(TestCase):
    def test_talent_and_option_editors_are_isolated_and_public_readable(self):
        talent = TbTalento.objects.create(
            nome='Talento de QA', slug='talento-de-qa', descricao='Talento publicado.',
        )
        option = TbOpcaojogo.objects.create(
            nome='Opção de QA', slug='opcao-de-qa', tipo='Estilo',
            descricao='Opção publicada.',
        )
        cases = (
            (talent, 'change_tbtalento', 'wiki_update_talent', 'jogador_talentos',
             'Talento publicado.', 'Talento revisado.'),
            (option, 'change_tbopcaojogo', 'wiki_update_option', 'jogador_opcoes',
             'Opção publicada.', 'Opção revisada.'),
        )
        users = get_user_model()
        generic_staff = users.objects.create_user('rule-generic-staff', is_staff=True)
        talent_editor = users.objects.create_user('talent-editor', is_staff=True)
        option_editor = users.objects.create_user('option-editor', is_staff=True)
        for user, codename in (
            (talent_editor, 'change_tbtalento'),
            (option_editor, 'change_tbopcaojogo'),
        ):
            user.user_permissions.add(Permission.objects.get(
                content_type__app_label='home', codename=codename,
            ))

        for obj, permission, route, catalog_route, original, revised in cases:
            url = reverse(route, args=[obj.pk])
            catalog_url = reverse(catalog_route)
            payload = json.dumps({'nome': obj.nome, 'descricao': revised})
            editor = talent_editor if permission == 'change_tbtalento' else option_editor
            other_editor = option_editor if editor == talent_editor else talent_editor

            for user in (generic_staff, other_editor):
                self.client.force_login(user)
                catalog = self.client.get(catalog_url)
                self.assertEqual(catalog.status_code, 200)
                self.assertFalse(catalog.context['can_edit_wiki'])
                self.assertEqual(self.client.post(
                    url, payload, content_type='application/json',
                ).status_code, 403)
                obj.refresh_from_db()
                self.assertEqual(obj.descricao, original)

            self.client.force_login(editor)
            catalog = self.client.get(catalog_url)
            self.assertTrue(catalog.context['can_edit_wiki'])
            response = self.client.post(
                url, payload, content_type='application/json',
            )
            self.assertEqual(response.status_code, 200)
            obj.refresh_from_db()
            self.assertEqual(obj.descricao, revised)
            self.assertTrue(LogEntry.objects.filter(
                user=editor, content_type=ContentType.objects.get_for_model(obj),
                object_id=str(obj.pk),
            ).exists())
            self.client.logout()
            public_catalog = self.client.get(catalog_url)
            self.assertEqual(public_catalog.status_code, 200)
            items = public_catalog.context['json_talentos' if obj is talent else 'json_opcoes']
            self.assertIn(revised, [item['descricao'] for item in items])
            self.assertContains(public_catalog, json.dumps(revised)[1:-1])
