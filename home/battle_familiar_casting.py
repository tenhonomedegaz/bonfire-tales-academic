"""Common Battle Familiar lifecycle in the Workshop; no hunter rules."""
from copy import copy, deepcopy
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.core import signing
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

KEY = 'familiar:battle:common'
BASE_FIELDS = (
    ('form', 'Forma original'), ('type', 'Tipo de criatura'),
    ('alignment', 'Alinhamento'), ('hp', 'PV atuais'),
    ('hp_max', 'PV máximos'), ('hit_dice', 'Dados de Vida'),
    ('traits', 'Características de Find Familiar (registre nenhuma se aplicável)'),
)


def identity(spell, name='Battle Familiar'):
    return str(getattr(spell, 'nome_ingles', '') or '').strip().casefold() == name.casefold()


def command_token(personagem):
    return signing.dumps({'p': personagem.pk, 'nonce': uuid4().hex}, salt=KEY)


def require_no_primordial(personagem):
    """Caller holds the character lock, in the same order as Hunter summon."""
    from .models import TbPersonagemCacador
    profiles = TbPersonagemCacador.objects.select_for_update().filter(
        personagem_classe__id_personagem=personagem)
    if any((profile.companion or {}).get('active') is True for profile in profiles):
        raise ValueError(
            'Você já possui um Companheiro Primordial ativo. Gerencie ou dispense '
            'esse familiar no painel Hunter antes de conjurar outro familiar.')


def find_states(personagem, name='Find Familiar'):
    from .models import TbMagia
    spells = list(TbMagia.objects.filter(nome_ingles__iexact=name))
    ids = {s.pk for s in spells}
    origins = {'magia:' + s.slug for s in spells}
    return [s for s in personagem.estados.filter(ativo=True, origem__startswith='magia:').order_by('-iniciado_em', '-pk')
            if s.chave != KEY and (s.payload_json.get('spell_id') in ids or s.origem in origins)]


def finish(personagem, state, *, restore=True):
    """Caller holds the character lock. Restore the exact underlying state."""
    from .resource_engine import end_state
    payload = deepcopy(state.payload_json)
    base = payload.get('base_state')
    if base and restore:
        personagem.estados.filter(pk=base['id'], id_personagem=personagem).update(
            ativo=True, encerrado_em=None, payload_json=base['payload'])
    payload['temp_hp'] = 0
    payload['revision'] = uuid4().hex
    state.payload_json = payload
    state.save(update_fields=['payload_json'])
    end_state(personagem, state.chave)


def sync_locked(personagem):
    state = personagem.estados.filter(chave=KEY, ativo=True).first()
    if state:
        payload = state.payload_json
        expires = parse_datetime(payload['expires_at'])
        if expires <= timezone.now() or payload.get('temp_hp' if payload.get('base_state') else 'hp', 0) <= 0:
            finish(personagem, state)
            return None
    return state


def workshop_context(personagem):
    from .models import TbPersonagem
    with transaction.atomic():
        personagem = TbPersonagem.objects.select_for_update().get(pk=personagem.pk)
        state = sync_locked(personagem)
        bases = find_states(personagem)
        base = ((state.payload_json.get('base_state') or {}).get('payload', {}) if state
                else (bases[0].payload_json if bases else {}))
        values = base.get('find_familiar', {})
        return {
            'battle_familiar_state': state,
            'battle_familiar_token': command_token(personagem),
            'battle_familiar_has_base': bool(bases or (state and state.payload_json.get('base_state'))),
            'battle_familiar_missing': [{'key': key, 'label': label} for key, label in BASE_FIELDS
                                        if key not in values or values[key] in (None, '')],
        }


def register_base(base, data):
    payload = deepcopy(base.payload_json)
    values = deepcopy(payload.get('find_familiar', {}))
    for key, _label in BASE_FIELDS:
        if key not in values or values[key] in (None, ''):
            value = str(data.get('familiar_base_' + key, '')).strip()
            if not value or len(value) > 4000:
                raise ValueError('Registre os dados ausentes do Find Familiar existente antes de aprimorá-lo.')
            values[key] = value
    try:
        values['hp'], values['hp_max'] = int(values['hp']), int(values['hp_max'])
    except (ValueError, TypeError):
        raise ValueError('Informe PV inteiros para o familiar existente.')
    if not 0 < values['hp'] <= values['hp_max']:
        raise ValueError('Os PV do familiar existente devem estar entre 1 e seu máximo.')
    payload['find_familiar'] = values
    return payload


