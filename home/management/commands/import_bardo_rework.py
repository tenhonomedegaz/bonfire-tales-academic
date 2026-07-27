# -*- coding: utf-8 -*-
"""Importa, de forma isolada, o rework do Bardo do HTML de referencia."""

import copy
import re
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from home.bardo_rework_data import (
    ACCORDS,
    BAILADOS,
    BASE_TAGS,
    CLASS_METADATA,
    CLASS_TAGS,
    SUBCLASS_TAGS,
    UNTAGGED_ALLOWED,
)


_BLOCKS = {"p", "ul", "ol", "table", "blockquote"}
_OPTION_SUFFIX_RE = re.compile(
    r"\s+\((?:Aliado|Adversário|Especial)\)\s*$", re.IGNORECASE)


def _source_path(root):
    matches = sorted((root / "ref" / "Classes Reworkadas").glob("Bardo*.html"))
    if len(matches) != 1:
        raise CommandError(
            "Esperado exatamente um HTML do Bardo em ref/Classes Reworkadas; "
            f"encontrados: {len(matches)}")
    return matches[0]


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _section_fragment(heading, stop_names):
    """Clona os irmaos posteriores ate o proximo heading relevante."""
    soup = BeautifulSoup("<div></div>", "html.parser")
    box = soup.div
    for node in heading.next_siblings:
        if isinstance(node, Tag) and node.name in stop_names:
            break
        if isinstance(node, (Tag, NavigableString)):
            box.append(copy.copy(node))
    return box


def _extract_accord_descriptions(source, parser):
    soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
    headings = soup.find_all("h2")
    accord_h2 = next(
        (h for h in headings if _clean(h.get_text(" ", strip=True)) == "Acordes de Poder"),
        None,
    )
    if accord_h2 is None:
        raise CommandError("Secao 'Acordes de Poder' nao encontrada no HTML.")

    descriptions = {}
    current_grade = None
    for heading in accord_h2.find_all_next(["h2", "h4", "h5"]):
        if heading is not accord_h2 and heading.name == "h2":
            break
        label = _clean(heading.get_text(" ", strip=True))
        if heading.name == "h4":
            match = re.search(r"Grau\s+(\d+)", label, re.IGNORECASE)
            current_grade = int(match.group(1)) if match else None
            continue
        if heading.name != "h5":
            continue
        name = _OPTION_SUFFIX_RE.sub("", label)
        fragment = _section_fragment(heading, {"h2", "h4", "h5"})
        description = parser.to_markdown(fragment).strip()
        descriptions[name] = {
            "descricao": description,
            "grau": current_grade,
        }
    return descriptions


def _extract_markdown_options(markdown):
    pattern = re.compile(
        r"^#####\s+(.+?)\s*$\n(.*?)(?=^#####\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    return {
        _clean(match.group(1)): match.group(2).strip()
        for match in pattern.finditer(markdown or "")
    }


def _extract_subclass_intros(source, parser):
    soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
    result = {}
    slug_map = {
        "Colégio do Conselho": "colegio-do-conselho",
        "Colégio da Conspiração": "colegio-da-conspiracao",
        "Colégio da Criação": "colegio-da-criacao",
        "Colégio da Dança": "colegio-da-danca",
        "Colégio dos Espíritos": "colegio-dos-espiritos",
        "Colégio do Fascínio": "colegio-do-fascinio",
        "Colégio das Lâminas": "colegio-das-laminas",
        "Colégio Skald": "colegio-skald",
    }
    seen = set()
    for heading in soup.find_all("h2"):
        label = _clean(heading.get_text(" ", strip=True))
        sub_slug = slug_map.get(label)
        if not sub_slug or sub_slug in seen:
            continue
        seen.add(sub_slug)
        parts = []
        current = parser.next_element_skipping_descendants(heading)
        while current:
            if isinstance(current, Tag):
                if current.name in {"h1", "h2", "h3", "hr"}:
                    break
                if current.name in _BLOCKS:
                    parts.append(parser.to_markdown(current))
                    current = parser.next_element_skipping_descendants(current)
                    continue
                current = current.next_element
            else:
                current = current.next_element
        intro = re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip()
        if intro:
            result[sub_slug] = intro
    return result


