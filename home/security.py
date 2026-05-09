import json
import re

from django.core.exceptions import ValidationError


SQL_DANGER_PATTERNS = (
    re.compile(r"\b(drop|truncate)\s+(table|database|schema|collection)\b", re.IGNORECASE),
    re.compile(r"\balter\s+table\b", re.IGNORECASE),
    re.compile(r"\bdelete\s+from\b", re.IGNORECASE),
    re.compile(r"\binsert\s+into\b", re.IGNORECASE),
    re.compile(r"\bupdate\s+[A-Za-z0-9_\"`\[\].]+\s+set\b", re.IGNORECASE),
    re.compile(r"\bunion\s+select\b", re.IGNORECASE),
    re.compile(r"\bexec(?:ute)?\s*\(", re.IGNORECASE),
    re.compile(r"\bsp_executesql\b", re.IGNORECASE),
)


def find_sql_danger(value, path="texto"):
    if value is None:
        return []
    if isinstance(value, str):
        return [
            f"{path}: contem comando SQL bloqueado ({pattern.pattern})"
            for pattern in SQL_DANGER_PATTERNS
            if pattern.search(value)
        ]
    if isinstance(value, dict):
        errors = []
        for key, item in value.items():
            errors.extend(find_sql_danger(item, f"{path}.{key}"))
        return errors
    if isinstance(value, (list, tuple, set)):
        errors = []
        for index, item in enumerate(value, start=1):
            errors.extend(find_sql_danger(item, f"{path}[{index}]"))
        return errors
    return []


def validate_no_sql_danger(value, path="texto"):
    errors = find_sql_danger(value, path)
    if errors:
        raise ValidationError("Entrada bloqueada por conter comando SQL potencialmente destrutivo.")


def validate_json_no_sql_danger(value, path="documento"):
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return
    validate_no_sql_danger(data, path)
