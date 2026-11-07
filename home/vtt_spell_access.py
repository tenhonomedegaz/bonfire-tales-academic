"""Read-only spell access transport, not a casting or preparation authorizer.

Persisted rows are character state; spell identity/metadata come exclusively from
the linked sealed catalog, or the current catalog for a genuinely unpinned sheet.
No class-list expansion, synchronization, view imports, or character writes.
"""
from copy import deepcopy
import json


def _ruleset_from_links(bindings, profiles):
    links = list(bindings) + list(profiles)
    if len({link.ruleset_id for link in links}) > 1:
        raise ValueError('Conflicting linked spell revisions.')
    return links[0].ruleset if links else None


def _read_ruleset(personagem):
    from .models import TbPersonagemCacador
    bindings = personagem.classes.exclude(ruleset__isnull=True).select_related('ruleset')
    profiles = TbPersonagemCacador.objects.filter(
        personagem_classe__id_personagem=personagem).select_related('ruleset')
    return _ruleset_from_links(bindings, profiles)


def _read_owned(personagem):
    return list(personagem.magias.order_by('id').values(
        'id', 'id_magia_id', 'preparada', 'sempre_preparada', 'origem'))


def _read_grants(personagem, ruleset):
    from .character_engine import magias_concedidas
    data = deepcopy(magias_concedidas(personagem, ruleset=ruleset))
    # The canonical reader's concrete grants are always prepared by the sheet's
    # established synchronization contract. Mirror that fact without syncing.
    for grant in data['concedidas']:
        grant['sempre_preparada'] = True
    return data


def _read_catalog(ruleset, owned, grants):
    if ruleset is not None:
        from .versioned_spells import spell_catalog
        return spell_catalog(ruleset)
    from django.db.models import Q
    from .models import TbMagia
    ids = [row.get('id_magia_id') for row in owned if isinstance(row, dict)]
    slugs = [row.get('slug') for row in grants if isinstance(row, dict)]
    return {spell.pk: spell for spell in TbMagia.objects.filter(
        Q(pk__in=[pk for pk in ids if type(pk) is int and pk > 0]) |
        Q(slug__in=[slug for slug in slugs if isinstance(slug, str) and slug]))}


def _catalog_source(ruleset):
    if ruleset is None:
        return {'tipo': 'atual', 'identidade': 'spell-catalog'}
    checksum = ruleset.manifest.get('spell-catalog')
    if not (type(ruleset.pk) is int and ruleset.pk > 0 and
            isinstance(checksum, str) and checksum and
            isinstance(ruleset.checksum, str) and ruleset.checksum):
        raise ValueError('Pinned spell catalog provenance unavailable.')
    return {'tipo': 'fixado', 'identidade': 'spell-catalog',
            'ruleset_pk': ruleset.pk, 'ruleset_checksum': ruleset.checksum,
            'revisao': checksum}


def _empty(catalog_source=None, warnings=()):
    return {'schema': 1, 'catalogo': deepcopy(catalog_source), 'magias': [],
            'conjuracao_automatica': False, 'avisos': sorted(set(warnings))}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _flag(values):
    # Unknown is not false. An explicit true does establish this aggregate fact.
    if any(value is True for value in values):
        return True
    return None if any(value is None for value in values) else False


