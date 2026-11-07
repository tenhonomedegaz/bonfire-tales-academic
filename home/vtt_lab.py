"""Owner-isolated 2D laboratory. No command writes to the official character."""

import hashlib
import json
from copy import deepcopy
from functools import wraps
from urllib.parse import quote
from uuid import UUID, uuid4

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError, connection, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from .editorial_links import safe_editorial_image
from .management.commands.export_personagem_vtt import exportar_personagem, serializar
from .models import TbBestiario, TbPersonagem
from .tag_engine.library import Library
from .vtt_lab_combat import apply_combat, preview_movement
from .vtt_lab_movement import validate_board
from .movement_contract import creature_movement
from .vtt_lab_models import VttLabReceipt, VttLabSession, initial_lab_state
from .vtt_lab_resources import validate_pools
from .vtt_lab_spatial import measure_tokens
from .vtt_lab_presentation import validate_presentation
from .vtt_lab_sources import character_resources, character_rules, creature_rules, creature_snapshot


MAX_BODY_BYTES = 16 * 1024
MAX_EXPORT_BYTES = 256 * 1024
MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_TOKENS = 128
MAX_EVENTS = 100
MAX_INTEGER = 2 ** 53 - 1
_COMMAND_FIELDS = {
    'move_token': {'token_id', 'x', 'y', 'z'},
    'set_hp': {'token_id', 'hp'},
    'set_resource': {'token_id', 'resource_id', 'current'},
    'configure_board': {'blocked_cells', 'terrain_cells'},
    'configure_presentation': {'presentation'},
    'next_turn': set(),
    'import_character': {'personagem_id'},
    'import_creature': {'criatura_id'},
    'combat_start': {'teams'},
    'combat_start_turn': {'actor_id'},
    'combat_attack': {'target_id', 'action_id', 'hit', 'damage', 'damage_type'},
    'combat_heal': {'target_id', 'amount'},
    'combat_end_turn': set(),
    'combat_end': set(),
    'combat_move': {'x', 'y', 'z'},
}


class LabError(Exception):
    def __init__(self, error, message, status=400):
        self.error, self.message, self.status = error, message, status


def _error(error, message, status):
    return JsonResponse({'error': error, 'message': message}, status=status)


def _endpoint(methods):
    def decorate(function):
        protected = csrf_protect(function)

        @never_cache
        @wraps(function)
        def wrapped(request, *args, **kwargs):
            if not getattr(settings, 'VTT_LAB_ENABLED', False):
                return _error('disabled', 'Laboratorio indisponivel.', 404)
            user = request.user
            if not (user.is_authenticated and user.is_active and user.is_superuser):
                return _error('forbidden', 'Acesso restrito a administradores ativos.', 403)
            if request.method not in methods:
                response = _error('method_not_allowed', 'Metodo nao permitido.', 405)
                response['Allow'] = ', '.join(sorted(methods))
                return response
            try:
                response = protected(request, *args, **kwargs)
            except LabError as exc:
                response = _error(exc.error, exc.message, exc.status)
            except Http404:
                response = _error('not_found', 'Registro nao encontrado.', 404)
            except DatabaseError:
                response = _error('storage_error', 'Nao foi possivel concluir a operacao.', 503)
            if response.status_code == 403 and not response.get('Content-Type', '').startswith('application/json'):
                response = _error('csrf_failed', 'Token CSRF ausente ou invalido.', 403)
            patch_vary_headers(response, ('Cookie',))
            return response
        return wrapped
    return decorate


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _read_json(request):
    if request.content_type != 'application/json':
        raise LabError('invalid_content_type', 'Envie application/json.', 415)
    try:
        body = request.body
    except RequestDataTooBig:
        raise LabError('body_too_large', 'Requisicao excede o limite.', 413) from None
    if len(body) > MAX_BODY_BYTES:
        raise LabError('body_too_large', 'Requisicao excede o limite.', 413)
    try:
        value = json.loads(body)
        _json_bytes(value)
    except (ValueError, UnicodeError, RecursionError):
        raise LabError('invalid_json', 'JSON invalido.') from None
    if not isinstance(value, dict):
        raise LabError('invalid_json', 'Envie um objeto JSON.')
    return value


def _integer(value, field, minimum=0, maximum=MAX_INTEGER):
    if type(value) is not int or not minimum <= value <= maximum:
        raise LabError('invalid_parameter', f'{field} deve ser um inteiro entre {minimum} e {maximum}.')
    return value


def _uuid(value, field):
    try:
        if not isinstance(value, str):
            raise ValueError
        return UUID(value)
    except ValueError:
        raise LabError('invalid_parameter', f'{field} deve ser UUID.') from None