def cast(request, personagem, owned_id):
    """Atomic slot/material/state/receipt write, serialized by character."""
    from . import views
    from .battle_familiar import stat_block
    from .character_engine import derive
    from .magic_workshop import character_casters
    from .models import TbPersonagem, TbPersonagemMagia
    from .resource_engine import activate_state

    if personagem.dono_id != request.user.pk:
        raise Http404
    try:
        token = signing.loads(request.POST.get('familiar_command', ''), salt=KEY)
        if token['p'] != personagem.pk:
            raise ValueError
        receipt_key = 'familiar:receipt:' + token['nonce']
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        raise ValueError('Atualize a Oficina antes de conjurar o familiar.')
    command = {k: request.POST.get(k) for k in request.POST
               if k.startswith('familiar_') or k in ('slot', 'magia_personagem', 'ritual')}
    with transaction.atomic():
        p = TbPersonagem.objects.select_for_update().get(pk=personagem.pk, dono=request.user)
        receipt = p.estados.filter(chave=receipt_key).first()
        if receipt:
            if receipt.payload_json != command:
                raise ValueError('Este comando já foi usado com outras escolhas. Atualize a Oficina.')
            return 'Conjuração já registrada; nenhum novo recurso foi gasto.'
        require_no_primordial(p)
        owned = TbPersonagemMagia.objects.select_for_update(of=('self',)).select_related('id_magia').get(
            pk=owned_id, id_personagem=p)
        spell = owned.id_magia
        caster = views._oficina_cast_caster(p, owned, character_casters(p))
        if not identity(spell) or not caster or (caster['contract'].get('mode') == 'prepared'
                and not (owned.preparada or owned.sempre_preparada)):
            raise ValueError('Battle Familiar precisa estar disponível e preparada nesta classe.')
        if request.POST.get('ritual'):
            raise ValueError('Battle Familiar exige um espaço de magia; não é um ritual.')
        try:
            circle = int(request.POST.get('slot', ''))
        except (TypeError, ValueError):
            raise ValueError('Escolha um espaço de magia válido, do 2º ao 9º círculo.')
        if not 2 <= circle <= 9:
            raise ValueError('Escolha um espaço de magia válido, do 2º ao 9º círculo.')
        form = request.POST.get('familiar_form')
        if form not in ('bruto', 'voador', 'espreitador'):
            raise ValueError('Escolha Bruto, Voador ou Espreitador.')
        state = sync_locked(p)
        base_snapshot = deepcopy(state.payload_json.get('base_state')) if state else None
        bases = find_states(p)
        if len(bases) > 1:
            raise ValueError('Há mais de um Find Familiar registrado. Encerre os registros excedentes.')
        if bases:
            base_snapshot = {'id': bases[0].pk, 'payload': register_base(bases[0], request.POST)}
        if request.POST.get('familiar_existing') == 'yes' and not base_snapshot:
            from .models import TbMagia
            find_spell = TbMagia.objects.filter(nome_ingles__iexact='Find Familiar').first()
            if not find_spell:
                raise ValueError('Find Familiar ainda não está disponível no catálogo.')
            # Explicit registration of an already existing familiar, never an invented stat block.
            from types import SimpleNamespace
            base_payload = register_base(SimpleNamespace(payload_json={
                'spell_id': find_spell.pk, 'spell_name': find_spell.nome,
                'spell_slug': find_spell.slug, 'explicit_registration': True}), request.POST)
            base = activate_state(p, 'familiar:find:registered', origin='magia:' + find_spell.slug,
                                  payload=base_payload, ends_on=['dismissed'])
            base_snapshot = {'id': base.pk, 'payload': base_payload}
        if not base_snapshot and request.POST.get('familiar_existing') != 'no':
            raise ValueError('Declare se já possui um familiar de Find Familiar.')
        creature_type = request.POST.get('familiar_type', '')
        appearance = request.POST.get('familiar_appearance', '').strip()
        if not base_snapshot and (creature_type not in ('Celestial', 'Feérico', 'Ínfero')
                                  or not appearance or len(appearance) > 200):
            raise ValueError('Escolha o tipo e a aparência animal do novo familiar.')
        focus = views._oficina_find_component(p, spell, 'focus', lock=True)
        if focus is None:
            raise ValueError('Falta o diamante reutilizável de pelo menos 25 PO. Compre o componente na Oficina.')
        from .magic_workshop import component_item_info
        component = component_item_info(views._personagem_item_tags(focus)) or {}
        try:
            valid_price = Decimal(str(component.get('cost_po', 0))) >= 25
        except InvalidOperation:
            valid_price = False
        if not valid_price:
            raise ValueError('O componente registrado precisa valer pelo menos 25 PO.')
        # The Mystic's pact contract spends points by circle; honor its declared limit/cost.
        resource_spell = spell
        if caster['contract'].get('slots') not in ('full', 'half', 'third'):
            if circle > int(caster['max_spell_level'] or 0):
                raise ValueError('Use um círculo disponível no contrato de conjuração da classe.')
            resource_spell = copy(spell)
            resource_spell.nivel = circle
        from .epic_free_cast import roll_free_cast
        free_roll = (roll_free_cast(p, int(spell.nivel or 0),
                                    ruleset=views._resource_ruleset(p))
                     if caster['contract'].get('slots') in ('full', 'half', 'third')
                     else None)
        ok, spending = views._oficina_casting_resource(
            p, caster, resource_spell, circle,
            preserve_slot=bool(free_roll and free_roll['slot_preserved']))
        if not ok:
            raise ValueError('Não há espaço/recurso de magia disponível para esse círculo.')
        if free_roll:
            spending['free_cast_roll'] = free_roll['die']
        sheet = derive(p)
        signatures = {'str': 'FOR', 'dex': 'DES', 'con': 'CON', 'int': 'INT', 'wis': 'SAB', 'cha': 'CAR'}
        ability = caster['contract'].get('ability') or 'int'
        attack = int(sheet['bonus_proficiencia']) + max(
            int(sheet['atributos'][signatures[a]]['mod']) for a in ability.split('|'))
        attack += int((sheet.get('_tag') or {}).get('spell_attack_bonus') or 0)
        block = stat_block(circle, form, spell_attack=attack)
        base_values = base_snapshot['payload']['find_familiar'] if base_snapshot else {}
        payload = {
            'spell_id': spell.pk, 'spell_slug': spell.slug, 'spell_name': spell.nome,
            'owned_id': owned.pk, 'spending': spending, 'concentration': False,
            'block': block, 'base_state': base_snapshot, 'form': form,
            'type': base_values.get('type', creature_type),
            'alignment': base_values.get('alignment', 'Neutro'),
            'appearance': base_values.get('form', appearance),
            'hp': base_values.get('hp', block['hp_max']),
            'hp_max': base_values.get('hp_max', block['hp_max']),
            'hit_dice': base_values.get('hit_dice'), 'traits': base_values.get('traits'),
            'temp_hp': block['hp_max'] if base_snapshot else 0,
            'expires_at': (timezone.now() + timedelta(hours=1)).isoformat(),
            'revision': uuid4().hex,
        }
        if base_snapshot:
            p.estados.filter(pk=base_snapshot['id']).update(ativo=False, encerrado_em=timezone.now(),
                                                         payload_json=base_snapshot['payload'])
        from .resource_engine import end_state
        for old in find_states(p, 'Battle Familiar'):
            end_state(p, old.chave)
        activate_state(p, KEY, origin='magia:' + spell.slug, payload=payload,
                       ends_on=['dispelled', 'dismissed', 'death', 'expired'])
        views._registrar_transacao(p, 'ajuste', 'Conjuração na Oficina: ' + spell.nome, 0,
                                   {'operacao': 'battle_familiar', 'gasto': spending, 'circle': circle})
        receipt = activate_state(p, receipt_key, origin='oficina:battle_familiar', payload=command)
        receipt.ativo = False
        receipt.save(update_fields=['ativo'])
    return 'Familiar de Batalha registrado por 1 hora. O diamante não foi consumido.'


