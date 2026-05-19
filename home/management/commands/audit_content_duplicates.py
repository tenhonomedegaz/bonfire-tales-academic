from collections import Counter

from django.core.management.base import BaseCommand

from home.models import TbMapMarker, TbRegiao, TbTerritorio


class Command(BaseCommand):
    help = "Audita duplicatas comuns em regioes, territorios e marcadores no PostgreSQL."

    def handle(self, *args, **options):
        self.stdout.write("PostgreSQL")
        self._report_model("Regioes por nome", TbRegiao.objects.values_list("nome", flat=True))
        self._report_model("Regioes por slug", TbRegiao.objects.values_list("slug", flat=True))
        self._report_model("Territorios por nome", TbTerritorio.objects.values_list("nome", flat=True))
        self._report_model("Marcadores por nome", TbMapMarker.objects.values_list("nome", flat=True))

    def _report_model(self, label, values):
        counter = Counter(str(value).strip().lower() for value in values if str(value).strip())
        duplicates = [(value, count) for value, count in counter.items() if count > 1]
        if not duplicates:
            self.stdout.write(f"{label}: sem duplicatas")
            return
        self.stdout.write(self.style.WARNING(f"{label}: {len(duplicates)} chaves duplicadas"))
        for value, count in sorted(duplicates)[:30]:
            self.stdout.write(f"  {value}: {count}")
