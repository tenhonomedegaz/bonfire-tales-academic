from django.core.management.base import BaseCommand, CommandError

from home.bot_mongo import BotMongoUnavailable, get_bot_database
from home.sqlite_mongo_sync import mongo_safe_collection, sqlite_table_to_mongo, table_names


class Command(BaseCommand):
    help = "Copia todos os dados do SQLite do Django para collections Mongo com upsert."

    def add_arguments(self, parser):
        parser.add_argument(
            "--namespace",
            default="site_sqlite",
            help="Prefixo das collections criadas no Mongo. Padrao: site_sqlite.",
        )
        parser.add_argument(
            "--table",
            action="append",
            dest="tables",
            help="Copia apenas uma tabela especifica. Pode repetir.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria copiado sem gravar no Mongo.",
        )
        parser.add_argument(
            "--confirm-write",
            action="store_true",
            help="Confirma escrita real no Mongo. Sem isso o comando fica em dry-run.",
        )

    def handle(self, *args, **options):
        namespace = options["namespace"].strip() or "site_sqlite"
        selected_tables = set(options["tables"] or [])
        dry_run = options["dry_run"] or not options["confirm_write"]
        if dry_run and not options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "Modo seguro: dry-run ativado. Use --confirm-write para gravar no Mongo."
            ))

        names = table_names()
        if selected_tables:
            missing = selected_tables.difference(names)
            if missing:
                raise CommandError(f"Tabelas inexistentes no SQLite: {', '.join(sorted(missing))}")
            names = [table for table in names if table in selected_tables]

        total_tables = 0
        total_rows = 0

        try:
            get_bot_database()
        except BotMongoUnavailable as exc:
            raise CommandError(str(exc)) from exc

        for table_name in names:
            if dry_run:
                row_count = self._count_rows(table_name)
            else:
                row_count = sqlite_table_to_mongo(table_name, namespace=namespace)
            collection_name = mongo_safe_collection(namespace, table_name)
            self.stdout.write(
                f"{table_name} -> {collection_name}: {row_count} registros"
                + (" (dry-run)" if dry_run else "")
            )
            total_tables += 1
            total_rows += row_count

        self.stdout.write(self.style.SUCCESS(
            f"Sincronizacao concluida: {total_rows} registros em {total_tables} tabelas."
        ))

    def _count_rows(self, table_name):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            return cursor.fetchone()[0]
