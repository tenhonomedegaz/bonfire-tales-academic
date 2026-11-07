"""Bounded catalog package import; never accepts SQL, remote URLs or filesystem paths."""
import json
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction

from .db_access import ApiProblem
from .master_legacy import bind_master, confirm_discord_masters, discover_bot_links, import_archive
from .models import TbImportacaoMestre, TbMestreLegado


def _package(payload):
    if (not isinstance(payload, dict) or set(payload) != {'package', 'source_sha256'}
            or not isinstance(payload['package'], str)
            or not re.fullmatch(r'[a-z0-9-]{1,80}', payload['package'])):
        raise ApiProblem(400, 'invalid_legacy_import', 'Informe package e source_sha256.')
    path = Path(settings.BASE_DIR) / 'home/content_packages/master_legacy' / (payload['package'] + '.json')
    if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ApiProblem(404, 'legacy_package_missing', 'Pacote legado nao instalado.')
    plan = json.loads(path.read_text(encoding='utf-8'))
    if plan['source_sha256'] != payload['source_sha256']:
        raise ApiProblem(409, 'legacy_source_changed', 'Checksum da planilha nao corresponde ao pacote.')
    return plan


def legacy_import_preview(payload, api_key):
    plan = _package(payload)
    archive = TbImportacaoMestre.objects.filter(fonte=payload['package']).first()
    return {'package': payload['package'], 'source_sha256': plan['source_sha256'],
            'masters': len(plan['masters']), 'records': len(plan['entries']),
            'warnings': plan.get('warnings', []), 'already_imported': bool(archive),
            'same_source': archive.checksum == plan['source_sha256'] if archive else True}


def _backup():
    from .content_maintenance import _fresh_backup, _local_postgres, _protected_directory
    if not _local_postgres():
        raise ValueError('Local PostgreSQL required for legacy import.')
    _fresh_backup(_protected_directory(), 'master-legacy')


def legacy_import_operation(payload, api_key):
    plan = _package(payload)
    try:
        if not TbImportacaoMestre.objects.filter(fonte=payload['package']).exists():
            _backup()
        archive, created = import_archive(plan, payload['package'])
        return {'import_id': archive.pk, 'created': created, 'masters': archive.mestres.count(),
                'next_operation': 'master-legacy-discover', 'wallets_changed': False}
    except (ValidationError, ValueError, OSError):
        raise ApiProblem(409, 'legacy_import_refused',
                         'Importacao ou backup recusado. Confira a fonte e a conciliacao existente.') from None


def legacy_discover_operation(payload, api_key):
    if (not isinstance(payload, dict) or set(payload) - {'import_id', 'guild_id'}
            or type(payload.get('import_id')) is not int):
        raise ApiProblem(400, 'invalid_legacy_import', 'Informe import_id inteiro.')
    try:
        _backup()
        with transaction.atomic():
            return discover_bot_links(payload['import_id'], guild_id=payload.get('guild_id'))
    except TbImportacaoMestre.DoesNotExist:
        raise ApiProblem(404, 'legacy_import_missing', 'Importacao nao encontrada.') from None
    except ValidationError as exc:
        raise ApiProblem(409, 'legacy_evidence_incomplete',
                         'Conferencia recusada; vinculos parciais nao foram aplicados.',
                         details={'reasons': exc.messages[:3]}) from None
    except DatabaseError as exc:
        code = getattr(exc.__cause__, 'sqlstate', None)
        raise ApiProblem(409, 'legacy_bot_database_unavailable',
                         'Leitura do bot recusada; nenhum vinculo parcial aplicado.',
                         details={'database_code': code if isinstance(code, str) and re.fullmatch(r'[A-Z0-9]{5}', code) else None}) from None
    except (ValueError, OSError):
        raise ApiProblem(409, 'legacy_bot_unavailable',
                         'Conferencia/backup do bot nao concluido; vinculos parciais recusados.') from None


