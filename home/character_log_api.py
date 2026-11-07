"""Administrative automation over the same preview/apply used by the operator UI."""
import json
import re

from django.core.exceptions import PermissionDenied, ValidationError

from .character_log_import import apply_log, preview_log, registered_logs
from .db_access import ApiProblem, MAX_BODY_BYTES


def _actor(api_key):
    actor = getattr(api_key, 'created_by', None)
    if not actor or not actor.is_active or not actor.is_superuser:
        raise ApiProblem(403, 'superuser_key_required', 'Importacao exige chave de administrador ativo.')
    return actor


def _invalid(error):
    return ApiProblem(400, 'invalid_character_log_import', '; '.join(error.messages)[:1000])


def character_logs_read(payload, api_key):
    actor = _actor(api_key)
    if not isinstance(payload, dict) or set(payload) - {'discord_id', 'offset', 'limit'}:
        raise ApiProblem(400, 'invalid_character_logs_query', 'Consulta invalida.')
    offset, limit = payload.get('offset', 0), payload.get('limit', 25)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 25:
        raise ApiProblem(400, 'invalid_pagination', 'Use offset >= 0 e limit entre 1 e 25.')
    try:
        logs = registered_logs(actor, payload.get('discord_id'))
    except ValidationError as error:
        raise _invalid(error) from None
    return {'total': len(logs), 'offset': offset, 'rows': [{
        'id': log.pk, 'spreadsheet_id': log.spreadsheetId, 'character_name': log.characterName,
        'class_name': log.className, 'level': log.level, 'rank_name': log.rankName,
        'adventures_reported': log.adventuresPlayed,
    } for log in logs[offset:offset + limit]]}


def character_log_preview(payload, api_key):
    actor = _actor(api_key)
    if (not isinstance(payload, dict) or set(payload) - {'log_id', 'guild_id'}
            or not isinstance(payload.get('log_id'), str) or not 1 <= len(payload['log_id']) <= 30):
        raise ApiProblem(400, 'invalid_character_log_import', 'Informe a ficha registrada no bot.')
    try:
        preview = preview_log(actor, payload['log_id'], guild_id=payload.get('guild_id'))
    except ValidationError as error:
        raise _invalid(error) from None
    result = {'base_version': preview['fingerprint'], 'ticket': preview['ticket'],
              'metadata': preview['metadata'], 'matched': preview['matched'],
              'pending': preview['pending'], 'total_rows': len(preview['rows']),
              'warnings': preview['warnings'], 'sample': preview['rows'][:10]}
    if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_BODY_BYTES - 1024:
        raise ApiProblem(413, 'character_log_preview_too_large',
                         'Previa grande para a API; use /gestao/fichas-bot/ para conferir esta fonte.')
    return result


def character_log_apply(payload, api_key):
    actor = _actor(api_key)
    if (not isinstance(payload, dict) or set(payload) != {'base_version', 'ticket'}
            or not isinstance(payload['base_version'], str)
            or not re.fullmatch(r'[a-f0-9]{64}', payload['base_version'])
            or not isinstance(payload['ticket'], str) or len(payload['ticket']) > MAX_BODY_BYTES):
        raise ApiProblem(400, 'invalid_character_log_import', 'Confirme a previa e sua versao.')
    try:
        batch = apply_log(actor, payload['ticket'], expected_fingerprint=payload['base_version'])
    except PermissionDenied:
        raise ApiProblem(403, 'character_log_actor_mismatch', 'A previa pertence a outro administrador.') from None
    except ValidationError as error:
        raise _invalid(error) from None
    return {'batch_id': batch.pk, 'source_id': batch.source_id,
            'matched': sum(row['state'] == 'matched' for row in batch.snapshot['rows']),
            'playable_character_created': False, 'rewards_credited': False,
            'receipt_url': f'/gestao/fichas-bot/?batch={batch.pk}'}
