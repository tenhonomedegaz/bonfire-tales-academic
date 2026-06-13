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

    print("\nIniciando limpeza e mesclagem do banco de dados...")
    
    # 1. Desconectar o signal do UserProfile temporariamente para nao dar conflito de chaves
    post_save.disconnect(create_user_profile, sender=User)
    print("- Sinal create_user_profile desconectado.")

    from django.utils.timezone import is_naive, make_aware, get_current_timezone
    from django.apps import apps

    # Modelos de bot para mesclagem
    bot_model_classes = [BotQuest, BotMember, BotTransaction, BotSchedulerJob, BotDedicatedRank, BotCharacterLog, BotKeyValueStore]
    bot_labels = {m._meta.label_lower: m for m in bot_model_classes}

    # 2. Ler todos os dados atuais do bot no banco antes de fazer qualquer limpeza
    print("\nLendo registros atuais do Bot no banco de dados para evitar perda de dados...")
    live_bot_data = {}
    for model_cls in bot_model_classes:
        label = model_cls._meta.label_lower
        try:
            live_bot_data[label] = {str(obj.pk): obj for obj in model_cls.objects.all()}
            print(f"  - Carregados {len(live_bot_data[label])} registros atuais de {model_cls.__name__}")
        except Exception as e:
            # Caso a tabela não exista ainda (ex: banco zerado)
            live_bot_data[label] = {}
            print(f"  - Nao foi possivel carregar {model_cls.__name__} (pode nao existir): {e}")

    # 3. Deserializar o arquivo de backup
    print("\nDeserializando arquivo de backup...")
    backup_deserialized = list(serializers.deserialize("json", data_str))
    print(f"  - Deserializados {len(backup_deserialized)} objetos do arquivo de backup.")

    # 4. Mesclar dados de bot e separar RPG/outros objetos
    final_bot_instances = []
    rpg_instances = []
    
    for deserialized_obj in backup_deserialized:
        instance = deserialized_obj.object
        model_label = instance._meta.label_lower
        
        if model_label in bot_labels:
            pk_str = str(instance.pk)
            live_instance = live_bot_data[model_label].get(pk_str)
            if live_instance:
                # Se existe em ambos, comparar updatedAt para manter a versao mais recente
                has_updated_at = hasattr(instance, 'updatedAt') and getattr(instance, 'updatedAt') is not None
                if has_updated_at:
                    backup_time = getattr(instance, 'updatedAt')
                    live_time = getattr(live_instance, 'updatedAt')
                    
                    if is_naive(backup_time):
                        backup_time = make_aware(backup_time, get_current_timezone())
                    if is_naive(live_time):
                        live_time = make_aware(live_time, get_current_timezone())
                        
                    if live_time >= backup_time:
                        final_bot_instances.append(live_instance)
                    else:
                        final_bot_instances.append(instance)
                else:
                    # Para tabelas sem updatedAt (ou nulo), mantém a versao em producao
                    final_bot_instances.append(live_instance)
                
                # Remover do dicionario temporario para nao duplicar
                live_bot_data[model_label].pop(pk_str, None)
            else:
                # Existe apenas no backup (ex: criado no dev)
                final_bot_instances.append(instance)
        else:
            # RPG ou outros modelos (como UserProfile)
            rpg_instances.append(instance)

    # Adicionar os registros do bot que existem apenas no banco de producao (criados no meio tempo)
    for model_label, pk_map in live_bot_data.items():
        for pk_str, live_instance in pk_map.items():
            final_bot_instances.append(live_instance)

    print(f"  - Total de objetos RPG/outros a restaurar: {len(rpg_instances)}")
    print(f"  - Total de objetos do Bot mesclados a salvar: {len(final_bot_instances)}")

    # 5. Limpeza total do banco de dados (preservando apenas auth.User, UserProfile, etc.)
    print("\nIniciando limpeza total do banco de dados (excluindo auth.User e UserProfile)...")
    all_models = apps.get_models()
    excluded_model_labels = {
        'auth.user', 
        'home.userprofile', 
        'contenttypes.contenttype', 
        'auth.permission',
        'auth.group'
    }
    models_to_delete = [
        m for m in all_models 
        if m._meta.label_lower not in excluded_model_labels
    ]
    
    attempts = 0
    max_attempts = 10
    while models_to_delete and attempts < max_attempts:
        attempts += 1
        deferred = []
        for model in models_to_delete:
            try:
                with transaction.atomic():
                    count, _ = model._default_manager.all().delete()
                    if count > 0:
                        print(f"  - Limpos {count} registros do modelo {model.__name__}")
            except Exception as e:
                deferred.append(model)
        models_to_delete = deferred

    if models_to_delete:
        print(f"[AVISO] Nao foi possivel limpar os seguintes modelos devido a restricoes: {[m.__name__ for m in models_to_delete]}")
    else:
        print("- Limpeza completa realizada com sucesso!")

    # 6. Criar usuarios dummy requeridos para chaves estrangeiras apenas se nao existirem
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

    # 7. Salvar objetos no banco de dados de forma transacional
    print("\nImportando objetos RPG/outros no banco de dados...")
    rpg_count = 0
    with transaction.atomic():
        for instance in rpg_instances:
            try:
                instance.save()
                rpg_count += 1
                if rpg_count % 500 == 0:
                    print(f"-> {rpg_count} objetos RPG salvos...")
            except Exception as e:
                print(f"[ERRO] Falha ao salvar objeto RPG {instance.__class__.__name__} (PK: {instance.pk}): {e}")
                raise e

    print(f"\nImportando objetos do Bot mesclados no banco de dados...")
    bot_count = 0
    with transaction.atomic():
        for instance in final_bot_instances:
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
                instance.save()
                bot_count += 1
                if bot_count % 100 == 0:
                    print(f"-> {bot_count} objetos do Bot salvos...")
            except Exception as e:
                print(f"[ERRO] Falha ao salvar objeto Bot {instance.__class__.__name__} (PK: {instance.pk}): {e}")
                raise e

    print(f"\nRESTAURACAO CONCLUIDA COM SUCESSO!")
    print(f"Total de objetos RPG importados: {rpg_count}")
    print(f"Total de objetos do Bot importados/atualizados: {bot_count}")

    # 8. Sincronizar sequencias auto-incrementais do PostgreSQL
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