def legacy_report_operation(payload, api_key):
    if not isinstance(payload, dict) or set(payload) - {'import_id', 'offset', 'limit'}:
        raise ApiProblem(400, 'invalid_legacy_report', 'Consulta invalida.')
    import_id, offset, limit = payload.get('import_id'), payload.get('offset', 0), payload.get('limit', 25)
    if (type(import_id) is not int or type(offset) is not int or offset < 0
            or type(limit) is not int or not 1 <= limit <= 50):
        raise ApiProblem(400, 'invalid_legacy_report', 'Informe import_id, offset >= 0 e limit 1..50.')
    try:
        archive = TbImportacaoMestre.objects.get(pk=import_id)
    except TbImportacaoMestre.DoesNotExist:
        raise ApiProblem(404, 'legacy_import_missing', 'Importacao nao encontrada.') from None
    query = archive.mestres.select_related('user__profile').order_by('numero')
    return {'import_id': archive.pk, 'source_sha256': archive.checksum, 'total': query.count(),
            'offset': offset, 'limit': limit,
            'masters': [{'id': row.pk, 'number': row.numero, 'name': row.nome, 'user_id': row.user_id,
                         'username': row.user.username if row.user_id else None,
                         'discord_id': row.discord_id, 'wallet_imported': bool(row.carteira_importada_em),
                         'legacy_mm': row.saldo_mm, 'legacy_event_coins': row.moedas_evento,
                         'current_mm': getattr(getattr(row.user, 'profile', None), 'moedas_mestragem', None),
                         'current_event_coins': getattr(getattr(row.user, 'profile', None), 'moedas_evento', None),
                         'reconciliation': row.conciliacao, 'evidence': row.evidencia}
                        for row in query[offset:offset + limit]]}


def legacy_bind_operation(payload, api_key):
    allowed = {'identity_id', 'username', 'wallet_mode', 'expected_balance', 'expected_events'}
    if (not isinstance(payload, dict) or set(payload) - allowed
            or type(payload.get('identity_id')) is not int
            or not isinstance(payload.get('username'), str) or not payload['username'].strip()):
        raise ApiProblem(400, 'invalid_master_binding', 'Informe identity_id e o login exato da conta.')
    users = list(get_user_model().objects.filter(username__iexact=payload['username'].strip())[:2])
    if len(users) != 1:
        raise ApiProblem(409, 'account_not_unique', 'Login nao encontrado ou ambiguo. Nao foi feita aproximacao de nomes.')
    try:
        from .master_legacy import require_admin
        actor = getattr(api_key, 'created_by', None)
        require_admin(actor)
        _backup()
        row = bind_master(payload['identity_id'], users[0].pk, actor=actor,
            wallet_mode=payload.get('wallet_mode', 'empty'),
            expected_balance=payload.get('expected_balance'), expected_events=payload.get('expected_events'))
        return {'identity_id': row.pk, 'user_id': row.user_id,
                'wallet_imported': bool(row.carteira_importada_em), 'reconciliation': row.conciliacao}
    except PermissionDenied:
        raise ApiProblem(403, 'superuser_key_required', 'Vinculo manual exige chave criada por superusuario ativo.') from None
    except TbMestreLegado.DoesNotExist:
        raise ApiProblem(404, 'legacy_master_missing', 'Identidade legada nao encontrada.') from None
    except (ValidationError, ValueError, OSError):
        raise ApiProblem(409, 'master_binding_refused', 'Vinculo/backup recusado; confira conta e saldos antes de conciliar.') from None


def legacy_confirm_operation(payload, api_key):
    if not isinstance(payload, dict) or set(payload) != {'import_id', 'source_sha256', 'confirmations'}:
        raise ApiProblem(400, 'invalid_master_confirmations',
                         'Informe import_id, source_sha256 e confirmations.')
    try:
        from .master_legacy import require_admin
        actor = getattr(api_key, 'created_by', None)
        require_admin(actor)
        _backup()
        return confirm_discord_masters(payload['import_id'], payload['source_sha256'],
                                       payload['confirmations'], actor=actor)
    except PermissionDenied:
        raise ApiProblem(403, 'superuser_key_required',
                         'Confirmacoes exigem chave criada por superusuario ativo.') from None
    except TbImportacaoMestre.DoesNotExist:
        raise ApiProblem(404, 'legacy_import_missing', 'Importacao nao encontrada.') from None
    except ValidationError as exc:
        raise ApiProblem(409, 'master_confirmation_refused', 'Lote recusado sem alteracoes parciais.',
                         details={'reasons': exc.messages[:3]}) from None
    except (ValueError, OSError):
        raise ApiProblem(409, 'master_confirmation_backup_refused',
                         'Backup/confirmacao recusado; nenhum vinculo parcial aplicado.') from None


