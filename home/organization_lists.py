"""Typed organization relationships shared by editors and the public catalog."""

import json
import re


def organization_list(value, *, strict=False):
    if value in (None, ''):
        return []
    for _ in range(3):
        if not isinstance(value, str):
            break
        value = value.strip()
        if not value:
            return []
        # Raw PostgreSQL cursors expose JSON strings as encoded literals.
        if value.startswith(('[', '{', '"')):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                if strict:
                    raise ValueError('Informe uma lista JSON válida.') from exc
                return []
        else:
            value = re.split(r'[,;/\n]+', value)
            break
    if not isinstance(value, (list, tuple, set)):
        if strict:
            raise ValueError('Informe uma lista de nomes.')
        return []
    if strict and any(not isinstance(item, str) for item in value):
        raise ValueError('Cada vínculo deve ser um texto.')
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
