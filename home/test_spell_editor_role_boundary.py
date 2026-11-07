"""The public spell editor requires an explicit editorial permission."""

import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbMagia


class SpellEditorRoleBoundaryTests(TestCase):
    def test_staff_without_spell_permission_cannot_edit_or_see_editor(self):
        users = get_user_model()
        spell = TbMagia.objects.create(
            nome='Luz Reservada', slug='luz-reservada', nivel=1,
            descricao='Texto publicado.',
        )
        url = reverse('wiki_update_spell', args=[spell.pk])
        catalog_url = reverse('magias_listas')
        payload = json.dumps({
            'nome': spell.nome, 'slug': spell.slug, 'nivel': 1,
            'descricao': 'Texto alterado sem permissão.',
            'classes_slugs': [], 'tags_json': [],
        })
        generic_staff = users.objects.create_user('spell-generic-staff', is_staff=True)
        journal_editor = users.objects.create_user('spell-journal-editor', is_staff=True)
        journal_editor.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='add_tbjornal',
        ))
        for user in (generic_staff, journal_editor):
            self.client.force_login(user)
            catalog = self.client.get(catalog_url)
            self.assertContains(catalog, 'Texto publicado.')
            self.assertFalse(catalog.context['can_edit'])
            self.assertContains(catalog, 'var CAN_EDIT = false;')
            self.assertEqual(catalog.context['magias'][0]['update_url'], '')
            self.assertEqual(self.client.post(
                url, payload, content_type='application/json',
            ).status_code, 403)
            spell.refresh_from_db()
            self.assertEqual(spell.descricao, 'Texto publicado.')

        self.assertFalse(LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(spell),
            object_id=str(spell.pk),
        ).exists())

    def test_authorized_spell_editor_updates_public_text_with_audit(self):
        spell = TbMagia.objects.create(
            nome='Luz Autorizada', slug='luz-autorizada', nivel=1,
            descricao='Versão inicial.',
        )
        editor = get_user_model().objects.create_user('spell-authorized-editor', is_staff=True)
        editor.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbmagia',
        ))
        self.client.force_login(editor)
        catalog = self.client.get(reverse('magias_listas'))
        self.assertTrue(catalog.context['can_edit'])
        self.assertContains(catalog, 'var CAN_EDIT = true;')
        self.assertEqual(catalog.context['magias'][0]['update_url'],
                         reverse('wiki_update_spell', args=[spell.pk]))
        response = self.client.post(
            reverse('wiki_update_spell', args=[spell.pk]),
            json.dumps({
                'nome': spell.nome, 'slug': spell.slug, 'nivel': 1,
                'descricao': 'Versão revisada.',
                'classes_slugs': [], 'tags_json': [],
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        spell.refresh_from_db()
        self.assertEqual(spell.descricao, 'Versão revisada.')
        self.assertTrue(LogEntry.objects.filter(
            user=editor, content_type=ContentType.objects.get_for_model(spell),
            object_id=str(spell.pk),
        ).exists())
        self.client.logout()
        self.assertContains(self.client.get(reverse('magias_listas') + '?magia=' + spell.slug),
                            'Versão revisada.')
