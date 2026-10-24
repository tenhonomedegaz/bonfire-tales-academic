"""Prepara definições épicas a partir do catálogo revisado, sem publicá-las."""

import json
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify
from home.epic_death_seal import DEATH_SEAL_TAG
from home.epic_reaping import REAPING_TAG
from home.epic_save_reroll import REROLL_TAG
from home.epic_battle_accuracy import NO_DISADVANTAGE_TAG, AUTO_HIT_TAG, FORTUNE_TAG
from home.epic_recovery_pool import RECOVERY_POOL_TAG, SURVIVAL_TAG
from home.epic_storm_save import STORM_SAVE_TAG
from home.epic_soul_siphon import SIPHON_TAG
from home.epic_hit_dice import HIT_DICE_MAX_TAG
from home.epic_free_cast import FREE_CAST_TAG
from home.tag_engine.library import SKILLS


STAGING_PATH = Path(settings.BASE_DIR) / "docs/integracao/talentos-epicos-staging.json"
ATTRIBUTE_TAGS = [
    "attr:talent_attr_score+2",
    "attr_max:talent_attr_score=30",
]

# Só publicar entradas cujos efeitos adicionais foram conferidos contra o motor.
VERIFIED_EFFECTS = {
    "dadiva-do-espirito-noturno": [
        "while_active{requires:in_dim_light, action:bonus_action, "
        "instant{apply:invisivel(target:self)}}",
        "while_active{requires:in_dim_light, resist:concussao, "
        "resist:cortante, resist:perfurante}",
    ],
    "dadiva-do-ceifador-de-almas": [
        "immune:veneno",
        "cond_immune:envenenado",
        "adv:death_save",
        DEATH_SEAL_TAG,
        REAPING_TAG,
    ],
    "dadiva-das-sombras-vivas": [
        "while_active{trigger=attack_action, reach:+10ft, duration:until_turn_end}",
        "while_active{action:bonus_action, instant{dodge}}",
    ],
    "dadiva-da-carnificina": [
        FORTUNE_TAG,
        "while_active{requires:self{sangrando}, 1/turn, "
        "instant{trigger=hit, dmg:+lvl}}",
        "while_active{requires:self{sangrando}, crit_range:+1}",
    ],
    "dadiva-da-velocidade": [
        "speed:+30",
        "cond_immune:paralisado",
        "cond_immune:restringido",
        "escape{action:move, condition:agarrado, cost:5ft}",
        "cast{spell:velocidade, always_prepared, uses{1, reset:short_or_long}, "
        "without{slot}, without{components}, without{lethargy}}",
    ],
    "dadiva-do-dominio-do-ceu": [
        "always_active{move:fly(=walk, hover, fall_threshold:5ft, "
        "fall_speed:60ft)}",
        "cast{spell:caminhar-no-vento, without{slot}, without{components}, "
        "uses{1, reset:long_rest}, always_prepared}",
    ],
    "dadiva-do-ataque-implacavel": [
        "always_active{ignore:resist(concussao,cortante,perfurante)}",
        "always_active{crit_dmg:+talent_attr_score}",
    ],
    "dadiva-da-memoria-arcana": [
        "if(already:prof{arcanismo}): expertise:arcanismo else: prof:arcanismo",
        "pick:pericia_expertise:1(requires:already_expertise{arcanismo})",
        FREE_CAST_TAG,
    ],
    "dadiva-da-saude-abundante": [
        "always_active{temp_hp:+5}",
        HIT_DICE_MAX_TAG,
    ],
    "dadiva-da-recuperacao": [SURVIVAL_TAG, RECOVERY_POOL_TAG],
    "dadiva-da-tempestade": [
        "always_active{resist:raio, resist:trovejante}",
        "while_active{requires:self{sangrando}, immune:raio, immune:trovejante}",
        STORM_SAVE_TAG,
    ],
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
    "dadiva-da-sorte-tola": [REROLL_TAG],
    "dadiva-da-aptidao-de-batalha": [NO_DISADVANTAGE_TAG, AUTO_HIT_TAG],
}

# Efeitos conferidos isoladamente. Estes talentos ainda não entram em epic_candidates:
# faltam outros efeitos da mesma definição e a carga permanece fechada até cobertura integral.
PARTIAL_EFFECTS = {
    "dadiva-da-folia": [
        "if(already:prof{atuacao}): expertise:atuacao else: prof:atuacao",
        "pick:pericia_expertise:1(requires:already_expertise{atuacao})",
    ],
    "dadiva-do-horror": [
        "cond_immune:amedrontado",
        "if(already:prof{intimidacao}): expertise:intimidacao else: prof:intimidacao",
        "pick:pericia_expertise:1(requires:already_expertise{intimidacao})",
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
