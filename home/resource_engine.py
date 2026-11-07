"""Persistent, vocabulary-neutral resources for the character sheet.

This module owns quantities that survive requests: class pools, spell slots, innate
uses and item charges. Combat resolution is intentionally absent; callers provide a
resource contract already derived from tags and this service only applies deltas and
reset events atomically.
"""
import re
import secrets

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify


_DICE_RE = re.compile(r'^\s*(?:(\d*)d(\d+)|([+-]?\d+))(?:\s*([+-])\s*(\d+))?\s*$', re.I)


def canonical_key(value):
    """Normalize a resource identity while preserving namespace separators."""
    parts = []
    for part in str(value or '').strip().split(':'):
        normalized = slugify(part).replace('-', '_')
        if normalized:
            parts.append(normalized)
    return ':'.join(parts)


def _dice_value(expression, *, maximum=False):
    match = _DICE_RE.fullmatch(str(expression or '').strip())
    if not match:
        return None
    count, faces, literal, sign, extra = match.groups()
    if literal is not None:
        value = int(literal)
    else:
        count = int(count or 1)
        faces = int(faces)
        if count <= 0 or faces <= 0:
            return None
        value = count * faces if maximum else sum(
            secrets.randbelow(faces) + 1 for _ in range(count))
    if extra:
        value += int(extra) * (-1 if sign == '-' else 1)
    return max(0, value)


def _tag_parts(raw):
    """Parse the small `charges:` envelope without interpreting its mechanics."""
    text = str(raw or '').strip()
    match = re.match(r'^charges\s*:\s*', text)
    if not match:
        return None
    tail = text[match.end():].strip()
    depth = 0
    qualifier_at = None
    for index, char in enumerate(tail):
        if char == '(' and depth == 0:
            qualifier_at = index
            break
        if char in '{[':
            depth += 1
        elif char in '}]' and depth:
            depth -= 1
    if qualifier_at is None:
        expression, qualifier_text, suffix = tail, '', ''
    else:
        expression = tail[:qualifier_at].strip()
        end = qualifier_at + 1
        paren_depth = 1
        while end < len(tail) and paren_depth:
            paren_depth += (tail[end] == '(') - (tail[end] == ')')
            end += 1
        qualifier_text = tail[qualifier_at + 1:end - 1] if paren_depth == 0 else ''
        suffix = tail[end:].strip()
    if not suffix and expression.endswith('}') and '{' in expression:
        brace = expression.find('{')
        suffix, expression = expression[brace:], expression[:brace].strip()
    return expression.strip(), qualifier_text.strip(), suffix.strip()


def _qualifiers(text):
    values = {}
    flags = set()
    for part in (piece.strip() for piece in str(text or '').split(',')):
        if not part:
            continue
        if ':' in part:
            key, value = part.split(':', 1)
            values[canonical_key(key)] = value.strip()
        else:
            flags.add(canonical_key(part))
    return values, flags


def item_tags(item):
    """Return the stable possession snapshot plus catalog mechanics, deduplicated."""
    tags = []
    for source in (
            getattr(item, 'tags_json', None),
            getattr(getattr(item, 'id_item_mundano', None), 'tags_json', None),
            getattr(getattr(item, 'id_item_magico', None), 'tags_json', None)):
        for tag in source or ():
            text = str(tag)
            if text not in tags:
                tags.append(text)
    return tags


def item_charge_specs(item):
    """Compile every unconditional charge pool declared by an item instance."""
    specs = []
    charge_index = 0
    for tag in item_tags(item):
        parsed = _tag_parts(tag)
        if parsed is None:
            continue
        expression, qualifier_text, suffix = parsed
        values, flags = _qualifiers(qualifier_text)
        maximum = _dice_value(expression, maximum=True)
        runtime = bool(suffix and re.search(
            r'\b(?:per|requires|trigger|target)\s*:', suffix))
        if maximum is not None:
            specs.append({
                'index': charge_index,
                'maximum': maximum,
                'expression': expression,
                'reset': canonical_key(values.get('reset', '')),
                'recovery': values.get('amount', '').strip(),
                'destroy_on_zero': 'destroy_on_zero' in flags
                    or values.get('destroy_on_zero', '').lower() in {'1', 'true', 'yes'},
                'runtime': runtime,
                'raw': tag,
            })
        charge_index += 1
    return specs


