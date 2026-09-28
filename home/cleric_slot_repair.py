"""Reparo Q04 limitado à tabela de slots do Clérigo conhecida na importação.

Não modifica fichas, contadores gastos ou subclasses. Alterações editoriais
divergentes exigem revisão, em vez de serem substituídas por este lote.
"""
from django.db import transaction

from .models import TbClasse, TbRecursoclasse


LEGACY_TABLES = {
  1: {'1': '2', '2': '3', '3': '4'},
  2: {'3': '2', '4': '3', '5': '4', '6': '3'},
  3: {'5': '2', '6': '3'},
  4: {'7': '1', '8': '2', '9': '3'},
  5: {'9': '1', '10': '2'},
  6: {'11': '1', '19': '2'},
  7: {'13': '1', '20': '2'},
  8: {'15': '1'},
  9: {'17': '1'},
}


class SlotRepairConflict(ValueError):
  """O catálogo mudou ou está ambíguo; nenhum reparo pode ser aplicado."""


def repair_cleric_slots(*, apply=False):
  """Relata antes/depois; aplicação atômica somente no estado conhecido."""
  with transaction.atomic():
    classes = list(TbClasse.objects.select_for_update().filter(slug='clerigo'))
    if len(classes) != 1:
      raise SlotRepairConflict('Esperada exatamente uma classe clerigo.')
    resources = list(TbRecursoclasse.objects.select_for_update().filter(
      id_classe=classes[0], id_subclasse__isnull=True))
    changes = []
    for circle, old_table in LEGACY_TABLES.items():
      rows = [r for r in resources if r.slug in {str(circle), '%so' % circle}]
      if len(rows) != 1:
        raise SlotRepairConflict('Círculo %s ausente ou duplicado.' % circle)
      resource = rows[0]
      target_table = dict(old_table)
      if circle == 5:
        target_table['18'] = '3'
      if resource.tipo != 'table-only' or resource.valores_json not in (old_table, target_table):
        raise SlotRepairConflict('Tabela divergente no círculo %s (recurso %s).' % (circle, resource.pk))
      target_slug = '%so' % circle
      if resource.slug != target_slug or resource.valores_json != target_table:
        changes.append((resource, {
          'id': resource.pk, 'circle': circle,
          'before': {'slug': resource.slug, 'valores_json': resource.valores_json},
          'after': {'slug': target_slug, 'valores_json': target_table},
        }))
    if apply:
      for resource, change in changes:
        resource.slug = change['after']['slug']
        resource.valores_json = change['after']['valores_json']
        resource.save(update_fields=['slug', 'valores_json'])
    return {'applied': apply, 'changes': [change for _, change in changes]}
