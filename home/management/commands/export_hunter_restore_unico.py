"""Consolidate reviewed Hunter additions; never writes to the database."""
import hashlib
import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.models import TbContentRevision, TbRuleset, TbRulesetContent
from home.hunter_restore_package import (APPROVED_ANCHORS_HASH, APPROVED_ROWS_HASH,
                                         KIND, rows_hash, source_anchors)


FINAL = 'da099956cb1abed5d158f64855076825d66e509a5d5aee0e4f19944291ce6289'
SOURCE_HASH = 'a6a674829b8d46f01d8d3966b31bf0e7ca049cd3df597a23ab0b17d013222227'
ALLOWED = ('home.tbsubclasse', 'home.tbmagia', 'home.tbcontentrevision',
           'home.tbruleset', 'home.tbrulesetcontent')


class Command(BaseCommand):
    help = 'Export a single Hunter fixture, checked against the supplied production snapshot.'

    def add_arguments(self, parser):
        parser.add_argument('--directory', default='ref/backups')

    def handle(self, *args, **options):
        root = Path(options['directory'])
        source = root / 'backup_completo_20260928_010338.json'
        if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_HASH:
            raise CommandError('Production snapshot changed; review required.')
        source_rows = json.loads(source.read_text(encoding='utf-8'))
        production = {(r['model'].lower(), r['pk']): r for r in source_rows}
        rows = []
        for name in ('reconciliacao_producao_rework_20260928.json',
                     'reconciliacao_producao_multiclasse_20260928.json'):
            rows.extend(json.loads((root / name).read_text(encoding='utf-8')))
        if connection.vendor != 'postgresql':
            raise CommandError('PostgreSQL required.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            final = TbRuleset.objects.get(checksum=FINAL)
            entries = TbRulesetContent.objects.filter(ruleset=final).order_by('pk')
            revisions = TbContentRevision.objects.filter(
                pk__in=entries.values_list('revision_id', flat=True)).order_by('pk')
            for objects in (revisions, [final], entries):
                rows.extend(json.loads(serializers.serialize('json', objects)))
        unique = {}
        for row in rows:
            key = (row['model'].lower(), row['pk'])
            if key[0] not in ALLOWED:
                raise CommandError('Unexpected model; refusing to export user data.')
            if key in production:
                raise CommandError('Production PK collision; no export generated.')
            if key in unique and unique[key] != row:
                raise CommandError('Conflicting duplicate in reviewed artifacts.')
            unique[key] = row
        available = set(production) | set(unique)
        relations = {'home.tbsubclasse': {'id_classe': 'home.tbclasse'},
                     'home.tbrulesetcontent': {'ruleset': 'home.tbruleset',
                                             'revision': 'home.tbcontentrevision'}}
        for (model, _), row in unique.items():
            for field, target in relations.get(model, {}).items():
                if (target, row['fields'][field]) not in available:
                    raise CommandError('Missing foreign key dependency.')
            author = row['fields'].get('author')
            if author is not None:
                raise CommandError('Author identity needs explicit production reconciliation.')
        ordered = sorted(unique.values(), key=lambda r: (ALLOWED.index(r['model'].lower()), r['pk']))
        output = root / 'restore_unico_cacador_producao_20260928.json'
        package = {'kind': KIND, 'source_sha256': SOURCE_HASH,
                   'final_ruleset_checksum': FINAL, 'rows_sha256': rows_hash(ordered),
                   'anchors': source_anchors(source_rows), 'rows': ordered}
        if (package['rows_sha256'] != APPROVED_ROWS_HASH or
                rows_hash(package['anchors']) != APPROVED_ANCHORS_HASH):
            raise CommandError('Reviewed Hunter package changed; explicit reconciliation required.')
        data = (json.dumps(package, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        report = {'file': output.name, 'records': len(ordered),
                  'sha256': hashlib.sha256(data).hexdigest(), 'production_sha256': SOURCE_HASH,
                  'final_ruleset_checksum': FINAL, 'production_records_modified': 0,
                  'models': {m: sum(r['model'] == m for r in ordered) for m in ALLOWED},
                  'validation': 'Static PK/FK checks against supplied snapshot; import through restore_backup requires matching production anchors.',
                  'warning': 'Requires compatible migrations and HUNTER_CREATOR_RULESET_CHECKSUM on the target.'}
        output.write_bytes(data)
        output.with_suffix('.report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.stdout.write(json.dumps(report, ensure_ascii=False))
