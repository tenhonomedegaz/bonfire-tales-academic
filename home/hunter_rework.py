"""Preparation rules for the reworked Hunter; no mutation of legacy characters."""
import json
from pathlib import Path


def catalog():
    return json.loads((Path(__file__).parent / 'rules/hunter_rework.json').read_text(encoding='utf-8'))


def level_features(level, order=''):
    from django.utils.text import slugify
    data = json.loads((Path(__file__).parent / 'rules/hunter_content.json').read_text(encoding='utf-8'))
    return [feature for feature in data['features'] if feature['level'] <= int(level)
            and (not feature['order'] or slugify(feature['order']) == order)]


def prepare(*, level, ability, order='', selected=(), total_level=None, data=None,
            allow_pending_order=False):
    data = catalog() if data is None else data
    level = int(level)
    total_level = level if total_level is None else int(total_level)
    if not 1 <= level <= total_level <= 20:
        raise ValueError('Níveis devem estar entre 1 e 20; o total inclui o nível de Caçador.')
    if ability not in ('int', 'wis'):
        raise ValueError('Escolha Inteligência ou Sabedoria.')
    orders = {row['id']: row for row in data['orders']}
    if ((level >= 3 and order not in orders and not (allow_pending_order and not order))
            or (level < 3 and order)):
        raise ValueError('Escolha uma Ordem a partir do nível 3.')
    if allow_pending_order and not order and selected:
        raise ValueError('Escolha uma Ordem antes de preparar Segredos.')
    master = orders[order]['line'] if order else None
    proficiency = 2 + (total_level - 1) // 4
    selected = list(selected)
    if len(selected) != len(set(selected)):
        raise ValueError('Um Segredo não pode ser preparado duas vezes.')
    options = [dict(row, automatic=row['line'] == master,
                    selected=row['id'] in selected) for row in data['secrets'] if row['level'] <= level]
    optional = {row['id'] for row in options if not row['automatic']}
    if not set(selected) <= optional:
        raise ValueError('Seleção contém Segredo bloqueado, inexistente ou da Linha Mestra.')
    if len(selected) > proficiency:
        raise ValueError('O limite de Segredos preparados é o bônus de proficiência.')
    exclusive = [dict(row, automatic=True, selected=False)
                 for row in data.get('exclusive_secrets', [])
                 if row['order'] == order and row['level'] <= level]
    return dict(level=level, total_level=total_level, ability=ability, order=order,
                master=master, proficiency=proficiency, points=level if level >= 2 else 0,
                progression=data['progression'][level - 1], options=options,
                spell_grants=[dict(g) for g in data.get('spell_grants', [])
                              if g['level'] <= level and g['order'] in ('', order)],
                exclusive=exclusive,
                available=[row for row in options if row['automatic'] or row['selected']] + exclusive,
                selected=selected, mark_limit=2 if level >= 17 else 1,
                mark_dispel_level=min(9, level // 2))


def secret_cost(preparation, secret_id, *, enhanced=False):
    secret = next((row for row in preparation['available'] if row['id'] == secret_id), None)
    if secret is None:
        raise ValueError('Prepare ou desbloqueie este Segredo antes de usá-lo.')
    if enhanced and not secret['enhancement']:
        raise ValueError('Este Segredo não possui Aprimoramento.')
    return secret['cost'] + int(enhanced)
