"""Compose reviewed Hunter replacements without editing live class rows."""
from copy import deepcopy
import json
from pathlib import Path

from django.db import transaction
from django.utils.text import slugify
from .content_versions import create_revision, resolve_content, seal_ruleset
from .models import TbClasse, TbClassehabilidade, TbRecursoclasse, TbSubclasse
from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog, _fields

CHOICE_SOURCES = {
    'preparation': '018-nivel-2-preparos-de-cacada',
    'expertise': '125-nivel-3-instinto-de-cacador',
}
PASSIVE_SOURCES = {
    'extra_attack': '127-nivel-5-ataque-extra',
    'relentless': '146-nivel-7-cacador-implacavel',
    'sharp_instinct': '148-nivel-9-instinto-afiado',
    'unshakable_will': '189-nivel-15-vontade-inabalavel',
    'predatory_instinct': '191-nivel-17-instinto-predatorio',
}
CONDITIONAL_SOURCES = {
    'favored': '072-nivel-2-inimigo-favorito',
    'territory': '128-nivel-5-territorio-de-caca',
    'predator': '168-nivel-11-predador-astuto',
    'hide': '170-nivel-13-passos-invisiveis',
    'domination': '210-nivel-20-dominio-da-cacada',
}


@transaction.atomic
def compose_class_basics_revision(ruleset, *, class_id, author=None):
    """Publish the HTML's Hunter multiclass basics without changing legacy rows."""
    catalog = VersionedClassCatalog(ruleset, class_id)
    if catalog.classe.slug != 'cacador':
        raise ValueError('Class basics require a Hunter snapshot.')
    identity = 'class-catalog:%s' % class_id
    payload = deepcopy(resolve_content(ruleset, identity, evaluator_version=EVALUATOR,
                                       vocabulary_version=VOCABULARY))
    rework = resolve_content(ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                             vocabulary_version=VOCABULARY)
    reference = json.loads((Path(__file__).parent / 'rules/hunter_rework.json').read_text(encoding='utf-8'))
    if rework.get('source_sha256') != reference['source_sha256']:
        raise ValueError('Hunter basics source differs from the sealed reference.')
    row = payload['collections'][TbClasse._meta.label_lower][0]
    old_req = 'multiclass_req{str>=13 | dex>=13, int>=13 | wis>=13}'
    old_prof = 'multiclass_prof{armadura_leve, armadura_media, escudos, armas_marciais, pick:pericia:1}'
    new_req = 'multiclass_req{dex>=13, wis>=13}'
    new_prof = 'multiclass_prof{armadura_leve, armas_marciais, pick:pericia:1}'
    skills = ('Escolha 1 entre Adestrar Animais, Atletismo, Furtividade, '
              'Intuição, Investigação, Natureza, Percepção e Sobrevivência')
    if new_req in row['tags_json'] and new_prof in row['tags_json']:
        if (row['multiclass_requisitos'], row['multiclass_pericias'],
                row['multiclass_armaduras']) != ('Destreza 13 e Sabedoria 13', skills,
                                                'Armaduras Leves'):
            raise ValueError('Hunter multiclass text differs from its reviewed tags.')
        return ruleset
    if row['tags_json'].count(old_req) != 1 or row['tags_json'].count(old_prof) != 1:
        raise ValueError('Hunter multiclass tags differ from the reviewed base.')
    row['tags_json'] = [new_req if t == old_req else new_prof if t == old_prof else t
                        for t in row['tags_json']]
    row['multiclass_requisitos'] = 'Destreza 13 e Sabedoria 13'
    row['multiclass_pericias'] = skills
    row['multiclass_armaduras'] = 'Armaduras Leves'
    previous = ruleset.entries.select_related('revision').get(identity=identity).revision
    replacement = create_revision(identity, payload,
        dependencies=sorted(set(previous.dependencies) | {'hunter-rework'}), author=author)
    revisions = [entry.revision for entry in ruleset.entries.select_related('revision')
                 if entry.identity != identity]
    return seal_ruleset(revisions + [replacement], evaluator_version=EVALUATOR,
                        vocabulary_version=VOCABULARY, author=author)


