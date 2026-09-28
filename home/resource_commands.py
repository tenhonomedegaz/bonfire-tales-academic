"""Comandos de slots com revisão otimista e recibos transacionais duráveis."""
import hashlib
import json
import uuid

from django.db import transaction

from .models import TbOperacaoRecurso, TbPersonagem, TbPersonagemRecurso
from .resource_engine import canonical_key, mutate_resource


def slot_state(personagem, level, total, resource=None):
    """Projeta sem escrever; o token inclui identidade, revisão e teto derivado."""
    total = max(0, int(total))
    # A projeção segue ensure_resource: uma mudança de teto conserva usos
    # gastos, inclusive antes de o contador persistido ser sincronizado.
    spent = max(0, int(resource.maximo) - int(resource.atual)) if resource else 0
    current = max(0, min(total, total - spent))
    source = [personagem.pk, level, total, resource.pk if resource else None,
              resource.versao if resource else 0, current,
              resource.maximo if resource else None]
    version = hashlib.sha256(json.dumps(source).encode()).hexdigest()
    return {'nivel': level, 'atual': current, 'total': total, 'version': version}


def _current_slot(personagem, level, total):
    key = 'spell-slot:%d' % level
    resource = TbPersonagemRecurso.objects.filter(
        id_personagem=personagem, chave=canonical_key(key)).first()
    if resource is None:
        resource = TbPersonagemRecurso.objects.filter(
            id_personagem=personagem, chave='', nome=key).first()
    return slot_state(personagem, level, total, resource)


def execute_slot_command(personagem, *, user_id, level, action, operation_id,
                         expected_version, total_factory):
    """Serializa o teto, a comparação, a mutação e o recibo no mesmo commit.

    A autorização pertence à view. Repetições do mesmo comando não alteram o
    recurso, mesmo após descanso/reload ou em outra conexão ao PostgreSQL.
    """
    try:
        operation_id = uuid.UUID(str(operation_id))
    except (ValueError, TypeError, AttributeError):
        return {'ok': False, 'code': 'invalid_operation',
                'message': 'Identificador da operação inválido. Atualize a ficha.'}, 400
    if action not in ('gastar', 'desfazer') or not 1 <= level <= 9:
        return {'ok': False, 'operation_id': str(operation_id), 'code': 'invalid_slot',
                'message': 'Espaço de magia ou ação inválidos.'}, 400
    if not isinstance(expected_version, str) or len(expected_version) != 64:
        return {'ok': False, 'operation_id': str(operation_id), 'code': 'invalid_version',
                'message': 'Atualize a ficha antes de alterar os espaços de magia.'}, 400
    fingerprint = hashlib.sha256(json.dumps(
        [user_id, level, action, expected_version]).encode()).hexdigest()
    with transaction.atomic():
        TbPersonagem.objects.select_for_update().only('pk').get(pk=personagem.pk)
        total = max(0, int(total_factory()))
        snapshot = _current_slot(personagem, level, total)
        previous = TbOperacaoRecurso.objects.filter(
            id_personagem=personagem, operation_id=operation_id).first()
        if previous:
            if previous.fingerprint != fingerprint:
                return dict(ok=False, code='operation_conflict',
                            operation_id=str(operation_id), slot=snapshot,
                            version=snapshot['version'],
                            message='Esta operação já foi usada com outros dados.'), 409
            # O recibo comprova a aplicação original; o contador é o estado atual,
            # pois comandos/descansos posteriores não podem ser ocultados no replay.
            return dict(previous.resposta, replayed=True, slot=snapshot,
                        version=snapshot['version']), previous.status_http
        code, message, status = '', 'Espaços de magia atualizados.', 200
        if expected_version != snapshot['version']:
            code, message, status = ('stale_version',
                                    'Os espaços mudaram. Confira o contador atualizado.', 409)
        elif total == 0:
            code, message, status = 'unavailable_slot', 'Este espaço de magia não está disponível.', 400
        elif ((action == 'gastar' and snapshot['atual'] == 0) or
              (action == 'desfazer' and snapshot['atual'] == total)):
            code, message, status = 'slot_limit', 'O contador já está no limite.', 409
        else:
            key = 'spell-slot:%d' % level
            mutate_resource(personagem, {
                'key': key, 'legacy_name': key, 'name': key,
                'maximum': total, 'reset': 'long_rest', 'origin': 'spellcasting',
            }, 1 if action == 'desfazer' else -1)
            snapshot = _current_slot(personagem, level, total)
        response = dict(ok=status == 200, code=code, message=message,
                        operation_id=str(operation_id), version=snapshot['version'],
                        slot=snapshot, replayed=False)
        TbOperacaoRecurso.objects.create(
            id_personagem=personagem, operation_id=operation_id,
            fingerprint=fingerprint, resposta=response, status_http=status)
        return response, status
