# -*- coding: utf-8 -*-
"""Slots corporais da MOCHILA (Ficha v2, onda B) — UM lugar só para responder
"o que é vestível, em que slot, e quantas vagas esse slot tem".

Princípio (briefing `docs/agentes/briefing_ficha_v2.md`, onda B): a grade de slots da
ficha NÃO é uma lista fixa no template. Ela é **derivada do catálogo real**:

  * os slots dos itens mágicos são os valores DISTINTOS de `TbItemMagico.slot`
    efetivamente usados pelo catálogo (não o vocabulário inteiro de `SLOT_CHOICES`);
  * os itens MUNDANOS entram pelos slots que a mecânica deles declara em tags_json —
    `ca:+N` → escudo, `ca=<fórmula>` → armadura, `dmg:...` → arma (ver item_mecanica).

Assim, cadastrar um item num slot novo faz o slot APARECER na ficha sozinho; e um slot
do vocabulário que ninguém usa não polui a grade.

### Vagas (decisão tomada sobre o DADO REAL, 27/07/2026)

| slot         | vagas | por quê                                                            |
|--------------|-------|--------------------------------------------------------------------|
| `acessorio`  |   ∞   | REGRA DO PO: acessório concede o efeito e **não consome vaga**. É o |
|              |       | fallback de forma exótica (implante, simbionte, arreio de montaria) |
|              |       | — ver `docs/agentes/relatorio_restore_20260727_174353.md`.          |
| `aneis`      |   2   | o catálogo nomeia o slot no PLURAL e tem 47 itens nele; 5e permite  |
|              |       | um anel por mão. (`dedos` existe no vocabulário com 0 itens, então  |
|              |       | nem aparece na grade — a grade vem do dado.)                        |
| `arma`       |   2   | as duas mãos: permite empunhar duas armas.                          |
| `empunhado`  |   2   | idem — é o slot "na mão" dos itens mágicos não-arma (focos, tochas).|
| todos os     |   1   | slot anatômico único (cabeça, torso, pés, pescoço, costas...).      |
| demais       |       |                                                                     |

Quem quiser mudar isso mexe em `VAGAS_POR_SLOT` — não em `if` espalhado por view.
"""

# Slots de CONSUMO (gastos por quantidade, nunca vestidos). Fonte única também para
# character_engine._item_consumivel_meta.
SLOTS_CONSUMIVEIS = {'pocao', 'pergaminho', 'municao'}

# Slots de USO/posse que não são equipamento vestível (o item existe na mochila, mas
# não ocupa o corpo). Fonte única também para character_engine._item_magico_equipavel.
SLOTS_NAO_VESTIVEIS = {'veiculo', 'edificacao', 'objeto', 'item_menor'}

# Slot que concede efeito SEM consumir vaga (regra do PO).
SLOT_SEM_VAGA = 'acessorio'

# Vagas por slot. Ausente = 1 vaga. `None` = ilimitado (não consome vaga).
VAGAS_POR_SLOT = {
    SLOT_SEM_VAGA: None,
    'aneis': 2,
    'arma': 2,
    'empunhado': 2,
}

# Ordem de EXIBIÇÃO (cabeça aos pés, depois o que se empunha). É só uma dica de
# apresentação: slot fora desta lista continua aparecendo na grade, no fim, em ordem
# alfabética — nenhum slot novo do catálogo fica invisível por não estar aqui.
ORDEM_EXIBICAO = [
    'cabeca', 'face_olhos', 'rosto', 'pescoco', 'costas', 'torso', 'armadura',
    'bracos', 'maos', 'aneis', 'dedos', 'cintura', 'pes', 'pele',
    'arma', 'escudo', 'empunhado', 'varinha', 'cajado_bastao', 'flutuando',
    SLOT_SEM_VAGA,
]


def slot_e_vestivel(slot):
    """Um slot do catálogo vira vaga na grade? Poção/pergaminho e itens de uso não."""
    s = (slot or '').strip().lower()
    return bool(s) and s not in SLOTS_CONSUMIVEIS and s not in SLOTS_NAO_VESTIVEIS


def vagas_do_slot(slot):
    """Quantas vagas o slot tem. `None` = ilimitado (acessório)."""
    s = (slot or '').strip().lower()
    return VAGAS_POR_SLOT.get(s, 1)


def rotulo_do_slot(slot):
    """Rótulo PT do slot, lido do próprio modelo (TbItemMagico.SLOT_CHOICES)."""
    from .models import TbItemMagico
    s = (slot or '').strip().lower()
    return dict(TbItemMagico.SLOT_CHOICES).get(s) or s.replace('_', ' ').capitalize()