@transaction.atomic
def compose_order_revision(ruleset, *, class_id, order_ids, author=None):
    """Add all eight reviewed Orders to a sealed Hunter class catalog.

    Order identities must be new, explicit subclass rows in the supplied snapshot.
    Existing subclass rows and features are never renamed or removed.
    """
    frozen = VersionedClassCatalog(ruleset, class_id)
    if frozen.classe.slug != 'cacador':
        raise ValueError('Order composition requires a Hunter class.')
    reference = json.loads((Path(__file__).parent / 'rules/hunter_content.json').read_text(encoding='utf-8'))
    rework = resolve_content(ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                             vocabulary_version=VOCABULARY)
    if reference['source_sha256'] != rework.get('source_sha256'):
        raise ValueError('Order source differs from the sealed Hunter reference.')
    names = {slugify(name): name for name in reference['orders']}
    if (len(names) != 8 or not isinstance(order_ids, dict) or set(order_ids) != set(names)
            or any(type(pk) is not int or pk <= 0 for pk in order_ids.values())
            or len(set(order_ids.values())) != 8):
        raise ValueError('Eight distinct reviewed Order identities are required.')
    new_subclasses = []
    for slug, pk in order_ids.items():
        subclass = frozen.subclasses.get(pk)
        if subclass is None:
            subclass = TbSubclasse.objects.filter(pk=pk, id_classe_id=class_id).first()
            if subclass is not None:
                new_subclasses.append(_fields(subclass))
        if (subclass is None or subclass.nome != names[slug]
                or subclass.slug != slug + '-rework'):
            raise ValueError('Order identity is absent or belongs to the legacy catalog.')
    source_rows = [row for row in reference['features'] if row['order']]
    if (len(source_rows) != 59 or {row['order'] for row in source_rows} != set(names.values())
            or any(row['level'] not in (3, 6, 10, 14, 18) for row in source_rows)):
        raise ValueError('The reviewed Order feature matrix is incomplete.')
    identity = 'class-catalog:%s' % class_id
    payload = deepcopy(resolve_content(ruleset, identity, evaluator_version=EVALUATOR,
                                       vocabulary_version=VOCABULARY))
    marker = {'source_sha256': reference['source_sha256'], 'order_ids': order_ids,
              'feature_count': len(source_rows)}
    if payload.get('hunter_order_replacements') == marker:
        return ruleset
    if 'hunter_order_replacements' in payload:
        raise ValueError('This class revision already has a different Order composition.')
    payload['collections'][TbSubclasse._meta.label_lower].extend(new_subclasses)
    features = payload['collections'][TbClassehabilidade._meta.label_lower]
    next_id = max((row['id_habilidade'] for row in features), default=0) + 1
    for row in source_rows:
        features.append({'id_habilidade': next_id, 'id_classe_id': class_id,
                         'id_subclasse_id': order_ids[slugify(row['order'])],
                         'nome': row['name'], 'nome_ingles': None,
                         'descricao': row['text'], 'niveladquirido': row['level'],
                         'table_only': False, 'tags_json': []})
        next_id += 1
    payload['hunter_order_replacements'] = marker
    previous = ruleset.entries.select_related('revision').get(identity=identity).revision
    replacement = create_revision(identity, payload,
        dependencies=sorted(set(previous.dependencies) | {'hunter-rework'}), author=author)
    revisions = [entry.revision for entry in ruleset.entries.select_related('revision')
                 if entry.identity != identity]
    return seal_ruleset(revisions + [replacement], evaluator_version=EVALUATOR,
                        vocabulary_version=VOCABULARY, author=author)


