"""Prepare a database revision of Hunter prose; never change the live catalog."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from io import StringIO
from django.utils.text import slugify
from django.core.management import call_command
from django.db import connection, transaction

from .models import TbClassehabilidade


RULES_DIR = Path(__file__).parent / 'rules'
BASE_CHECKSUM = 'da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289'
EXPLANATORY_IDS = frozenset({
    '076-nivel-3-ordem-do-cacador',
    '129-nivel-6-habilidade-da-ordem',
    '149-nivel-10-habilidade-da-ordem',
    '171-nivel-14-habilidade-da-ordem',
    '192-nivel-18-habilidade-da-ordem',
})
ASI_LEVELS = frozenset({4, 8, 12, 16, 19})
ASI_PK = 1035  # Existing, reviewed level-4 identity in BASE_CHECKSUM.
NEW_PK_START = 2_100_000_000  # Snapshot-only identities; never insert live rows.
TARGET_CHECKSUM = 'ed230c319a8959a78cce978a1e72d11281f9f03bbe49b4c3f0e0158eb2a6e0a2'
SEED_SHA256 = 'c82ee0038c09cb6ebe645c7d90e32b122e004f53756c9a8fd3bdf2ff5e630e1f'
PACKAGE_KIND = 'bonfire.hunter_markdown.v1'


def compose_markdown_payload(original):
    """Return a new snapshot with source-identified Markdown and missing cards."""
    rules = json.loads((RULES_DIR / 'hunter_content.json').read_text(encoding='utf-8'))
    markdown = json.loads((RULES_DIR / 'hunter_markdown_revision.json').read_text(encoding='utf-8'))
    if (markdown.get('schema') != 1 or markdown.get('source_sha256') != rules['source_sha256']
            or [row['id'] for row in markdown['features']] != [row['id'] for row in rules['features']]):
        raise ValueError('Hunter Markdown source does not match reviewed content.')
    payload = deepcopy(original)
    if payload.get('hunter_order_replacements', {}).get('source_sha256') != rules['source_sha256']:
        raise ValueError('Hunter class revision is not the reviewed Order catalog.')
    order_ids = payload['hunter_order_replacements']['order_ids']
    features = payload['collections'][TbClassehabilidade._meta.label_lower]
    if any(row['id_habilidade'] >= NEW_PK_START for row in features):
        raise ValueError('Reserved snapshot identities are already in use.')
    used_ids = {row['id_habilidade'] for row in features}
    added = []
    updated = []
    for source, formatted in zip(rules['features'], markdown['features']):
        digest = hashlib.sha256(source['text'].encode('utf-8')).hexdigest()
        if (formatted['raw_sha256'] != digest or formatted['level'] != source['level']
                or formatted['name'] != source['name'] or formatted['order'] != source['order']
                or '<' in formatted['markdown']):
            raise ValueError('Hunter Markdown row differs from the reviewed source.')
        is_asi = source['name'] == 'Aprimoramento de Atributo ou Talento'
        is_explanatory = source['id'] in EXPLANATORY_IDS
        candidates = [row for row in features
                      if row['niveladquirido'] == source['level']
                      and row['nome'] == source['name']
                      and ((row['id_subclasse_id'] == order_ids.get(slugify(source['order']))) if source['order']
                           else row['id_subclasse_id'] is None)
                      and row['descricao'] == source['text']]
        if is_asi and source['level'] == 4:
            candidates = [row for row in features if row['id_habilidade'] == ASI_PK
                          and row['id_subclasse_id'] is None
                          and row['niveladquirido'] == 4
                          and row['nome'] == source['name']]
        if is_explanatory or (is_asi and source['level'] != 4):
            if candidates or (is_asi and source['level'] not in ASI_LEVELS):
                raise ValueError('Missing Hunter card already has an unexpected identity.')
            new_id = NEW_PK_START + len(added)
            if new_id in used_ids:
                raise ValueError('Hunter display identity collides with the catalog.')
            features.append({
                'id_habilidade': new_id, 'id_classe_id': original['class_id'],
                'id_subclasse_id': None, 'nome': source['name'], 'nome_ingles': None,
                'descricao': formatted['markdown'], 'niveladquirido': source['level'],
                'table_only': False, 'tags_json': [],
            })
            used_ids.add(new_id)
            added.append(source['id'])
        else:
            if len(candidates) != 1:
                raise ValueError('Hunter card identity is absent or ambiguous: ' + source['id'])
            candidates[0]['descricao'] = formatted['markdown']
            updated.append(source['id'])
    if (len(updated), len(added)) != (75, 9):
        raise ValueError('Hunter Markdown coverage is incomplete.')
    payload['hunter_markdown_revision'] = {
        'schema': 1, 'source_sha256': rules['source_sha256'],
        'updated': len(updated), 'added': added,
    }
    return payload


def restore_markdown_package(package):
    """Use admin restore to seal the reviewed DB revision without importing PKs."""
    expected = {'kind': PACKAGE_KIND, 'base_ruleset_checksum': BASE_CHECKSUM,
                'final_ruleset_checksum': TARGET_CHECKSUM, 'seed_sha256': SEED_SHA256}
    if package != expected:
        raise ValueError('Hunter Markdown package identity or checksum differs.')
    if connection.vendor != 'postgresql':
        raise ValueError('Hunter Markdown publication requires PostgreSQL.')
    seed = RULES_DIR / 'hunter_markdown_revision.json'
    if hashlib.sha256(seed.read_bytes()).hexdigest() != SEED_SHA256:
        raise ValueError('Hunter Markdown seed differs from the reviewed artifact.')
    from .models import TbRuleset
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [0x424f4e46495245])
        call_command('compose_hunter_markdown_revision', apply=True,
                     base_checksum=BASE_CHECKSUM, stdout=StringIO())
        if not TbRuleset.objects.filter(checksum=TARGET_CHECKSUM).exists():
            raise ValueError('Hunter Markdown checksum differs after composition.')
    return {'ruleset_checksum': TARGET_CHECKSUM}
