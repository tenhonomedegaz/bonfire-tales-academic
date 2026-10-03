"""Inline editorial actions remain visible in the Django audit history."""

import json
from unittest.mock import patch

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbMagia, TbMapLayer, TbTerritorio


class EditorialInlineAuditTests(TestCase):
    def setUp(self):
        self.editor = get_user_model().objects.create_user(
            'editor-auditoria-inline', password='test', is_staff=True,
        )
        self.client.force_login(self.editor)

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json')

    def entries_for(self, obj):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(obj), object_id=str(obj.pk),
        ).order_by('pk')

    def test_world_creation_and_edit_are_attributed_and_public(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superfície', 'ordem': 0, 'publica': True},
        )
        create_url = reverse('wiki_create_territory')
        created = self.post_json(create_url, {'nome': 'Vale da Auditoria'})
        self.assertEqual(created.status_code, 200)
        territory = TbTerritorio.objects.get(slug='vale-da-auditoria')
        entries = list(self.entries_for(territory))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].action_flag, ADDITION)
        self.assertEqual(entries[0].user_id, self.editor.pk)
        self.assertIn(territory.nome, entries[0].change_message)

        duplicate = self.post_json(create_url, {'nome': territory.nome})
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(self.entries_for(territory).count(), 1)

        changed = self.post_json(reverse('wiki_update_territory', args=[territory.pk]), {
            'nome': territory.nome, 'descricao_breve': 'Descrição pública revisada.',
            'lore_markdown': 'Lore pública revisada.',
        })
        self.assertEqual(changed.status_code, 200)
        territory.refresh_from_db()
        entries = list(self.entries_for(territory))
        self.assertEqual([entry.action_flag for entry in entries], [ADDITION, CHANGE])
        self.assertEqual(entries[1].user_id, self.editor.pk)
        self.assertIn(territory.nome, entries[1].change_message)

        self.client.logout()
        public = self.client.get(reverse('territorio_detail', args=[territory.slug]))
        self.assertEqual(public.status_code, 200)
        self.assertContains(public, 'Lore pública revisada.')

    def test_spell_edit_is_attributed_and_invalid_input_does_not_log(self):
        spell = TbMagia.objects.create(
            nome='Luz de Auditoria', slug='luz-de-auditoria', nivel=1,
        )
        url = reverse('wiki_update_spell', args=[spell.pk])
        invalid = self.post_json(url, {'nivel': 10, 'descricao': 'Não salvar'})
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(self.entries_for(spell).exists())

        changed = self.post_json(url, {
            'nome': spell.nome, 'slug': spell.slug, 'nivel': 1,
            'classes_slugs': [], 'tags_json': [],
            'descricao': 'Descrição revisada no catálogo.',
        })
        self.assertEqual(changed.status_code, 200)
        spell.refresh_from_db()
        entry = self.entries_for(spell).get()
        self.assertEqual(entry.action_flag, CHANGE)
        self.assertEqual(entry.user_id, self.editor.pk)
        self.assertIn(spell.nome, entry.change_message)

        self.client.logout()
        public = self.client.get(reverse('magias_listas'))
        self.assertEqual(public.status_code, 200)
        self.assertContains(public, 'Descrição revisada no catálogo.')

    def test_audit_outage_is_reported_without_damaging_saved_content(self):
        spell = TbMagia.objects.create(
            nome='Luz em Revisão', slug='luz-em-revisao', nivel=1,
        )
        with patch.object(LogEntry.objects, 'create', side_effect=RuntimeError('auditoria indisponível')):
            with self.assertLogs('home.views', level='ERROR') as captured:
                response = self.post_json(reverse('wiki_update_spell', args=[spell.pk]), {
                    'nome': spell.nome, 'slug': spell.slug, 'nivel': 1,
                    'classes_slugs': [], 'tags_json': [],
                    'descricao': 'Conteúdo preservado após falha de auditoria.',
                })
        self.assertEqual(response.status_code, 200)
        self.assertIn('Falha ao registrar edicao inline', captured.output[0])
        spell.refresh_from_db()
        self.assertEqual(spell.descricao, 'Conteúdo preservado após falha de auditoria.')
        self.assertFalse(self.entries_for(spell).exists())
