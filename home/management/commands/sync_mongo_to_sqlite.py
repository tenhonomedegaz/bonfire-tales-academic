from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Desativado: o projeto agora usa PostgreSQL como banco definitivo."

    def handle(self, *args, **options):
        raise CommandError(
            "sync_mongo_to_sqlite foi desativado. O site nao usa mais SQLite/Mongo como fonte de dados; use PostgreSQL."
        )
