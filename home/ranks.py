"""Patentes existentes e o título narrativo de Lenda, sem alterar progressão."""

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _rank_art_catalog():
    path = Path(__file__).resolve().parent / 'static/icons/ranks/art.json'
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def rank_art_url(key):
    from .cosmetic_packages import _asset_url
    return _asset_url(_rank_art_catalog().get(key))


def character_rank(character):
    from .character_engine import nivel_por_aventuras, rank_icone_url, rank_por_nivel

    adventures = max(0, int(character.aventuras or 0))
    current = rank_por_nivel(nivel_por_aventuras(adventures))
    legend = current == 'Lenda'
    name = 'Diamante' if legend else current
    from django.utils.text import slugify
    from django.templatetags.static import static
    return {'nome': name, 'icone_url': rank_icone_url(name), 'is_lenda': legend,
            'key': slugify(name),
            'art_url': rank_art_url(slugify(name)),
            'helmet_url': static('cosmetics/knight-closed-helm.png'),
            'titulo': 'Lenda' if legend else '', 'personagem_id': character.pk}
