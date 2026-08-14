# -*- coding: utf-8 -*-
"""Gera o fixture consolidado seguro para o merge de conteudo do admin."""
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction

from home.deploy_sync import (
    CONTENT_MODELS,
    MEMORY_MODELS,
    OFFICIAL_REPLACE_MODELS,
    PRODUCTION_PRESERVED_MODELS,
    SUBSTITUI,
    UPSERT_POR_SLUG,
    sincronizar_conteudo,
)


FK_TARGETS = {
    "home.tblinhagem": {"id_raca": "home.tbraca"},
    "home.tbsubclasse": {"id_classe": "home.tbclasse"},
    "home.tbconquista": {"recompensa": "home.tbcosmetico"},
    "home.tbclassehabilidade": {
        "id_classe": "home.tbclasse",
        "id_subclasse": "home.tbsubclasse",
    },
    "home.tbrecursoclasse": {
        "id_classe": "home.tbclasse",
        "id_subclasse": "home.tbsubclasse",
    },
    "home.tbacessoopcao": {
        "id_opcao": "home.tbopcaojogo",
        "id_classe": "home.tbclasse",
        "id_subclasse": "home.tbsubclasse",
    },
    "home.tbtracoracial": {
        "id_raca": "home.tbraca",
        "id_linhagem": "home.tblinhagem",
        "id_essencia": "home.tbessencia",
    },
    "home.tbbestiario": {
        "companheiro_classe": "home.tbclasse",
        "companheiro_subclasse": "home.tbsubclasse",
    },
}

COMPOSITE_KEYS = {
    "home.tbclassehabilidade": (
        "id_classe", "id_subclasse", "niveladquirido", "nome"),
    "home.tbrecursoclasse": (
        "id_classe", "id_subclasse", "slug", "nivel"),
    "home.tbacessoopcao": (
        "id_opcao", "id_classe", "id_subclasse", "nivel_recebimento"),
    "home.tbtracoracial": (
        "id_raca", "id_linhagem", "id_essencia", "nivel_requisito",
        "talento_racial", "nome"),
}


def _json_bytes(value):
    text = json.dumps(
        value, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)
    return (text.replace("\r\n", "\n").replace("\n", "\r\n") + "\r\n").encode(
        "utf-8")


def _records_hash(records):
    raw = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        cls=DjangoJSONEncoder).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _pk_maps(records):
    maps = defaultdict(dict)
    for record in records:
        label = str(record.get("model", "")).lower()
        fields = record.get("fields") or {}
        value = fields.get("slug")
        if value is None:
            value = fields.get("nome") or record.get("pk")
        maps[label][str(record.get("pk"))] = value
    return maps


def _canonical_fields(record, pk_maps):
    label = str(record.get("model", "")).lower()
    fields = dict(record.get("fields") or {})
    for field, target in FK_TARGETS.get(label, {}).items():
        value = fields.get(field)
        if value is not None:
            fields[field] = pk_maps.get(target, {}).get(
                str(value), "pk:%s" % value)
    return fields


def _record_key(label, fields, pk):
    key_fields = COMPOSITE_KEYS.get(label)
    if key_fields:
        return "|".join(
            "%s=%s" % (field, fields.get(field)) for field in key_fields)
    if fields.get("slug"):
        return "slug:%s" % fields["slug"]
    return "pk:%s" % pk


def _index_records(records):
    pk_maps = _pk_maps(records)
    buckets = defaultdict(lambda: defaultdict(list))
    for record in records:
        label = str(record.get("model", "")).lower()
        fields = _canonical_fields(record, pk_maps)
        key = _record_key(label, fields, record.get("pk"))
        buckets[label][key].append(fields)

    indexed = defaultdict(dict)
    duplicates = defaultdict(dict)
    for label, model_buckets in buckets.items():
        for key, values in model_buckets.items():
            values.sort(key=lambda value: json.dumps(
                value, ensure_ascii=False, sort_keys=True,
                cls=DjangoJSONEncoder))
            if len(values) > 1:
                duplicates[label][key] = len(values)
            for index, value in enumerate(values, start=1):
                final_key = key if len(values) == 1 else "%s#%d" % (key, index)
                indexed[label][final_key] = value
    return indexed, duplicates


