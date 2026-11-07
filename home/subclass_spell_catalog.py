"""Reviewable data-to-tag planning; never reads/writes a configured database."""
import re
import unicodedata
from collections import defaultdict
import hashlib
import json


def identity_name(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(text.replace('\u2019', "'").replace('\u2018', "'").casefold().split())


def _unique_index(rows, field):
    index = defaultdict(list)
    for row in rows:
        if row.get(field):
            index[identity_name(row[field])].append(row)
    return index


def spell_grant_tag(slug, class_level):
    """Existing generic grant DSL; never a per-spell runtime implementation."""
    if not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9_-]{1,220}', slug):
        raise ValueError('Invalid canonical spell slug')
    if type(class_level) is not int or not 1 <= class_level <= 20:
        raise ValueError('Invalid source class level')
    mechanical_name = slug.replace('-', '_')
    return f'spell_selection:{mechanical_name}{{always_prepared, extra, requires:lvl{{{class_level}}}}}'


def grant_tags(entries, *, choice_kind=None, existing=()):
    """Build generic tags from already resolved data, keeping variants exclusive."""
    tags=list(existing)
    variants=sorted({row['variant'] for row in entries if row.get('variant')})
    if variants:
        if not choice_kind or not re.fullmatch(r'[a-z][a-z0-9_]{0,59}',choice_kind):
            raise ValueError('A reviewed choice binding is required for variants')
        values={value:identity_name(value).replace(' ','_') for value in variants}
        if any(not re.fullmatch(r'[a-z0-9_]+',v) for v in values.values()):
            raise ValueError('Invalid variant choice value')
        if not any(re.search(r'\bpick:'+re.escape(choice_kind)+r':',tag) for tag in tags):
            tags.append(f'pick:{choice_kind}:1('+'|'.join(values.values())+')')
    for row in entries:
        tag=row['tag']
        if row.get('variant'):
            tag=f"match(pick:{choice_kind}){{{values[row['variant']]}:{{{tag}}}}}"
        if tag not in tags:
            tags.append(tag)
    return tags


def build_definitions(resolution, *, bindings=None):
    """Portable content package with no database PKs and no runtime dispatch."""
    bindings=bindings or {}
    grouped=defaultdict(list)
    for row in resolution['resolved']:
        grouped[(row['class'],row['subclass'])].append(row)
    out=[]
    for (class_name,subclass_name),rows in sorted(grouped.items()):
        key=class_name+'/'+subclass_name
        binding=bindings.get(key,{})
        out.append({'class':class_name,'subclass':subclass_name,
                    'subclass_slug_override':binding.get('subclass_slug'),
                    'source_feature_hint':binding.get('feature_name'),
                    'niveladquirido':min(row['class_level'] for row in rows),
                    'tags_json':grant_tags(rows,choice_kind=binding.get('choice_kind')),
                    'resolved_occurrences':len(rows),
                    'pending_spells':[row for row in resolution['pending']
                                      if (row['class'],row['subclass'])==(class_name,subclass_name)]})
    return {'schema':1,'status':'prepared_not_applied','definitions':out,
            'counts':{'subclasses':len(out),**resolution['counts']}}


def resolve_spells(manifest, catalog, *, overrides=None):
    """Match explicit identities only; ambiguous/missing names remain review items.

    Overrides are reviewed DATA mapping a supplied English name to canonical slug.
    Display translations alone never authorize replacing an English identity.
    """
    english = _unique_index(catalog, 'nome_ingles')
    slugs = _unique_index(catalog, 'slug')
    overrides = {identity_name(key): value for key, value in (overrides or {}).items()}
    resolved, pending = [], []
    for occurrence in manifest['entries']:
        row = dict(occurrence)
        override = overrides.get(identity_name(row['english_name']))
        matches = slugs.get(identity_name(override['slug']), []) if override else english.get(identity_name(row['english_name']), [])
        if len(matches) != 1:
            pending.append({**row, 'reason': 'ambiguous_identity' if matches else 'missing_identity',
                            'candidates': [m['slug'] for m in matches]})
            continue
        spell = matches[0]
        if override and spell['nivel'] != override['level']:
            pending.append({**row, 'reason': 'override_level_conflict', 'candidate': spell['slug']})
            continue
        if ('spell_level' in row and row['spell_level'] != spell['nivel']):
            pending.append({**row, 'reason': 'spell_level_conflict', 'candidate': spell['slug'],
                            'catalog_level': spell['nivel']})
            continue
        resolved.append({**row, 'spell_pk': spell['id_magia'], 'spell_slug': spell['slug'],
                         'catalog_name': spell['nome'], 'catalog_level': spell['nivel'],
                         'tag': spell_grant_tag(spell['slug'], row['class_level'])})
    return {'schema': 1, 'resolved': resolved, 'pending': pending,
            'counts': {'total': len(manifest['entries']), 'resolved': len(resolved), 'pending': len(pending)}}


