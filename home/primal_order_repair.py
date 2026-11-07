"""Mecânica Q07 correspondente à descrição Bonfire importada da Ordem Primal."""
from hashlib import sha256

from django.db import transaction

from .models import TbClassehabilidade


DESCRIPTION_SHA256 = '0eb47c4d395727e6b8063a8db2aa9d06ce4aa0328792d790a2534eb103300372'
PRIMAL_TAGS = [
  'pick:ordem_primal:{xama|guardiao}:1',
  'match(pick:ordem_primal){'
  'xama:{spell_selection:mago{nivel:0, qtd:2, spell_mod:wis, fora_do_limite}, '
  'always_active{check_bonus:arcanismo=max(wis_mod, 1), check_bonus:religiao=max(wis_mod, 1)}}, '
  'guardiao:{prof:weapon{armas_marciais}, prof:armor{armadura_media}}}',
]


class PrimalOrderConflict(ValueError):
  """O conteúdo alvo diverge do registro importado conhecido."""


def repair_primal_order(*, apply=False):
  """Prévia por padrão; completa só tags vazias, preservando ID, nível e escolhas."""
  with transaction.atomic():
    rows = list(TbClassehabilidade.objects.select_for_update().filter(
      id_classe__slug='druida', id_subclasse__isnull=True, nome='Ordem Primal'))
    if len(rows) != 1:
      raise PrimalOrderConflict('Esperada exatamente uma Ordem Primal da classe druida.')
    row = rows[0]
    if (row.niveladquirido != 2 or row.table_only
        or sha256((row.descricao or '').encode('utf-8')).hexdigest() != DESCRIPTION_SHA256
        or row.tags_json not in (None, [], PRIMAL_TAGS)):
      raise PrimalOrderConflict('Ordem Primal divergente: conferir nível, descrição e tags antes de aplicar.')
    changes = [] if row.tags_json == PRIMAL_TAGS else [{
      'id': row.pk, 'before': row.tags_json, 'after': PRIMAL_TAGS}]
    if apply and changes:
      row.tags_json = list(PRIMAL_TAGS)
      row.save(update_fields=['tags_json'])
    return {'applied': apply, 'changes': changes}