def _compare_baseline(path, records):
    if not path:
        return None
    baseline_path = Path(path)
    if not baseline_path.is_absolute():
        baseline_path = Path(settings.BASE_DIR) / baseline_path
    old_records = json.loads(baseline_path.read_text(encoding="utf-8"))
    records = json.loads(json.dumps(
        records, ensure_ascii=False, cls=DjangoJSONEncoder))
    compared_labels = {record["model"] for record in records}
    official_labels = {
        apps.get_app_config("home").get_model(name)._meta.label_lower
        for name in OFFICIAL_REPLACE_MODELS
    }
    old_records = [
        record for record in old_records
        if record.get("model") in compared_labels
        and not (
            record.get("model") in official_labels
            and (
                (record.get("fields") or {}).get("comunidade")
                or (record.get("fields") or {}).get("autor") is not None
            )
        )
    ]
    old_by_model, old_duplicates = _index_records(old_records)
    new_by_model, new_duplicates = _index_records(records)
    upsert_labels = {
        apps.get_app_config("home").get_model(name)._meta.label_lower
        for name in UPSERT_POR_SLUG
    }
    replace_labels = {
        apps.get_app_config("home").get_model(name)._meta.label_lower
        for name in SUBSTITUI
    }

    changed_models = {}
    for label in sorted(set(old_by_model) | set(new_by_model)):
        old = old_by_model[label]
        new = new_by_model[label]
        inserted = sorted(str(key) for key in set(new) - set(old))
        only_production = sorted(str(key) for key in set(old) - set(new))
        changed = []
        fields_changed = defaultdict(int)
        for key in sorted(set(old) & set(new), key=str):
            if old[key] == new[key]:
                continue
            changed.append(str(key))
            old_fields = old[key]
            new_fields = new[key]
            for field in set(old_fields) | set(new_fields):
                if old_fields.get(field) != new_fields.get(field):
                    fields_changed[field] += 1
        if inserted or only_production or changed:
            only_production_action = (
                "preservados_por_upsert"
                if label in upsert_labels else "removidos_por_substituicao"
            )
            changed_models[label] = {
                "alterados": len(changed),
                "inseridos": len(inserted),
                "somente_na_producao": len(only_production),
                "acao_somente_na_producao": only_production_action,
                "campos_alterados": dict(sorted(fields_changed.items())),
                "exemplos_alterados": changed[:20],
                "exemplos_inseridos": inserted[:20],
                "exemplos_somente_na_producao": only_production[:20],
            }
    return {
        "arquivo": str(path),
        "modelos_com_diferenca": changed_models,
        "chaves_duplicadas_producao": dict(old_duplicates),
        "chaves_duplicadas_dev": dict(new_duplicates),
        "politica": {
            "upsert": sorted(upsert_labels),
            "substituicao": sorted(replace_labels),
        },
    }