def build_tag_plan(resolution, classes, subclasses, features, *, bindings=None):
    """Plan targeted tag updates by natural identities; never trust foreign PKs.

    Catalog inputs are explicit source rows, not a claim about pinned revisions.
    Feature selection requires spell names in the supplied description or an
    explicit reviewed feature binding, not a subclass-name runtime dispatch.
    """
    bindings = bindings or {}
    grouped = defaultdict(list)
    for row in resolution['resolved']:
        grouped[(row['class'], row['subclass'])].append(row)
    class_index = _unique_index(classes, 'nome')
    plans, pending = [], []
    for (class_name, subclass_name), entries in sorted(grouped.items()):
        key = class_name + '/' + subclass_name
        binding = bindings.get(key, {})
        class_rows = class_index.get(identity_name(class_name), [])
        if len(class_rows) != 1:
            pending.append({'source': key, 'reason': 'class_identity_missing_or_ambiguous'})
            continue
        classe = class_rows[0]
        eligible = [s for s in subclasses if s['id_classe'] == classe['id_classe']]
        desired = identity_name(binding.get('subclass_slug', subclass_name))
        matches = [s for s in eligible if desired in (identity_name(s['slug']),identity_name(s['nome']))]
        if not matches and not binding.get('subclass_slug'):
            matches = [s for s in eligible if identity_name(s['nome']).endswith(' ' + desired)]
        if len(matches) != 1:
            pending.append({'source':key,'reason':'subclass_identity_missing_or_ambiguous'})
            continue
        subclass = matches[0]
        candidates = [f for f in features if f['id_subclasse'] == subclass['id_subclasse']
                      and f['id_classe'] == classe['id_classe'] and not f.get('table_only')
                      and f['niveladquirido'] <= min(row['class_level'] for row in entries)]
        if binding.get('feature_name'):
            candidates = [f for f in candidates if f['nome'] == binding['feature_name']]
            if not candidates:
                pending.append({'source':key,'reason':'reviewed_feature_binding_not_found'})
                continue
        else:
            names = {identity_name(row['english_name']) for row in entries}
            scores = [(len(names & {identity_name(n) for n in re.findall(r'\[([^\]]+)\]',f.get('descricao') or '')}), f)
                      for f in candidates]
            best = max((score for score,_ in scores),default=0)
            candidates = [f for score,f in scores if best >= 2 and score == best]
            if not candidates:
                # Editorial sources often omit their table. Reuse only a unique
                # spell-source card, otherwise plan a separate explicit data row.
                candidates = [f for f in features if f['id_subclasse'] == subclass['id_subclasse']
                              and f['id_classe'] == classe['id_classe']
                              and f['niveladquirido'] <= min(row['class_level'] for row in entries)
                              and re.match(r'^magias?\b',identity_name(f['nome']))]
        if len(candidates) > 1:
            pending.append({'source':key,'reason':'grant_feature_missing_or_ambiguous'})
            continue
        feature = candidates[0] if candidates else {
            'id_habilidade':None,'nome':'Magias de ' + subclass['nome'], 'tags_json':[],
            'niveladquirido':min(row['class_level'] for row in entries)}
        variants = sorted({row['variant'] for row in entries if row.get('variant')})
        choice_kind = binding.get('choice_kind')
        if variants and not choice_kind:
            pending.append({'source':key,'reason':'variant_choice_binding_required','variants':variants})
            continue
        before = feature.get('tags_json') or []
        replacements = binding.get('replace_tags', [])
        if (not isinstance(replacements, list)
                or any(not isinstance(tag, str) or not tag.startswith('spell_selection:')
                       for tag in replacements)):
            raise ValueError('Only explicitly reviewed spell-selection tags may be replaced')
        removed = [tag for tag in before if tag in replacements]
        after = grant_tags(entries,choice_kind=choice_kind,
                           existing=[tag for tag in before if tag not in removed])
        description = None
        if feature['id_habilidade'] is None:
            description = ('Voce tem sempre preparadas as magias abaixo. Elas nao contam '
                           'contra o numero de magias que pode preparar. Use seu nivel nesta classe.\n\n'
                           '| Nivel de classe | Variante | Magia |\n| --- | --- | --- |\n')
            description += '\n'.join(f"| {row['class_level']} | {row.get('variant') or 'Universal'} | "
                                      f"[{row['catalog_name']}](tbMagia, {row['spell_slug']}) [{row['english_name']}] |"
                                      for row in entries)
        plans.append({'action':'update' if feature['id_habilidade'] is not None else 'create',
                      'class_slug':classe['slug'],'subclass_slug':subclass['slug'],
                      'feature_name':feature['nome'],'source':key,
                      'niveladquirido':feature['niveladquirido'],
                      'create_description':description,
                      'source_pk_advisory_only':feature['id_habilidade'],
                      'before_tags_sha256':hashlib.sha256(json.dumps(before,ensure_ascii=False,
                                                                   separators=(',',':')).encode()).hexdigest(),
                      'before_tags':before,'removed_tags':removed,'tags_json':after,
                      'resolved_occurrences':len(entries),'variant_choice':choice_kind})
    return {'schema':1,'status':'draft_not_applied','scope':'source_rows_not_published_rulesets',
            'updates':plans,'pending_targets':pending,'pending_spells':resolution['pending'],
            'counts':{'updates':len(plans),'pending_targets':len(pending),
                      'resolved_occurrences':sum(p['resolved_occurrences'] for p in plans)}}
