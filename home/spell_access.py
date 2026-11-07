"""Acesso base de magias por classe, com slugs como fonte mecânica."""
from __future__ import annotations

import re
import unicodedata

from django.db.models import Q


def access_key(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = value.encode('ascii', 'ignore').decode('ascii').lower().strip()
    return re.sub(r'[^a-z0-9]+', '-', value).strip('-')


def _class_maps(classes=None):
    if classes is None:
        from .models import TbClasse
        classes = TbClasse.objects.all()
    by_key = {}
    by_slug = {}
    for classe in classes:
        by_slug[classe.slug] = classe
        by_key[access_key(classe.slug)] = classe
        by_key[access_key(classe.nome)] = classe
    return by_key, by_slug


def spell_class_slugs(spell, *, classes=None):
    """Lista exata de slugs; lê o texto legado apenas quando ainda não migrado."""
    by_key, by_slug = _class_maps(classes)
    out = []
    for raw in getattr(spell, 'classes_slugs', None) or []:
        classe = by_slug.get(str(raw).strip()) or by_key.get(access_key(raw))
        if classe and classe.slug not in out:
            out.append(classe.slug)
    if out:
        return out
    for raw in re.split(r'[,;|]', getattr(spell, 'classes', '') or ''):
        classe = by_key.get(access_key(raw))
        if classe and classe.slug not in out:
            out.append(classe.slug)
    return out


def spell_class_objects(spell, *, classes=None):
    classes = list(classes) if classes is not None else None
    _by_key, by_slug = _class_maps(classes)
    return [by_slug[slug] for slug in spell_class_slugs(spell, classes=classes)
            if slug in by_slug]


def spell_class_names(spell, *, classes=None):
    return [classe.nome for classe in spell_class_objects(spell, classes=classes)]


def set_spell_class_access(spell, classes, *, save=False):
    """Grava slugs validados e mantém o texto apenas como espelho editorial."""
    clean = []
    seen = set()
    for classe in classes or ():
        if classe.slug in seen:
            continue
        seen.add(classe.slug)
        clean.append(classe)
    spell.classes_slugs = [classe.slug for classe in clean]
    spell.classes = ', '.join(classe.nome for classe in clean)
    if save:
        spell.save(update_fields=['classes_slugs', 'classes'])
    return spell


def class_scopes(scopes):
    """Resolve nomes ou slugs declarados pelo contrato para classes válidas."""
    by_key, _by_slug = _class_maps()
    out = []
    for raw in scopes or ():
        classe = by_key.get(access_key(raw))
        if classe and classe.slug not in out:
            out.append(classe.slug)
    return out


def spell_class_query(scopes):
    """Q de acesso exato, sem confundir slugs que sejam prefixos entre si."""
    from django.db import connection

    from .models import TbMagia

    wanted = set(class_scopes(scopes))
    if not wanted:
        return Q(pk__in=[])

    # JSON containment é exato e indexável no PostgreSQL. O SQLite de reserva
    # não implementa esse lookup; nele o catálogo pequeno é resolvido em Python.
    if connection.vendor != 'postgresql':
        ids = [
            spell.pk for spell in TbMagia.objects.all().only(
                'id_magia', 'classes', 'classes_slugs')
            if wanted & set(spell_class_slugs(spell))
        ]
        return Q(pk__in=ids)

    q = Q(pk__in=[])
    for slug in wanted:
        q |= Q(classes_slugs__contains=[slug])

    # Compatibilidade defensiva para uma linha criada por integração antiga
    # depois da migração, ainda com apenas o espelho editorial preenchido.
    legacy_ids = [
        spell.pk for spell in TbMagia.objects.filter(classes_slugs=[]).only(
            'id_magia', 'classes', 'classes_slugs')
        if wanted & set(spell_class_slugs(spell))
    ]
    if legacy_ids:
        q |= Q(pk__in=legacy_ids)
    return q


def spell_has_base_access(spell, scopes):
    wanted = set(class_scopes(scopes))
    return bool(wanted & set(spell_class_slugs(spell)))