def update(request, personagem):
    from .models import TbPersonagem
    if personagem.dono_id != request.user.pk:
        raise Http404
    with transaction.atomic():
        p = TbPersonagem.objects.select_for_update().get(pk=personagem.pk, dono=request.user)
        state = sync_locked(p)
        if not state:
            return 'O efeito já terminou.'
        if request.POST.get('familiar_revision') != state.payload_json['revision']:
            raise ValueError('O familiar mudou desde a abertura deste formulário. Atualize a Oficina.')
        action = request.POST.get('familiar_action', 'end')
        if action in ('end', 'death'):
            finish(p, state, restore=action != 'death')
            return 'Familiar de Batalha encerrado; os itens carregados ficam no local.'
        if action != 'hp':
            raise ValueError('Ação inválida.')
        payload = deepcopy(state.payload_json)
        key = 'temp_hp' if payload.get('base_state') else 'hp'
        try:
            hp = int(request.POST.get('familiar_hp', ''))
        except (TypeError, ValueError):
            raise ValueError('Informe PV inteiros.')
        if not 0 <= hp <= payload[key]:
            raise ValueError('Informe o total restante, entre zero e o valor atual.')
        payload[key] = hp
        payload['revision'] = uuid4().hex
        state.payload_json = payload
        state.save(update_fields=['payload_json'])
        if hp == 0:
            finish(p, state)
        return 'Pontos de Vida do familiar atualizados.'


def replace_with_find(personagem):
    """Called under the Workshop casting lock before registering Find Familiar."""
    from .resource_engine import end_state
    state = personagem.estados.filter(chave=KEY, ativo=True).first()
    if state:
        finish(personagem, state, restore=False)
    for base in find_states(personagem):
        end_state(personagem, base.chave)
    for old in find_states(personagem, 'Battle Familiar'):
        end_state(personagem, old.chave)