def project_spell_access(owned, grants, catalog, *, catalog_source):
    """Pure union of actual rows and resolved grants; never copy the class pool.

    Arbitrary grant inputs may supply an explicit bool `sempre_preparada` (or
    `always_prepared`). Inputs supplying only slug/nivel/fonte prove
    the specific grant, but its preparation semantics remain null with a warning.
    `fontes` retains each persisted row and each named active grant independently.
    Tags are opaque transported data and must not enter actor-wide passive rules.
    """
    result = _empty(catalog_source)
    warnings = []
    by_pk, by_slug, collisions = {}, {}, set()
    for pk, spell in catalog.items():
        slug = getattr(spell, 'slug', None)
        level = getattr(spell, 'nivel', None)
        if (type(pk) is not int or pk <= 0 or getattr(spell, 'pk', None) != pk or
                not _text(slug) or slug != slug.strip() or
                not _text(getattr(spell, 'nome', None)) or
                type(level) is not int or not 0 <= level <= 9):
            warnings.append('Spell access: invalid catalog identity omitted.')
            continue
        by_pk[pk] = spell
        if slug in by_slug:
            collisions.add(slug)
        by_slug[slug] = spell
    for slug in collisions:
        warnings.append('Spell access: ambiguous catalog slug omitted: ' + slug)
        by_slug.pop(slug, None)
    selected = {}

    def add(spell, source):
        if spell.slug in collisions:
            return
        if spell.pk not in selected:
            selected[spell.pk] = {
                'magia_pk': spell.pk, 'slug': spell.slug, 'nome': spell.nome,
                'circulo': spell.nivel, 'fontes': [],
            }
            tags = getattr(spell, 'tags_json', None)
            valid_tags = (isinstance(tags, list) and len(tags) <= 128 and
                          all(isinstance(tag, str) and tag.strip() and len(tag) <= 4096
                              for tag in tags) and
                          sum(len(tag.encode('utf-8')) for tag in tags) <= 65536)
            selected[spell.pk]['tags_disponiveis'] = valid_tags
            if valid_tags:
                selected[spell.pk]['tags'] = deepcopy(tags)
            else:
                warnings.append('Spell access: unavailable tags for spell PK %s.' % spell.pk)
        if source not in selected[spell.pk]['fontes']:
            selected[spell.pk]['fontes'].append(source)

    for row in owned:
        if (not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0 or
                type(row.get('id_magia_id')) is not int):
            warnings.append('Spell access: persisted spell without canonical identity omitted.')
            continue
        spell = by_pk.get(row['id_magia_id'])
        if spell is None:
            warnings.append('Spell access: persisted row %s absent from selected catalog.' % row['id'])
            continue
        if any(type(row.get(key)) is not bool for key in ('preparada', 'sempre_preparada')):
            warnings.append('Spell access: invalid persisted preparation in row %s.' % row['id'])
            continue
        origin = row.get('origem')
        if not _text(origin):
            origin = None
            warnings.append('Spell access: persisted row %s has no named origin; row identity retained.' % row['id'])
        add(spell, {'tipo': 'persistida', 'id_fonte': 'TbPersonagemMagia:%s' % row['id'],
                    'origem': origin, 'preparada': row['preparada'],
                    'sempre_preparada': row['sempre_preparada']})

    for grant in grants:
        if (not isinstance(grant, dict) or not _text(grant.get('slug')) or
                not _text(grant.get('fonte'))):
            warnings.append('Spell access: grant without identity or named source omitted.')
            continue
        spell = by_slug.get(grant['slug'])
        if spell is None:
            warnings.append('Spell access: granted spell absent or ambiguous in selected catalog: ' + grant['slug'])
            continue
        if type(grant.get('nivel')) is not int or grant['nivel'] != spell.nivel:
            warnings.append('Spell access: grant level differs from selected catalog: ' + grant['slug'])
            continue
        always = grant.get('sempre_preparada', grant.get('always_prepared'))
        if type(always) is not bool:
            always = None
            warnings.append('Spell access: grant preparation semantics unavailable: ' + grant['slug'])
        add(spell, {'tipo': 'concedida', 'fonte': grant['fonte'],
                    'sempre_preparada': always})

    for pk in sorted(selected):
        entry = selected[pk]
        entry['fontes'].sort(key=lambda source: json.dumps(source, sort_keys=True))
        entry['persistida'] = any(source['tipo'] == 'persistida' for source in entry['fontes'])
        entry['concedida'] = any(source['tipo'] == 'concedida' for source in entry['fontes'])
        entry['sempre_preparada'] = _flag([source['sempre_preparada'] for source in entry['fontes']])
        preparation = [source['preparada'] for source in entry['fontes'] if source['tipo'] == 'persistida']
        if entry['sempre_preparada'] is True:
            preparation.append(True)
        elif entry['concedida']:
            preparation.append(None)
        entry['preparada'] = _flag(preparation)
        result['magias'].append(entry)
    result['avisos'] = sorted(set(warnings))
    return result


def effective_spell_access(personagem):
    """Read adapters fail closed; a pinned failure never falls back to live spells."""
    try:
        ruleset = _read_ruleset(personagem)
        source = _catalog_source(ruleset)
    except Exception:
        return _empty(warnings=['Spell access unavailable: linked revision or catalog provenance could not be resolved.'])
    warnings = []
    try:
        owned = _read_owned(personagem)
    except Exception:
        owned = []
        warnings.append('Spell access partial: persisted spells unavailable.')
    try:
        data = _read_grants(personagem, ruleset)
        grants = data['concedidas']
        if not isinstance(grants, list):
            raise ValueError('Invalid granted spells.')
        if data.get('pendentes'):
            warnings.append('Spell access partial: pending spell choices are not granted.')
        if isinstance(data.get('avisos'), list):
            warnings.extend(warning for warning in data['avisos'] if _text(warning))
    except Exception:
        grants = []
        warnings.append('Spell access partial: active grants unavailable.')
    try:
        catalog = _read_catalog(ruleset, owned, grants)
        result = project_spell_access(owned, grants, catalog, catalog_source=source)
    except Exception:
        result = _empty(source, ['Spell access unavailable: selected catalog could not be projected; no current-catalog fallback.'])
    result['avisos'] = sorted(set(result['avisos'] + warnings))
    return result
