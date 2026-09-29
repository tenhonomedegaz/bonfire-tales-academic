"""Add-only Hunter package accepted by the existing admin restore action."""
import hashlib
import json

from django.core import serializers
from django.db import connection, transaction

from .models import (TbClasse, TbContentRevision, TbMagia, TbPersonagem,
                     TbPersonagemClasse, TbRuleset, TbRulesetContent, TbSubclasse)


KIND = 'bonfire.hunter_restore.v1'
MODELS = ('home.tbsubclasse', 'home.tbmagia', 'home.tbcontentrevision',
          'home.tbruleset', 'home.tbrulesetcontent')
FINAL_CHECKSUM = 'da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289'
SOURCE_HASH = 'a6a674829b8d46f01d8d3966b31bf0e7ca049cd3df597a23ab0b17d013222227'
APPROVED_ROWS_HASH = '199344475103e35d280b8b634b0a7d5205555b7ccd23685f69da0f8a74ba9ef3'
APPROVED_ANCHORS_HASH = '3fa7600074a129ebd4670334f77f482c5cd40ab758d50ddbc005a2a4147375a9'
MODEL_CLASSES = dict(zip(MODELS, (TbSubclasse, TbMagia, TbContentRevision,
                                  TbRuleset, TbRulesetContent)))


def rows_hash(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def source_anchors(production):
    """Only stable production identities: later level-ups must not block a replay."""
    classes = sorted((r['pk'], r['fields']['slug']) for r in production
                     if r['model'] == 'home.tbclasse')
    characters = sorted((r['pk'], r['fields']['dono'][0]) for r in production
                        if r['model'] == 'home.tbpersonagem')
    links = sorted((r['pk'], r['fields']['id_personagem'], r['fields']['id_classe'])
                   for r in production if r['model'] == 'home.tbpersonagemclasse')
    return {'classes': classes, 'characters': characters, 'class_links': links}


def _check_anchors(anchors):
    for pk, slug in anchors['classes']:
        if not TbClasse.objects.filter(pk=pk, slug=slug).exists():
            raise ValueError('Identidade de classe da producao mudou: PK %s.' % pk)
    for pk, owner in anchors['characters']:
        if not TbPersonagem.objects.filter(pk=pk, dono__username=owner).exists():
            raise ValueError('Propriedade de personagem da producao mudou: PK %s.' % pk)
    for pk, person_id, class_id in anchors['class_links']:
        if not TbPersonagemClasse.objects.filter(
                pk=pk, id_personagem_id=person_id, id_classe_id=class_id).exists():
            raise ValueError('Vinculo de classe da producao mudou: PK %s.' % pk)


def _natural_match(model, fields):
    if model == 'home.tbsubclasse':
        return TbSubclasse.objects.filter(id_classe_id=fields['id_classe'],
                                          slug=fields['slug']).first()
    if model == 'home.tbmagia':
        return TbMagia.objects.filter(slug=fields['slug']).first()
    if model == 'home.tbcontentrevision':
        return TbContentRevision.objects.filter(identity=fields['identity'],
                                                checksum=fields['checksum']).first()
    if model == 'home.tbruleset':
        return TbRuleset.objects.filter(checksum=fields['checksum']).first()
    return TbRulesetContent.objects.filter(ruleset_id=fields['ruleset'],
                                           identity=fields['identity']).first()


def restore_hunter_package(package):
    """Preflight all identities, insert missing rows, verify; never update existing rows."""
    if connection.vendor != 'postgresql':
        raise ValueError('O pacote do Cacador exige PostgreSQL.')
    if not isinstance(package, dict) or set(package) != {
            'kind', 'source_sha256', 'final_ruleset_checksum', 'rows_sha256',
            'anchors', 'rows'} or package['kind'] != KIND:
        raise ValueError('Formato do pacote do Cacador invalido.')
    rows = package['rows']
    if (not isinstance(rows, list) or len(rows) != 107 or
            package['source_sha256'] != SOURCE_HASH or
            package['final_ruleset_checksum'] != FINAL_CHECKSUM or
            package['rows_sha256'] != APPROVED_ROWS_HASH or
            rows_hash(rows) != APPROVED_ROWS_HASH):
        raise ValueError('Conteudo ou checksum do pacote do Cacador invalido.')
    anchors = package['anchors']
    if not isinstance(anchors, dict) or set(anchors) != {
            'classes', 'characters', 'class_links'} or rows_hash(anchors) != APPROVED_ANCHORS_HASH:
        raise ValueError('Ancora de identidades da producao ausente.')
    with transaction.atomic():
        # Serialize package operations on this database; ordinary generic restores
        # continue to use their existing path and guard.
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [0x424f4e46495245])
        _check_anchors(anchors)
        keys = set()
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {'model', 'pk', 'fields'} or
                    row['model'] not in MODELS or type(row['pk']) is not int or
                    row['pk'] <= 0 or not isinstance(row['fields'], dict)):
                raise ValueError('Registro inesperado no pacote do Cacador.')
            key = (row['model'], row['pk'])
            if key in keys:
                raise ValueError('PK duplicada no pacote do Cacador.')
            keys.add(key)
            model_class = MODEL_CLASSES[row['model']]
            current = model_class.objects.filter(pk=row['pk']).first()
            natural = _natural_match(row['model'], row['fields'])
            if natural is not None and natural.pk != row['pk']:
                raise ValueError('Identidade natural ocupada por outra PK: %s.' % (key,))
            if current is not None:
                stored = json.loads(serializers.serialize('json', [current]))[0]
                if stored['fields'] != row['fields']:
                    raise ValueError('PK ocupada por conteudo divergente: %s.' % (key,))
        # Missing parent rows precede dependent rows in the exporter order.
        added = 0
        added_models = set()
        for row in rows:
            if not MODEL_CLASSES[row['model']].objects.filter(pk=row['pk']).exists():
                wrapper = next(serializers.deserialize('json', json.dumps([row])))
                wrapper.save()
                added += 1
                added_models.add(row['model'])
        if not TbRuleset.objects.filter(checksum=FINAL_CHECKSUM).exists():
            raise ValueError('Revisao final do Cacador ausente apos importacao.')
        for row in rows:
            current = MODEL_CLASSES[row['model']].objects.get(pk=row['pk'])
            stored = json.loads(serializers.serialize('json', [current]))[0]
            if stored['fields'] != row['fields']:
                raise ValueError('Conferencia pos-importacao falhou: %s %s.' %
                                 (row['model'], row['pk']))
        # Only imported models need alignment. Never lower a sequence that
        # another writer may have advanced, and do nothing at all on replay.
        with connection.cursor() as cursor:
            for label in added_models:
                model = MODEL_CLASSES[label]
                table = model._meta.db_table
                pk_column = model._meta.pk.column
                cursor.execute('SELECT pg_get_serial_sequence(%s, %s)',
                               [connection.ops.quote_name(table), pk_column])
                sequence = cursor.fetchone()[0]
                if sequence:
                    cursor.execute('SELECT MAX(%s) FROM %s' % (
                        connection.ops.quote_name(pk_column),
                        connection.ops.quote_name(table)))
                    maximum = cursor.fetchone()[0]
                    cursor.execute('SELECT nextval(%s)', [sequence])
                    reserved = cursor.fetchone()[0]
                    cursor.execute('SELECT setval(%s, GREATEST(%s, %s))',
                                   [sequence, maximum, reserved])
        return {'added': added, 'unchanged': len(rows) - added,
                'ruleset_checksum': FINAL_CHECKSUM}
