import json
import tempfile

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import TbMapDesenho, TbMapLayer, TbMapMarker, TbRegiao, TbTerritorio


MAP_ROLE = (
    'add_tbmapmarker', 'change_tbmapmarker',
    'add_tbregiao', 'change_tbregiao',
    'add_tbterritorio', 'change_tbterritorio',
    'add_tbmapdesenho', 'change_tbmapdesenho', 'delete_tbmapdesenho',
)


class WorldEditorPermissionTests(TestCase):
    def setUp(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superficie', 'ordem': 0, 'publica': True},
        )
        self.territory = TbTerritorio.objects.create(nome='Vale Editorial', slug='vale-editorial')
        self.region = TbRegiao.objects.create(
            nome='Porto Editorial', slug='porto-editorial', territorio=self.territory.nome,
        )

    def login(self, name, permissions=()):
        user = get_user_model().objects.create_user(username=name, is_staff=True)
        user.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='home', codename__in=permissions,
        ))
        self.client.force_login(user)
        return user

    def post(self, name, payload):
        return self.client.post(reverse(name), json.dumps(payload), content_type='application/json')

    def test_generic_staff_reads_map_without_editor_or_write_access(self):
        self.login('world-reader')
        page = self.client.get(reverse('mapa'))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, 'id="adminToolbar"')
        self.assertEqual(self.post('wiki_batch_save_map', {
            'markers': [{'nome': 'Intrusao', 'lat': 1, 'lng': 2}],
        }).status_code, 403)
        self.assertEqual(self.post('wiki_save_desenho', {
            'tipo': 'linha', 'dados_json': {'pontos': [[0, 0], [1, 1]]},
        }).status_code, 403)
        self.assertEqual(self.post('wiki_delete_desenho', {'id': 1}).status_code, 403)
        self.assertEqual(self.client.post(reverse('wiki_update_marker_position', args=[1]),
                                          json.dumps({'lat': 1, 'lng': 2}),
                                          content_type='application/json').status_code, 403)
        self.assertEqual(self.post('wiki_create_region', {'nome': 'Intrusao'}).status_code, 403)
        self.assertEqual(self.post('wiki_create_territory', {'nome': 'Intrusao'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('wiki_upload_map_image'), {
            'imagem': SimpleUploadedFile('teste.png', b'png', content_type='image/png'),
        }).status_code, 403)
        self.assertEqual(self.client.post(reverse('wiki_update_region', args=[self.region.pk]),
                                          json.dumps({'nome': 'Intrusao'}),
                                          content_type='application/json').status_code, 403)
        self.assertEqual(self.client.post(reverse('wiki_update_territory', args=[self.territory.pk]),
                                          json.dumps({'nome': 'Intrusao'}),
                                          content_type='application/json').status_code, 403)
        self.assertFalse(TbRegiao.objects.filter(nome='Intrusao').exists())
        self.assertFalse(TbTerritorio.objects.filter(nome='Intrusao').exists())
        self.assertFalse(LogEntry.objects.exists())

    def test_explicit_map_role_edits_map_and_records_drawing_creation(self):
        editor = self.login('world-map-editor', MAP_ROLE)
        page = self.client.get(reverse('mapa'))
        self.assertContains(page, 'id="adminToolbar"')
        self.assertNotContains(page, 'layer-manage-btn')
        self.assertEqual(self.client.post(reverse('wiki_add_layer')).status_code, 403)
        self.assertEqual(self.post('wiki_create_territory', {'nome': 'Lago Editorial'}).status_code, 200)
        with tempfile.TemporaryDirectory(prefix='bonfire-map-upload-') as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                uploaded = self.client.post(reverse('wiki_upload_map_image'), {
                    'imagem': SimpleUploadedFile('teste.png', b'png', content_type='image/png'),
                })
                self.assertEqual(uploaded.status_code, 200)
                self.assertTrue(uploaded.json()['url'].startswith('/media/map_uploads/'))
        created = self.post('wiki_batch_save_map', {
            'markers': [{'nome': 'Farol Editorial', 'lat': 3, 'lng': 4,
                         'territorio': self.territory.nome}],
        })
        self.assertEqual(created.status_code, 200)
        marker = TbMapMarker.objects.get(nome='Farol Editorial')
        region = TbRegiao.objects.get(nome='Farol Editorial')
        drawing = self.post('wiki_save_desenho', {
            'tipo': 'linha', 'nome': 'Rota editorial',
            'dados_json': {'pontos': [[0, 0], [1, 1]]},
        })
        self.assertEqual(drawing.status_code, 200)
        saved = TbMapDesenho.objects.get(pk=drawing.json()['id'])
        self.assertEqual(saved.criado_por_id, editor.pk)
        updated = self.post('wiki_save_desenho', {
            'id': saved.pk, 'tipo': 'linha', 'nome': 'Rota revisada',
            'dados_json': {'pontos': [[0, 0], [2, 2]]},
        })
        self.assertEqual(updated.status_code, 200)
        entries = LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(saved),
            object_id=str(saved.pk),
        ).order_by('pk')
        self.assertEqual(list(entries.values_list('action_flag', flat=True)), [ADDITION, CHANGE])
        self.assertEqual({entry.user_id for entry in entries}, {editor.pk})
        self.assertTrue(LogEntry.objects.filter(object_id=str(marker.pk)).exists())
        self.client.logout()
        public = self.client.get(reverse('regiao_detail', args=[region.slug]))
        self.assertEqual(public.status_code, 200)
        self.assertContains(public, 'Farol Editorial')
        self.assertContains(self.client.get(reverse('mapa')), 'Rota revisada')
        self.client.force_login(editor)
        deleted = self.post('wiki_delete_desenho', {'id': saved.pk})
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(TbMapDesenho.objects.filter(pk=saved.pk).exists())
        self.assertEqual(list(entries.values_list('action_flag', flat=True)),
                         [ADDITION, CHANGE, DELETION])
        self.assertNotContains(self.client.get(reverse('mapa')), 'Rota revisada')

    def test_region_and_territory_controls_follow_separate_permissions(self):
        region_editor = self.login('world-region-editor', ('change_tbregiao',))
        self.assertTrue(region_editor.has_perm('home.change_tbregiao'))
        region_page = self.client.get(reverse('regiao_detail', args=[self.region.slug]))
        territory_page = self.client.get(reverse('territorio_detail', args=[self.territory.slug]))
        self.assertContains(region_page, 'const canEditRegion = true;')
        self.assertContains(territory_page, 'const canEditTerritory = false;')
        self.assertNotContains(region_page, 'id="adminToolbar"')
        updated = self.client.post(reverse('wiki_update_region', args=[self.region.pk]),
                                   json.dumps({'nome': self.region.nome,
                                               'lore_markdown': 'Lore revisada.'}),
                                   content_type='application/json')
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.post(reverse('wiki_update_territory', args=[self.territory.pk]),
                                          json.dumps({'nome': 'Nome indevido'}),
                                          content_type='application/json').status_code, 403)
        self.client.logout()
        self.assertContains(self.client.get(reverse('regiao_detail', args=[self.region.slug])),
                            'Lore revisada.')

    def test_region_creator_can_publish_without_territory_creation_control(self):
        self.login('world-region-creator', ('add_tbregiao',))
        listing = self.client.get(reverse('mundo_regioes'))
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, 'id="btnNewRegion"')
        self.assertNotContains(listing, 'id="btnShowCreateTerritoryRegion"')
        created = self.post('wiki_create_region', {
            'nome': 'Cidade Nova Editorial', 'territorio': self.territory.nome,
            'lore_markdown': 'Lore publicada.',
        })
        self.assertEqual(created.status_code, 200)
        self.assertEqual(self.post('wiki_create_territory', {'nome': 'Intrusao'}).status_code, 403)
        self.client.logout()
        self.assertContains(self.client.get(reverse('regiao_detail', args=['cidade-nova-editorial'])),
                            'Lore publicada.')
