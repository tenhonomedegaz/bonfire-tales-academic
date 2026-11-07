"""S09 contract for the 22 routes found only in the redesign inventory.

The two caravan actions remain outside G01-A/C authorization. This suite
checks their absence while exercising the compatible routes through Django's
URL resolver and HTTP client with anonymous, owner, visitor and staff users.
"""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import Resolver404, resolve, reverse

from .models import TbMesaAnuncio, TbPerfilMestre, TbPersonagem, TbTrabalhoMestre


INVENTORY = Path(__file__).resolve().parent.parent / 'docs/integracao/redesign-s01-inventory.json'

# Inventory name -> current name. The MM action was renamed when integrated.
APPROVED = {
  'subscription_management': 'subscription_management',
  'master_gallery': 'master_gallery',
  'master_work_create': 'master_work_create',
  'master_gallery_review': 'master_gallery_review',
  'master_work_edit': 'master_work_edit',
  'master_work_review': 'master_work_review',
  'master_work_detail': 'master_work_detail',
  'theme_studio': 'theme_studio',
  'theme_acquire_mm': 'buy_theme_with_mm',
  'character_slots': 'character_slots',
  'master_dashboard': 'master_dashboard',
  'participation_edit': 'participation_edit',
  'master_request': 'master_request',
  'master_authorize': 'master_authorize',
  'masters_directory': 'masters_directory',
  'master_table_create': 'master_table_create',
  'master_table_edit': 'master_table_edit',
  'master_table_action': 'master_table_action',
  'master_table_detail': 'master_table_detail',
  'personagem_lenda': 'personagem_lenda',
}
# G01-A approves presentation only. Both caravan mutations require a
# separate mechanics/commerce decision before any URL may become reachable.
BLOCKED = {
  'mercado_configurar_caravana': 'caravan configuration changes mechanics',
  'mercado_comprar_pergaminho': 'scroll purchase changes commerce state',
}


