"""Restaura o banco LOCAL a partir do backup de produção mais recente em ``ref/``.

Diferente de ``restore_backup`` (que faz merge a partir de ``backup_sqlite.json``),
este comando faz uma substituição limpa: **apaga** o conteúdo das tabelas presentes
no backup e recarrega com os dados de produção. Assim não sobram registros locais
órfãos (ex.: raças que existem só no local).

- Preserva ``auth`` (usuários/admin) e sessões — só apaga as tabelas ``home.*``
  que estão no backup.
- Pula modelos cujas tabelas não existem localmente (modelos ``managed=False``
  que só existem no Postgres de produção, ex.: ``backgrounds`` e tabelas do bot).

Uso:
    python manage.py restore_ref_backup                 # usa o backup mais recente em ref/
    python manage.py restore_ref_backup --file <path>   # backup específico
    python manage.py restore_ref_backup --keep          # não apaga (faz merge)
"""

import glob
import json
import os

from django.apps import apps
from django.core import serializers
from django.core.management.base import BaseCommand
from django.db import connection

# Ordem de inserção: pais antes das filhas (evita problemas de FK).
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
    'home.tbmagia',
    'home.tbantecedente',
    'home.tbcronica',
    'home.tbjornal',
    'home.tbitemmundano',
    'home.tbitemmagico',
]

# Modelos que não devem ser restaurados (dependem de auth.User, que não está no
# backup de conteúdo) — evita erros de FK/coluna e preserva os usuários locais.
EXCLUDE_MODELS = {'home.userprofile'}


class Command(BaseCommand):
    help = 'Apaga o conteúdo local e restaura a partir do backup de produção mais recente em ref/.'

    def add_arguments(self, parser):
        parser.add_argument('--file', help='Caminho do backup JSON (default: mais recente em ref/).')
        parser.add_argument('--keep', action='store_true', help='Não apaga as tabelas antes (faz merge).')

    def _project_root(self):
        # .../home/management/commands/restore_ref_backup.py -> sobe 4 níveis
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    def _find_backup(self, explicit):
        if explicit:
            return explicit if os.path.exists(explicit) else None
        ref_dir = os.path.join(self._project_root(), 'ref')
        candidates = sorted(glob.glob(os.path.join(ref_dir, 'backup_site_*.json')))
        return candidates[-1] if candidates else None

    def handle(self, *args, **options):
        path = self._find_backup(options.get('file'))
        if not path:
            self.stderr.write(self.style.ERROR('Nenhum backup encontrado (ref/backup_site_*.json).'))
            return

        self.stdout.write(f'Backup: {path}')
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        home_records = [r for r in data if r['model'].startswith('home.')]

        # Mapeia model -> db_table e descobre quais tabelas existem localmente.
        existing_tables = set(connection.introspection.table_names())
        models_in_backup = []
        seen = set()
        for r in home_records:
            if r['model'] not in seen:
                seen.add(r['model'])
                models_in_backup.append(r['model'])

        skipped = []
        table_of = {}
        for ml in models_in_backup:
            if ml in EXCLUDE_MODELS:
                skipped.append(f'{ml} (excluído: depende de auth.User)')
                continue
            app_label, model_name = ml.split('.')
            try:
                table = apps.get_model(app_label, model_name)._meta.db_table
            except LookupError:
                skipped.append(f'{ml} (modelo inexistente)')
                continue
            if table not in existing_tables:
                skipped.append(f'{ml} -> tabela "{table}" ausente')
                continue
            table_of[ml] = table
        loadable = [ml for ml in models_in_backup if ml in table_of]

        def order_key(ml):
            return MODEL_ORDER.index(ml) if ml in MODEL_ORDER else len(MODEL_ORDER)
        loadable.sort(key=order_key)

        cursor = connection.cursor()
        if connection.vendor == 'postgresql':
            cursor.execute('SET CONSTRAINTS ALL DEFERRED')
        elif connection.vendor == 'sqlite':
            cursor.execute('PRAGMA foreign_keys = OFF')

        # 1) Apaga as tabelas que serão restauradas (substituição limpa).
        if not options['keep']:
            for ml in reversed(loadable):  # filhas antes dos pais
                table = table_of[ml]
                cursor.execute(f'DELETE FROM "{table}"')
            self.stdout.write(self.style.WARNING(f'Tabelas limpas: {len(loadable)}'))

        # 2) Recarrega na ordem de dependência.
        total_saved = total_err = 0
        errors = []
        for ml in loadable:
            recs = [r for r in home_records if r['model'] == ml]
            saved = err = 0
            for obj in serializers.deserialize('json', json.dumps(recs)):
                try:
                    obj.save()
                    saved += 1
                except Exception as exc:  # noqa: BLE001
                    err += 1
                    errors.append(f'{ml} pk={obj.object.pk}: {exc}')
            total_saved += saved
            total_err += err
            self.stdout.write(f'  {ml}: {saved} salvos' + (f', {err} erros' if err else ''))

        if connection.vendor == 'sqlite':
            cursor.execute('PRAGMA foreign_keys = ON')

        self.stdout.write(self.style.SUCCESS(f'\nRestauração concluída. Salvos: {total_saved} | erros: {total_err}'))
        if skipped:
            self.stdout.write(self.style.WARNING('Modelos pulados (sem tabela local):'))
            for s in skipped:
                self.stdout.write(f'  - {s}')
        if errors:
            self.stdout.write(self.style.WARNING(f'\nPrimeiros erros ({min(len(errors), 10)} de {len(errors)}):'))
            for e in errors[:10]:
                self.stdout.write(f'  - {e}')
