"""Reclassification checks using temporary packages and isolated database rows."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .cosmetic_reclassification import SELECTIONS, reclassify_cosmetics
from .cosmetics import catalog_options, get_catalog
from .models import (
  CosmeticCheckoutOffer, EventCosmeticOffer, EventCosmeticRedemption,
  TbCosmetico, TbPersonagem, TbUsuarioCosmetico, UserProfile,
)


class CosmeticReclassificationTests(TestCase):
  def setUp(self):
    cache.clear()
    self.addCleanup(cache.clear)
    self.actor = get_user_model().objects.create_superuser('reclassifier', password='test')
    self.user = get_user_model().objects.create_user('owner')
    temporary = TemporaryDirectory()
    self.addCleanup(temporary.cleanup)
    self.root = Path(temporary.name)
    self.patcher = patch('home.cosmetic_packages.PACKAGE_ROOT', self.root)
    self.patcher.start()
    self.addCleanup(self.patcher.stop)
    (self.root / 'test.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    self.item = self.make_item('sample')

  def make_item(self, key, kind='tema', **kwargs):
    return TbCosmetico.objects.create(
      slug=f'{kind}-{key}', tipo=kind, nome=key, origem='staff', **kwargs)

  def manifest(self, key='sample', target='efeito', **changes):
    raw = {
      'version': 1, 'slug': f'{target}-{key}', 'type': target, 'scope': 'ambos',
      'layers': [{'slot': 'banner', 'file': 'test.svg', 'fallback': 'test.svg',
                  'width': 100, 'height': 100}],
    }
    raw.update(changes)
    (self.root / f'{target}-{key}.json').write_text(json.dumps(raw), encoding='utf-8')

  def run_service(self, target='efeito', **kwargs):
    return reclassify_cosmetics(
      TbCosmetico.objects.filter(pk=self.item.pk), target, actor=self.actor, **kwargs)

  def test_moves_only_source_users_and_preserves_inventory_and_receipt(self):
    self.manifest()
    self.item.css_class = 'old-palette'
    self.item.definicao_json = {'metadata': 'preserved'}
    self.item.save()
    profile, _ = UserProfile.objects.get_or_create(user=self.user)
    profile.profile_theme, profile.profile_effect = 'sample', 'none'
    profile.save()
    character = TbPersonagem.objects.create(dono=self.user, nome='Test', ficha_theme='sample')
    other = TbPersonagem.objects.create(dono=self.user, nome='Other', ficha_theme='bonfire')
    suspended = timezone.now()
    inventory = TbUsuarioCosmetico.objects.create(
      user=self.user, cosmetico=self.item, origem='staff', suspenso_em=suspended)
    offer = EventCosmeticOffer.objects.create(
      event_key='test', cosmetico=self.item, active=False, cost_braseiros=0)
    receipt = EventCosmeticRedemption.objects.create(
      request_id=uuid4(), offer=offer, cosmetico=self.item, user=self.user, cost_braseiros=0)
    inventory_before = TbUsuarioCosmetico.objects.filter(pk=inventory.pk).values().get()
    receipt_before = EventCosmeticRedemption.objects.filter(pk=receipt.pk).values().get()
    get_catalog('tema')  # Prime the old category cache.
    result = self.run_service()
    self.assertEqual((result['changed'], result['moved'], result['conflicts']), (1, 2, 0))
    profile.refresh_from_db()
    character.refresh_from_db()
    other.refresh_from_db()
    self.item.refresh_from_db()
    self.assertEqual((profile.profile_theme, profile.profile_effect), ('bonfire', 'sample'))
    self.assertEqual((character.ficha_theme, character.ficha_effect), ('bonfire', 'sample'))
    self.assertIsNone(other.ficha_effect)
    self.assertEqual(self.item.slug, 'efeito-sample')
    self.assertEqual(self.item.css_class, 'old-palette')
    self.assertEqual(self.item.definicao_json, {'metadata': 'preserved'})
    self.assertEqual(inventory_before, TbUsuarioCosmetico.objects.filter(pk=inventory.pk).values().get())
    self.assertEqual(receipt_before, EventCosmeticRedemption.objects.filter(pk=receipt.pk).values().get())
    self.assertNotIn('sample', get_catalog('tema'))
    self.assertIn('sample', get_catalog('efeito'))
    self.assertIn('sample', [entry['key'] for entry in catalog_options(self.user, 'effect')])
    log = LogEntry.objects.get(object_id=str(self.item.pk))
    self.assertEqual(log.user_id, self.actor.pk)
    self.assertIn('movidos=2; conflitos=0', log.change_message)

  def test_all_type_directions_and_destination_conflicts(self):
    for source, source_fields in SELECTIONS.items():
      for target, target_fields in SELECTIONS.items():
        if source == target:
          continue
        key = f'{source}-to-{target}'
        item = self.make_item(key, source)
        self.manifest(key, target)
        user = get_user_model().objects.create_user(key)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        setattr(profile, source_fields['perfil'], key)
        setattr(profile, target_fields['perfil'], 'other-choice')
        profile.save()
        character = TbPersonagem.objects.create(dono=user, nome=key, **{
          source_fields['ficha']: key, target_fields['ficha']: target_fields['default']})
        result = reclassify_cosmetics(TbCosmetico.objects.filter(pk=item.pk), target, actor=self.actor)
        self.assertEqual((result['moved'], result['conflicts']), (1, 1))
        profile.refresh_from_db()
        character.refresh_from_db()
        self.assertEqual(getattr(profile, source_fields['perfil']), source_fields['default'])
        self.assertEqual(getattr(profile, target_fields['perfil']), 'other-choice')
        self.assertEqual(getattr(character, target_fields['ficha']), key)

  def test_invalid_manifest_rejects_entire_batch_before_writes(self):
    self.manifest()
    second = self.make_item('second')
    for changes in ({'scope': 'perfil'}, {'scope': 'ficha'}, {'type': 'tema'}, {'layers': []}):
      with self.subTest(changes=changes):
        self.manifest('second', **changes)
        with self.assertRaises(ValidationError):
          reclassify_cosmetics(TbCosmetico.objects.all(), 'efeito', actor=self.actor)
        self.item.refresh_from_db()
        self.assertEqual(self.item.tipo, 'tema')
        self.assertEqual(LogEntry.objects.count(), 0)
    (self.root / 'efeito-second.json').unlink()
    with self.assertRaises(ValidationError):
      reclassify_cosmetics(TbCosmetico.objects.filter(pk__in=[self.item.pk, second.pk]), 'efeito', actor=self.actor)

  def test_collision_rejects_batch_and_keeps_existing_destination(self):
    self.manifest()
    target = self.make_item('sample', 'efeito')
    with self.assertRaises(ValidationError):
      self.run_service()
    self.item.refresh_from_db()
    target.refresh_from_db()
    self.assertEqual(self.item.tipo, 'tema')
    self.assertEqual(target.slug, 'efeito-sample')

  def test_duplicate_destinations_in_batch_are_rejected(self):
    self.manifest()
    self.make_item('sample', 'moldura')
    with self.assertRaises(ValidationError):
      reclassify_cosmetics(TbCosmetico.objects.all(), 'efeito', actor=self.actor)

  def test_each_active_offer_blocks_even_future_event_and_preserves_finance(self):
    self.manifest()
    for model, fields in (
      (CosmeticCheckoutOffer, {'amount': '12.00'}),
      (EventCosmeticOffer, {'event_key': 'test', 'cost_braseiros': 0,
                           'starts_at': timezone.now() + timezone.timedelta(days=1)}),
    ):
      offer = model.objects.create(cosmetico=self.item, active=True, **fields)
      before = model.objects.filter(pk=offer.pk).values().get()
      with self.assertRaises(ValidationError):
        self.run_service()
      self.assertEqual(before, model.objects.filter(pk=offer.pk).values().get())
      offer.active = False
      offer.save()
    self.assertEqual(self.run_service()['changed'], 1)

  def test_idempotent_same_type_ignores_package_offer_and_css_option(self):
    self.item.css_class = 'keep'
    self.item.save()
    CosmeticCheckoutOffer.objects.create(cosmetico=self.item, amount='1.00', active=True)
    result = self.run_service('tema', clear_css_class=True)
    self.assertEqual((result['changed'], result['noop']), (0, 1))
    self.item.refresh_from_db()
    self.assertEqual(self.item.css_class, 'keep')
    self.assertFalse(LogEntry.objects.exists())

  def test_explicit_css_clear_preserves_all_other_catalog_fields_and_second_run_noop(self):
    self.manifest()
    self.item.css_class = 'old-palette'
    self.item.save()
    before = TbCosmetico.objects.filter(pk=self.item.pk).values().get()
    self.run_service(clear_css_class=True)
    after = TbCosmetico.objects.filter(pk=self.item.pk).values().get()
    for field in before.keys() - {'tipo', 'slug', 'css_class'}:
      self.assertEqual(before[field], after[field], field)
    self.assertEqual(after['css_class'], '')
    self.assertIn('limpar_css_class=True', LogEntry.objects.get().change_message)
    self.assertEqual(self.run_service()['noop'], 1)

  def test_runtime_failure_rolls_back_catalog_selections_and_logs(self):
    self.manifest()
    profile, _ = UserProfile.objects.get_or_create(user=self.user)
    profile.profile_theme = 'sample'
    profile.save()
    with patch.object(LogEntry.objects, 'create', side_effect=RuntimeError('test')):
      with self.assertRaises(RuntimeError):
        self.run_service()
    profile.refresh_from_db()
    self.item.refresh_from_db()
    self.assertEqual(profile.profile_theme, 'sample')
    self.assertEqual(self.item.tipo, 'tema')

  def test_inactive_item_and_empty_destination_are_preserved_correctly(self):
    self.manifest()
    self.item.ativo = False
    self.item.save()
    profile, _ = UserProfile.objects.get_or_create(user=self.user)
    profile.profile_theme, profile.profile_effect = 'sample', ''
    profile.save()
    self.assertEqual(self.run_service()['moved'], 1)
    self.item.refresh_from_db()
    profile.refresh_from_db()
    self.assertFalse(self.item.ativo)
    self.assertEqual(profile.profile_effect, 'sample')
    self.assertNotIn('sample', get_catalog('efeito'))

  def test_admin_shows_service_validation_error_without_applying_batch(self):
    self.client.force_login(self.actor)
    response = self.client.post(reverse('admin:home_tbcosmetico_changelist'), {
      'action': 'reclassificar', '_selected_action': [self.item.pk],
      'apply': '1', 'target': 'efeito', 'confirm': 'on',
    })
    self.assertContains(response, 'pacote de destino valido')
    self.assertTrue(response.context['form'].non_field_errors())
    self.item.refresh_from_db()
    self.assertEqual(self.item.tipo, 'tema')
    self.assertFalse(LogEntry.objects.exists())

  def test_invalid_types_prefixes_reserved_keys_and_non_superuser(self):
    with self.assertRaises(PermissionDenied):
      reclassify_cosmetics(TbCosmetico.objects.all(), 'efeito', actor=self.user)
    with self.assertRaises(ValidationError):
      self.run_service('badge')
    for slug, kind in (('sample', 'tema'), ('tema-bonfire', 'tema'), ('badge-test', 'badge')):
      self.item.slug, self.item.tipo = slug, kind
      self.item.save()
      with self.assertRaises(ValidationError):
        self.run_service()

  def test_admin_requires_confirmation_and_reports_conflicts_and_css_clear(self):
    self.manifest()
    self.item.css_class = 'old-palette'
    self.item.save()
    profile, _ = UserProfile.objects.get_or_create(user=self.user)
    profile.profile_theme, profile.profile_effect = 'sample', 'existing'
    profile.save()
    self.client.force_login(self.actor)
    url = reverse('admin:home_tbcosmetico_changelist')
    data = {'action': 'reclassificar', '_selected_action': [self.item.pk]}
    response = self.client.post(url, data)
    self.assertContains(response, 'name="clear_css_class"')
    self.assertFalse(response.context['form'].fields['clear_css_class'].initial)
    response = self.client.post(url, {**data, 'apply': '1', 'target': 'efeito'})
    self.assertEqual(response.status_code, 200)
    self.assertIn('confirm', response.context['form'].errors)
    self.item.refresh_from_db()
    self.assertEqual(self.item.tipo, 'tema')
    response = self.client.post(url, {**data, 'apply': '1', 'target': 'efeito',
                                    'confirm': 'on', 'clear_css_class': 'on'}, follow=True)
    self.assertContains(response, 'conflitos preservados: 1')
    self.item.refresh_from_db()
    self.assertEqual(self.item.css_class, '')

  def test_admin_hides_and_rejects_action_for_staff(self):
    model_admin = admin.site._registry[TbCosmetico]
    self.user.is_staff = True
    self.user.save()
    request = RequestFactory().post('/', {'apply': '1', 'target': 'efeito', 'confirm': 'on'})
    request.user = self.user
    self.assertNotIn('reclassificar', model_admin.get_actions(request))
    with self.assertRaises(PermissionDenied):
      model_admin.reclassificar(request, TbCosmetico.objects.all())