def _owned_session(request, session_id, *, lock=False):
    query = VttLabSession.objects.filter(owner=request.user)
    if lock:
        query = query.select_for_update()
    try:
        return query.get(pk=session_id)
    except VttLabSession.DoesNotExist:
        raise Http404 from None


def _envelope(session):
    return {'id': str(session.pk), 'nome': session.nome, 'revision': session.revision,
            'state': session.state, 'updated_at': session.atualizado_em.isoformat()}


def _portrait_url(value):
    image = safe_editorial_image(value)
    if image:
        return image
    if (isinstance(value, str) and value.startswith('/') and not value.startswith('//')
            and not any(ord(char) < 33 or ord(char) == 127 or char == '\\' for char in value)):
        return quote(value, safe='/:?&=#%[]@!$+,;~.-_')
    return ''


def _import_character(state, personagem_id):
    _integer(personagem_id, 'personagem_id', minimum=1)
    if len(state['tokens']) >= MAX_TOKENS:
        raise LabError('token_limit', 'Limite de tokens atingido.', 409)
    try:
        character = TbPersonagem.objects.select_related('id_raca', 'id_essencia').get(pk=personagem_id)
    except TbPersonagem.DoesNotExist:
        raise Http404 from None
    attempted_write = False

    def readonly(execute, sql, params, many, context):
        nonlocal attempted_write
        command = sql.lstrip().split(None, 1)[0].upper() if isinstance(sql, str) and sql.strip() else ''
        if command not in {'SELECT', 'SAVEPOINT', 'RELEASE', 'ROLLBACK', 'BEGIN'}:
            attempted_write = True
            raise RuntimeError('Official data is read-only in the laboratory')
        return execute(sql, params, many, context)

    try:
        # Existing export helpers may evolve; fail closed even if they swallow a blocked write.
        with connection.execute_wrapper(readonly):
            exported = exportar_personagem(character)
            rules = character_rules(character, exported)
            try:
                resources = validate_pools(character_resources(exported))
            except ValueError as error:
                resources = {}
                rules.setdefault('warnings', []).append('Recursos parciais: ' + str(error))
        if attempted_write:
            raise RuntimeError('Export attempted to write')
        encoded = serializar(exported).encode('utf-8')
        _json_bytes(exported)
        maximum = (exported.get('derive') or {}).get('pv_max', exported['estado_mesa']['pv_atual'])
        hp = exported['estado_mesa']['pv_atual']
        _integer(maximum, 'max_hp')
        _integer(hp, 'hp', maximum=maximum)
    except Exception:
        raise LabError('export_failed', 'Nao foi possivel obter uma copia somente leitura da ficha.', 422) from None
    if len(encoded) > MAX_EXPORT_BYTES:
        raise LabError('export_too_large', 'Exportacao da ficha excede o limite.', 413)
    index = len(state['tokens'])
    token = {
        'id': str(uuid4()), 'nome': character.nome,
        'x': index % state['board']['width'], 'y': index // state['board']['width'], 'z': 0,
        'hp': hp, 'max_hp': maximum,
        'source': {'personagem_id': character.pk, 'export_hash': hashlib.sha256(encoded).hexdigest()},
        'snapshot': deepcopy(exported),
        'rules': rules,
        'resources': resources,
        'movement': deepcopy((exported.get('derive') or {}).get('movimento') or {
            'schema': 1, 'unit': 'ft', 'speeds': {}, 'warnings': ['Deslocamento estruturado indisponivel; reimporte a ficha.']}),
    }
    portrait = _portrait_url(character.foto_url)
    if portrait:
        token['portrait'] = portrait
    state['tokens'].append(token)
    return token['id']


def _import_creature(state, criatura_id):
    _integer(criatura_id, 'criatura_id', minimum=1)
    if len(state['tokens']) >= MAX_TOKENS:
        raise LabError('token_limit', 'Limite de tokens atingido.', 409)
    try:
        creature = TbBestiario.objects.get(pk=criatura_id)
    except TbBestiario.DoesNotExist:
        raise Http404 from None
    try:
        exported = creature_snapshot(creature)
        movement = creature_movement(creature)
        exported['derive']['movimento'] = movement
        rules = creature_rules(creature)
        encoded = _json_bytes(exported)
        maximum = _integer(exported['derive']['pv_max'], 'max_hp', minimum=1)
    except (ValueError, TypeError, KeyError) as error:
        raise LabError('creature_import_failed', str(error), 422) from None
    if len(encoded) > MAX_EXPORT_BYTES:
        raise LabError('export_too_large', 'Exportacao da criatura excede o limite.', 413)
    index = len(state['tokens'])
    token = {'id': str(uuid4()), 'nome': creature.nome, 'x': index % state['board']['width'],
             'y': index // state['board']['width'], 'z': 0, 'hp': maximum, 'max_hp': maximum,
             'source': {'criatura_id': creature.pk, 'export_hash': hashlib.sha256(encoded).hexdigest()},
             'snapshot': exported, 'rules': rules, 'resources': {}, 'movement': movement}
    portrait = _portrait_url(creature.imagem_url)
    if portrait:
        token['portrait'] = portrait
    state['tokens'].append(token)
    return token['id']