def has_persistent_charges(item_or_catalog):
    """Whether an inventory item/catalog object declares a sheet-managed charge pool."""
    if hasattr(item_or_catalog, 'id_personagem_id'):
        return any(not spec['runtime'] for spec in item_charge_specs(item_or_catalog))

    class Adapter:
        tags_json = []
        id_item_mundano = None
        id_item_magico = None

    adapter = Adapter()
    adapter.tags_json = list(getattr(item_or_catalog, 'tags_json', None) or [])
    return any(not spec['runtime'] for spec in item_charge_specs(adapter))


def _resource_defaults(contract):
    return {
        'nome': str(contract.get('name') or contract['key'])[:100],
        'atual': int(contract.get('maximum') or 0),
        'maximo': int(contract.get('maximum') or 0),
        'origem': str(contract.get('origin') or '')[:180],
        'reset': canonical_key(contract.get('reset'))[:40],
        'recuperacao': str(contract.get('recovery') or '')[:80],
        'id_item': contract.get('item'),
    }


def preview_resource(personagem, contract):
    """Project the materialized balance without changing the resource ledger."""
    from types import SimpleNamespace
    from .models import TbPersonagemRecurso

    resources = TbPersonagemRecurso.objects.filter(id_personagem=personagem)
    resource = resources.filter(chave=canonical_key(contract['key'])).first()
    if resource is None and contract.get('legacy_name'):
        resource = resources.filter(chave='', nome=contract['legacy_name']).first()
    maximum = max(0, int(contract.get('maximum') or 0))
    spent = max(0, int(resource.maximo or 0) - int(resource.atual or 0)) if resource else 0
    return SimpleNamespace(pk=resource.pk if resource else None,
                           atual=max(0, min(maximum, maximum - spent)), maximo=maximum)


def preview_item_charges(personagem, inventory):
    contracts = []
    for item in inventory:
        for spec in item_charge_specs(item):
            if spec['runtime']:
                continue
            contract = _charge_contract(item, spec)
            resource = preview_resource(personagem, contract)
            contract.update(current=resource.atual, resource_id=resource.pk)
            contracts.append(contract)
    return contracts


def ensure_resource(personagem, contract, *, lock=False):
    """Create/update one resource while preserving the amount already spent."""
    from .models import TbPersonagem

    # Também serializa sincronizações feitas fora de um comando de consumo.
    with transaction.atomic():
        TbPersonagem.objects.select_for_update().only('pk').get(pk=personagem.pk)
        return _ensure_resource_locked(personagem, contract)


def _ensure_resource_locked(personagem, contract):
    from .models import TbPersonagemRecurso

    contract = dict(contract)
    contract['key'] = canonical_key(contract.get('key'))
    defaults = _resource_defaults(contract)
    queryset = TbPersonagemRecurso.objects.select_for_update()
    resource = queryset.filter(
        id_personagem=personagem, chave=contract['key']).first()
    if resource is None and contract.get('legacy_name'):
        resource = queryset.filter(
            id_personagem=personagem, chave='',
            nome=contract['legacy_name']).first()
    if resource is None:
        resource, created = TbPersonagemRecurso.objects.get_or_create(
            id_personagem=personagem, chave=contract['key'], defaults=defaults)
        if created:
            return resource

    old_max = int(resource.maximo or 0)
    spent = max(0, old_max - int(resource.atual or 0))
    new_max = int(defaults['maximo'])
    previous = (resource.chave, resource.atual, resource.maximo)
    resource.chave = contract['key']
    resource.nome = defaults['nome']
    resource.maximo = new_max
    resource.atual = max(0, min(new_max, new_max - spent))
    resource.origem = defaults['origem']
    resource.reset = defaults['reset']
    resource.recuperacao = defaults['recuperacao']
    resource.id_item = defaults['id_item']
    if previous != (resource.chave, resource.atual, resource.maximo):
        resource.versao += 1
    resource.save(update_fields=[
        'chave', 'nome', 'maximo', 'atual', 'origem', 'reset',
        'recuperacao', 'id_item', 'versao'])
    return resource


