import re
import unicodedata
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from home.bot_mongo import BotMongoUnavailable, get_bot_database
from home.models import TbRegiao


LOCAL_SYNC_RE = re.compile(r"-local-\d{14,}$")


class Command(BaseCommand):
    help = "Remove duplicatas de regioes geradas pela sync preservando a regiao canonica."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Aplica a limpeza. Sem isso roda em dry-run.")

    def handle(self, *args, **options):
        apply = options["apply"]
        sqlite_deleted = self._dedupe_sqlite(apply)
        mongo_deleted = self._dedupe_mongo(apply)
        mode = "aplicada" if apply else "simulada"
        self.stdout.write(self.style.SUCCESS(
            f"Limpeza {mode}: {sqlite_deleted} duplicatas SQLite, {mongo_deleted} duplicatas Mongo."
        ))

    def _dedupe_sqlite(self, apply):
        groups = defaultdict(list)
        for region in TbRegiao.objects.all().order_by("id_regiao"):
            groups[self._norm(region.nome)].append(region)

        to_delete = []
        for regions in groups.values():
            if len(regions) < 2:
                continue
            keep = self._choose_sqlite_keep(regions)
            for region in regions:
                if region.pk != keep.pk and LOCAL_SYNC_RE.search(region.slug or ""):
                    to_delete.append(region.pk)
                    self.stdout.write(f"SQLite removeria

        if apply and to_delete:
            with transaction.atomic():
                TbRegiao.objects.filter(pk__in=to_delete).delete()
        return len(to_delete)

    def _dedupe_mongo(self, apply):
        try:
            db = get_bot_database()
        except BotMongoUnavailable as exc:
            self.stdout.write(self.style.WARNING(f"Mongo indisponivel: {exc}"))
            return 0

        collection_name = getattr(settings, "SITE_MONGO_COLLECTIONS", {}).get("regions", "site_sqlite_TB_Regiao")
        if collection_name not in db.list_collection_names():
            return 0
        collection = db[collection_name]
        groups = defaultdict(list)
        for document in collection.find({}):
            name = document.get("Nome")
            if name:
                groups[self._norm(name)].append(document)

        ids_to_delete = []
        for documents in groups.values():
            if len(documents) < 2:
                continue
            keep = self._choose_mongo_keep(documents)
            for document in documents:
                slug = document.get("Slug") or ""
                if document.get("_id") != keep.get("_id") and LOCAL_SYNC_RE.search(slug):
                    ids_to_delete.append(document["_id"])
                    self.stdout.write(f"Mongo removeria {document['_id']} {document.get('Nome')} ({slug}); manter {keep.get('_id')} ({keep.get('Slug')})")

        if apply and ids_to_delete:
            collection.delete_many({"_id": {"$in": ids_to_delete}})
        return len(ids_to_delete)

    def _choose_sqlite_keep(self, regions):
        return sorted(
            regions,
            key=lambda region: (
                bool(LOCAL_SYNC_RE.search(region.slug or "")),
                -len(region.lore_markdown or ""),
                region.pk,
            ),
        )[0]

    def _choose_mongo_keep(self, documents):
        return sorted(
            documents,
            key=lambda document: (
                bool(LOCAL_SYNC_RE.search(document.get("Slug") or "")),
                -len(document.get("LoreMarkdown") or ""),
                str(document.get("_id")),
            ),
        )[0]

    def _norm(self, value):
        return re.sub(
            r"[\u0300-\u036f]",
            "",
            unicodedata.normalize("NFD", str(value or "")),
        ).lower().strip()