def _bounded_state(state):
    if len(_json_bytes(state)) > MAX_STATE_BYTES:
        raise LabError('state_too_large', 'Estado do laboratorio excede o limite.', 413)


def _command(data):
    kind = data.get('type')
    if not isinstance(kind, str) or kind not in _COMMAND_FIELDS:
        raise LabError('unknown_command', 'Comando desconhecido.')
    fields = {'type', 'command_id', 'expected_revision'} | _COMMAND_FIELDS[kind]
    if set(data) != fields:
        raise LabError('invalid_parameter', 'Campos ausentes ou nao permitidos no comando.')
    normalized = dict(data)
    normalized['command_id'] = str(_uuid(data['command_id'], 'command_id'))
    _integer(data['expected_revision'], 'expected_revision')
    if 'token_id' in data:
        normalized['token_id'] = str(_uuid(data['token_id'], 'token_id'))
    if kind == 'import_character':
        _integer(data['personagem_id'], 'personagem_id', minimum=1)
    if kind == 'import_creature':
        _integer(data['criatura_id'], 'criatura_id', minimum=1)
    if kind == 'set_hp':
        _integer(data['hp'], 'hp')
    if kind == 'set_resource':
        _integer(data['current'], 'current')
        if not isinstance(data['resource_id'], str) or not 1 <= len(data['resource_id']) <= 180:
            raise LabError('invalid_parameter', 'resource_id deve identificar um recurso importado.')
    if kind in {'move_token', 'combat_move'}:
        for name in ('x', 'y', 'z'):
            normalized[name] = _integer(data[name], name)
    return normalized


def _apply(state, command):
    kind = command['type']
    if kind.startswith('combat_'):
        try:
            library = None
            if kind == 'combat_start':
                # Library's documented file fallback must not poison the command
                # transaction if its optional revision table is unavailable.
                with transaction.atomic():
                    library = Library()
            token_id = apply_combat(state, command, library_raw=library.raw if library else None)
            if library:
                state['combat_vocabulary'] = {'source': library.source, 'revision_id': library.revision_id}
            return token_id
        except ValueError as error:
            raise LabError('combat_invalid', str(error), 422) from None
    if (state.get('combat') or {}).get('active') and kind in {
            'set_hp', 'set_resource', 'move_token', 'configure_board', 'configure_presentation', 'next_turn', 'import_character', 'import_creature'}:
        raise LabError('combat_active', 'Encerre o combate antes de alterar a composicao ou os PV manualmente.', 409)
    if kind == 'import_character':
        return _import_character(state, command['personagem_id'])
    if kind == 'import_creature':
        return _import_creature(state, command['criatura_id'])
    if kind == 'configure_presentation':
        try:
            state['presentation']=validate_presentation(command['presentation'])
        except ValueError as error:
            raise LabError('presentation_invalid',str(error),422) from None
        return None
    if kind == 'configure_board':
        candidate = dict(state['board'], blocked_cells=command['blocked_cells'], terrain_cells=command['terrain_cells'])
        try:
            board = validate_board(candidate)
        except ValueError as error:
            raise LabError('board_invalid', str(error), 422) from None
        blocked = {(cell['x'], cell['y']) for cell in board['blocked_cells']}
        if any((token['x'], token['y']) in blocked and token['z'] == 0 for token in state['tokens']):
            raise LabError('board_occupied', 'Nao bloqueie uma celula ocupada por token.', 422)
        state['board'] = board
        return None
    if kind == 'next_turn':
        state['turn'] = _integer(state['turn'] + 1, 'turn')
        return None
    token = next((token for token in state['tokens'] if token['id'] == command['token_id']), None)
    if token is None:
        raise LabError('token_not_found', 'Token nao encontrado.', 404)
    if kind == 'move_token':
        if command['x'] >= state['board']['width'] or command['y'] >= state['board']['height'] or command['z'] > 100:
            raise LabError('out_of_bounds', 'Posicao fora dos limites do tabuleiro (z: 0..100).')
        token.update({name: command[name] for name in ('x', 'y', 'z')})
    elif kind == 'set_hp':
        token['hp'] = _integer(command['hp'], 'hp', maximum=token['max_hp'])
    elif kind == 'set_resource':
        pool = (token.get('resources') or {}).get(command['resource_id'])
        if not pool:
            raise LabError('resource_not_found', 'Recurso nao pertence a esta copia.', 404)
        pool['current'] = _integer(command['current'], 'current', maximum=pool['max'])
    return token['id']


