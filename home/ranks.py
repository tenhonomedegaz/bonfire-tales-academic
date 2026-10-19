"""Patentes existentes e o título narrativo de Lenda, sem alterar progressão."""


def character_rank(character):
    from .character_engine import nivel_por_aventuras, rank_icone_url, rank_por_nivel

    adventures = max(0, int(character.aventuras or 0))
    current = rank_por_nivel(nivel_por_aventuras(adventures))
    legend = current == 'Lenda'
    name = 'Diamante' if legend else current
    return {'nome': name, 'icone_url': rank_icone_url(name), 'is_lenda': legend,
            'titulo': 'Lenda' if legend else '', 'personagem_id': character.pk}
