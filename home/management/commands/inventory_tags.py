# -*- coding: utf-8 -*-
"""Exporta o vocabulario completo do DSL e sua frequencia no banco."""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand

from home.management.commands.validate_tags import _iter_models
from home.tag_engine import Library


_WORD = re.compile(r"(?<![a-z0-9_])[a-z_][a-z0-9_]*(?![a-z0-9_])", re.I)


def _public_items(value):
    if not isinstance(value, dict):
        return []
    return [(key, item) for key, item in value.items()
            if not str(key).startswith("_")]


def _doc(value):
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    for key in ("doc", "descricao", "description"):
        if value.get(key):
            return str(value[key])
    return ""


def _detail(value):
    if not isinstance(value, dict):
        return ""
    bits = []
    for key in ("forma", "op", "target", "tipo", "lang", "fonte", "fonte_db"):
        if value.get(key) is not None:
            bits.append("%s=%s" % (key, value[key]))
    return "; ".join(bits)


def _row(group, name, value, usage, models):
    return {
        "grupo": group,
        "nome": str(name),
        "usos": usage.get(str(name), 0),
        "modelos": ", ".join(sorted(models.get(str(name), set()))),
        "detalhes": _detail(value),
        "documentacao": _doc(value),
    }


def _collect_rows(library, usage, models):
    raw = library.raw
    rows = []
    simple_groups = (
        "ops", "references", "selectors", "conditions", "events",
        "primitives", "escolhas", "definicoes_inline", "tags_de_classe",
        "recursos_universais",
    )
    for group in simple_groups:
        for name, value in _public_items(raw.get(group)):
            rows.append(_row(group, name, value, usage, models))

    functions = raw.get("functions") or {}
    for name, value in _public_items(functions):
        if name in {"operadores", "variaveis_de_formula", "limiters"}:
            continue
        rows.append(_row("functions", name, value, usage, models))
    for nested, label in (
        ("operadores", "functions.operadores"),
        ("variaveis_de_formula", "functions.variaveis_de_formula"),
        ("limiters", "functions.limiters"),
    ):
        for name, value in _public_items(functions.get(nested)):
            rows.append(_row(label, name, value, usage, models))

    for subgroup, values in _public_items(raw.get("scopes")):
        for name, value in _public_items(values):
            rows.append(_row("scopes.%s" % subgroup, name, value, usage, models))

    for catalog, info in _public_items(raw.get("catalogs")):
        rows.append(_row("catalogs", catalog, info, usage, models))
        if isinstance(info, dict):
            for value in info.get("valores") or []:
                rows.append(_row(
                    "catalogs.%s.valores" % catalog,
                    value,
                    {"doc": "Valor fechado do catalogo %s." % catalog},
                    usage,
                    models,
                ))

    for group in ("forbidden_heads", "forbidden_operands"):
        for name, value in _public_items(raw.get(group)):
            rows.append(_row(group, name, value, usage, models))

    registered = set(library.primitives)
    for prefix in library.wildcards:
        for name in sorted(
                word for word in usage
                if word.startswith(prefix) and word not in registered):
            rows.append(_row(
                "wildcard_usage.%s*" % prefix,
                name,
                {
                    "forma": "observada",
                    "doc": (
                        "Expansao real aceita pela familia wildcard; revisar se "
                        "a negacao e composicional ou especifica demais."
                    ),
                },
                usage,
                models,
            ))

    return sorted(rows, key=lambda item: (item["grupo"], item["nome"]))


