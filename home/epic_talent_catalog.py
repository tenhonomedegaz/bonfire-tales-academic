"""Load epic catalog data without embedding per-talent mechanics in Python."""

import json
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify


STAGING_PATH = Path(settings.BASE_DIR) / "docs/integracao/talentos-epicos-staging.json"
TAG_PACKAGE_PATH = Path(settings.BASE_DIR) / "home/content_packages/epic_talent_tags.json"


def _tag_package(path=TAG_PACKAGE_PATH):
    package = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(package, dict) or package.get("schema") != 1:
        raise ValueError("Invalid epic catalog tag package.")
    common = package.get("common_tags")
    if not isinstance(common, list) or not all(isinstance(tag, str) for tag in common):
        raise ValueError("Invalid common catalog tags.")
    for name in ("effects", "declarative_tags"):
        mapping = package.get(name)
        if not isinstance(mapping, dict) or any(
                not isinstance(slug, str) or not isinstance(tags, list)
                or not all(isinstance(tag, str) for tag in tags)
                for slug, tags in mapping.items()):
            raise ValueError("Invalid catalog effect definitions.")
    gaps = package.get("declarative_gaps")
    if not isinstance(gaps, dict) or any(
            not isinstance(slug, str) or not isinstance(reason, str)
            for slug, reason in gaps.items()):
        raise ValueError("Invalid declarative gap descriptions.")
    if set(gaps) != set(package["declarative_tags"]):
        raise ValueError("Declarative gaps must match their definitions.")
    return package


_PACKAGE = _tag_package()
ATTRIBUTE_TAGS = _PACKAGE["common_tags"]
VERIFIED_EFFECTS = _PACKAGE["effects"]
VTT_DECLARATIVE_TAGS = _PACKAGE["declarative_tags"]
DECLARATIVE_GAPS = _PACKAGE["declarative_gaps"]

CATEGORIES = {
    "Combate": "combate",
    "Conjuração": "conjuracao",
    "Exploração": "exploracao",
    "Sobrevivência": "sobrevivencia",
    "Social": "social",
    "Suporte": "suporte",
    "Utilidade": "utilidade",
}


def epic_candidates(path=STAGING_PATH):
    """Valida as 31 identidades e devolve apenas definições completas para importação."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    talents = data["talentos"]
    if len(talents) != 31:
        raise ValueError("O staging épico deve conter exatamente 31 entradas.")
    slugs = set()
    ready = []
    for entry in talents:
        title = entry["titulo"].strip()
        slug = slugify(title)
        if not title or slug in slugs or len(slug) > 150:
            raise ValueError(f"Identidade épica duplicada ou inválida: {title!r}")
        slugs.add(slug)
        if entry["categoria_fonte"] not in CATEGORIES:
            raise ValueError(f"Categoria épica desconhecida: {title}")
        if "+2 em um atributo à sua escolha, até o máximo de 30" not in entry["descricao_markdown"]:
            raise ValueError(f"Regra de atributo ausente: {title}")
        effects = VERIFIED_EFFECTS.get(slug, [])
        ready.append({
            "nome": title,
            "slug": slug,
            "tipo": "epico",
            "etiqueta": CATEGORIES[entry["categoria_fonte"]],
            "etiquetas_adicionais": "epico",
            "pre_requisito": entry["pre_requisito"] or "",
            "descricao": entry["descricao_markdown"],
            "tags_json": ATTRIBUTE_TAGS + effects,
        })
    if not (set(VERIFIED_EFFECTS) | set(VTT_DECLARATIVE_TAGS)).issubset(slugs):
        raise ValueError("Mapa de efeitos contém talento ausente do staging.")
    if set(VTT_DECLARATIVE_TAGS) != set(DECLARATIVE_GAPS):
        raise ValueError("Lacunas declarativas sem explicação correspondente.")
    return ready