class RedesignRouteMatrixTests(TestCase):
  """Integrated URL, method and access contract on an isolated test DB."""

  @classmethod
  def setUpTestData(cls):
    users = get_user_model()
    cls.owner = users.objects.create_user('matrix-owner')
    cls.visitor = users.objects.create_user('matrix-visitor')
    cls.staff = users.objects.create_superuser('matrix-staff', 'staff@example.test', 'test-pass')
    TbPerfilMestre.objects.create(user=cls.owner, status_mestre='aprovado',
                                  modo='mestre', listado=True)
    cls.work = TbTrabalhoMestre.objects.create(
      mestre=cls.owner, titulo='Relato fictício', categoria='relato',
      texto='Uma jornada anônima.', estado='rascunho', revisao=1)
    cls.table = TbMesaAnuncio.objects.create(
      mestre=cls.owner, titulo='Mesa fictícia', descricao='Sessão anônima.',
      rank='Obsidiana', ranks=['Obsidiana'], agenda_combinar=True,
      estado='rascunho', revisao=1)
    cls.legend = TbPersonagem.objects.create(
      dono=cls.owner, nome='Lenda fictícia', publico=True, aventuras=200)

  def setUp(self):
    self.assertEqual(connection.vendor, 'postgresql')
    self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))

  def url(self, name):
    args = [self.owner.pk] if name == 'master_authorize' else (
      [self.legend.pk] if name == 'personagem_lenda' else (
        [self.work.pk] if name.startswith('master_work_') and name not in (
          'master_work_create',) else (
          [self.table.pk] if name.startswith('master_table_') and name not in (
            'master_table_create',) else [])))
    return reverse(name, args=args)

  def request(self, role, method, name, data=None):
    self.client.logout()
    if role != 'anonymous':
      self.client.force_login(getattr(self, role))
    return getattr(self.client, method)(self.url(name), data or {})

  def test_inventory_has_twenty_compatible_and_two_blocked_routes(self):
    inventory = json.loads(INVENTORY.read_text(encoding='utf-8'))
    routes = [row for row in inventory['routes'] if row['status'] == 'source_only']
    self.assertEqual(len(routes), 22)
    self.assertEqual({row['name'] for row in routes}, set(APPROVED) | set(BLOCKED))
    for row in routes:
      with self.subTest(route=row['name']):
        self.assertEqual(row['gate'], 'G01')
        self.assertEqual(row['file'], 'home/urls.py')
        if row['name'] in APPROVED:
          path = self.url(APPROVED[row['name']])
          self.assertEqual(resolve(path).url_name, APPROVED[row['name']])
          self.assertEqual(path.lstrip('/'), row['pattern'].replace(
            '<int:pk>', str(self.legend.pk if row['name'] == 'personagem_lenda'
                                   else self.work.pk if 'work_' in row['name']
                                   else self.table.pk if 'table_' in row['name']
                                   else self.owner.pk)))
        else:
          path = '/' + row['pattern'].replace('<int:pk>', '1')
          with self.assertRaises(Resolver404):
            resolve(path)
          self.assertEqual(self.client.get(path).status_code, 404)
          self.assertEqual(self.client.post(path).status_code, 404)

  @override_settings(BONFIRE_COMMERCE_ENABLED=False)
  def test_integrated_method_and_access_matrix(self):
    # Each tuple is role, HTTP method, current route, expected status.
    cases = (
      ('anonymous', 'get', 'subscription_management', 302),
      ('owner', 'get', 'subscription_management', 200),
      ('owner', 'post', 'subscription_management', 405),
      ('anonymous', 'get', 'master_gallery', 302),
      ('visitor', 'get', 'master_gallery', 403),
      ('owner', 'get', 'master_gallery', 200),
      ('visitor', 'get', 'master_work_create', 403),
      ('owner', 'get', 'master_work_create', 200),
      ('visitor', 'get', 'master_work_edit', 403),
      ('owner', 'get', 'master_work_edit', 200),
      ('visitor', 'get', 'master_work_detail', 404),
      ('owner', 'get', 'master_work_detail', 200),
      ('visitor', 'post', 'master_work_review', 403),
      ('staff', 'post', 'master_work_review', 403),
      ('owner', 'get', 'master_gallery_review', 403),
      ('staff', 'get', 'master_gallery_review', 200),
      ('anonymous', 'get', 'theme_studio', 200),
      ('anonymous', 'post', 'theme_studio', 405),
      ('anonymous', 'post', 'buy_theme_with_mm', 302),
      ('owner', 'get', 'buy_theme_with_mm', 405),
      ('owner', 'post', 'buy_theme_with_mm', 403),
      ('anonymous', 'get', 'character_slots', 302),
      ('owner', 'get', 'character_slots', 200),
      ('owner', 'post', 'character_slots', 405),
      ('anonymous', 'get', 'master_dashboard', 302),
      ('visitor', 'get', 'master_dashboard', 403),
      ('staff', 'get', 'master_dashboard', 200),
      ('visitor', 'get', 'participation_edit', 403),
      ('owner', 'get', 'participation_edit', 200),
      ('owner', 'get', 'master_request', 403),
      ('visitor', 'post', 'master_request', 403),
      ('visitor', 'get', 'master_authorize', 405),
      ('visitor', 'post', 'master_authorize', 403),
      ('staff', 'post', 'master_authorize', 400),
      ('anonymous', 'get', 'masters_directory', 200),
      ('visitor', 'get', 'master_table_create', 403),
      ('owner', 'get', 'master_table_create', 200),
      ('visitor', 'get', 'master_table_edit', 403),
      ('owner', 'get', 'master_table_edit', 200),
      ('visitor', 'get', 'master_table_detail', 404),
      ('owner', 'get', 'master_table_detail', 200),
      ('visitor', 'post', 'master_table_action', 403),
      ('staff', 'post', 'master_table_action', 403),
      ('visitor', 'get', 'master_table_action', 405),
      ('anonymous', 'get', 'personagem_lenda', 200),
      ('anonymous', 'post', 'personagem_lenda', 405),
    )
    for role, method, name, expected in cases:
      with self.subTest(role=role, method=method, route=name):
        self.assertEqual(self.request(role, method, name).status_code, expected)

  def test_missing_objects_and_private_legend_stay_hidden(self):
    self.assertEqual(self.client.get(reverse('master_work_detail', args=[999999])).status_code, 404)
    self.assertEqual(self.client.get(reverse('master_table_detail', args=[999999])).status_code, 404)
    self.legend.publico = False
    self.legend.save(update_fields=['publico'])
    self.assertEqual(self.client.get(self.url('personagem_lenda')).status_code, 404)
