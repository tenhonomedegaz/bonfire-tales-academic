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

        self.stdout.write("Configurando acesso ao banco SQLite temporario...")
        settings.DATABASES['sqlite_backup'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_db_path,
        }

        backup_file = os.path.join(settings.BASE_DIR, 'backup_sqlite.json')

        try:
            self.stdout.write("Lendo dados do SQLite (home, auth.user)...")
            with open(backup_file, 'w', encoding='utf-8') as f:
                # Exclui contenttypes e auth.permission para nao conflitar com os IDs gerados no PostgreSQL
                call_command(
                    'dumpdata', 
                    'home', 
                    'auth.user', 
                    database='sqlite_backup', 
                    stdout=f
                )
            
            self.stdout.write("Carregando dados no PostgreSQL...")
            call_command('loaddata', backup_file, database='default')
            
            self.stdout.write(self.style.SUCCESS("🎉 Todos os dados do site foram restaurados com sucesso!"))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erro durante a restauracao: {e}"))
        finally:
            if os.path.exists(backup_file):
                try:
                    os.remove(backup_file)
                    self.stdout.write("Arquivo de backup temporario removido.")
                except:
                    pass