def _compress_progression(source):
    soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
    table = soup.find("table")
    if table is None:
        raise CommandError("Tabela de progressao do Bardo nao encontrada.")
    rows = table.find_all("tr")
    headers = [_clean(cell.get_text(" ", strip=True))
               for cell in rows[0].find_all(["th", "td"])]
    if not headers:
        raise CommandError("Tabela de progressao sem cabecalhos.")

    characteristic_index = next(
        (index for index, header in enumerate(headers)
         if slugify(header) in {
             "caracteristicas", "caracteristicas-de-classe",
             "habilidades", "habilidades-de-classe",
         }),
        None,
    )
    series = {index: [] for index in range(len(headers))
              if index not in {0, characteristic_index}}
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < len(headers):
            continue
        match = re.search(r"\d+", _clean(cells[0].get_text(" ", strip=True)))
        if not match:
            continue
        level = int(match.group())
        for index in series:
            value = _clean(cells[index].get_text(" ", strip=True))
            if value and value not in {"—", "-", "–"}:
                series[index].append((level, value))

    choice_slugs = {"acordes", "truques", "magias-conhecidas"}
    resources = []
    for index, values in series.items():
        if not values:
            continue
        changes = {}
        previous = object()
        for level, value in values:
            if value != previous:
                changes[str(level)] = value
                previous = value
        name = headers[index]
        resource_slug = slugify(name)
        resources.append({
            "nome": name,
            "slug": resource_slug,
            "nivel": values[0][0],
            "valor": values[0][1],
            "valores_json": changes,
            "tipo": "choice" if resource_slug in choice_slugs else "table-only",
        })
    return resources


def _append_options_widget(ability, label):
    marker = f"::options={label}"
    if marker in (ability.descricao or ""):
        return
    ability.descricao = (
        (ability.descricao or "").rstrip()
        + f"\n\n::click {label}\n{marker}\n::endclick"
    )