def _mission_request(payload, api_key, *, backfill=False, apply=False):
    from .master_legacy import _owner, require_admin
    actor = getattr(api_key, 'created_by', None)
    try:
        require_admin(actor)
    except PermissionDenied:
        raise ApiProblem(403, 'superuser_key_required', 'Esta operacao exige chave de superusuario ativo.') from None
    allowed = ({'import_id', 'guild_id', 'source_sha256', 'record_keys', 'admin_validated'} if backfill
               else {'import_id', 'guild_id', 'after_id', 'limit'})
    if apply:
        allowed = allowed | {'base_version'}
    if (not isinstance(payload, dict) or set(payload) - allowed
            or type(payload.get('import_id')) is not int
            or not isinstance(payload.get('guild_id'), str)
            or _owner(payload['guild_id']) != payload['guild_id']):
        raise ApiProblem(400, 'invalid_mission_request', 'Informe import_id e guild_id numerico em texto.')
    if backfill:
        keys = payload.get('record_keys')
        if (payload.get('admin_validated') is not True
                or not isinstance(payload.get('source_sha256'), str)
                or not re.fullmatch(r'[a-f0-9]{64}', payload['source_sha256'])
                or not isinstance(keys, list) or not 1 <= len(keys) <= 200
                or any(not isinstance(k, str) or not 1 <= len(k) <= 200 for k in keys)
                or len(set(keys)) != len(keys)):
            raise ApiProblem(400, 'invalid_legacy_records',
                             'Exige checksum, record_keys unicos (1..200) e admin_validated=true.')
        if apply and not re.fullmatch(r'[a-f0-9]{64}', str(payload.get('base_version', ''))):
            raise ApiProblem(400, 'invalid_base_version', 'Informe o base_version da previa.')
    elif (type(payload.get('limit', 50)) is not int or not 1 <= payload.get('limit', 50) <= 50
          or not isinstance(payload.get('after_id', ''), str)
          or not re.fullmatch(r'[a-zA-Z0-9_-]{0,30}', payload.get('after_id', ''))):
        raise ApiProblem(400, 'invalid_mission_page', 'Informe limit 1..50 e cursor after_id valido.')
    return actor


def _mission_error(exc):
    if isinstance(exc, TbImportacaoMestre.DoesNotExist):
        return ApiProblem(404, 'legacy_import_missing', 'Importacao nao encontrada.')
    if isinstance(exc, ValidationError):
        return ApiProblem(409, 'mission_archive_refused', 'Operacao recusada sem alteracoes parciais.',
                          details={'reasons': exc.messages[:3]})
    return ApiProblem(409, 'mission_source_unavailable', 'Fonte ou backup indisponivel; nao presumir registros ausentes.')


def master_missions_audit_operation(payload, api_key):
    from .master_mission_archive import mission_audit
    _mission_request(payload, api_key)
    try:
        return mission_audit(payload['import_id'], payload['guild_id'],
                             after_id=payload.get('after_id', ''), limit=payload.get('limit', 50))
    except (TbImportacaoMestre.DoesNotExist, ValidationError, DatabaseError) as exc:
        raise _mission_error(exc) from None


def legacy_bot_preview_operation(payload, api_key):
    from .master_mission_archive import backfill_plan
    _mission_request(payload, api_key, backfill=True)
    try:
        return backfill_plan(payload['import_id'], payload['source_sha256'],
                             payload['guild_id'], payload['record_keys'])
    except (TbImportacaoMestre.DoesNotExist, ValidationError, DatabaseError) as exc:
        raise _mission_error(exc) from None


def legacy_bot_apply_operation(payload, api_key):
    from .master_mission_archive import backfill_apply
    actor = _mission_request(payload, api_key, backfill=True, apply=True)
    try:
        _backup()
        return backfill_apply(payload['import_id'], payload['source_sha256'], payload['guild_id'],
                              payload['record_keys'], payload['base_version'], actor=actor)
    except (TbImportacaoMestre.DoesNotExist, ValidationError, DatabaseError, ValueError, OSError) as exc:
        raise _mission_error(exc) from None


def _review_operation(payload, api_key, *, apply=False):
    from .master_legacy import require_admin
    from .master_mission_review import preview, apply as apply_reviews
    try:
        actor = getattr(api_key, 'created_by', None)
        require_admin(actor)
        plan = preview(payload)
        if not apply:
            return plan
        if payload.get('base_version') != plan['base_version']:
            raise ValidationError('Previa desatualizada; nenhuma alteracao aplicada.')
        _backup()
        return apply_reviews(payload, actor=actor)
    except PermissionDenied:
        raise ApiProblem(403, 'superuser_key_required', 'Revisao exige chave de superusuario ativo.') from None
    except (ValidationError, DatabaseError, ValueError, OSError) as exc:
        raise _mission_error(exc) from None


def mission_review_preview_operation(payload, api_key):
    return _review_operation(payload, api_key)


def mission_review_apply_operation(payload, api_key):
    return _review_operation(payload, api_key, apply=True)
