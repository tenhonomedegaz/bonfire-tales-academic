"""Prepara definições épicas a partir do catálogo revisado, sem publicá-las."""

import json
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify
from home.epic_soul_siphon import SIPHON_TAG
from home.tag_engine.library import SKILLS


STAGING_PATH = Path(settings.BASE_DIR) / "docs/integracao/talentos-epicos-staging.json"
ATTRIBUTE_TAGS = [
    "attr:talent_attr_score+2",
    "attr_max:talent_attr_score=30",
]

# Só publicar entradas cujos efeitos adicionais foram conferidos contra o motor.
VERIFIED_EFFECTS = {
    "dadiva-da-fortitude": [
        "always_active{buff:max_hp:+40}",
        "always_active{trigger=healing, 1/turn, instant{heal:+con_mod}}",
    ],
    "dadiva-da-visao-verdadeira": ["sense:truesight(range:120ft)"],
    "dadiva-da-resiliencia-sangrenta": [
        "while_active{requires:self{sangrando}, "
        "resist:acido, resist:concussao, resist:frio, resist:fogo, "
        "resist:raio, resist:necrotico, resist:perfurante, resist:veneno, "
        "resist:psiquico, resist:radiante, resist:cortante, resist:trovejante}"
    ],
    "dadiva-do-erudito": [
        *(f"prof:{skill}" for skill in sorted(SKILLS)),
        "expertise:original_prof",
    ],
    "dadiva-do-devorador-de-almas": [
        "if(already:resist{frio}): immune:frio else: resist:frio",
        "if(already:resist{necrotico}): immune:necrotico else: resist:necrotico",
        SIPHON_TAG,
    ],
}

# Efeitos conferidos isoladamente. Estes talentos ainda não entram em epic_candidates:
# faltam outros efeitos da mesma definição e a carga permanece fechada até cobertura integral.
PARTIAL_EFFECTS = {
    "dadiva-do-ceifador-de-almas": [
        "immune:veneno",
        "cond_immune:envenenado",
        "adv:death_save",
    ],
    "dadiva-da-memoria-arcana": [
        "if(already:prof{arcanismo}): expertise:arcanismo else: prof:arcanismo",
        "pick:pericia_expertise:1(requires:already_expertise{arcanismo})",
    ],
    "dadiva-da-folia": [
        "if(already:prof{atuacao}): expertise:atuacao else: prof:atuacao",
        "pick:pericia_expertise:1(requires:already_expertise{atuacao})",
    ],
    "dadiva-do-horror": [
        "cond_immune:amedrontado",
        "if(already:prof{intimidacao}): expertise:intimidacao else: prof:intimidacao",
        "pick:pericia_expertise:1(requires:already_expertise{intimidacao})",
    ],
    "dadiva-do-ataque-implacavel": [
        "always_active{ignore:resist(concussao,cortante,perfurante)}",
        "always_active{crit_dmg:+talent_attr_score}",
    ],
    "dadiva-da-tempestade": [
        "always_active{resist:raio, resist:trovejante}",
        "while_active{requires:self{sangrando}, immune:raio, immune:trovejante}",
    ],
    "dadiva-do-dominio-do-ceu": [
        "always_active{move:fly(=walk, hover, fall_threshold:5ft, "
        "fall_speed:60ft)}",
        "cast{spell:caminhar-no-vento, without{slot}, without{components}, "
        "uses{1, reset:long_rest}, always_prepared}",
    ],
    "dadiva-da-saude-abundante": [
        "always_active{temp_hp:+5}",
    ],
    "dadiva-da-velocidade": [
        "speed:+30",
        "cond_immune:paralisado",
        "cond_immune:restringido",
        "cast{spell:velocidade, always_prepared, uses{1, reset:short_or_long}, "
        "without{slot}, without{components}, without{lethargy}}",
    ],
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
