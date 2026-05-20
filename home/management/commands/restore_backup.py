"""
Restaura os dados do site a partir do backup_sqlite.json (formato Django dumpdata/loaddata).
Uso: python manage.py restore_backup
"""
import json
import os

from django.core.management.base import BaseCommand
from django.core import serializers


class Command(BaseCommand):
    help = 'Restaura dados do site a partir do backup_sqlite.json'

    def handle(self, *args, **options):
        backup_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'backup_sqlite.json')

        if not os.path.exists(backup_path):
            self.stderr.write(self.style.ERROR(f'Arquivo de backup nao encontrado: {backup_path}'))
            return

        self.stdout.write(f'Lendo backup de: {backup_path}')

        with open(backup_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Separate auth.user from home.* models
        auth_records = [r for r in data if r['model'].startswith('auth.')]
        home_records = [r for r in data if r['model'].startswith('home.')]

        # Count by model
        model_counts = {}
        for record in data:
            model_counts[record['model']] = model_counts.get(record['model'], 0) + 1

        self.stdout.write('Conteudo do backup:')
        for model, count in sorted(model_counts.items()):
            self.stdout.write(f'  {model}: {count} registros')

        # Use Django's built-in deserializer which handles the dumpdata format natively
        total_saved = 0
        total_skipped = 0
        errors = []

        # Process home models first (they have FK dependencies, but Django serializer handles ordering)
        json_str = json.dumps(home_records)
        try:
            for obj in serializers.deserialize('json', json_str):
                try:
                    obj.save()
                    total_saved += 1
                except Exception as e:
                    total_skipped += 1
                    errors.append(f'{obj.object.__class__.__name__} pk={obj.object.pk}: {e}')
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Erro ao desserializar: {e}'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nRestauracao concluida!'))
        self.stdout.write(f'  Salvos: {total_saved}')
        self.stdout.write(f'  Ignorados/Erros: {total_skipped}')

        if errors:
            self.stdout.write(self.style.WARNING('\nErros encontrados:'))
            for err in errors[:20]:
                self.stdout.write(f'  - {err}')
            if len(errors) > 20:
                self.stdout.write(f'  ... e mais {len(errors) - 20} erros')