@transaction.atomic
def compose_choice_revision(ruleset, *, class_id, feature_ids, passive_ids=None,
                            secrets_ids=None, conditional_ids=None, spellcasting_ids=None,
                            mark_feature_id=None, author=None):
    """IDs are supplied by the reviewed mapping, never inferred from display names.

    Explicit choices, passives, conditional features and Secrets may be replaced. Other release
    requirements remain pending; this operation neither publishes nor migrates characters.
    """
    if (not isinstance(feature_ids, dict) or set(feature_ids) != set(CHOICE_SOURCES)
            or any(type(value) is not int or value <= 0 for value in feature_ids.values())
            or len(set(feature_ids.values())) != 2):
        raise ValueError('An explicit distinct identity is required for each choice feature.')
    source_ids = dict(CHOICE_SOURCES)
    mapped_ids = dict(feature_ids)
    if passive_ids is not None:
        if (not isinstance(passive_ids, dict) or set(passive_ids) != set(PASSIVE_SOURCES)
                or any(type(value) is not int or value <= 0 for value in passive_ids.values())
                or len(set(list(feature_ids.values()) + list(passive_ids.values()))) != 7):
            raise ValueError('An explicit distinct identity is required for every passive feature.')
        source_ids.update(PASSIVE_SOURCES)
        mapped_ids.update(passive_ids)
    if secrets_ids is not None:
        if (not isinstance(secrets_ids, dict) or set(secrets_ids) != {'feature', 'points', 'known'}
                or any(type(value) is not int or value <= 0 for value in secrets_ids.values())
                or secrets_ids['feature'] in mapped_ids.values()
                or secrets_ids['points'] == secrets_ids['known']):
            raise ValueError('Explicit distinct feature and resource identities are required for Secrets.')
        source_ids['secrets'] = '021-nivel-2-segredos-do-cacador'
        mapped_ids['secrets'] = secrets_ids['feature']
    if conditional_ids is not None:
        if (not isinstance(conditional_ids, dict)
                or set(conditional_ids) != set(CONDITIONAL_SOURCES) | {'favored_resource'}
                or any(type(value) is not int or value <= 0 for value in conditional_ids.values())):
            raise ValueError('Explicit identities are required for every conditional feature and favored resource.')
        conditional_features = {key: conditional_ids[key] for key in CONDITIONAL_SOURCES}
        all_ids = list(mapped_ids.values()) + list(conditional_features.values())
        if len(set(all_ids)) != len(all_ids):
            raise ValueError('Conditional feature identities must be distinct from other replacements.')
        source_ids.update(CONDITIONAL_SOURCES)
        mapped_ids.update(conditional_features)
    if spellcasting_ids is not None:
        if (not isinstance(spellcasting_ids, dict)
                or set(spellcasting_ids) != {'feature', 'slots'}
                or type(spellcasting_ids['feature']) is not int or spellcasting_ids['feature'] <= 0
                or spellcasting_ids['feature'] in mapped_ids.values()
                or not isinstance(spellcasting_ids['slots'], list) or len(spellcasting_ids['slots']) != 5
                or any(type(pk) is not int or pk <= 0 for pk in spellcasting_ids['slots'])
                or len(set(spellcasting_ids['slots'])) != 5):
            raise ValueError('Explicit feature and five distinct slot identities are required for spellcasting.')
        source_ids['spellcasting'] = '012-nivel-1-conjuracao'
        mapped_ids['spellcasting'] = spellcasting_ids['feature']
    if mark_feature_id is not None:
        if type(mark_feature_id) is not int or mark_feature_id <= 0 or mark_feature_id in mapped_ids.values():
            raise ValueError('An explicit distinct Mark feature identity is required.')
        source_ids['mark'] = '006-nivel-1-marca-do-cacador'
        mapped_ids['mark'] = mark_feature_id
    frozen = VersionedClassCatalog(ruleset, class_id)
    if frozen.classe.slug != 'cacador':
        raise ValueError('Choice replacements require a Hunter class.')
    data = resolve_content(ruleset, 'hunter-rework', evaluator_version=EVALUATOR,
                           vocabulary_version=VOCABULARY)
    if (data.get('weapon_masteries', {}).get('level') != 2
            or data.get('weapon_masteries', {}).get('count') != 3
            or data.get('expertise', {}).get('levels') != [3, 9]):
        raise ValueError('Revision lacks the replacement choice mechanics.')
    if passive_ids is not None and data.get('base_passives', {}).get('version') != 1:
        raise ValueError('Revision lacks the replacement passive mechanics.')
    if conditional_ids is not None and data.get('favored_enemies', {}).get('levels') != [2, 8, 14]:
        raise ValueError('Revision lacks the replacement favored-enemy progression.')
    reference = json.loads((Path(__file__).parent / 'rules/hunter_content.json').read_text(encoding='utf-8'))
    if reference['source_sha256'] != data.get('source_sha256'):
        raise ValueError('Hunter reference differs from the sealed revision.')
    identity = 'class-catalog:%s' % class_id
    payload = deepcopy(resolve_content(ruleset, identity, evaluator_version=EVALUATOR,
                                       vocabulary_version=VOCABULARY))
    features = payload['collections'][TbClassehabilidade._meta.label_lower]
    if mark_feature_id is not None:
        from .versioned_spells import spell_catalog
        marks = [s for s in spell_catalog(ruleset).values()
                 if s.slug == 'marca-do-cacador' and s.nivel == 1]
        if len(marks) != 1 or marks[0].duracao.strip().casefold() != '1 hora':
            raise ValueError('Mark tracking requires the reviewed one-hour spell duration.')
        payload['hunter_mark_replacement'] = {'version': 1, 'duration_seconds': 3600,
            'feature_id': mark_feature_id, 'source_sha256': reference['source_sha256']}
    if spellcasting_ids is not None:
        from .hunter_spellcasting import progression_at
        progression = [progression_at(frozen.classe, level, ruleset) for level in range(1, 21)]
        if any(row is None for row in progression):
            raise ValueError('Revision lacks the replacement spell progression.')
        if ([(row['slots'], row['prepared_spells']) for row in progression]
                != [(row['slots'], row['prepared_spells']) for row in reference['progression']]):
            raise ValueError('Spell progression differs from the reviewed reference.')
        resources = payload['collections'][TbRecursoclasse._meta.label_lower]
        for circle, pk in enumerate(spellcasting_ids['slots'], 1):
            matches = [row for row in resources if row['id_recurso'] == pk]
            if (len(matches) != 1 or matches[0]['id_subclasse_id'] is not None
                    or matches[0]['tipo'] != 'table-only' or matches[0]['slug'] != '%so' % circle):
                raise ValueError('Mapped slot resource is absent or belongs to another circle.')
            matches[0].update(nivel=None, valor=None,
                valores_json={str(row['level']): str(row['slots'][circle - 1]) for row in progression})
        payload['hunter_spellcasting_replacement'] = {
            'source_sha256': reference['source_sha256'], 'identities': spellcasting_ids}
    if conditional_ids is not None:
        resources = payload['collections'][TbRecursoclasse._meta.label_lower]
        matches = [row for row in resources if row['id_recurso'] == conditional_ids['favored_resource']]
        if (len(matches) != 1 or matches[0]['id_subclasse_id'] is not None
                or matches[0]['tipo'] != 'choice'):
            raise ValueError('Mapped favored-enemy resource is absent or incompatible.')
        matches[0].update(nivel=None, valor=None, valores_json={'2': '1', '8': '2', '14': '3'})
    if secrets_ids is not None:
        resources = payload['collections'][TbRecursoclasse._meta.label_lower]
        marker = {'source_sha256': reference['source_sha256'], 'identities': secrets_ids}
        already_replaced = payload.get('hunter_secret_replacements') == marker
        for key, kind in (('points', 'consumable'), ('known', 'choice')):
            matches = [row for row in resources if row['id_recurso'] == secrets_ids[key]]
            if not matches and already_replaced:
                continue
            if (len(matches) != 1 or matches[0]['id_subclasse_id'] is not None
                    or matches[0]['tipo'] != kind):
                raise ValueError('Mapped Secret resource is absent or incompatible.')
            resources.remove(matches[0])
        # The dedicated preparation and resource services own the replacement.
        # Retain identities in the sealed manifest for audit and idempotence.
        payload['hunter_secret_replacements'] = marker
    replacements = []
    for key, source_id in source_ids.items():
        matches = [row for row in features if row['id_habilidade'] == mapped_ids[key]]
        source = next(row for row in reference['features'] if row['id'] == source_id)
        if len(matches) != 1 or matches[0]['id_subclasse_id'] is not None:
            raise ValueError('Mapped feature is absent or belongs to a subclass.')
        row = matches[0]
        row.update(nome=source['name'], descricao=source['text'], niveladquirido=source['level'],
                   tags_json=[])
        # Dedicated services own these choices and effects. Keeping legacy tags
        # would grant the old mechanics alongside the replacements.
        replacements.append({'feature_id': row['id_habilidade'], 'source_id': source_id,
                             'level': source['level']})
    payload['hunter_choice_replacements'] = {
        'source_sha256': reference['source_sha256'],
        'features': [r for r in replacements if r['source_id'] in CHOICE_SOURCES.values()]}
    if passive_ids is not None:
        payload['hunter_passive_replacements'] = {
            'source_sha256': reference['source_sha256'],
            'features': [r for r in replacements if r['source_id'] in PASSIVE_SOURCES.values()]}
    if conditional_ids is not None:
        payload['hunter_conditional_replacements'] = {
            'source_sha256': reference['source_sha256'],
            'favored_resource': conditional_ids['favored_resource'],
            'features': [r for r in replacements if r['source_id'] in CONDITIONAL_SOURCES.values()]}
    previous = ruleset.entries.select_related('revision').get(identity=identity).revision
    replacement = create_revision(identity, payload,
        dependencies=sorted(set(previous.dependencies) | {'hunter-rework'}), author=author)
    revisions = [entry.revision for entry in ruleset.entries.select_related('revision')
                 if entry.identity != identity]
    return seal_ruleset(revisions + [replacement], evaluator_version=EVALUATOR,
                        vocabulary_version=VOCABULARY, author=author)
