"""Broken rule-catalog requests must preserve published content and audit truth."""

import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbOpcaojogo, TbTalento


class RuleEditorPayloadIntegrityTests(TestCase):
    def setUp(self):
        self.talent = TbTalento.objects.create(
            nome='Talento Resguardado', slug='talento-resguardado', tipo='geral',
            etiqueta='combate', descricao='Talento publicado.',
            pre_requisito='Força 13', etiquetas_adicionais='marcial',
            tags_json=['editorial:talento'], atrib_forca=True,
        )
        self.option = TbOpcaojogo.objects.create(
            nome='Opção Resguardada', slug='opcao-resguardada', tipo='Estilo',
            descricao='Opção publicada.', pre_requisito='Nível 2',
            etiquetas_adicionais='combate', tags_json=['editorial:opcao'],
        )
        self.urls = (
            (self.talent, reverse('wiki_update_talent', args=[self.talent.pk])),
            (self.option, reverse('wiki_update_option', args=[self.option.pk])),
        )
        editor = get_user_model().objects.create_user('editor-integridade-regras', is_staff=True)
        editor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='home',
            codename__in=('change_tbtalento', 'change_tbopcaojogo'),
        ))
        self.client.force_login(editor)

    @staticmethod
    def audit_count(obj):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(obj),
            object_id=str(obj.pk),
        ).count()

    def test_invalid_payload_does_not_clear_publication_or_create_audit(self):
        for obj, url in self.urls:
            original = (obj.descricao, obj.pre_requisito, obj.etiquetas_adicionais, obj.tags_json)
            for payload in ('{', '[]', '{}', '', '{"desconhecido": 1}'):
                with self.subTest(model=type(obj).__name__, payload=payload):
                    response = self.client.post(url, payload, content_type='application/json')
                    self.assertEqual(response.status_code, 400)
                    obj.refresh_from_db()
                    self.assertEqual(
                        (obj.descricao, obj.pre_requisito, obj.etiquetas_adicionais, obj.tags_json),
                        original,
                    )
                    self.assertEqual(self.audit_count(obj), 0)
            self.assertTrue(self.talent.atrib_forca)

    def test_partial_edits_preserve_omitted_rules_and_public_reading(self):
        for obj, url in self.urls:
            with self.subTest(model=type(obj).__name__):
                revised = f'{obj.nome}: revisado.'
                response = self.client.post(
                    url, json.dumps({'descricao': revised}), content_type='application/json',
                )
                self.assertEqual(response.status_code, 200)
                obj.refresh_from_db()
                self.assertEqual(obj.descricao, revised)
                self.assertTrue(obj.pre_requisito)
                self.assertTrue(obj.etiquetas_adicionais)
                self.assertTrue(obj.tags_json)
                self.assertEqual(self.audit_count(obj), 1)
        self.assertTrue(self.talent.atrib_forca)
        self.client.logout()
        talents_page = self.client.get(reverse('jogador_talentos'))
        options_page = self.client.get(reverse('jogador_opcoes'))
        self.assertEqual(talents_page.status_code, 200)
        self.assertEqual(options_page.status_code, 200)
        self.assertIn('Talento Resguardado: revisado.',
                      [item['descricao'] for item in talents_page.context['json_talentos']])
        self.assertIn('Opção Resguardada: revisado.',
                      [item['descricao'] for item in options_page.context['json_opcoes']])

    def test_explicit_clear_still_works(self):
        for obj, url in self.urls:
            with self.subTest(model=type(obj).__name__):
                payload = {'pre_requisito': '', 'etiquetas_adicionais': '', 'tags_json': []}
                if obj is self.talent:
                    payload['atrib_forca'] = False
                response = self.client.post(url, json.dumps(payload), content_type='application/json')
                self.assertEqual(response.status_code, 200)
                obj.refresh_from_db()
                self.assertIsNone(obj.pre_requisito)
                self.assertIsNone(obj.etiquetas_adicionais)
                self.assertEqual(obj.tags_json, [])
                self.assertTrue(obj.descricao)
                self.assertEqual(self.audit_count(obj), 1)
        self.assertFalse(self.talent.atrib_forca)
