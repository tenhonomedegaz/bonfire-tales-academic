"""Moving a map marker requires valid coordinates and a real change."""

import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from home.models import TbMapLayer, TbMapMarker
from home.views import MAP_EDITOR_PERMISSIONS


class MapMarkerPositionIntegrityTests(TestCase):
    def setUp(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superfície', 'ordem': 0, 'publica': True},
        )
        self.marker = TbMapMarker.objects.create(nome='Farol Íntegro', lat=12, lng=34)
        self.url = reverse('wiki_update_marker_position', args=[self.marker.pk])
        editor = get_user_model().objects.create_user('editor-posicao-mapa', is_staff=True)
        editor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='home',
            codename__in=[name.split('.')[1] for name in MAP_EDITOR_PERMISSIONS],
        ))
        self.client.force_login(editor)

    def audit_count(self):
        return LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(self.marker),
            object_id=str(self.marker.pk),
        ).count()

    def test_bad_requests_do_not_move_or_audit_marker(self):
        for payload in ('{', '[]', '{}', '{"unknown": 1}',
                        '{"lat": "NaN"}', '{"lng": "Infinity"}',
                        '{"lat": true}', '{"lat": "errado", "lng": 40}'):
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.marker.refresh_from_db()
                self.assertEqual((self.marker.lat, self.marker.lng), (12, 34))
                self.assertEqual(self.audit_count(), 0)

    def test_partial_move_is_visible_on_public_map_and_audited(self):
        response = self.client.post(
            self.url, json.dumps({'lat': 15}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['changed'])
        self.marker.refresh_from_db()
        self.assertEqual((self.marker.lat, self.marker.lng), (15, 34))
        self.assertEqual(self.audit_count(), 1)
        self.client.logout()
        public_map = self.client.get(reverse('mapa'))
        self.assertEqual(public_map.status_code, 200)
        marker = next(row for row in public_map.context['json_markers']
                      if row['id'] == self.marker.pk)
        self.assertEqual((marker['lat'], marker['lng']), (15, 34))

    def test_repeated_position_does_not_duplicate_audit(self):
        for coordinates, changed, entries in (
            ({'lat': 15, 'lng': 34}, True, 1),
            ({'lat': 15, 'lng': 34}, False, 1),
        ):
            with self.subTest(coordinates=coordinates, changed=changed):
                response = self.client.post(
                    self.url, json.dumps(coordinates), content_type='application/json',
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['changed'], changed)
                self.assertEqual(self.audit_count(), entries)