def slot_de_mecanica(mec):
    """Slot corporal de um item MUNDANO, a partir da mecânica derivada das tags."""
    if mec.get('is_escudo'):
        return 'escudo'
    if mec.get('is_armadura'):
        return 'armadura'
    if mec.get('dano_dado'):
        return 'arma'
    return None


def slot_de_item(item_linha):
    """Slot corporal de uma linha de inventário (`TbPersonagemItem`). `None` = não veste.

    Item mágico manda pelo catálogo (`TbItemMagico.slot`); item mundano cai na mecânica
    das próprias tags (armadura / escudo / arma)."""
    from .item_mecanica import mecanica_de_tags
    magico = getattr(item_linha, 'id_item_magico', None)
    if magico is not None:
        slot = (magico.slot or '').strip().lower()
        return slot if slot_e_vestivel(slot) else None
    return slot_de_mecanica(mecanica_de_tags(item_linha.tags_json))


def slots_do_catalogo():
    """Slots VESTÍVEIS que o catálogo real usa, já na ordem de exibição.

    Mágicos: `SELECT DISTINCT slot FROM TB_ItemMagico`. Mundanos: os slots que a
    mecânica dos itens mundanos cadastrados produz (armadura/escudo/arma)."""
    from .models import TbItemMagico, TbItemMundano
    from .item_mecanica import mecanica_de_tags

    achados = {s for s in TbItemMagico.objects.values_list('slot', flat=True).distinct()
               if slot_e_vestivel(s)}
    for tags, sub in TbItemMundano.objects.values_list('tags_json', 'subcategoria'):
        slot = slot_de_mecanica(mecanica_de_tags(tags, sub))
        if slot_e_vestivel(slot):
            achados.add(slot)

    ordem = {s: i for i, s in enumerate(ORDEM_EXIBICAO)}
    return sorted(achados, key=lambda s: (ordem.get(s, len(ORDEM_EXIBICAO)), s))


def grade_de_slots(itens_equipados):
    """Monta a grade da Mochila: um cartão por slot do catálogo, com o que está nele.

    `itens_equipados`: iterável de `TbPersonagemItem` equipados. Devolve lista de dicts
    prontos pro template (nada de lógica de slot no HTML)."""
    por_slot = {}
    for it in itens_equipados:
        slot = slot_de_item(it)
        if slot:
            por_slot.setdefault(slot, []).append(it)

    grade = []
    for slot in slots_do_catalogo():
        ocupantes = por_slot.pop(slot, [])
        vagas = vagas_do_slot(slot)
        grade.append({
            'slug': slot,
            'rotulo': rotulo_do_slot(slot),
            'vagas': vagas,
            'sem_vaga': vagas is None,
            'itens': [{'id': it.id, 'nome': it.nome, 'qtd': it.qtd,
                       'sintonizado': bool(it.sintonizado)} for it in ocupantes],
            'ocupadas': len(ocupantes),
            'livres': None if vagas is None else max(0, vagas - len(ocupantes)),
            'livre': vagas is not None and len(ocupantes) < vagas,
        })
    # Item equipado num slot que sumiu do catálogo (item removido/renomeado) não some da
    # grade: ganha o próprio cartão no fim, para o jogador ver e poder desequipar.
    for slot, ocupantes in sorted(por_slot.items()):
        grade.append({
            'slug': slot, 'rotulo': rotulo_do_slot(slot), 'vagas': vagas_do_slot(slot),
            'sem_vaga': vagas_do_slot(slot) is None,
            'itens': [{'id': it.id, 'nome': it.nome, 'qtd': it.qtd,
                       'sintonizado': bool(it.sintonizado)} for it in ocupantes],
            'ocupadas': len(ocupantes), 'livres': 0, 'livre': False,
        })
    return grade


def conflito_de_slot(item_linha, equipados):
    """Guarda do EQUIPAR. Devolve `(slot, rotulo, ocupante)` quando não cabe, ou `None`.

    `equipados`: linhas de inventário JÁ equipadas (a própria linha alvo pode estar na
    lista; é ignorada). Slot ilimitado (acessório) nunca conflita."""
    slot = slot_de_item(item_linha)
    if not slot:
        return None
    vagas = vagas_do_slot(slot)
    if vagas is None:
        return None
    ocupantes = [o for o in equipados
                 if o.id != item_linha.id and slot_de_item(o) == slot]
    if len(ocupantes) < vagas:
        return None
    return slot, rotulo_do_slot(slot), ocupantes[0]
