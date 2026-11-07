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
    if spell.get('concentracao'):
        from .hunter_mutagens import concentration_blocked
        if concentration_blocked(locked):
            raise ValueError('Concentracao bloqueada pelo efeito ativo.')
    key = spell['innate_key']
    ok, snapshot = spend_resource(locked, {
        'key': key, 'legacy_name': key, 'name': spell['nome'],
        'maximum': spell['innate_max'],
        'reset': spell.get('innate_reset') or 'long_rest',
        'origin': 'magia_inata:%s' % owned_spell_id,
    })
    if not ok:
        raise ValueError('Uso inato esgotado.')
    if spell.get('concentracao'):
        from .epic_concentration import begin_concentration
        from .models import TbPersonagemMagia
        from .resource_engine import activate_state

        owned = TbPersonagemMagia.objects.select_related('id_magia').get(
            pk=owned_spell_id, id_personagem=locked)
        state_key = 'spell:%s' % owned_spell_id
        begin_concentration(locked, state_key)
        activate_state(
            locked, state_key, origin='magia:%s' % spell['slug'],
            payload={
                'spell_id': owned.id_magia_id, 'spell_slug': spell['slug'],
                'spell_name': spell['nome'], 'owned_id': owned_spell_id,
                'concentration': True, 'innate': True,
            }, ends_on=['dispelled', 'dismissed'])
    response = {
        'operation_id': str(operation_id), 'spell_id': owned_spell_id,
        'spell_name': spell['nome'], 'without_slot': True,
        'without_components': True,
        'without_lethargy': bool(spell.get('innate_without_lethargy')),
        'remaining': snapshot['current'],
        'replayed': False,
    }
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=response, status_http=200)
    return response
