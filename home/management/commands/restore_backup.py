"""
Restaura os dados do site a partir do backup_sqlite.json (formato Django dumpdata/loaddata).
Usa SET CONSTRAINTS ALL DEFERRED para evitar erros de FK durante a importacao.
Uso: python manage.py restore_backup
"""
import json
import os

from django.core.management.base import BaseCommand
from django.core import serializers
from django.db import connection


# Ordem de insercao: tabelas pai primeiro, filhas depois
MODEL_ORDER = [
    'home.tbraca',
    'home.tblinhagem',
    'home.tbessencia',
    'home.tbtracoracial',
    'home.tbclasse',
    'home.tbsubclasse',
    'home.tbclassehabilidade',
    'home.tbrecursoclasse',
    'home.tbopcaojogo',
    'home.tbacessoopcao',
    'home.tbtalento',
    'home.tbregiao',
    'home.tbterritorio',
    'home.tbmapmarker',
    'home.tbcronica',
    'home.tbjornal',
    'home.tbitemmundano',
    'home.tbitemmagico',
]


class Command(BaseCommand):
    help = 'Restaura dados do site a partir do backup_sqlite.json'

    def handle(self, *args, **options):
        backup_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            'backup_sqlite.json',
        )

        if not os.path.exists(backup_path):
            self.stderr.write(self.style.ERROR(f'Arquivo de backup nao encontrado: {backup_path}'))
            return

        self.stdout.write(f'Lendo backup de: {backup_path}')

        with open(backup_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Separate home.* records only (skip auth.user etc)
        home_records = [r for r in data if r['model'].startswith('home.')]

        # Count by model
        model_counts = {}
        for record in home_records:
            model_counts[record['model']] = model_counts.get(record['model'], 0) + 1

        self.stdout.write('Conteudo do backup:')
        for model, count in sorted(model_counts.items()):
            self.stdout.write(f'  {model}: {count} registros')

        # Sort records by dependency order
        def sort_key(record):
            model = record['model']
            try:
                return MODEL_ORDER.index(model)
            except ValueError:
                return len(MODEL_ORDER)  # unknown models go last

        home_records.sort(key=sort_key)

        total_saved = 0
        total_skipped = 0
        errors = []

        # Use SET CONSTRAINTS ALL DEFERRED to allow inserting in any order
        cursor = connection.cursor()
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")

        # Process each model group separately for better error reporting
        for model_name in MODEL_ORDER:
            model_records = [r for r in home_records if r['model'] == model_name]
            if not model_records:
                continue

            json_str = json.dumps(model_records)
            saved = 0
            skipped = 0

            for obj in serializers.deserialize('json', json_str):
                try:
                    obj.save()
                    saved += 1
                except Exception as e:
                    skipped += 1
                    errors.append(f'{obj.object.__class__.__name__} pk={obj.object.pk}: {e}')

            total_saved += saved
            total_skipped += skipped
            if saved > 0:
                self.stdout.write(f'  {model_name}: {saved} salvos' + (f', {skipped} erros' if skipped else ''))

        # Also process any models not in MODEL_ORDER
        remaining = [r for r in home_records if r['model'] not in MODEL_ORDER]
        if remaining:
            json_str = json.dumps(remaining)
            for obj in serializers.deserialize('json', json_str):
                try:
                    obj.save()
                    total_saved += 1
                except Exception as e:
                    total_skipped += 1
                    errors.append(f'{obj.object.__class__.__name__} pk={obj.object.pk}: {e}')

        self.stdout.write(self.style.SUCCESS(f'\nRestauracao concluida!'))
        self.stdout.write(f'  Salvos: {total_saved}')
        self.stdout.write(f'  Ignorados/Erros: {total_skipped}')

        if errors:
            self.stdout.write(self.style.WARNING(f'\nErros encontrados ({len(errors)}):'))
            for err in errors[:10]:
                self.stdout.write(f'  - {err}')
            if len(errors) > 10:
                self.stdout.write(f'  ... e mais {len(errors) - 10} erros')
