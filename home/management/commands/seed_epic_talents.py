"""Importa somente talentos épicos com todos os efeitos já representados por tags."""

from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from home.epic_talent_catalog import epic_candidates
from home.models import TbTalento


class Command(BaseCommand):
    help = "Exibe candidatos épicos completos; --apply exige backup local explícito."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--backup", type=Path)
        parser.add_argument("--allow-partial-test", action="store_true")

    def handle(self, *args, **options):
        try:
            ready = epic_candidates()
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc
        slugs = [item["slug"] for item in ready]
        existing = list(TbTalento.objects.filter(slug__in=slugs))
        names = list(TbTalento.objects.filter(nome__in=[item["nome"] for item in ready]))
        for current in existing + names:
            expected = next((item for item in ready if item["slug"] == current.slug), None)
            if expected is None or expected["nome"] != current.nome or "epico" not in {
                tag.strip().casefold() for tag in (current.etiquetas_adicionais or "").split(",")
            }:
                raise CommandError(f"Colisão com conteúdo existente: {current.slug}")
        self.stdout.write(f"Candidatos completos: {len(ready)}/31; pendentes: {31-len(ready)}")
        if not options["apply"]:
            return
        db_name = str(connection.settings_dict["NAME"])
        local_postgres_test = (connection.vendor == "postgresql"
                               and db_name.startswith("test_")
                               and connection.settings_dict["HOST"] in {"127.0.0.1", "localhost"}
                               and str(connection.settings_dict["PORT"]) != "5432")
        isolated_test = local_postgres_test or (
            connection.vendor == "sqlite" and "mode=memory" in db_name)
        if len(ready) != 31 and not (options["allow_partial_test"] and isolated_test):
            raise CommandError("Carga parcial permitida somente no banco de teste isolado.")
        backup = options["backup"]
        if backup is None or backup.exists():
            raise CommandError("--apply exige --backup apontando para arquivo novo.")
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(serializers.serialize("json", existing, indent=2), encoding="utf-8")
        with transaction.atomic():
            for item in ready:
                slug = item.pop("slug")
                TbTalento.objects.update_or_create(slug=slug, defaults=item)
        self.stdout.write(self.style.SUCCESS(f"{len(ready)} talentos completos sincronizados."))
