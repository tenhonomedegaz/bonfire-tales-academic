from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand

from home.bot_mongo import BotMongoUnavailable, get_bot_database
from home.models import TbMapMarker, TbRegiao, TbTerritorio


class Command(BaseCommand):
    help = "Audita duplicatas comuns em regioes, territorios e marcadores sem alterar dados."

    def handle(self, *args, **options):
        self.stdout.write("SQLite")
        self._report_model("Regioes por nome", TbRegiao.objects.values_list("nome", flat=True))
        self._report_model("Regioes por slug", TbRegiao.objects.values_list("slug", flat=True))
        self._report_model("Territorios por nome", TbTerritorio.objects.values_list("nome", flat=True))
        self._report_model("Marcadores por nome", TbMapMarker.objects.values_list("nome", flat=True))

        self.stdout.write("")
        self.stdout.write("Mongo")
        try:
            db = get_bot_database()
        except BotMongoUnavailable as exc:
            self.stdout.write(self.style.WARNING(f"Mongo indisponivel: {exc}"))
            return

        site_collections = getattr(settings, "SITE_MONGO_COLLECTIONS", {})
        checks = [
            (site_collections.get("regions", "site_sqlite_TB_Regiao"), "Nome"),
            (site_collections.get("regions", "site_sqlite_TB_Regiao"), "Slug"),
            (site_collections.get("territories", "site_sqlite_TB_Territorio"), "Nome"),
            (site_collections.get("map_markers", "site_sqlite_TB_MapMarker"), "Nome"),
        ]
        for collection_name, field in checks:
            if collection_name not in db.list_collection_names():
                self.stdout.write(f"{collection_name}.{field}: collection ausente")
                continue
            values = [
                document.get(field)
                for document in db[collection_name].find({}, {field: 1})
                if document.get(field)
            ]
            self._report_model(f"{collection_name}.{field}", values)

    def _report_model(self, label, values):
        counter = Counter(str(value).strip().lower() for value in values if str(value).strip())
        duplicates = [(value, count) for value, count in counter.items() if count > 1]
        if not duplicates:
            self.stdout.write(f"{label}: sem duplicatas")
            return
        self.stdout.write(self.style.WARNING(f"{label}: {len(duplicates)} chaves duplicadas"))
        for value, count in sorted(duplicates)[:30]:
            self.stdout.write(f"  {value}: {count}")