def _charge_contract(item, spec):
    suffix = '' if spec['index'] == 0 else ' %d' % (spec['index'] + 1)
    quantity = max(1, int(getattr(item, 'qtd', 1) or 1))
    return {
        'key': 'item:%s:charges:%s' % (item.pk, spec['index']),
        'name': 'Cargas%s' % suffix,
        # Itens mundanos com cargas podem ser empilhados. O ledger agrega os usos
        # das unidades da mesma linha sem confundir carga com ``qtd``.
        'maximum': spec['maximum'] * quantity,
        'reset': spec['reset'],
        'recovery': spec['recovery'],
        'origin': 'item:%s' % item.pk,
        'item': item,
        'destroy_on_zero': spec['destroy_on_zero'],
    }


def _sync_item_charges_locked(personagem, inventory=None):
    from .models import TbPersonagemRecurso

    full_inventory = inventory is None
    inventory = list(inventory if inventory is not None else
                     personagem.inventario.select_related(
                         'id_item_magico', 'id_item_mundano').all())
    contracts = []
    active_keys = set()
    for item in inventory:
        for spec in item_charge_specs(item):
            if spec['runtime']:
                continue
            contract = _charge_contract(item, spec)
            resource = ensure_resource(personagem, contract)
            contract.update({
                'current': max(0, min(int(resource.atual or 0), contract['maximum'])),
                'resource_id': resource.pk,
            })
            active_keys.add(contract['key'])
            contracts.append(contract)
    stale = TbPersonagemRecurso.objects.filter(
        id_personagem=personagem, id_item__isnull=False)
    if not full_inventory:
        stale = stale.filter(id_item_id__in=[item.pk for item in inventory])
    if active_keys:
        stale = stale.exclude(chave__in=active_keys)
    stale.delete()
    return contracts


def sync_item_charges(personagem, inventory=None):
    """Materialize charge contracts atomically for one character inventory."""
    from .models import TbPersonagem

    with transaction.atomic():
        TbPersonagem.objects.select_for_update().only('pk').get(pk=personagem.pk)
        return _sync_item_charges_locked(personagem, inventory)


def mutate_resource(personagem, contract, delta):
    """Apply a signed delta atomically and return a serializable snapshot."""
    from .models import TbPersonagemItem

    with transaction.atomic():
        from .models import TbPersonagem
        TbPersonagem.objects.select_for_update().only('pk').get(pk=personagem.pk)
        resource = ensure_resource(personagem, contract, lock=True)
        maximum = max(0, int(contract.get('maximum', resource.maximo) or 0))
        before = max(0, min(int(resource.atual or 0), maximum))
        after = max(0, min(maximum, before + int(delta)))
        resource.atual = after
        resource.maximo = maximum
        if after != before:
            resource.versao += 1
        resource.save(update_fields=['atual', 'maximo', 'versao'])
        destroyed = False
        item = contract.get('item')
        if after == 0 and contract.get('destroy_on_zero') and item is not None:
            destroyed = bool(TbPersonagemItem.objects.filter(pk=item.pk).delete()[0])
        return {
            'key': resource.chave, 'name': resource.nome,
            'before': before, 'current': after, 'maximum': maximum,
            'destroyed': destroyed,
        }


def contract_for_key(personagem, key, *, ruleset=None):
    """Rebuild the persistence contract for a materialized resource key."""
    from .models import TbPersonagemRecurso

    key = canonical_key(key)
    resource = TbPersonagemRecurso.objects.select_related('id_item').filter(
        id_personagem=personagem, chave=key).first()
    if resource is None:
        return None
    contract = {
        'key': resource.chave, 'name': resource.nome,
        'maximum': int(resource.maximo or 0), 'reset': resource.reset or '',
        'recovery': resource.recuperacao or '', 'origin': resource.origem or '',
        'item': resource.id_item,
    }
    if resource.id_item_id:
        item = resource.id_item
        if ruleset is not None:
            from .versioned_items import resolved_inventory
            item = resolved_inventory(ruleset, [item])[0]
        wanted = resource.chave.rsplit(':', 1)[-1]
        spec = next((row for row in item_charge_specs(item)
                     if str(row['index']) == wanted and not row['runtime']), None)
        contract['destroy_on_zero'] = bool(spec and spec['destroy_on_zero'])
    return contract


