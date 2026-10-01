"""Audit the current PostgreSQL bestiary without exporting private model fields."""

from hashlib import sha256
import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.bestiary_audit import audit_snapshot


CREATURE_FIELDS = (
    'slug', 'tipo', 'tamanho', 'nd', 'escala_com_dono',
    'companheiro_classe', 'companheiro_subclasse', 'statblock_json', 'tags_json',
)


class Command(BaseCommand):
    help = 'Audita classificacao, tags e referencias do bestiario PostgreSQL atual sem gravar no banco.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('A auditoria atual exige PostgreSQL.')
        target = Path(options['output']).resolve()
        if target.exists():
            raise CommandError('O relatorio ja existe; escolha outro caminho.')

        rows = []
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                cursor.execute('SELECT current_database()')
                database_name = cursor.fetchone()[0]
            tables = set(connection.introspection.table_names())
            missing_tables = []
            for model in apps.get_models():
                if model._meta.app_label != 'home':
                    continue
                field_names = {field.name for field in model._meta.concrete_fields}
                if model._meta.model_name == 'tbmagia':
                    selected = ('slug',)
                elif model._meta.model_name == 'tbbestiario':
                    selected = CREATURE_FIELDS
                elif 'tags_json' in field_names:
                    selected = ('tags_json',)
                else:
                    continue
                if model._meta.db_table not in tables:
                    missing_tables.append(model._meta.label_lower)
                    continue
                for record in model.objects.order_by('pk').values('pk', *selected):
                    pk = record.pop('pk')
                    rows.append({'model': model._meta.label_lower, 'pk': pk, 'fields': record})

        report = audit_snapshot(rows)
        if not report['summary']['creatures']:
            raise CommandError('Nenhuma criatura encontrada no PostgreSQL atual.')
        payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        report['source'] = {
            'kind': 'live_postgres', 'database': database_name,
            'snapshot_sha256': sha256(payload.encode('utf-8')).hexdigest(),
            'missing_tag_tables': missing_tables,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open('x', encoding='utf-8') as output:
                json.dump(report, output, ensure_ascii=False, indent=2)
                output.write('\n')
        except FileExistsError as exc:
            raise CommandError('O relatorio ja existe; escolha outro caminho.') from exc
        self.stdout.write(
            f"Auditadas {report['summary']['creatures']} criaturas; "
            f"{report['summary']['tag_syntax_errors']} erros de sintaxe; "
            f"{report['summary']['untagged_features']} habilidades sem tags; "
            f'relatorio: {target}'
        )
