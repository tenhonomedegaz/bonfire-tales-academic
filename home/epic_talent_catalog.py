"""Prepara definições épicas a partir do catálogo revisado, sem publicá-las."""

import json
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify


STAGING_PATH = Path(settings.BASE_DIR) / "docs/integracao/talentos-epicos-staging.json"
ATTRIBUTE_TAGS = [
    "attr:talent_attr_score+2",
    "attr_max:talent_attr_score=30",
]

# Só publicar entradas cujos efeitos adicionais foram conferidos contra o motor.
VERIFIED_EFFECTS = {
    "dadiva-da-visao-verdadeira": ["sense:truesight(range:120ft)"],
}

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
        effects = VERIFIED_EFFECTS.get(slug)
        if effects is None:
            continue
        ready.append({
            "nome": title,
            "slug": slug,
            "tipo": "geral",
            "etiqueta": CATEGORIES[entry["categoria_fonte"]],
            "etiquetas_adicionais": "epico",
            "pre_requisito": entry["pre_requisito"] or "",
            "descricao": entry["descricao_markdown"],
            "tags_json": ATTRIBUTE_TAGS + effects,
        })
    if not set(VERIFIED_EFFECTS).issubset(slugs):
        raise ValueError("Mapa de efeitos contém talento ausente do staging.")
    return ready
