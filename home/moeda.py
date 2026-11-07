# -*- coding: utf-8 -*-
"""Moeda do jogo — UM lugar só para converter e EXIBIR dinheiro.

Regra do PO (Ficha v2): **não existe meio PO**. O ARMAZENAMENTO interno continua exato em
peças de cobre (`carteira_pc`, `TbTransacao.valor_pc`, preços do catálogo em string), mas a
EXIBIÇÃO é SEMPRE composta em PO/PP/PC, como na ficha clássica de D&D:

    1 PO = 10 PP = 100 PC

Formato canônico (`moeda_display`): componentes não-zero separados por espaço, do maior para
o menor — `134` → `"1 PO 3 PP 4 PC"`, `160` → `"1 PO 6 PP"`, `20` → `"2 PP"`, `0` → `"0 PO"`.
Negativo leva UM sinal na frente (`-134` → `"-1 PO 3 PP 4 PC"`). Não sobrou exibição decimal
em lugar nenhum: não há como escrever "12,5 PO".
"""
import re

# Peças de cobre por moeda. 1 PO = 100 PC, 1 PP = 10 PC, 1 PL = 1000 PC, 1 PE = 50 PC.
MOEDA_PC = {'PC': 1, 'PP': 10, 'PO': 100, 'PL': 1000, 'PE': 50, 'CP': 1, 'SP': 10, 'GP': 100}

# Ordem de decomposição da exibição — só as três moedas da ficha clássica.
_DECOMPOSICAO = (('PO', 100), ('PP', 10), ('PC', 1))


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


def decompor(pc):
    """Peças de cobre -> `(negativo, po, pp, pc)` já decompostos.

    Base das TRÊS CAIXINHAS da carteira na ficha (PO | PP | PC) e do `moeda_display`."""
    total = int(pc or 0)
    resto, negativo = abs(total), total < 0
    po, resto = divmod(resto, 100)
    pp, cobre = divmod(resto, 10)
    return (negativo, po, pp, cobre)


def moeda_display(pc):
    """Peças de cobre -> exibição COMPOSTA: '1 PO 3 PP 4 PC'.

    Componentes zero somem ('1 PO 6 PP', '2 PP'); carteira zerada vira '0 PO'."""
    negativo, po, pp, cobre = decompor(pc)
    partes = ['%d %s' % (n, sigla)
              for (sigla, _), n in zip(_DECOMPOSICAO, (po, pp, cobre)) if n]
    if not partes:
        return '0 PO'
    return ('-' if negativo else '') + ' '.join(partes)


def preco_display(preco):
    """String de preço do catálogo ('2 PP', '5 PO', '15 PC') -> exibição composta.
    None se o item não tem preço (recompensa de missão, não comercializável)."""
    pc = preco_em_pc(preco)
    return None if pc is None else moeda_display(pc)


def po_para_pc(valor_po):
    """Preço guardado como NÚMERO em PO (catálogo mágico) -> peças de cobre exatas."""
    return int(round(float(valor_po) * 100))


def preco_po_display(valor_po):
    """Preço guardado como NÚMERO em PO -> exibição composta ('1 PO 5 PP')."""
    return moeda_display(po_para_pc(valor_po))
