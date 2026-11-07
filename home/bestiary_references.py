"""Protect catalog creatures used by mechanical bestiary references."""

from django.apps import apps
from django.db.models import JSONField, TextField
from django.db.models.functions import Cast

from .bestiary_audit import (STATIC_REF, _mechanical_tags,
                             bestiary_references as parse_bestiary_references,
                             normalized_slug)


def has_inbound_bestiary_reference(slug):
    """Return whether a static summon tag targets this creature or a slug alias."""
    target = normalized_slug(slug)
    for model in apps.get_models():
        for field in model._meta.fields:
            if not isinstance(field, JSONField) or field.name not in ('tags_json', 'statblock_json'):
                continue
            candidates = model.objects.annotate(
                _bestiary_text=Cast(field.name, TextField())
            ).filter(_bestiary_text__icontains='bestiary').values_list(field.name, flat=True)
            for value in candidates.iterator(chunk_size=200):
                tags = value if field.name == 'tags_json' and isinstance(value, list) else []
                if field.name == 'statblock_json':
                    tags = (tag for _, tag in _mechanical_tags(value))
                for tag in tags:
                    if not isinstance(tag, str):
                        continue
                    for reference in parse_bestiary_references(tag):
                        reference = reference.strip()
                        if STATIC_REF.fullmatch(reference) and normalized_slug(reference) == target:
                            return True
    return False
