"""Atomic catalog reclassification without replacing items or entitlements."""

import re

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .cosmetic_packages import load_package
from .cosmetics import invalidate_cosmetic_cache
from .models import (
  CosmeticCheckoutOffer, EventCosmeticOffer, TbCosmetico, TbPersonagem, UserProfile,
)


SELECTIONS = {
  'tema': {'default': 'bonfire', 'perfil': 'profile_theme', 'ficha': 'ficha_theme'},
  'efeito': {'default': 'none', 'perfil': 'profile_effect', 'ficha': 'ficha_effect'},
  'moldura': {'default': 'none', 'perfil': 'avatar_frame', 'ficha': 'foto_frame'},
}
TARGET_CHOICES = [(kind, kind.title()) for kind in SELECTIONS]


@transaction.atomic
def reclassify_cosmetics(queryset, target, *, actor, clear_css_class=False):
  """Validate the entire locked batch, then move only matching saved selections.

  Active offers are deliberately blocked even outside their scheduled window.
  Financial records and inventories are never rewritten.
  """
  if not actor.is_active or not actor.is_superuser:
    raise PermissionDenied
  if target not in SELECTIONS:
    raise ValidationError('Tipo de destino invalido.')
  if type(clear_css_class) is not bool:
    raise ValidationError('A opcao de limpar css_class deve ser booleana.')
  items = list(queryset.select_for_update().order_by('pk'))
  result = {'changed': 0, 'noop': 0, 'moved': 0, 'conflicts': 0, 'items': []}
  plan = []
  destinations = set()
  for item in items:
    if item.tipo == target:
      result['noop'] += 1
      continue
    if item.tipo not in SELECTIONS or not item.slug.startswith(item.tipo + '-'):
      raise ValidationError(f'{item.slug}: tipo ou prefixo de origem invalido.')
    key = item.slug[len(item.tipo) + 1:]
    slug = target + '-' + key
    if (not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', key)
        or len(key) > 40 or len(slug) > 60
        or key in {entry['default'] for entry in SELECTIONS.values()}):
      raise ValidationError(f'{item.slug}: chave invalida ou reservada.')
    if slug in destinations or TbCosmetico.objects.filter(slug=slug).exclude(pk=item.pk).exists():
      raise ValidationError(f'{slug}: colisao com outro cosmetico.')
    destinations.add(slug)
    if any(load_package(target, key, scope) is None for scope in ('perfil', 'ficha')):
      raise ValidationError(f'{slug}: pacote de destino valido com scope ambos obrigatorio.')
    plan.append((item, key, slug))

  ids = [item.pk for item, _, _ in plan]
  for model in (CosmeticCheckoutOffer, EventCosmeticOffer):
    offers = list(model.objects.select_for_update().filter(cosmetico_id__in=ids))
    if any(offer.active for offer in offers):
      raise ValidationError('Lote bloqueado: existe oferta ativa ligada a um cosmetico selecionado.')

  for item, key, slug in plan:
    detail = {'pk': item.pk, 'source': item.slug, 'target': slug, 'moved': 0, 'conflicts': 0}
    source = SELECTIONS[item.tipo]
    destination = SELECTIONS[target]
    for scope, model in (('perfil', UserProfile), ('ficha', TbPersonagem)):
      source_field, target_field = source[scope], destination[scope]
      rows = model.objects.select_for_update().filter(**{source_field: key}).order_by('pk')
      for row in rows:
        updates = {source_field: source['default']}
        if getattr(row, target_field) in (None, '', destination['default']):
          updates[target_field] = key
          detail['moved'] += 1
        else:
          detail['conflicts'] += 1
        # Update only appearance fields; unrelated model hooks must not grant rights.
        model.objects.filter(pk=row.pk).update(**updates)
    item.tipo, item.slug = target, slug
    fields = ['tipo', 'slug']
    if clear_css_class:
      item.css_class = ''
      fields.append('css_class')
    item.save(update_fields=fields)
    result['changed'] += 1
    for count in ('moved', 'conflicts'):
      result[count] += detail[count]
    result['items'].append(detail)
    LogEntry.objects.create(
      user_id=actor.pk, content_type=ContentType.objects.get_for_model(TbCosmetico),
      object_id=str(item.pk), object_repr=str(item), action_flag=CHANGE,
      change_message=(f"Reclassificacao {detail['source']} -> {slug}; "
                      f"movidos={detail['moved']}; conflitos={detail['conflicts']}; "
                      f"lote={len(plan)}; sem_alteracao={result['noop']}; "
                      f"limpar_css_class={clear_css_class}"),
    )
  transaction.on_commit(invalidate_cosmetic_cache)
  return result
