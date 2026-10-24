"""Apply a temporary HP grant using the character's evaluated tag operations."""

import hashlib
import json
import uuid

from django.db import transaction

from .character_engine import _build_ctx, derive
from .models import TbOperacaoRecurso, TbPersonagem
from .tag_engine import ParseError, evaluate_tags


def received_temporary_hp(amount, operations):
    if type(amount) is not int or amount < 0:
        raise ValueError('PV temporários recebidos devem ser um inteiro não negativo.')
    if amount == 0:
        return 0
    bonus = sum(
        max(0, int(op['value']))
        for op in operations
        if op.get('active') and op.get('op') == 'heal'
        and op.get('target') == 'pv_temporario'
        and isinstance(op.get('value'), (int, float))
        and not isinstance(op.get('value'), bool)
    )
    return amount + bonus


def _grant_operations(personagem, *, ruleset=None):
    operations = []
    sheet = derive(personagem, ruleset=ruleset)
    context = dict(_build_ctx(sheet['nivel_total'], sheet['bonus_proficiencia'],
                              sheet['atributos']), resolve_runtime=True,
                   event='receive_temp_hp', self_hp=personagem.pv_atual,
                   self_max_hp=sheet['pv']['maximo_calculado'])
    for feature in sheet['tags_brutas']:
        try:
            operations.extend(vars(op) for op in evaluate_tags(
                feature['tags'], context).operations)
        except ParseError:
            # A ficha já informa o erro dessa fonte; não interrompa a concessão.
            continue
    return operations


def temporary_hp_bonus(personagem, *, ruleset=None):
    """Project active tag bonuses to a positive temporary HP grant."""
    return received_temporary_hp(1, _grant_operations(personagem, ruleset=ruleset)) - 1


def grant_temporary_hp(personagem, amount, *, ruleset=None):
    """Replace a lower pool after applying grants from the canonical sheet tags."""
    operations = _grant_operations(personagem, ruleset=ruleset) if amount else []
    received = received_temporary_hp(amount, operations)
    personagem.pv_temporario = max(personagem.pv_temporario or 0, received)
    personagem.save(update_fields=['pv_temporario'])
    return received


@transaction.atomic
def receive_tagged_temporary_hp(personagem, *, operation_id, amount, confirmed,
                                ruleset=None):
    """Owner-declared receipt; active tags determine the amount actually received."""
    try:
        operation_id = uuid.UUID(str(operation_id))
        amount = int(amount)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError('Informe uma concessão válida.') from exc
    if type(confirmed) is not bool or not confirmed or not 1 <= amount <= 100000:
        raise ValueError('Confirme a concessão de PV temporários na mesa.')
    fingerprint = hashlib.sha256(json.dumps(
        ['receive-temp-hp', amount, confirmed], separators=(',', ':')
    ).encode()).hexdigest()
    locked = TbPersonagem.objects.select_for_update().get(pk=personagem.pk)
    receipt = TbOperacaoRecurso.objects.filter(
        id_personagem=locked, operation_id=operation_id).first()
    if receipt:
        if receipt.fingerprint != fingerprint:
            raise ValueError('Esta operação já foi usada com outros dados.')
        return dict(receipt.resposta, replayed=True)
    if temporary_hp_bonus(locked, ruleset=ruleset) < 1:
        raise ValueError('Não há tag ativa para ampliar PV temporários.')
    before = max(0, int(locked.pv_temporario or 0))
    received = grant_temporary_hp(locked, amount, ruleset=ruleset)
    result = {'operation_id': str(operation_id), 'base': amount,
              'received': received, 'before': before,
              'after': locked.pv_temporario, 'replayed': False}
    TbOperacaoRecurso.objects.create(
        id_personagem=locked, operation_id=operation_id,
        fingerprint=fingerprint, resposta=result, status_http=200)
    return result