class Command(BaseCommand):
    help = (
        "Exporta o conteudo dev-vence para merge por slug, preservando mundo/mapa "
        "e toda memoria por ausencia.")

    def add_arguments(self, parser):
        parser.add_argument("--output", default="")
        parser.add_argument("--report", default="")
        parser.add_argument("--baseline", default="")
        parser.add_argument(
            "--rollback",
            default="ref/backup_completo_20260722_230533.json")

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path(options["output"]) if options["output"] else (
            root / "ref" / "backups" / f"restore_consolidado_{stamp}.json")
        report_path = Path(options["report"]) if options["report"] else (
            output.with_suffix(".report.json"))
        if not output.is_absolute():
            output = root / output
        if not report_path.is_absolute():
            report_path = root / report_path
        output.parent.mkdir(parents=True, exist_ok=True)

        model_names = list(CONTENT_MODELS)
        records = []
        by_label = defaultdict(list)
        table_report = {}
        for name in model_names:
            model = apps.get_app_config("home").get_model(name)
            queryset = model.objects.all()
            if name in OFFICIAL_REPLACE_MODELS:
                queryset = queryset.filter(comunidade=False, autor__isnull=True)
            queryset = queryset.order_by(model._meta.pk.name)
            model_records = serializers.serialize("python", queryset)
            for record in model_records:
                record["model"] = model._meta.label_lower
            records.extend(model_records)
            by_label[model._meta.label_lower].extend(model_records)
            count = len(model_records)
            table_report[model._meta.label_lower] = {
                "modelo": name,
                "acao": (
                    "upsert_por_slug"
                    if name in UPSERT_POR_SLUG else (
                        "substitui_oficiais_preserva_comunidade"
                        if name in OFFICIAL_REPLACE_MODELS else "substitui"
                    )),
                "linhas_no_arquivo": count,
                "contagem_esperada_pos_aplicacao": count,
                "sha256_registros": (
                    _records_hash(model_records) if count else None),
            }
            if not count:
                table_report[model._meta.label_lower]["obs"] = (
                    "0 no arquivo: modelo ausente no fixture e preservado na prod.")

        for name in PRODUCTION_PRESERVED_MODELS:
            model = apps.get_app_config("home").get_model(name)
            table_report[model._meta.label_lower] = {
                "modelo": name,
                "acao": "skip_preserva_prod",
                "linhas_no_arquivo": 0,
                "contagem_esperada_pos_aplicacao": model.objects.count(),
                "sha256_registros": None,
                "obs": "Fora do arquivo; mundo/wiki da producao e preservado.",
            }

        output_bytes = _json_bytes(records)
        output.write_bytes(output_bytes)
        fixture_text = output_bytes.decode("utf-8")
        deserialized = sum(
            1 for _obj in serializers.deserialize("json", fixture_text))
        if deserialized != len(records):
            raise RuntimeError(
                f"Deserialize incompleto: {deserialized}/{len(records)}")

        with transaction.atomic():
            merge_report = sincronizar_conteudo(fixture_text)
            transaction.set_rollback(True)
        if not merge_report["mem_ok"]:
            raise RuntimeError("A simulacao alterou a memoria.")
        if not merge_report["prod_preservada_ok"]:
            raise RuntimeError("A simulacao alterou mapa/wiki da producao.")
        if not merge_report["comunidade_ok"]:
            raise RuntimeError("A simulacao alterou conteudo comunitario.")

        labels_in_fixture = set(by_label)
        memory_labels = {
            apps.get_app_config("home").get_model(name)._meta.label_lower
            for name in MEMORY_MODELS
        }
        memory_overlap = sorted(labels_in_fixture & memory_labels)
        if memory_overlap:
            raise RuntimeError(
                "Modelos de memoria no fixture: " + ", ".join(memory_overlap))
        preserved_labels = {
            apps.get_app_config("home").get_model(name)._meta.label_lower
            for name in PRODUCTION_PRESERVED_MODELS
        }
        preserved_overlap = sorted(labels_in_fixture & preserved_labels)
        if preserved_overlap:
            raise RuntimeError(
                "Modelos de mapa/wiki no fixture: " + ", ".join(preserved_overlap))

        report = {
            "output": str(output.relative_to(root)),
            "gerado_em": stamp,
            "fonte": f"DEV ({connection.vendor}) via ORM",
            "aplicador_recomendado": (
                "admin console -> acao 'merge_conteudo' "
                "(home.deploy_sync.sincronizar_conteudo)"),
            "base_analise": options["baseline"] or None,
            "rollback": options["rollback"],
            "principio": (
                "CONTEUDO dev-vence; MAPA/MUNDO prod-vence; MEMORIA ausente."),
            "final_records": len(records),
            "sha256_arquivo": hashlib.sha256(output_bytes).hexdigest(),
            "comparacao_baseline": _compare_baseline(
                options["baseline"], records),
            "por_tabela": table_report,
            "validacao": {
                "deserialize_records": deserialized,
                "merge_mem_ok": merge_report["mem_ok"],
                "merge_prod_preservada_ok": merge_report["prod_preservada_ok"],
                "merge_comunidade_ok": merge_report["comunidade_ok"],
                "merge_pass2_skipped": [
                    name for name, _reason
                    in merge_report.get("pass2_skipped", [])
                ],
                "memory_models_in_fixture": memory_overlap,
                "production_preserved_models_in_fixture": preserved_overlap,
                "line_endings": "CRLF",
                "bom": True,
            },
        }
        report_path.write_bytes(_json_bytes(report))
        self.stdout.write(self.style.SUCCESS(
            f"Restore consolidado -> {output} ({len(records)} registros)"))
        self.stdout.write(f"Relatorio -> {report_path}")
        self.stdout.write(f"SHA-256 -> {report['sha256_arquivo']}")
