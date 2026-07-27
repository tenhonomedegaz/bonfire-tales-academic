# -*- coding: utf-8 -*-
"""Moeda do jogo — UM lugar só para converter e EXIBIR dinheiro.

Regra do PO (Ficha v2, onda A): o ARMAZENAMENTO interno continua em peças de cobre
(`carteira_pc`, `TbTransacao.valor_pc`, preços do catálogo em string), mas a EXIBIÇÃO é
SEMPRE em PO. PP e PC não aparecem mais em lugar nenhum da interface.

Formato canônico: `"12 PO"`, com UMA casa decimal só quando há fração (`"12,5 PO"`,
vírgula decimal pt-BR). Frações abaixo de 0,1 PO arredondam (1 PC vira `"0 PO"`).
"""
import re

# Peças de cobre por moeda. 1 PO = 100 PC, 1 PP = 10 PC, 1 PL = 1000 PC, 1 PE = 50 PC.
MOEDA_PC = {'PC': 1, 'PP': 10, 'PO': 100, 'PL': 1000, 'PE': 50, 'CP': 1, 'SP': 10, 'GP': 100}


def preco_em_pc(preco):
    """'5 PO' / '1 PP' / '1.500 PO' / '0,2 PC' -> peças de cobre (int). None se não comprável."""
    if not preco:
        return None
    m = re.match(r'\s*([\d.,]+)\s*(PC|PP|PO|PL|PE|CP|SP|GP)', str(preco).strip(), re.I)
    if not m:
        return None
    try:
        val = float(m.group(1).replace('.', '').replace(',', '.'))
    except ValueError:
        return None
    return int(round(val * MOEDA_PC.get(m.group(2).upper(), 0)))


def po_display(pc):
    """Peças de cobre -> exibição SEMPRE em PO: '12 PO', '12,5 PO', '-3 PO'."""
    pc = int(pc or 0)
    sinal = '-' if pc < 0 else ''
    val = round(abs(pc) / 100.0, 1)
    if val == int(val):
        return '%s%d PO' % (sinal, int(val))
    return '%s%s PO' % (sinal, ('%.1f' % val).replace('.', ','))


def preco_display(preco):
    """String de preço do catálogo ('2 PP', '5 PO', '15 PC') -> 'N PO'. None se sem preço."""
    pc = preco_em_pc(preco)
    return None if pc is None else po_display(pc)