@_endpoint({'GET'})
@ensure_csrf_cookie
def laboratory(request):
    # Avoid shared profile processors: visiting this tool cannot create official profile data.
    context = {'request': request, 'user': request.user, 'csrf_token': get_token(request),
               'page_title': 'Laboratorio VTT', 'ads_enabled': False, 'noindex': True,
               'vtt_lab_api_url': reverse('vtt_lab_sessions')}
    return HttpResponse(render_to_string('home/vtt_lab.html', context))


@_endpoint({'GET', 'POST'})
def sessions(request):
    if request.method == 'GET':
        return JsonResponse({'sessions': [
            {'id': str(row.pk), 'nome': row.nome, 'revision': row.revision,
             'updated_at': row.atualizado_em.isoformat()}
            for row in VttLabSession.objects.filter(owner=request.user).defer('state')]})
    data = _read_json(request)
    if set(data) - {'nome', 'personagem_id'}:
        raise LabError('invalid_parameter', 'Campos nao permitidos na criacao.')
    name = data.get('nome')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120 or '\x00' in name:
        raise LabError('invalid_parameter', 'nome deve ter de 1 a 120 caracteres.')
    with transaction.atomic():
        state = initial_lab_state()
        if 'personagem_id' in data:
            _import_character(state, data['personagem_id'])
        _bounded_state(state)
        session = VttLabSession.objects.create(owner=request.user, nome=name.strip(), state=state)
    return JsonResponse(_envelope(session), status=201)


@_endpoint({'GET'})
def session_snapshot(request, session_id):
    return JsonResponse(_envelope(_owned_session(request, session_id)))


@_endpoint({'GET'})
def measure(request, session_id):
    session = _owned_session(request, session_id)
    try:
        origin_id = str(_uuid(request.GET.get('origin_id'), 'origin_id'))
        target_id = str(_uuid(request.GET.get('target_id'), 'target_id'))
        result = measure_tokens(session.state, origin_id, target_id)
    except ValueError as error:
        raise LabError('measurement_invalid', str(error), 422) from None
    return JsonResponse(dict(result, revision=session.revision))


@_endpoint({'GET'})
def movement_preview(request, session_id):
    session = _owned_session(request, session_id)
    destination = {}
    for axis in ('x', 'y', 'z'):
        value = request.GET.get(axis, '')
        if not value.isdecimal() or len(value) > 6:
            raise LabError('invalid_parameter', 'Destino deve usar coordenadas inteiras nao negativas.')
        destination[axis] = _integer(int(value), axis, maximum=100000)
    try:
        plan = preview_movement(session.state, destination)
    except ValueError as error:
        raise LabError('movement_invalid', str(error), 422) from None
    return JsonResponse(dict(plan, revision=session.revision))


@_endpoint({'POST'})
def commands(request, session_id):
    command = _command(_read_json(request))
    payload_hash = hashlib.sha256(_json_bytes(command)).hexdigest()
    with transaction.atomic():
        session = _owned_session(request, session_id, lock=True)
        receipt = VttLabReceipt.objects.filter(session=session, command_id=command['command_id']).first()
        if receipt:
            if receipt.payload_hash != payload_hash:
                raise LabError('command_conflict', 'UUID ja utilizado para outro payload.', 409)
            response = JsonResponse(_envelope(session))
            response['X-VTT-Lab-Replayed'] = 'true'
            return response
        if command['expected_revision'] != session.revision:
            raise LabError('revision_conflict', 'Revisao desatualizada; recarregue o snapshot.', 409)
        if session.revision >= MAX_INTEGER:
            raise LabError('revision_limit', 'Limite de revisoes atingido.', 409)
        state = deepcopy(session.state)
        token_id = _apply(state, command)
        session.revision += 1
        event = dict(command, revision=session.revision)
        if token_id:
            event['token_id'] = token_id
        state['events'] = (state['events'] + [event])[-MAX_EVENTS:]
        _bounded_state(state)
        session.state = state
        session.save(update_fields=['state', 'revision', 'atualizado_em'])
        VttLabReceipt.objects.create(session=session, command_id=command['command_id'],
                                    payload_hash=payload_hash, revision=session.revision)
    return JsonResponse(_envelope(session))
