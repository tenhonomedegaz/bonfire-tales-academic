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
    """`scores`: iterável de valores-base. Retorna (ok, lista_de_erros)."""
    erros = []
    for s in scores:
        v = int(s)
        if v < MIN_SCORE or v > MAX_SCORE:
            erros.append(f'Atributo {v} fora da faixa de point-buy [{MIN_SCORE}, {MAX_SCORE}].')
    tot = total_pontos(scores)
    if tot > MAX_PONTOS:
        erros.append(f'{tot} pontos gastos — máximo {MAX_PONTOS}.')
    return (not erros, erros)


def validar_asi(mais2, mais1):
    """ASI do antecedente: +2 num atributo e +1 noutro (distintos). (ok, erros)."""
    erros = []
    if mais2 not in SIGLAS or mais1 not in SIGLAS:
        erros.append('Atributos do ASI inválidos.')
    elif mais2 == mais1:
        erros.append('O +2 e o +1 do ASI devem ser em atributos diferentes.')
    return (not erros, erros)
