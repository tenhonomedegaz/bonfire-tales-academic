"""A map batch either publishes all edits with audit history or none of them."""

import json
from unittest.mock import patch

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbMapLayer, TbMapMarker, TbRegiao, TbTerritorio


class MapBatchAtomicTests(TestCase):
    def setUp(self):
        self.editor = get_user_model().objects.create_user(
            'map-batch-editor', password='test', is_staff=True,
        )
        self.editor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='home', codename__in=(
                'add_tbmapmarker', 'change_tbmapmarker',
                'add_tbregiao', 'change_tbregiao',
                'add_tbterritorio', 'change_tbterritorio',
                'add_tbmapdesenho', 'change_tbmapdesenho', 'delete_tbmapdesenho',
            ),
        ))
        self.client.force_login(self.editor)
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superfície', 'ordem': 0, 'publica': True},
        )
        self.url = reverse('wiki_batch_save_map')

    def save_batch(self, markers):
        return self.client.post(
            self.url, json.dumps({'markers': markers}), content_type='application/json',
        )

    def entries_for(self, obj):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(obj), object_id=str(obj.pk),
        ).order_by('pk')

    def test_later_rejection_rolls_back_new_markers_regions_and_history(self):
        rejected = self.save_batch([
            {'nome': 'QA Lote Inicial 460', 'lat': 3, 'lng': 4},
            {'nome': 'QA Lote Inválido 460', 'lat': 5, 'lng': 6, 'territorio': 'Inexistente'},
        ])
        self.assertEqual(rejected.status_code, 400)
        self.assertFalse(TbMapMarker.objects.filter(nome='QA Lote Inicial 460').exists())
        self.assertFalse(TbRegiao.objects.filter(nome='QA Lote Inicial 460').exists())
        self.assertFalse(LogEntry.objects.filter(user=self.editor).exists())

    def test_later_duplicate_rolls_back_earlier_edit_and_history(self):
        marker = TbMapMarker.objects.create(nome='QA Lote Antigo 460', lat=1, lng=2)
        TbMapMarker.objects.create(nome='QA Lote Ocupado 460', lat=8, lng=9)
        rejected = self.save_batch([
            {'id': marker.pk, 'nome': 'QA Lote Renomeado 460', 'lat': 3, 'lng': 4},
            {'nome': 'QA Lote Ocupado 460', 'lat': 5, 'lng': 6},
        ])
        self.assertEqual(rejected.status_code, 400)
        marker.refresh_from_db()
        self.assertEqual((marker.nome, marker.lat, marker.lng), ('QA Lote Antigo 460', 1, 2))
        self.assertTrue(TbRegiao.objects.filter(slug='qa-lote-antigo-460', nome='QA Lote Antigo 460').exists())
        self.assertFalse(LogEntry.objects.filter(user=self.editor).exists())

    def test_valid_batch_creates_then_edits_with_public_region_and_correct_history(self):
        created = self.save_batch([{'nome': 'QA Lote Público 460', 'lat': 3, 'lng': 4}])
        self.assertEqual(created.status_code, 200)
        marker = TbMapMarker.objects.get(nome='QA Lote Público 460')
        region = TbRegiao.objects.get(nome='QA Lote Público 460')
        self.assertEqual(list(self.entries_for(marker).values_list('action_flag', flat=True)), [ADDITION])
        self.assertEqual(list(self.entries_for(region).values_list('action_flag', flat=True)), [ADDITION])

        changed = self.save_batch([{'id': marker.pk, 'nome': 'QA Lote Público 460', 'lat': 7, 'lng': 8}])
        self.assertEqual(changed.status_code, 200)
        marker.refresh_from_db()
        self.assertEqual((marker.lat, marker.lng), (7, 8))
        self.assertEqual(list(self.entries_for(marker).values_list('action_flag', flat=True)),
                         [ADDITION, CHANGE])
        self.assertEqual(list(self.entries_for(region).values_list('action_flag', flat=True)),
                         [ADDITION])

        self.client.logout()
        public = self.client.get(reverse('regiao_detail', args=[region.slug]))
        self.assertEqual(public.status_code, 200)
        self.assertContains(public, region.nome)

    def test_repeated_batch_does_not_invent_marker_or_region_edits(self):
        payload = {'nome': 'QA Farol Sem Duplicata', 'lat': 3, 'lng': 4}
        self.assertEqual(self.save_batch([payload]).status_code, 200)
        marker = TbMapMarker.objects.get(nome=payload['nome'])
        region = TbRegiao.objects.get(nome=payload['nome'])
        repeated = dict(payload, id=marker.pk)
        self.assertEqual(self.save_batch([repeated]).status_code, 200)
        self.assertEqual(list(self.entries_for(marker).values_list('action_flag', flat=True)),
                         [ADDITION])
        self.assertEqual(list(self.entries_for(region).values_list('action_flag', flat=True)),
                         [ADDITION])
        changed = dict(repeated, categoria='capital')
        self.assertEqual(self.save_batch([changed]).status_code, 200)
        self.assertEqual(list(self.entries_for(marker).values_list('action_flag', flat=True)),
                         [ADDITION, CHANGE])
        self.assertEqual(list(self.entries_for(region).values_list('action_flag', flat=True)),
                         [ADDITION, CHANGE])

    def test_territory_geometry_repeated_batch_does_not_duplicate_audit(self):
        territory = TbTerritorio.objects.create(nome='QA Vale Sem Duplicata', slug='qa-vale-sem-duplicata')
        payload = {'territories': [{'id': territory.pk, 'coordenadas_poligono': {'type': 'Polygon', 'coordinates': []},
                                    'camada': 0}]}
        for expected in (1, 1):
            response = self.client.post(self.url, json.dumps(payload), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.entries_for(territory).count(), expected)
        territory.refresh_from_db()
        self.assertEqual(territory.coordenadas_poligono, payload['territories'][0]['coordenadas_poligono'])

    def test_malformed_marker_rejects_entire_batch_with_useful_error(self):
        for invalid, expected in (
            ({'nome': 'QA Inválido 461', 'lat': 'não-numérico', 'lng': 4}, 'Coordenadas'),
            ({'nome': 'QA Inválido 461', 'lat': float('nan'), 'lng': 4}, 'Coordenadas'),
            ({'id': 'abc', 'nome': 'QA Inválido 461', 'lat': 3, 'lng': 4}, 'ID de marcador'),
            ({'nome': '  ', 'lat': 3, 'lng': 4}, 'Nome de marcador'),
        ):
            with self.subTest(invalid=invalid):
                rejected = self.save_batch([
                    {'nome': 'QA Primeiro 461', 'lat': 1, 'lng': 2}, invalid,
                ])
                self.assertEqual(rejected.status_code, 400)
                self.assertIn(expected, rejected.json()['error'])
                self.assertFalse(TbMapMarker.objects.filter(nome='QA Primeiro 461').exists())
                self.assertFalse(TbRegiao.objects.filter(nome='QA Primeiro 461').exists())
                self.assertFalse(LogEntry.objects.filter(user=self.editor).exists())

    def test_invalid_territory_rejects_marker_change_and_valid_update_is_visible(self):
        territory = TbTerritorio.objects.create(nome='QA Território 461', slug='qa-territorio-461')
        for invalid_id, status in (('abc', 400), (999999999, 404)):
            with self.subTest(invalid_id=invalid_id):
                rejected = self.client.post(self.url, json.dumps({
                    'markers': [{'nome': 'QA Porto 461', 'lat': 1, 'lng': 2}],
                    'territories': [{'id': invalid_id, 'camada': 1}],
                }), content_type='application/json')
                self.assertEqual(rejected.status_code, status)
                self.assertFalse(TbMapMarker.objects.filter(nome='QA Porto 461').exists())
                self.assertFalse(LogEntry.objects.filter(user=self.editor).exists())

        saved = self.client.post(self.url, json.dumps({
            'markers': [], 'territories': [{'id': territory.pk, 'camada': 1}],
        }), content_type='application/json')
        self.assertEqual(saved.status_code, 200)
        territory.refresh_from_db()
        self.assertEqual(territory.camada, 1)
        self.assertEqual(list(self.entries_for(territory).values_list('action_flag', flat=True)), [CHANGE])

    def test_unexpected_failure_does_not_expose_exception_to_editor(self):
        with patch.object(TbMapMarker.objects, 'create', side_effect=RuntimeError('segredo interno')):
            with self.assertLogs('home.views', level='ERROR'):
                response = self.save_batch([{'nome': 'QA Falha 461', 'lat': 1, 'lng': 2}])
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['error'], 'Falha ao salvar lote do mapa.')
        self.assertFalse(LogEntry.objects.filter(user=self.editor).exists())

    def test_malformed_batch_document_is_rejected(self):
        for body in ('{', '{}', '{"markers": {}}', '{"markers": [null]}'):
            with self.subTest(body=body):
                response = self.client.post(self.url, body, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertFalse(LogEntry.objects.filter(user=self.editor).exists())
