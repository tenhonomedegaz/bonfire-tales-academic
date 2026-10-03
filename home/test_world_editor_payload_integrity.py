"""Region and territory editors keep published content on malformed requests."""

import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbMapLayer, TbRegiao, TbTerritorio


class WorldEditorPayloadIntegrityTests(TestCase):
    def setUp(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superfície', 'ordem': 0, 'publica': True},
        )
        self.territory = TbTerritorio.objects.create(
            nome='Vale Íntegro', slug='vale-integro',
            imagem_url='https://example.com/vale.png',
            descricao_breve='Descrição publicada.', lore_markdown='Lore do território.',
            riqueza_natural=9, poder_militar=4,
        )
        self.region = TbRegiao.objects.create(
            nome='Porto Íntegro', slug='porto-integro', territorio=self.territory.nome,
            lore_markdown='Lore da região.', brasao_url='https://example.com/brasao.png',
            mapa_url='https://example.com/mapa.png', etiquetas_adicionais='porto',
            poder_militar=7,
        )
        self.targets = (
            (self.region, reverse('wiki_update_region', args=[self.region.pk])),
            (self.territory, reverse('wiki_update_territory', args=[self.territory.pk])),
        )
        editor = get_user_model().objects.create_user('editor-integridade-mundo', is_staff=True)
        editor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='home',
            codename__in=('change_tbregiao', 'change_tbterritorio'),
        ))
        self.client.force_login(editor)

    @staticmethod
    def audit_count(obj):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(obj),
            object_id=str(obj.pk),
        ).count()

    def test_invalid_json_or_number_does_not_change_publication_or_audit(self):
        for obj, url in self.targets:
            original = (obj.lore_markdown, obj.poder_militar)
            for payload in ('{', '[]', '{}', '', '{"unknown": 1}',
                            '{"lore_markdown": "Apagar", "poder_militar": "inválido"}',
                            '{"lore_markdown": "Apagar", "poder_militar": 1.5}'):
                with self.subTest(model=type(obj).__name__, payload=payload):
                    response = self.client.post(url, payload, content_type='application/json')
                    self.assertEqual(response.status_code, 400)
                    obj.refresh_from_db()
                    self.assertEqual((obj.lore_markdown, obj.poder_militar), original)
                    self.assertEqual(self.audit_count(obj), 0)
        self.assertEqual(self.region.brasao_url, 'https://example.com/brasao.png')
        self.assertEqual(self.territory.imagem_url, 'https://example.com/vale.png')

    def test_partial_edits_preserve_omitted_world_fields_and_public_reading(self):
        for obj, url, payload in (
            (self.region, self.targets[0][1], {'lore_markdown': 'Região revisada.'}),
            (self.territory, self.targets[1][1], {'descricao_breve': 'Território revisado.'}),
        ):
            with self.subTest(model=type(obj).__name__):
                self.assertEqual(self.client.post(
                    url, json.dumps(payload), content_type='application/json',
                ).status_code, 200)
                obj.refresh_from_db()
                self.assertEqual(self.audit_count(obj), 1)
        self.assertEqual(self.region.brasao_url, 'https://example.com/brasao.png')
        self.assertEqual(self.region.mapa_url, 'https://example.com/mapa.png')
        self.assertEqual(self.region.etiquetas_adicionais, 'porto')
        self.assertEqual(self.region.poder_militar, 7)
        self.assertEqual(self.territory.imagem_url, 'https://example.com/vale.png')
        self.assertEqual(self.territory.lore_markdown, 'Lore do território.')
        self.assertEqual(self.territory.riqueza_natural, 9)
        self.assertEqual(self.territory.poder_militar, 4)
        self.client.logout()
        self.assertContains(self.client.get(reverse('regiao_detail', args=[self.region.slug])),
                            'Região revisada.')
        territory_page = self.client.get(reverse('territorio_detail', args=[self.territory.slug]))
        self.assertEqual(territory_page.status_code, 200)
        self.assertEqual(
            territory_page.context['client_territories'][self.territory.nome]['descricao_breve'],
            'Território revisado.',
        )

    def test_explicit_zero_and_clear_are_saved_without_resetting_other_fields(self):
        self.assertEqual(self.client.post(
            self.targets[0][1], json.dumps({'poder_militar': 0, 'brasao_url': ''}),
            content_type='application/json',
        ).status_code, 200)
        self.assertEqual(self.client.post(
            self.targets[1][1], json.dumps({'riqueza_natural': 0, 'imagem_url': ''}),
            content_type='application/json',
        ).status_code, 200)
        self.region.refresh_from_db()
        self.territory.refresh_from_db()
        self.assertEqual(self.region.poder_militar, 0)
        self.assertIsNone(self.region.brasao_url)
        self.assertEqual(self.region.mapa_url, 'https://example.com/mapa.png')
        self.assertEqual(self.territory.riqueza_natural, 0)
        self.assertIsNone(self.territory.imagem_url)
        self.assertEqual(self.territory.poder_militar, 4)
