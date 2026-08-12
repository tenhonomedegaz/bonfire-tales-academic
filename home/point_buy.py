# -*- coding: utf-8 -*-
"""Point-buy nativo — regras de compra dos atributos BASE.

Cada atributo começa em 8. Subir custa 1 ponto por ponto até 13 (8→13 = 5 pontos);
de 14 em diante custa 2 pontos por ponto (14 = 7, 15 = 9). Máximo 15 por atributo,
27 pontos no total. Esta é a fonte de verdade: a view passa CUSTO/MAX_PONTOS para
o JS, então cliente e servidor concordam.
"""

MIN_SCORE = 8
MAX_SCORE = 15
MAX_PONTOS = 27

# custo CUMULATIVO de 8 até cada valor (8→13: +1/ponto; 14,15: +2/ponto)
CUSTO = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}


def custo(score):
    """Custo em pontos de um atributo (None se fora da faixa de point-buy)."""
    return CUSTO.get(int(score))


def total_pontos(scores):
    """Soma dos custos dos 6 atributos."""
    return sum(CUSTO.get(int(s), 0) for s in scores)


SIGLAS = ('FOR', 'DES', 'CON', 'INT', 'SAB', 'CAR')


def validar(scores):
    """Valida os seis valores-base e exige que os 27 pontos sejam distribuídos."""
    erros = []
    try:
        valores = [int(s) for s in scores]
    except (TypeError, ValueError):
        return False, ['Os valores da compra de pontos devem ser números inteiros.']

    for v in valores:
        if v < MIN_SCORE or v > MAX_SCORE:
            erros.append(f'Atributo {v} fora da faixa de point-buy [{MIN_SCORE}, {MAX_SCORE}].')
    tot = total_pontos(valores)
    if tot < MAX_PONTOS:
        faltam = MAX_PONTOS - tot
        verbo = 'falta' if faltam == 1 else 'faltam'
        unidade = 'ponto' if faltam == 1 else 'pontos'
        erros.append(
            f'Compra de pontos incompleta: {verbo} {faltam} {unidade} para distribuir '
            f'(use os {MAX_PONTOS} pontos).'
        )
    elif tot > MAX_PONTOS:
        erros.append(f'{tot} pontos gastos — máximo {MAX_PONTOS}.')
    return (not erros, erros)


def validar_asi(modo, attrs=None):
    """ASI do antecedente. Duas formas (regra de SISTEMA 5.5e):
      - '2/1'   → +2 num atributo e +1 noutro (2 siglas distintas)
      - '1/1/1' → +1 em três atributos distintos
    Forma canônica: `validar_asi(modo, attrs)` com `modo in ASI_SHAPES` e `attrs` = lista de
    2 ou 3 siglas. COMPAT (legado): `validar_asi(mais2, mais1)` com duas siglas soltas é
    interpretado como a forma '2/1'. Retorna (ok, erros)."""
    from .character_engine import ASI_SHAPES
    # compat: duas siglas soltas (mais2, mais1) → forma '2/1'
    if isinstance(attrs, str) and modo in SIGLAS:
        modo, attrs = '2/1', [modo, attrs]
    shape = ASI_SHAPES.get(modo)
    erros = []
    if not shape:
        return (False, ['Forma de ASI inválida (use +2/+1 ou +1/+1/+1).'])
    attrs = list(attrs or [])
    if any(a not in SIGLAS for a in attrs):
        erros.append('Atributos do ASI inválidos.')
    elif len(attrs) != len(shape):
        erros.append('Escolha exatamente %d atributo(s) para o ASI %s.' % (len(shape), modo))
    elif len(set(attrs)) != len(attrs):
        erros.append('Os atributos do ASI devem ser diferentes entre si.')
    return (not erros, erros)


def validar_asi_classe(attr1, attr2):
    """ASI de classe: dois incrementos de +1. Repetir o atributo equivale a +2."""
    erros = []
    if attr1 not in SIGLAS or attr2 not in SIGLAS:
        erros.append('Atributos do ASI invalidos.')
    return (not erros, erros)