class Command(BaseCommand):
    help = "Gera Markdown e CSV com todo o vocabulario cadastrado do DSL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="docs/agentes/listagem_tags_cadastradas.md",
            help="Caminho do relatorio Markdown.",
        )

    def handle(self, *args, **options):
        library = Library()
        usage = Counter()
        models = defaultdict(set)
        records = tagged = tag_lines = 0
        model_specs = list(_iter_models()) + list(_iter_models("item-magico"))

        for model_key, importer in model_specs:
            for _label, tags in importer():
                records += 1
                if not tags:
                    continue
                tagged += 1
                lines = tags if isinstance(tags, list) else [tags]
                for line in lines:
                    if not isinstance(line, str):
                        continue
                    tag_lines += 1
                    words = [word.lower() for word in _WORD.findall(line)]
                    usage.update(words)
                    for word in set(words):
                        models[word].add(model_key)

        rows = _collect_rows(library, usage, models)
        output = Path(options["output"])
        if not output.is_absolute():
            output = Path.cwd() / output
        output.parent.mkdir(parents=True, exist_ok=True)
        csv_path = output.with_suffix(".csv")

        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=(
                "grupo", "nome", "usos", "modelos", "detalhes", "documentacao",
            ))
            writer.writeheader()
            writer.writerows(rows)

        groups = Counter(row["grupo"] for row in rows)
        invalid = [
            row for row in rows
            if "-" in row["nome"]
            and row["grupo"] not in {"forbidden_heads", "forbidden_operands"}
        ]
        unused = [
            row for row in rows
            if row["usos"] == 0
            and row["grupo"] in {
                "primitives", "references", "selectors", "conditions",
                "events", "functions", "tags_de_classe",
            }
        ]
        forbidden_used = [
            row for row in rows
            if row["grupo"] in {"forbidden_heads", "forbidden_operands"}
            and row["usos"]
        ]

        lines = [
            "# Listagem completa das tags cadastradas",
            "",
            "Gerado diretamente de `home/tag_library.json` e cruzado com o banco local.",
            "A contagem e textual e inclui classes, habilidades, talentos, opcoes,",
            "tracos raciais, antecedentes, magias, bestiario e itens mundanos/magicos.",
            "",
            "## Resumo",
            "",
            "- Registros lidos: %d" % records,
            "- Registros com tags: %d" % tagged,
            "- Linhas de formula: %d" % tag_lines,
            "- Entradas cadastradas: %d" % len(rows),
            "- Nomes ativos com hifen: %d" % len(invalid),
            "- Termos proibidos ainda usados: %d" % len(forbidden_used),
            "- Entradas estruturais sem uso atual: %d" % len(unused),
            "",
            "## Grupos",
            "",
            "| Grupo | Entradas |",
            "|---|---:|",
        ]
        lines.extend(
            "| `%s` | %d |" % (group, count)
            for group, count in sorted(groups.items())
        )

        lines.extend(["", "## Vocabulario", ""])
        current = None
        for row in rows:
            if row["grupo"] != current:
                current = row["grupo"]
                lines.extend([
                    "### `%s`" % current,
                    "",
                    "| Nome | Usos | Modelos | Contrato | Documentacao |",
                    "|---|---:|---|---|---|",
                ])
            cells = [
                "`%s`" % row["nome"],
                str(row["usos"]),
                row["modelos"] or "-",
                row["detalhes"] or "-",
                row["documentacao"] or "-",
            ]
            cells = [str(cell).replace("|", "\\|").replace("\n", " ")
                     for cell in cells]
            lines.append("| %s |" % " | ".join(cells))

        lines.extend(["", "## Auditoria automatica", ""])
        if invalid:
            lines.append("### Nomes ativos com hifen")
            lines.append("")
            lines.extend("- `%s.%s`" % (row["grupo"], row["nome"])
                         for row in invalid)
        else:
            lines.append("- Nenhum nome ativo usa hifen.")
        if forbidden_used:
            lines.append("- Termos proibidos ainda encontrados: %s." % ", ".join(
                "`%s` (%d)" % (row["nome"], row["usos"])
                for row in forbidden_used
            ))
        else:
            lines.append("- Nenhum termo proibido permanece nas formulas.")
        lines.extend([
            "- O CSV espelho esta em `%s`." % csv_path.as_posix(),
            "",
        ])

        output.write_text("\n".join(lines), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(
            "Inventario gerado: %s (%d entradas)" % (output, len(rows))))
        self.stdout.write("CSV: %s" % csv_path)
