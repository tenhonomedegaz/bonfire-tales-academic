import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = "Restaura os dados do SQLite (bonfas_classes.db) para o PostgreSQL atual"

    def handle(self, *args, **options):
        sqlite_db_path = os.path.join(settings.BASE_DIR, 'bonfas_classes.db')
        
        if not os.path.exists(sqlite_db_path):
            self.stderr.write(self.style.ERROR(f"Arquivo SQLite nao encontrado: {sqlite_db_path}"))
            return

        import copy
        from django.db import connections
        
        sqlite_db = copy.deepcopy(connections.databases['default'])
        sqlite_db['ENGINE'] = 'django.db.backends.sqlite3'
        sqlite_db['NAME'] = sqlite_db_path
        sqlite_db['OPTIONS'] = {}
        
        # Remove postgres-specific parameters
        for key in ['USER', 'PASSWORD', 'HOST', 'PORT']:
            sqlite_db[key] = ''
            
        settings.DATABASES['sqlite_backup'] = sqlite_db
        connections.databases['sqlite_backup'] = sqlite_db

        backup_file = os.path.join(settings.BASE_DIR, 'backup_sqlite.json')

        self.stdout.write("Lendo dados do SQLite (home, auth.user)...")
        with open(backup_file, 'w', encoding='utf-8') as f:
            call_command(
                'dumpdata', 
                'home', 
                'auth.user', 
                database='sqlite_backup', 
                stdout=f
            )
        
        self.stdout.write("Carregando dados no PostgreSQL...")
        
        # O banco precisa estar limpo antes de carregar os dados do SQLite
        self.stdout.write("Limpando banco de dados PostgreSQL antes do import...")
        call_command('flush', '--noinput', database='default')
        
        call_command('loaddata', backup_file, database='default')
        
        self.stdout.write(self.style.SUCCESS("Todos os dados do site foram restaurados com sucesso!"))
        
        if os.path.exists(backup_file):
            try:
                os.remove(backup_file)
                self.stdout.write("Arquivo de backup temporario removido.")
            except:
                pass
