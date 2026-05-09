from django.core.management.base import BaseCommand, CommandError

from home.bot_mongo import BotMongoUnavailable
from home.sqlite_mongo_sync import bidirectional_sync, mongo_to_sqlite


class Command(BaseCommand):
    help = "Puxa dados do Mongo para o SQLite local e salva backup generico das collections."

    def add_arguments(self, parser):
        parser.add_argument(
            "--namespace",
            default="site_sqlite",
            help="Prefixo das collections que representam tabelas SQLite. Padrao: site_sqlite.",
        )
        parser.add_argument(
            "--bidirectional",
            action="store_true",
            help="Depois de puxar Mongo -> SQLite, sobe SQLite -> Mongo para cruzar dados locais preservados.",
        )
        parser.add_argument(
            "--skip-generic-backup",
            action="store_true",
            help="Nao atualiza a tabela SQLite de backup generico das collections Mongo.",
        )
        parser.add_argument(
            "--confirm-merge",
            action="store_true",
            help="Confirma sincronizacao bidirecional, que pode preservar conflitos como duplicatas.",
        )

    def handle(self, *args, **options):
        namespace = options["namespace"].strip() or "site_sqlite"
        if options["bidirectional"] and not options["confirm_merge"]:
            self.stderr.write(self.style.ERROR(
                "Sincronizacao bidirecional bloqueada. Use --confirm-merge somente depois de backup e revisao de duplicatas."
            ))
            return

        try:
            if options["bidirectional"]:
                result = bidirectional_sync(namespace=namespace, backup=not options["skip_generic_backup"])
                pull_results = result["pull"]
                backup_total = result["backup_total"]
                push_results = result["push"]
            else:
                pull_results, backup_total = mongo_to_sqlite(
                    namespace=namespace,
                    backup=not options["skip_generic_backup"],
                )
                push_results = {}
        except BotMongoUnavailable as exc:
            raise CommandError(str(exc)) from exc

        total_inserted = 0
        total_updated = 0
        total_conflicts = 0

        for collection_name, stats in pull_results.items():
            if stats.get("skipped"):
                continue
            total_inserted += stats["inserted"]
            total_updated += stats["updated"]
            total_conflicts += stats["conflicts"]
            self.stdout.write(
                f"{collection_name} -> {stats['table']}: "
                f"{stats['inserted']} inseridos, {stats['updated']} atualizados, "
                f"{stats['conflicts']} conflitos preservados"
            )

        self.stdout.write(f"Backup generico de documentos Mongo: {backup_total} documentos.")

        if push_results:
            pushed = sum(push_results.values())
            self.stdout.write(f"SQLite cruzado de volta para Mongo: {pushed} registros enviados.")

        self.stdout.write(self.style.SUCCESS(
            "Mongo -> SQLite concluido: "
            f"{total_inserted} inseridos, {total_updated} atualizados, "
            f"{total_conflicts} conflitos preservados."
        ))
