import os
import sys
import django
from pathlib import Path

# Add project root to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Initialize Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bonfire.settings')
django.setup()

import glob
import ast
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core import serializers
from django.db import transaction
from django.db.models.signals import post_save
from home.models import (
    UserProfile, create_user_profile, BotQuest, BotMember, 
    BotTransaction, BotSchedulerJob, BotDedicatedRank, 
    BotCharacterLog, BotKeyValueStore
)

def get_backup_file():
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.exists(path):
            return path
        else:
            print(f"[ERRO] Arquivo de backup nao encontrado no caminho fornecido: {path}")
            sys.exit(1)
            
    # Procurar no diretorio C:\Users\helio\Downloads
    downloads_dir = r"C:\Users\helio\Downloads"
    files = glob.glob(os.path.join(downloads_dir, "backup_site_*.json"))
    if not files:
        print("[ERRO] Nenhum arquivo backup_site_*.json encontrado em Downloads.")
        print("Por favor, passe o caminho do arquivo de backup como argumento para o script.")
        sys.exit(1)
        
    # Sort files by modification time (most recent first)
    files.sort(key=os.path.getmtime, reverse=True)
    selected_file = files[0]
    print(f"Nenhum argumento fornecido. Usando o backup mais recente encontrado em Downloads:")
    print(f"-> {selected_file}")
    return selected_file

def list_to_pg_array(lst):
    if not lst:
        return '{}'
    escaped = []
    for item in lst:
        if item == '':
            escaped.append('""')
        else:
            item_esc = str(item).replace('\\', '\\\\').replace('"', '\\"')
            escaped.append(f'"{item_esc}"')
    return '{' + ','.join(escaped) + '}'

def main():
    backup_file = get_backup_file()
    
    print("\nLendo arquivo de backup...")
    with open(backup_file, encoding='utf-8') as f:
        data_str = f.read()

    print("\nIniciando limpeza seletiva do banco de dados (preservando usuarios e tabelas do bot)...")
    
    # 1. Desconectar o signal do UserProfile temporariamente para nao dar conflito de chaves
    post_save.disconnect(create_user_profile, sender=User)
    print("- Sinal create_user_profile desconectado.")

    # 2. Identificar e limpar apenas os modelos contidos no arquivo de backup
    try:
        import json
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        # Identificar modelos únicos presentes no backup
        model_labels = set()
        for item in backup_data:
            if 'model' in item:
                model_labels.add(item['model'])
        
        # Excluir explicitamente modelos de autenticação/usuários e perfis do processo de deleção
        excluded_models = {'auth.user', 'home.userprofile'}
        model_labels = [m for m in model_labels if m not in excluded_models]
        
        print(f"- Modelos encontrados no backup a serem limpos: {model_labels}")
        
        # Obter classes de modelo do Django
        from django.apps import apps
        model_classes = []
        for label in model_labels:
            try:
                model_classes.append(apps.get_model(label))
            except Exception as e:
                print(f"- Aviso: Nao foi possivel carregar o modelo {label}: {e}")
        
        # Definir prioridade manual de deleção para evitar erros de restrição de integridade (Foreign Key)
        priority_order = [
            'tbtracoracial', 'tblinhagem', 'tbessencia', 'tbraca',
            'tbclassehabilidade', 'tbrecursoclasse', 'tbsubclasse', 'tbclasse',
            'tbacessoopcao', 'tbopcaojogo', 'tbtalento',
            'tbmapmarker', 'tbterritorio', 'tbregiao',
            'tbcronica', 'tbjornal', 'tbitemmundano', 'tbitemmagico', 'tbmagia'
        ]
        
        def get_deletion_priority(model_class):
            name = model_class._meta.model_name
            if name in priority_order:
                return priority_order.index(name)
            return len(priority_order)
            
        # Ordenamos as classes para que os modelos filhos (com menor índice na lista priority_order) sejam limpos primeiro
        model_classes.sort(key=get_deletion_priority)
        
        # Deletar dados de forma atômica
        with transaction.atomic():
            for model_cls in model_classes:
                count_deleted, _ = model_cls.objects.all().delete()
                print(f"  - Limpos {count_deleted} registros do modelo {model_cls.__name__}")
                
        print("- Limpeza seletiva concluída com sucesso.")
    except Exception as e:
        print(f"[ERRO] Falha ao realizar a limpeza seletiva: {e}")
        sys.exit(1)
        
    # 3. Criar usuarios dummy requeridos para chaves estrangeiras apenas se nao existirem
    print("\nVerificando/Criando usuarios dummy requeridos...")
    dummy_uids = [1, 5, 7, 12, 13, 14, 15, 16]
    created_count = 0
    for uid in dummy_uids:
        _, created = User.objects.get_or_create(
            id=uid, 
            defaults={
                'username': f'dummy_user_{uid}', 
                'email': f'dummy_{uid}@example.com', 
                'is_active': True
            }
        )
        if created:
            created_count += 1
    print(f"- {created_count} novos usuarios dummy criados.")

    # 5. Importar dados utilizando o deserializador oficial
    print("\nImportando dados do backup no banco de dados PostgreSQL...")
    count = 0
    with transaction.atomic():
        for deserialized_obj in serializers.deserialize("json", data_str):
            instance = deserialized_obj.object
            
            # Conversao especifica para BotQuest
            if isinstance(instance, BotQuest):
                for field_name in ['tags', 'allowedRanks', 'mandatoryPlayers', 'highPriorityPlayers', 'removedPlayers']:
                    val = getattr(instance, field_name)
                    if val:
                        try:
                            if isinstance(val, str) and val.startswith('['):
                                parsed = ast.literal_eval(val)
                                setattr(instance, field_name, list_to_pg_array(parsed))
                        except Exception as e:
                            print(f"Erro ao converter campo {field_name} da quest {instance.pk}: {e}")
            
            try:
                deserialized_obj.save()
                count += 1
                if count % 500 == 0:
                    print(f"-> {count} objetos importados...")
            except Exception as e:
                print(f"[ERRO] Falha ao salvar objeto {instance.__class__.__name__} (PK: {instance.pk}): {e}")
                raise e

    print(f"\nRESTAURACAO CONCLUIDA COM SUCESSO!")
    print(f"Total de objetos importados: {count}")

    # 6. Sincronizar sequencias auto-incrementais do PostgreSQL
    print("\nReiniciando sequencias auto-incrementais do PostgreSQL...")
    from django.db import connection
    from io import StringIO
    
    sql_statements = []
    for app in ['auth', 'home', 'contenttypes', 'admin', 'sessions']:
        out = StringIO()
        try:
            call_command('sqlsequencereset', app, stdout=out)
            sql_statements.append(out.getvalue())
        except Exception as e:
            print(f"- Erro ao gerar SQL de sequencias para {app}: {e}")
            
    with connection.cursor() as cursor:
        for sql_block in sql_statements:
            for sql in sql_block.split('\n'):
                sql = sql.strip()
                if sql and not sql.startswith('--') and sql.endswith(';'):
                    sql = sql.rstrip(';')
                    try:
                        cursor.execute(sql)
                    except Exception as e:
                        # Ignorar silenciosamente erros de execução de SQL para DBs sem sequências
                        pass
    print("- Sequencias resetadas com sucesso.")

if __name__ == '__main__':
    main()