def spend_resource(personagem, contract, amount=1):
    """Consume an amount atomically, refusing the operation when insufficient."""
    from .models import TbPersonagem

    amount = max(0, int(amount or 0))
    with transaction.atomic():
        TbPersonagem.objects.select_for_update().only('pk').get(pk=personagem.pk)
        resource = ensure_resource(personagem, contract, lock=True)
        maximum = max(0, int(contract.get('maximum', resource.maximo) or 0))
        current = max(0, min(int(resource.atual or 0), maximum))
        if current < amount:
            return False, {
                'key': resource.chave, 'current': current, 'maximum': maximum}
        resource.atual = current - amount
        resource.maximo = maximum
        if amount:
            resource.versao += 1
        resource.save(update_fields=['atual', 'maximo', 'versao'])
        return True, {
            'key': resource.chave, 'current': resource.atual,
            'maximum': maximum, 'spent': amount}


def _event_matches(policy, event):
    policy, event = canonical_key(policy), canonical_key(event)
    if not policy or policy in {'none', 'manual'}:
        return False
    if policy in {'short_or_long', 'rest'}:
        return event in {'short_rest', 'long_rest'}
    if policy == 'day':
        return event in {'long_rest', 'dawn'}
    if policy in {'dawn', 'daily'}:
        return event == 'dawn'
    return policy == event


def reset_resources(personagem, event, *, ruleset=None):
    """Apply one declared reset event, including partial dice recovery."""
    from .models import TbPersonagem, TbPersonagemRecurso

    changed = []
    with transaction.atomic():
        TbPersonagem.objects.select_for_update().only('pk').get(pk=personagem.pk)
        inventory = None
        if ruleset is not None:
            from .versioned_items import resolved_inventory
            inventory = resolved_inventory(ruleset, personagem.inventario.all())
        _sync_item_charges_locked(personagem, inventory)
        rows = list(TbPersonagemRecurso.objects.select_for_update().filter(
            id_personagem=personagem))
        for resource in rows:
            if not _event_matches(resource.reset, event):
                continue
            amount = (_dice_value(resource.recuperacao)
                      if resource.recuperacao else int(resource.maximo or 0))
            if amount is None:
                continue
            before = int(resource.atual or 0)
            resource.atual = min(int(resource.maximo or 0), before + int(amount))
            if resource.atual != before:
                resource.versao += 1
            resource.save(update_fields=['atual', 'versao'])
            changed.append({
                'key': resource.chave, 'before': before,
                'current': resource.atual, 'maximum': resource.maximo})
    return changed


def item_resource_state(item):
    """Snapshot transferable with a concrete item instance."""
    resources = []
    for resource in item.recursos.order_by('chave'):
        resources.append({
            'suffix': resource.chave.rsplit(':', 1)[-1],
            'current': int(resource.atual or 0),
            'maximum': int(resource.maximo or 0),
            'reset': resource.reset or '',
            'recovery': resource.recuperacao or '',
        })
    return {'resources': resources} if resources else {}


def restore_item_resource_state(personagem, item, snapshot):
    contracts = sync_item_charges(personagem, [item])
    by_suffix = {
        str(row.get('suffix')): row
        for row in (snapshot or {}).get('resources', [])}
    for contract in contracts:
        saved = by_suffix.get(contract['key'].rsplit(':', 1)[-1])
        if saved is None:
            continue
        mutate_resource(
            personagem, contract,
            int(saved.get('current') or 0) - int(contract['current']))


def activate_state(personagem, key, *, origin='', payload=None, ends_on=None):
    """Activate or replace one persistent out-of-combat state."""
    from .models import TbPersonagemEstado

    state, _ = TbPersonagemEstado.objects.update_or_create(
        id_personagem=personagem, chave=canonical_key(key),
        defaults={
            'origem': str(origin or '')[:180],
            'payload_json': dict(payload or {}),
            'ends_on_json': list(dict.fromkeys(
                canonical_key(value) for value in (ends_on or []) if value)),
            'ativo': True,
            'encerrado_em': None,
        })
    return state


def end_state(personagem, key):
    from .models import TbPersonagemEstado

    return TbPersonagemEstado.objects.filter(
        id_personagem=personagem, chave=canonical_key(key), ativo=True).update(
            ativo=False, encerrado_em=timezone.now())


def end_states_on(personagem, event):
    """End states whose declarative lifecycle contains the supplied event."""
    event = canonical_key(event)
    ended = []
    for state in personagem.estados.filter(ativo=True):
        if event not in {canonical_key(value) for value in state.ends_on_json or []}:
            continue
        state.ativo = False
        state.encerrado_em = timezone.now()
        state.save(update_fields=['ativo', 'encerrado_em'])
        ended.append(state.chave)
    return ended
