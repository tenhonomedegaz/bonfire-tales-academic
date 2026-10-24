"""Idempotent casting for an identified slotless spell granted by active tags."""

import hashlib
import json
import uuid

from django.db import transaction

from .models import TbOperacaoRecurso, TbPersonagem
from .resource_engine import spend_resource


@transaction.atomic
def cast_tagged_innate_spell(person, *, operation_id, owned_spell_id, ruleset=None):
    try:
        operation_id = uuid.UUID(str(operation_id))
        owned_spell_id = int(owned_spell_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Conjuração inata inválida.') from exc
    if owned_spell_id <= 0:
        raise ValueError('Magia inválida.')
    fingerprint = hashlib.sha256(json.dumps(
        ['innate-cast', owned_spell_id], separators=(',', ':')).encode()).hexdigest()

    locked = TbPersonagem.objects.select_for_update().get(pk=person.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Esta operação já foi usada com outros dados.')
        return dict(receipt.resposta, replayed=True)

    from .character_engine import derive
    from .views import _magias_sheet_info

    info = _magias_sheet_info(locked, derive(locked, ruleset=ruleset), [],
                              ruleset=ruleset)
    spell = next((row for row in info.get('lista', ())
                  if row.get('id') == owned_spell_id), None)
    if (not spell or spell.get('catalog_only') or spell.get('suspensa_na_revisao')
            or not spell.get('sempre_preparada') or not spell.get('innate_key')
            or not spell.get('innate_without_slot')
            or not spell.get('innate_without_components')):
        raise ValueError('Magia inata indisponível.')
    key = spell['innate_key']
    ok, snapshot = spend_resource(locked, {
        'key': key, 'legacy_name': key, 'name': spell['nome'],
        'maximum': spell['innate_max'],
        'reset': spell.get('innate_reset') or 'long_rest',
        'origin': 'magia_inata:%s' % owned_spell_id,
    })
    if not ok:
        raise ValueError('Uso inato esgotado.')
    response = {
        'operation_id': str(operation_id), 'spell_id': owned_spell_id,
        'spell_name': spell['nome'], 'without_slot': True,
        'without_components': True, 'remaining': snapshot['current'],
        'replayed': False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
