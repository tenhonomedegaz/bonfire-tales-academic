# -*- coding: utf-8 -*-
"""Exporta um backup parcial para o restaurador do admin.

Uso principal: gerar um JSON pequeno com registros de conteúdo alterados na dev,
comparando o banco local atual contra um `backup_completo_*.json` recém-baixado
da produção. O arquivo resultante pode ser enviado pelo restaurador de backup
do admin, que faz `deserialize(...).save()`.

Por segurança, este exportador só inclui modelos com `slug` único. Para registros
existentes, usa o PK do backup da produção; para registros novos, usa `pk: null`.
Assim evita sobrescrever um PK que pertença a outro conteúdo na produção.
"""
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from home.deploy_sync import UPSERT_POR_SLUG
from home.management.commands.dump_conteudo import CONTENT_MODELS


DEFAULT_BACKUP = Path("ref/backup_completo_20260630_193250.json")
DEFAULT_OUTPUT_DIR = Path("ref/backups")


def _label(model):
    return model._meta.label_lower


def _has_slug(model):
    try:
        model._meta.get_field("slug")
    except Exception:
        return False
    return True


def _has_unique_slug_field(model):
    try:
        field = model._meta.get_field("slug")
    except Exception:
        return False
    return bool(getattr(field, "unique", False))


def _has_duplicate_slugs(model):
    seen = set()
    duplicates = set()
    for slug in model.objects.exclude(slug__isnull=True).values_list("slug", flat=True):
        if slug in seen:
            duplicates.add(slug)
        seen.add(slug)
    return sorted(duplicates)


def _model_field_names(model):
    names = set()
    for field in model._meta.fields:
        names.add(field.name)
        names.add(field.attname)
    for field in model._meta.many_to_many:
        names.add(field.name)
    return names


def _clean_record(record, model):
    allowed = _model_field_names(model)
    fields = record.get("fields") or {}
    return {
        "model": record["model"],
        "pk": record.get("pk"),
        "fields": {key: value for key, value in fields.items() if key in allowed},
    }


def _comparable(record):
    fields = dict(record.get("fields") or {})
    fields.pop("id", None)
    return fields


class Command(BaseCommand):
    help = "Gera JSON parcial para restaurador do admin com conteúdo alterado por slug."

    def add_arguments(self, parser):
        parser.add_argument("--base", default=str(DEFAULT_BACKUP), help="Backup completo fresco da produção.")
        parser.add_argument("--output", default="", help="Arquivo JSON de saída.")
        parser.add_argument("--report", default="", help="Relatório JSON/MD de saída.")
        parser.add_argument("--models", nargs="*", default=[], help="Modelos home.* ou nomes de classe. Vazio = conteúdo slugado.")

    def handle(self, *args, **opts):
        base_path = Path(opts["base"])
        if not base_path.exists():
            raise CommandError(f"Backup base nao encontrado: {base_path}")

        with base_path.open(encoding="utf-8") as handle:
            base_records_raw = json.load(handle)
        if not isinstance(base_records_raw, list):
            raise CommandError("Backup base invalido: esperado JSON list.")

        content_models = [apps.get_app_config("home").get_model(name) for name in CONTENT_MODELS]
        requested = {item.lower() for item in opts["models"]}
        if requested:
            selected = []
            for model in content_models:
                aliases = {_label(model), model.__name__.lower()}
                if aliases & requested:
                    selected.append(model)
            missing = requested - {alias for model in selected for alias in (_label(model), model.__name__.lower())}
            if missing:
                raise CommandError("Modelos nao encontrados no conteudo: %s" % ", ".join(sorted(missing)))
        else:
            upsert_names = set(UPSERT_POR_SLUG)
            selected = [
                model for model in content_models
                if _has_slug(model) and (model.__name__ in upsert_names or _has_unique_slug_field(model))
            ]

        skipped = []
        selected_slugged = []
        for model in selected:
            if not _has_slug(model):
                skipped.append(f"{model.__name__}: sem slug; use sync_conteudo/merge_conteudo")
                continue
            duplicates = _has_duplicate_slugs(model)
            if duplicates:
                skipped.append(
                    f"{model.__name__}: slug duplicado no banco local ({', '.join(duplicates[:10])}); "
                    "use sync_conteudo/merge_conteudo"
                )
                continue
            if _has_unique_slug_field(model) or model.__name__ in UPSERT_POR_SLUG:
                selected_slugged.append(model)
            else:
                skipped.append(f"{model.__name__}: slug sem regra segura; use sync_conteudo/merge_conteudo")

        by_model_slug = defaultdict(dict)
        stripped_fields = Counter()
        for record in base_records_raw:
            model_label = str(record.get("model", "")).lower()
            try:
                model = apps.get_model(model_label)
            except LookupError:
                continue
            if model not in selected_slugged:
                continue
            clean = _clean_record(record, model)
            for key in set((record.get("fields") or {})) - set(clean["fields"]):
                stripped_fields[f"{model_label}.{key}"] += 1
            slug = clean["fields"].get("slug")
            if slug:
                by_model_slug[model_label][slug] = clean

        output_records = []
        summary = {}
        deleted_in_dev = {}

        for model in selected_slugged:
            model_label = _label(model)
            current_records = serializers.serialize("python", model.objects.all().order_by("slug"))
            changed = new = same = 0
            current_slugs = set()

            for record in current_records:
                record["model"] = model_label
                clean_current = _clean_record(record, model)
                slug = clean_current["fields"].get("slug")
                if not slug:
                    continue
                current_slugs.add(slug)
                base_record = by_model_slug[model_label].get(slug)
                if not base_record:
                    clean_current["pk"] = None
                    output_records.append(clean_current)
                    new += 1
                    continue
                if _comparable(clean_current) != _comparable(base_record):
                    clean_current["pk"] = base_record["pk"]
                    output_records.append(clean_current)
                    changed += 1
                else:
                    same += 1

            deleted = sorted(set(by_model_slug[model_label]) - current_slugs)
            if deleted:
                deleted_in_dev[model.__name__] = deleted
            summary[model.__name__] = {
                "changed": changed,
                "new": new,
                "same": same,
                "deleted_not_in_patch": len(deleted),
            }

        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(opts["output"]) if opts["output"] else DEFAULT_OUTPUT_DIR / f"restore_patch_conteudo_{stamp}.json"
        report_path = Path(opts["report"]) if opts["report"] else output_path.with_suffix(".report.json")

        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(output_records, handle, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)

        report = {
            "base": str(base_path),
            "output": str(output_path),
            "records": len(output_records),
            "summary": summary,
            "skipped_models": skipped,
            "stripped_base_fields": dict(stripped_fields),
            "deleted_not_represented_by_restore": deleted_in_dev,
            "note": "Este patch faz update/insert pelo restaurador. Delecoes nao sao aplicadas por esse fluxo.",
        }
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)

        self.stdout.write(self.style.SUCCESS(f"Patch restore -> {output_path} ({len(output_records)} registros)"))
        self.stdout.write(f"Relatorio -> {report_path}")
        if skipped:
            self.stdout.write(self.style.WARNING("Modelos pulados:"))
            for item in skipped:
                self.stdout.write(f"  - {item}")
        if deleted_in_dev:
            self.stdout.write(self.style.WARNING("Delecoes detectadas, mas nao aplicaveis via restaurador:"))
            for model_name, slugs in deleted_in_dev.items():
                self.stdout.write(f"  - {model_name}: {', '.join(slugs[:20])}" + (" ..." if len(slugs) > 20 else ""))
