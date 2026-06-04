"""
Gera um backup dos dados do site e salva em backup_sqlite.json (formato Django dumpdata/loaddata).
Uso: python manage.py make_backup
"""
import json
import os
from django.core.management.base import BaseCommand
from django.core import serializers
from django.apps import apps

class Command(BaseCommand):
    help = 'Gera backup dos dados do site e salva em backup_sqlite.json'

    def handle(self, *args, **options):
        backup_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            'backup_sqlite.json',
        )

        self.stdout.write('Iniciando exportacao de dados...')
        
        home_models = apps.get_app_config('home').get_models()
        
        model_order_names = [
            'tbraca', 'tblinhagem', 'tbessencia', 'tbtracoracial',
            'tbclasse', 'tbsubclasse', 'tbclassehabilidade', 'tbrecursoclasse',
            'tbopcaojogo', 'tbacessoopcao', 'tbtalento',
            'tbregiao', 'tbterritorio', 'tbmapmarker',
            'tbcronica', 'tbjornal', 'tbitemmundano', 'tbitemmagico', 'tbmagia'
        ]
        
        sorted_models = []
        model_dict = {m._meta.model_name: m for m in home_models}
        
        for name in model_order_names:
            if name in model_dict:
                sorted_models.append(model_dict.pop(name))
        sorted_models.extend(model_dict.values())
        
        records = []
        for model in sorted_models:
            try:
                qs = model.objects.all().order_by('pk')
                count = qs.count()
                if count > 0:
                    serialized = serializers.serialize('python', qs)
                    records.extend(serialized)
                    self.stdout.write(f'  {model._meta.label}: {count} registros exportados')
            except Exception as e:
                self.stderr.write(self.style.WARNING(f'Erro ao exportar {model._meta.label}: {e}'))
                
        # Write to backup_sqlite.json
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
            
        self.stdout.write(self.style.SUCCESS(f'\nBackup salvo com sucesso em: {backup_path} ({len(records)} registros no total)'))
