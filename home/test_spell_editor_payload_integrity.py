"""A damaged inline request must not erase a published spell or class access."""

import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbClasse, TbMagia
from home.spell_access import spell_has_base_access


class SpellEditorPayloadIntegrityTests(TestCase):
    def setUp(self):
        self.classe = TbClasse.objects.create(nome='Mago Editorial', slug='mago-editorial')
        self.spell = TbMagia.objects.create(
            nome='Luz Permanente', slug='luz-permanente', nivel=1,
            descricao='Descrição publicada.', em_niveis_superiores='Efeito ampliado.',
            escola='Evocação', concentracao=True, ritual=True,
            classes='Mago Editorial', classes_slugs=['mago-editorial'],
            tags_json=['editorial:preservar'],
        )
        editor = get_user_model().objects.create_user('editor-payload-magia', is_staff=True)
        editor.user_permissions.add(Permission.objects.get(
            content_type__app_label='home', codename='change_tbmagia',
        ))
        self.client.force_login(editor)
        self.url = reverse('wiki_update_spell', args=[self.spell.pk])

    def audit_count(self):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(self.spell),
            object_id=str(self.spell.pk),
        ).count()

    def test_malformed_or_empty_payload_preserves_publication_and_audit(self):
        for payload in ('{', '[]', '{}', ''):
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.spell.refresh_from_db()
                self.assertEqual(self.spell.descricao, 'Descrição publicada.')
                self.assertEqual(self.spell.classes_slugs, ['mago-editorial'])
                self.assertEqual(self.spell.tags_json, ['editorial:preservar'])
                self.assertEqual(self.audit_count(), 0)

    def test_partial_edit_keeps_omitted_fields_and_public_class_access(self):
        response = self.client.post(
            self.url, json.dumps({'descricao': 'Descrição revisada.'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.spell.refresh_from_db()
        self.assertEqual(self.spell.descricao, 'Descrição revisada.')
        self.assertEqual(self.spell.em_niveis_superiores, 'Efeito ampliado.')
        self.assertEqual(self.spell.escola, 'Evocação')
        self.assertTrue(self.spell.concentracao)
        self.assertTrue(self.spell.ritual)
        self.assertEqual(self.spell.classes_slugs, ['mago-editorial'])
        self.assertEqual(self.spell.tags_json, ['editorial:preservar'])
        self.assertTrue(spell_has_base_access(self.spell, ['mago-editorial']))
        self.assertEqual(self.audit_count(), 1)
        self.client.logout()
        self.assertContains(self.client.get(reverse('magias_listas') + '?magia=' + self.spell.slug),
                            'Descrição revisada.')

    def test_bad_class_shape_is_rejected_but_explicit_empty_list_is_allowed(self):
        rejected = self.client.post(
            self.url, json.dumps({'classes_slugs': 'mago-editorial'}),
            content_type='application/json',
        )
        self.assertEqual(rejected.status_code, 400)
        self.spell.refresh_from_db()
        self.assertEqual(self.spell.classes_slugs, ['mago-editorial'])
        self.assertEqual(self.audit_count(), 0)

        cleared = self.client.post(
            self.url, json.dumps({'classes_slugs': [], 'tags_json': []}),
            content_type='application/json',
        )
        self.assertEqual(cleared.status_code, 200)
        self.spell.refresh_from_db()
        self.assertEqual(self.spell.classes_slugs, [])
        self.assertEqual(self.spell.tags_json, [])
        self.assertEqual(self.spell.descricao, 'Descrição publicada.')
        self.assertEqual(self.audit_count(), 1)
