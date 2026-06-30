# -*- coding: utf-8 -*-
"""Restaura um backup completo do admin no banco local atual.

O backup completo vem da produção e pode ter campos antigos que já foram removidos
no código de dev (ex.: source/fonte). Este comando filtra campos inexistentes,
restaura auth + home, pula modelos/tabelas ausentes e é pensado para ambiente local.
"""
import json
import os
import ast
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.contrib.auth.models import Group, User
from django.core import serializers
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models.signals import post_save


DEFAULT_BACKUP = Path("ref/backup_completo_20260630_193250.json")
ALLOWED_APPS = {"auth", "home"}
EXCLUDED_MODELS = {
    "auth.permission",
    "contenttypes.contenttype",
    "sessions.session",
}
BOTQUEST_ARRAY_FIELDS = {"tags", "allowedRanks", "mandatoryPlayers", "highPriorityPlayers", "removedPlayers"}


def _label(model):
    return model._meta.label_lower


def _model_field_names(model):
    names = set()
    for field in model._meta.fields:
        names.add(field.name)
        names.add(field.attname)
    for field in model._meta.many_to_many:
        names.add(field.name)
    return names


def _table_exists(model, existing_tables):
    return model._meta.db_table in existing_tables


def _list_to_pg_array(value):
    if value in (None, ""):
        return "{}"
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            parsed = [value]
    else:
        parsed = value
    if not isinstance(parsed, (list, tuple)):
        parsed = [parsed]
    escaped = []
    for item in parsed:
        item = "" if item is None else str(item)
        item = item.replace("\\", "\\\\").replace('"', '\\"')
        escaped.append(f'"{item}"')
    return "{" + ",".join(escaped) + "}"


def _fix_legacy_values(model_label, fields):
    if model_label == "home.botquest":
        for field in BOTQUEST_ARRAY_FIELDS:
            if field in fields:
                fields[field] = _list_to_pg_array(fields[field])
    return fields


def _sort_models(models):
    preferred = [
        Group,
        User,
        "home.TbRaca",
        "home.TbEssencia",
        "home.TbAntecedente",
        "home.TbClasse",
        "home.TbOpcaojogo",
        "home.TbMagia",
        "home.TbTalento",
        "home.TbItemMagico",
        "home.TbItemMundano",
        "home.TbLinhagem",
        "home.TbSubclasse",
        "home.TbClassehabilidade",
        "home.TbRecursoclasse",
        "home.TbAcessoopcao",
        "home.TbTracoracial",
        "home.TbCondicao",
        "home.TbIdioma",
        "home.TbRegra",
        "home.TbRecompensaMestre",
        "home.TbRegiao",
        "home.TbTerritorio",
        "home.TbMapLayer",
        "home.TbMapMarker",
        "home.TbBestiario",
        "home.TbArmadilha",
        "home.UserProfile",
    ]
    rank = {}
    for idx, item in enumerate(preferred):
        if isinstance(item, str):
            app_label, model_name = item.split(".")
            try:
                item = apps.get_model(app_label, model_name)
            except LookupError:
                continue
        rank[_label(item)] = idx
    return sorted(models, key=lambda model: rank.get(_label(model), 10_000 + len(model._meta.parents)))


class Command(BaseCommand):
    help = "Restaura backup_completo_*.json no banco local, filtrando campos obsoletos."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_BACKUP), help="Arquivo backup_completo_*.json.")
        parser.add_argument("--confirm", default="", help="Digite RESTAURAR_LOCAL para gravar.")
        parser.add_argument("--no-local-backup", action="store_true", help="Nao gera dump local antes de limpar.")

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            raise CommandError(f"Backup nao encontrado: {path}")
        if opts["confirm"] != "RESTAURAR_LOCAL":
            raise CommandError("Confirme com --confirm RESTAURAR_LOCAL. Este comando limpa auth/home local.")

        with path.open(encoding="utf-8") as handle:
            raw_records = json.load(handle)
        if not isinstance(raw_records, list):
            raise CommandError("Backup invalido: esperado JSON list.")

        existing_tables = set(connection.introspection.table_names())
        by_model = defaultdict(list)
        skipped = Counter()
        stripped_fields = Counter()

        for record in raw_records:
            model_label = str(record.get("model", "")).lower()
            app_label = model_label.split(".", 1)[0] if "." in model_label else ""
            if app_label not in ALLOWED_APPS or model_label in EXCLUDED_MODELS:
                skipped[model_label or "?"] += 1
                continue
            try:
                model = apps.get_model(model_label)
            except LookupError:
                skipped[model_label] += 1
                continue
            if not _table_exists(model, existing_tables):
                skipped[model_label] += 1
                continue

            allowed = _model_field_names(model)
            fields = record.get("fields") or {}
            clean_fields = {key: value for key, value in fields.items() if key in allowed}
            clean_fields = _fix_legacy_values(model_label, clean_fields)
            for key in set(fields) - set(clean_fields):
                stripped_fields[f"{model_label}.{key}"] += 1
            clean_record = {
                "model": record["model"],
                "pk": record.get("pk"),
                "fields": clean_fields,
            }
            by_model[model_label].append(clean_record)

        restore_models = []
        for model_label in by_model:
            restore_models.append(apps.get_model(model_label))
        restore_models = _sort_models(restore_models)

        if not opts["no_local_backup"]:
            backup_dir = Path("backups")
            backup_dir.mkdir(exist_ok=True)
            out = backup_dir / f"local_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            labels = [model._meta.label for model in restore_models]
            with out.open("w", encoding="utf-8") as handle:
                call_command("dumpdata", *labels, indent=2, stdout=handle)
            self.stdout.write(f"Backup local antes do restore -> {out}")

        try:
            from home.models import create_user_profile
            post_save.disconnect(create_user_profile, sender=User)
        except Exception:
            pass

        saved = Counter()
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            elif connection.vendor == "sqlite":
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA foreign_keys = OFF")

            for model in reversed(restore_models):
                model.objects.all().delete()

            for model in restore_models:
                model_label = _label(model)
                records = by_model.get(model_label, [])
                if not records:
                    continue
                for deserialized in serializers.deserialize("json", json.dumps(records), handle_forward_references=True):
                    deserialized.save()
                    saved[model_label] += 1

            if connection.vendor == "sqlite":
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA foreign_keys = ON")

        if connection.vendor == "postgresql":
            from io import StringIO
            sql_blocks = []
            for app_label in ("auth", "home"):
                buf = StringIO()
                call_command("sqlsequencereset", app_label, stdout=buf)
                sql_blocks.append(buf.getvalue())
            with connection.cursor() as cursor:
                for block in sql_blocks:
                    for statement in block.splitlines():
                        statement = statement.strip().rstrip(";")
                        if statement and not statement.startswith("--"):
                            try:
                                cursor.execute(statement)
                            except Exception:
                                pass

        self.stdout.write(self.style.SUCCESS("Restore local concluido."))
        for model_label, count in saved.most_common():
            self.stdout.write(f"  {model_label}: {count}")
        if stripped_fields:
            self.stdout.write(self.style.WARNING("Campos obsoletos ignorados:"))
            for key, count in stripped_fields.most_common(20):
                self.stdout.write(f"  {key}: {count}")
        if skipped:
            self.stdout.write(self.style.WARNING("Registros/modelos pulados:"))
            for key, count in skipped.most_common(20):
                self.stdout.write(f"  {key}: {count}")
