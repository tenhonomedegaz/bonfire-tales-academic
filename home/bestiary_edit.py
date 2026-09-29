"""Lossless updates for the small, form-editable part of a creature statblock."""

from copy import deepcopy
from hashlib import sha256
import json


class UnsafeBestiaryEdit(ValueError):
    pass


def edit_token(creature):
    state = {
        key: getattr(creature, key)
        for key in ('nome', 'tipo', 'tamanho', 'nd', 'alinhamento', 'ca', 'pv',
                    'descricao_markdown', 'imagem_url', 'comunidade')
    }
    state['statblock_json'] = creature.statblock_json
    return sha256(json.dumps(state, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def merge_statblock(original, before, submitted, parse_blocks):
    """Change only fields the form actually changed; retain every other imported key."""
    sb = deepcopy(original if isinstance(original, dict) else {})
    modern = 'traits' in sb or 'actions' in sb

    def changed(field):
        return str(submitted.get(field, '')).strip() != str(before.get(field, '')).strip()

    def put(field, key, value):
        if changed(field):
            sb[key] = value

    put('nome', 'name', submitted.get('nome', '').strip())
    if changed('tipo'):
        if isinstance(sb.get('type'), dict):
            sb['type']['type'] = submitted.get('tipo', '').strip()
        else:
            sb['type'] = submitted.get('tipo', '').strip()
    if changed('tamanho'):
        value = submitted.get('tamanho', '').strip()
        sb['size'] = value if modern else [value]
    if changed('alinhamento'):
        value = submitted.get('alinhamento', '').strip()
        sb['alignment'] = value if modern else [value]
    put('nd', 'cr', submitted.get('nd', '').strip())
    for field, key in (('ca', 'ac'), ('pv', 'hp'), ('desloc_ft', 'speed')):
        if not changed(field):
            continue
        value = submitted.get(field, '').strip()
        if not value:
            raise UnsafeBestiaryEdit(f'{field.upper()} não pode ficar vazio.')
        if field == 'ca':
            if isinstance(sb.get(key), list):
                if not value.isdecimal():
                    raise UnsafeBestiaryEdit('CA estruturada requer um número inteiro.')
                sb[key][0]['ac'] = int(value)
            else:
                sb[key] = int(value) if value.isdecimal() else value
        elif field == 'pv':
            if isinstance(sb.get(key), dict):
                if not value.isdecimal():
                    raise UnsafeBestiaryEdit('PV estruturado requer um número inteiro.')
                sb[key]['average'] = int(value)
            else:
                sb[key] = int(value) if value.isdecimal() else value
        elif isinstance(sb.get(key), dict):
            if not value.isdecimal():
                raise UnsafeBestiaryEdit('Deslocamento estruturado requer um número inteiro.')
            sb[key]['walk'] = int(value)
        else:
            sb[key] = int(value) if value.isdecimal() else value
    for field in ('str', 'dex', 'con', 'int', 'wis', 'cha', 'passivo'):
        if changed(field):
            value = submitted.get(field, '').strip()
            if value and not value.isdecimal():
                raise UnsafeBestiaryEdit(f'{field.upper()} requer um número inteiro.')
            if value:
                sb['passive' if field == 'passivo' else field] = int(value)
            elif field == 'passivo':
                sb.pop('passive', None)
    for field, key in (('idiomas', 'languages'), ('sentidos', 'senses')):
        if changed(field):
            sb[key] = [part.strip() for part in submitted.get(field, '').split(',') if part.strip()]
    for field, key in (('tracos', 'traits' if modern else 'trait'),
                       ('acoes', 'actions' if modern else 'action')):
        if not changed(field):
            continue
        if any(line.count('|') > 2 for line in submitted.get(field, '').splitlines()):
            raise UnsafeBestiaryEdit('Uma habilidade contém separadores extras.')
        parsed = parse_blocks(submitted.get(field, ''))
        previous = sb.get(key) or []
        if not isinstance(previous, list):
            raise UnsafeBestiaryEdit('Lista de habilidades não editável neste formulário.')
        updated = []
        for index, feature in enumerate(parsed):
            if not feature.get('name'):
                raise UnsafeBestiaryEdit('Cada habilidade precisa de nome.')
            if index < len(previous):
                old = previous[index]
                if not isinstance(old, dict) or old.get('name') != feature['name']:
                    raise UnsafeBestiaryEdit('Reordenação ou renomeação de habilidade importada exige revisão específica.')
                if any(not isinstance(entry, str) for entry in old.get('entries', [])):
                    raise UnsafeBestiaryEdit('Habilidade estruturada exige revisão específica.')
                item = deepcopy(old)
                item['entries'] = feature['entries']
                tag_key = 'tags_json' if 'tags_json' in item else 'tags'
                if 'tags' in feature:
                    item[tag_key] = feature['tags']
                else:
                    item.pop(tag_key, None)
                updated.append(item)
            else:
                updated.append(feature)
        sb[key] = updated
    return sb