class Command(BaseCommand):
    help = (
        "Importa somente o Bardo reworkado. O padrao e dry-run; "
        "use --apply para persistir."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Persiste a importacao transacional.")

    def handle(self, *args, **options):
        from home.models import (
            TbAcessoopcao,
            TbClasse,
            TbClassehabilidade,
            TbOpcaojogo,
            TbRecursoclasse,
            TbSubclasse,
        )
        from scripts import parse_classes_html as legacy_parser

        root = Path(settings.BASE_DIR)
        source = _source_path(root)
        resources = _compress_progression(source)
        accord_descriptions = _extract_accord_descriptions(
            source, legacy_parser)
        self.stdout.write(
            f"Fonte: {source.relative_to(root)} | "
            f"recursos={len(resources)} | acordes={len(accord_descriptions)}")

        missing_accords = sorted(set(ACCORDS) - set(accord_descriptions))
        extra_accords = sorted(set(accord_descriptions) - set(ACCORDS))
        if missing_accords or extra_accords:
            raise CommandError(
                f"Divergencia nos Acordes. faltando={missing_accords}; "
                f"extras={extra_accords}")

        classe = TbClasse.objects.get(slug="bardo")
        current = TbClassehabilidade.objects.filter(id_classe=classe).count()
        self.stdout.write(
            f"Banco atual: habilidades={current}, "
            f"recursos={TbRecursoclasse.objects.filter(id_classe=classe).count()}")
        if not options["apply"]:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN: nenhuma alteracao persistida."))
            return

        scratch = root / "scratch" / "bardo_rework_import"
        scratch.mkdir(parents=True, exist_ok=True)
        old_classes_dir = legacy_parser.classes_dir
        old_output_dir = legacy_parser.output_imports_dir
        try:
            with transaction.atomic():
                bardo_access_scope = (
                    Q(id_classe=classe)
                    | Q(id_subclasse__id_classe=classe)
                )
                previous_accesses = TbAcessoopcao.objects.filter(
                    bardo_access_scope)
                previous_option_ids = set(
                    previous_accesses.values_list("id_opcao_id", flat=True))
                removed_access_count = previous_accesses.count()
                previous_accesses.delete()

                legacy_parser.classes_dir = str(source.parent)
                legacy_parser.output_imports_dir = str(scratch)
                if not legacy_parser.parse_class_html_file(source.name):
                    raise CommandError("O parser legado nao conseguiu ler o Bardo.")

                classe.refresh_from_db()
                for field, value in CLASS_METADATA.items():
                    setattr(classe, field, value)
                classe.tags_json = CLASS_TAGS
                classe.save(update_fields=[*CLASS_METADATA.keys(), "tags_json"])

                placeholders = TbClassehabilidade.objects.filter(
                    id_classe=classe,
                    id_subclasse__isnull=True,
                    nome="Característica de Colégio",
                    table_only=True,
                )
                placeholder_count = placeholders.count()
                placeholders.delete()

                abilities = list(
                    TbClassehabilidade.objects.filter(id_classe=classe)
                    .select_related("id_subclasse")
                    .order_by("id_subclasse__slug", "niveladquirido", "nome")
                )
                missing_tags = []
                for ability in abilities:
                    sub_slug = (
                        ability.id_subclasse.slug
                        if ability.id_subclasse_id else None
                    )
                    key = (sub_slug, ability.nome)
                    if sub_slug is None:
                        tags = BASE_TAGS.get(ability.nome)
                    else:
                        tags = SUBCLASS_TAGS.get(key)
                    if tags is None:
                        missing_tags.append(key)
                        continue
                    if not tags and key not in UNTAGGED_ALLOWED:
                        missing_tags.append(key)
                        continue
                    ability.tags_json = list(tags)
                    if ability.nome == "Acordes de Poder":
                        _append_options_widget(ability, "Acordes de Poder")
                    if ability.nome == "Bailados de Combate":
                        _append_options_widget(ability, "Bailados de Combate")
                    ability.save(update_fields=["tags_json", "descricao"])
                if missing_tags:
                    raise CommandError(
                        "Habilidades sem mapeamento mecanico: "
                        + ", ".join(f"{sub or 'base'}:{name}"
                                    for sub, name in missing_tags))

                intros = _extract_subclass_intros(source, legacy_parser)
                subclasses = {
                    sub.slug: sub
                    for sub in TbSubclasse.objects.filter(id_classe=classe)
                }
                if set(intros) != set(subclasses):
                    raise CommandError(
                        "Subclasses divergentes entre fonte e banco. "
                        f"fonte={sorted(intros)} banco={sorted(subclasses)}")
                for sub_slug, intro in intros.items():
                    sub = subclasses[sub_slug]
                    sub.tagline = intro
                    sub.save(update_fields=["tagline"])

                TbRecursoclasse.objects.filter(id_classe=classe).delete()
                for resource in resources:
                    TbRecursoclasse.objects.create(
                        id_classe=classe,
                        id_subclasse=None,
                        reset=None,
                        **resource,
                    )

                dance_ability = next(
                    ability for ability in abilities
                    if ability.id_subclasse_id
                    and ability.id_subclasse.slug == "colegio-da-danca"
                    and ability.nome == "Bailados de Combate"
                )
                dance_descriptions = _extract_markdown_options(
                    dance_ability.descricao)
                missing_dances = sorted(set(BAILADOS) - set(dance_descriptions))
                if missing_dances:
                    raise CommandError(
                        "Bailados ausentes na descricao: "
                        + ", ".join(missing_dances))

                option_specs = []
                for name, (level, tags) in ACCORDS.items():
                    detail = accord_descriptions[name]
                    grade = detail["grau"]
                    expected_grade = {2: 1, 6: 2, 10: 3, 18: 4}[level]
                    if grade != expected_grade:
                        raise CommandError(
                            f"Grau inesperado para {name}: {grade}")
                    option_specs.append({
                        "nome": name,
                        "tipo": "Acordes de Poder",
                        "descricao": detail["descricao"],
                        "pre_requisito": f"Bardo nível {level}",
                        "etiquetas_adicionais": f"Grau {grade}",
                        "tags_json": tags,
                        "nivel": level,
                        "subclasse": None,
                    })
                dance_sub = subclasses["colegio-da-danca"]
                for name, tags in BAILADOS.items():
                    option_specs.append({
                        "nome": name,
                        "tipo": "Bailados de Combate",
                        "descricao": dance_descriptions[name],
                        "pre_requisito": "Colégio da Dança",
                        "etiquetas_adicionais": "Bailado",
                        "tags_json": tags,
                        "nivel": 3,
                        "subclasse": dance_sub,
                    })

                expected_slugs = set()
                expected_accesses = set()
                for spec in option_specs:
                    option_slug = slugify(spec["nome"])
                    expected_slugs.add(option_slug)
                    option, _created = TbOpcaojogo.objects.update_or_create(
                        slug=option_slug,
                        defaults={
                            "nome": spec["nome"],
                            "tipo": spec["tipo"],
                            "descricao": spec["descricao"],
                            "pre_requisito": spec["pre_requisito"],
                            "etiquetas_adicionais": spec[
                                "etiquetas_adicionais"],
                            "tags_json": spec["tags_json"],
                        },
                    )
                    TbAcessoopcao.objects.filter(
                        id_opcao=option,
                        id_classe=classe,
                    ).delete()
                    access = TbAcessoopcao.objects.create(
                        id_opcao=option,
                        id_classe=classe,
                        id_subclasse=spec["subclasse"],
                        nivel_recebimento=spec["nivel"],
                    )
                    expected_accesses.add((
                        access.id_opcao.slug,
                        access.id_subclasse.slug
                        if access.id_subclasse_id else None,
                        access.nivel_recebimento,
                    ))

                all_bardo_accesses = TbAcessoopcao.objects.filter(
                    bardo_access_scope).select_related(
                        "id_opcao", "id_subclasse")
                extra_accesses = all_bardo_accesses.exclude(
                    id_opcao__slug__in=expected_slugs)
                extra_option_ids = set(
                    extra_accesses.values_list("id_opcao_id", flat=True))
                removed_extra_access_count = extra_accesses.count()
                extra_accesses.delete()

                stale_specific_options = TbOpcaojogo.objects.filter(
                    tipo__in=["Acordes de Poder", "Bailados de Combate"]
                ).exclude(slug__in=expected_slugs)
                stale_specific_ids = set(
                    stale_specific_options.values_list("id_opcao", flat=True))
                foreign_stale_accesses = TbAcessoopcao.objects.filter(
                    id_opcao_id__in=stale_specific_ids,
                ).exclude(bardo_access_scope)
                if foreign_stale_accesses.exists():
                    stale_names = list(
                        stale_specific_options.values_list("nome", flat=True))
                    raise CommandError(
                        "Opcoes antigas do Bardo ainda usadas por outra classe: "
                        + ", ".join(stale_names))
                TbAcessoopcao.objects.filter(
                    id_opcao_id__in=stale_specific_ids).delete()

                cleanup_option_ids = (
                    previous_option_ids
                    | extra_option_ids
                    | stale_specific_ids
                )
                orphan_options = TbOpcaojogo.objects.filter(
                    id_opcao__in=cleanup_option_ids,
                ).exclude(
                    slug__in=expected_slugs,
                ).exclude(
                    tbacessoopcao__isnull=False,
                )
                removed_orphan_option_count = orphan_options.count()
                orphan_options.delete()

                final_accesses = set(
                    TbAcessoopcao.objects.filter(
                        bardo_access_scope,
                    ).select_related(
                        "id_opcao", "id_subclasse",
                    ).values_list(
                        "id_opcao__slug",
                        "id_subclasse__slug",
                        "nivel_recebimento",
                    )
                )
                if final_accesses != expected_accesses:
                    missing = sorted(
                        expected_accesses - final_accesses, key=str)
                    extra = sorted(
                        final_accesses - expected_accesses, key=str)
                    raise CommandError(
                        "Acessos de opcao divergentes apos limpeza. "
                        f"faltando={missing}; extras={extra}")

                final_specific_slugs = set(
                    TbOpcaojogo.objects.filter(
                        tipo__in=[
                            "Acordes de Poder",
                            "Bailados de Combate",
                        ],
                    ).values_list("slug", flat=True)
                )
                if final_specific_slugs != expected_slugs:
                    raise CommandError(
                        "Catalogo de opcoes do Bardo divergente apos limpeza. "
                        f"esperado={sorted(expected_slugs)}; "
                        f"obtido={sorted(final_specific_slugs)}")

                final_count = len(abilities)
                if final_count != 78:
                    raise CommandError(
                        f"Esperadas 78 habilidades finais; obtidas {final_count}.")

            self.stdout.write(self.style.SUCCESS(
                "Bardo reworkado importado: "
                f"habilidades={final_count}, recursos={len(resources)}, "
                f"opcoes={len(option_specs)}, "
                f"placeholders_removidos={placeholder_count}, "
                f"acessos_antigos_removidos={removed_access_count}, "
                f"acessos_extras_removidos={removed_extra_access_count}, "
                f"opcoes_orfas_removidas={removed_orphan_option_count}."))
        finally:
            legacy_parser.classes_dir = old_classes_dir
            legacy_parser.output_imports_dir = old_output_dir
