"""Validação e auditoria de revisões administráveis do DSL de tags."""
from __future__ import annotations

import hashlib
import json
import re

from django.apps import apps

from .library import Library
from .validator import ERROR, WARN, validate_tags_json


REQUIRED_GROUPS = (
    "token_forms", "ops", "primitives", "functions", "catalogs",
)
MECHANICAL_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*(?:\*)?$")
BLOCKING_USAGE_CODES = {
    "verbo-desconhecido",
    "escopo-desconhecido",
    "primitiva-nao-mecanica",
}


def canonical_library_json(raw):
    return json.dumps(
        raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def library_checksum(raw):
    return hashlib.sha256(canonical_library_json(raw).encode("utf-8")).hexdigest()


def parse_library_json(value):
    raw = json.loads(value) if isinstance(value, str) else value
    if not isinstance(raw, dict):
        raise ValueError("A raiz da biblioteca precisa ser um objeto JSON.")
    return raw


def _schema_diagnostics(raw):
    diagnostics = []
    for group in REQUIRED_GROUPS:
        if not isinstance(raw.get(group), dict):
            diagnostics.append((
                "ERROR", "%s precisa existir e ser um objeto JSON." % group,
            ))
    # Verbo executável e nome de operação são identificadores da linguagem.
    # Eventos/referências podem declarar caminhos e assinaturas estruturais
    # (ex.: magic.deal_dmg, ability{...}) e por isso não usam esta regex.
    for group in ("primitives", "ops"):
        values = raw.get(group) or {}
        if not isinstance(values, dict):
            continue
        for name in values:
            if name.startswith("_"):
                continue
            if not MECHANICAL_IDENTIFIER.fullmatch(name):
                diagnostics.append((
                    "ERROR",
                    "%s.%s: identificadores mecânicos aceitam somente snake_case; "
                    "hífen fica reservado para subtração." % (group, name),
                ))
    return diagnostics


def _iter_tag_rows():
    for model in apps.get_app_config("home").get_models():
        try:
            model._meta.get_field("tags_json")
        except Exception:
            continue
        for pk, tags in model.objects.values_list("pk", "tags_json").iterator(
                chunk_size=500):
            yield model._meta.label_lower, pk, tags


def _usage_errors(library):
    rows = tagged = tag_lines = 0
    errors = set()
    warnings = set()
    for model_label, pk, tags in _iter_tag_rows():
        rows += 1
        if not tags:
            continue
        tagged += 1
        tag_lines += len(tags) if isinstance(tags, list) else 1
        for diagnostic in validate_tags_json(
                tags, library, data=None, strict_names=True):
            signature = (
                model_label, str(pk), diagnostic.code,
                str(diagnostic.fragment or ""), str(diagnostic.message or ""),
            )
            if (diagnostic.level == ERROR
                    or diagnostic.code in BLOCKING_USAGE_CODES):
                errors.add(signature)
            elif diagnostic.level == WARN:
                warnings.add(signature)
    return {
        "rows": rows,
        "tagged": tagged,
        "tag_lines": tag_lines,
        "errors": errors,
        "warnings": warnings,
    }


def _diagnostic_payload(signature):
    model_label, pk, code, fragment, message = signature
    return {
        "model": model_label,
        "pk": pk,
        "code": code,
        "fragment": fragment,
        "message": message,
    }


def audit_library(raw, *, baseline=None, scan_usage=True):
    """Retorna um relatório serializável e bloqueia apenas regressões.

    O banco pode conter resíduos anteriores sem relação com a edição. Por isso
    uma revisão é recusada quando cria erros novos, não por erros preexistentes.
    """
    raw = parse_library_json(raw)
    candidate = Library(raw=raw, prefer_db=False)
    lint = _schema_diagnostics(raw) + list(candidate.lint())
    lint_errors = [message for level, message in lint if level == "ERROR"]
    result = {
        "valid": not lint_errors,
        "checksum": library_checksum(raw),
        "source_version": str((raw.get("meta") or {}).get("versao") or ""),
        "lint": [
            {"level": level, "message": message} for level, message in lint
        ],
        "usage": {
            "scanned": False,
            "rows": 0,
            "tagged": 0,
            "tag_lines": 0,
            "errors": 0,
            "warnings": 0,
            "new_errors": 0,
            "new_error_examples": [],
        },
    }
    if not scan_usage or lint_errors:
        return result

    candidate_usage = _usage_errors(candidate)
    baseline_library = baseline or Library()
    baseline_usage = _usage_errors(baseline_library)
    new_errors = sorted(candidate_usage["errors"] - baseline_usage["errors"])
    result["usage"] = {
        "scanned": True,
        "rows": candidate_usage["rows"],
        "tagged": candidate_usage["tagged"],
        "tag_lines": candidate_usage["tag_lines"],
        "errors": len(candidate_usage["errors"]),
        "warnings": len(candidate_usage["warnings"]),
        "baseline_errors": len(baseline_usage["errors"]),
        "new_errors": len(new_errors),
        "new_error_examples": [
            _diagnostic_payload(item) for item in new_errors[:40]
        ],
    }
    result["valid"] = result["valid"] and not new_errors
    return result
