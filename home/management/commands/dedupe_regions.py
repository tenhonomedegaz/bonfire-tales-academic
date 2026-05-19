import re
import unicodedata
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from home.models import TbRegiao


LOCAL_SYNC_RE = re.compile(r"-local-\d{14,}$")


class Command(BaseCommand):
    help = "Remove duplicatas de regioes no PostgreSQL preservando a regiao canonica."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Aplica a limpeza. Sem isso roda em dry-run.")

    def handle(self, *args, **options):
        apply = options["apply"]
        deleted = self._dedupe_postgres(apply)
        mode = "aplicada" if apply else "simulada"
        self.stdout.write(self.style.SUCCESS(
            f"Limpeza {mode}: {deleted} duplicatas PostgreSQL."
        ))

    def _dedupe_postgres(self, apply):
        groups = defaultdict(list)
        for region in TbRegiao.objects.all().order_by("id_regiao"):
            groups[self._norm(region.nome)].append(region)

        to_delete = []
        for regions in groups.values():
            if len(regions) < 2:
                continue
            keep = self._choose_keep(regions)
            for region in regions:
                if region.pk != keep.pk and LOCAL_SYNC_RE.search(region.slug or ""):
                    to_delete.append(region.pk)
                    self.stdout.write(
                        f"PostgreSQL removeria {region.pk} {region.nome} ({region.slug}); "
                        f"manter {keep.pk} ({keep.slug})"
                    )

        if apply and to_delete:
            with transaction.atomic():
                TbRegiao.objects.filter(pk__in=to_delete).delete()
        return len(to_delete)

    def _choose_keep(self, regions):
        return sorted(
            regions,
            key=lambda region: (
                bool(LOCAL_SYNC_RE.search(region.slug or "")),
                -len(region.lore_markdown or ""),
                region.pk,
            ),
        )[0]

    def _norm(self, value):
        return re.sub(
            r"[\u0300-\u036f]",
            "",
            unicodedata.normalize("NFD", str(value or "")),
        ).lower().strip()
