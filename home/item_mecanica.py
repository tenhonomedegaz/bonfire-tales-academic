# -*- coding: utf-8 -*-
"""Deriva a MECANICA de um item mundano a partir das suas tags_json (o DSL componivel),
substituindo as colunas dedicadas (dano/propriedades/maestria/ca/ca_base/ca_limite_des/
forca_minima/furtividade_desvantagem/tipo_equip). Fonte unica: as tags.

Convencao das tags (geradas por taggear_itens.py):
  dmg:1d8(cortante)            -> dano (dado + tipo)
  add-property:acuidade        -> propriedade de arma (0..n)
  maestrias{corte-nick, ...}   -> maestrias disponiveis
  ca=18                        -> armadura: CA base (antes de DES)
  ca:+2                        -> escudo: bonus de CA
  dex-ca-max:2                 -> teto do mod de DES (armadura)
  requires:str_score>=15       -> forca minima
  dadv:furtividade             -> desvantagem em Furtividade
tipo_equip e derivado: ca:+ => 'escudo'; ca= => 'armadura-<subcategoria>'.
"""
import re

_DMG = re.compile(r"^dmg:\s*([0-9]+d[0-9]+(?:\s*[+-]\s*[0-9]+)?)\s*\(([^)]+)\)", re.I)
_PROP = re.compile(r"^add-property:\s*([^(]+?)\s*(?:\((.+)\))?\s*$", re.I)
_MAEST = re.compile(r"^maestrias\s*\{(.+)\}", re.I | re.S)
_CA_SET = re.compile(r"^ca\s*=\s*(.+?)\s*$", re.I)          # ca=<formula> (14+min(dex_mod,2), 18, ...)
_CA_ADD = re.compile(r"^ca\s*:\s*\+\s*([0-9]+)", re.I)      # escudo ca:+N
_DEXMAX = re.compile(r"^dex-ca-max:\s*([0-9]+)", re.I)      # legado (retrocompat): sintetiza a formula
_FORCA = re.compile(r"^requires:\s*str[_-]score\s*>=\s*([0-9]+)", re.I)
_FURT = re.compile(r"^dadv:\s*furtividade\b", re.I)


def mecanica_de_tags(tags, subcategoria=None):
    """tags_json (list[str]) -> dict com a mecanica derivada."""
    dano_dado = dano_tipo = None
    propriedades = []
    prop_params = {}
    maestrias = []
    ca_base = ca_limite_des = forca_minima = None
    ca_rhs = None
    is_escudo = is_armadura = furtividade_desv = False

    for t in (tags or []):
        if not isinstance(t, str):
            continue
        t = t.strip()
        m = _DMG.match(t)
        if m:
            dano_dado = re.sub(r"\s+", "", m.group(1))
            dano_tipo = m.group(2).strip().lower()
            continue
        m = _PROP.match(t)
        if m:
            base = m.group(1).strip().lower()
            propriedades.append(base)
            if m.group(2):
                prop_params[base] = m.group(2).strip().lower()
            continue
        m = _MAEST.match(t)
        if m:
            maestrias = [x.strip() for x in m.group(1).split(",") if x.strip()]
            continue
        m = _CA_ADD.match(t)
        if m:
            is_escudo = True
            ca_base = int(m.group(1))
            continue
        m = _CA_SET.match(t)
        if m:
            is_armadura = True
            ca_rhs = m.group(1).strip()
            continue
        m = _DEXMAX.match(t)
        if m:
            ca_limite_des = int(m.group(1))
            continue
        m = _FORCA.match(t)
        if m:
            forca_minima = int(m.group(1))
            continue
        if _FURT.match(t):
            furtividade_desv = True

    # tipo_equip derivado (escudo / armadura-<sub>)
    tipo_equip = None
    if is_escudo:
        tipo_equip = "escudo"
    elif is_armadura:
        sub = (subcategoria or "").strip().lower()
        tipo_equip = "armadura-" + sub if sub else "armadura"

    # ca_formula: fonte unica p/ o motor avaliar (base + teto de DES via min()).
    # Retrocompat: se veio no formato antigo (ca=<int> + dex-ca-max:N), sintetiza a formula.
    ca_formula = None
    if is_armadura and ca_rhs is not None:
        if re.fullmatch(r"[0-9]+", ca_rhs) and ca_limite_des is not None:
            # LEGADO: ca=<int> + dex-ca-max:N -> sintetiza a formula.
            ca_base = int(ca_rhs)
            ca_formula = ("%d" % ca_base if ca_limite_des == 0
                          else "%d+min(dex_mod,%d)" % (ca_base, ca_limite_des))
        else:
            # NOVO formato: ca=<formula> avaliada literalmente. Leve = 'base+dex_mod',
            # media = 'base+min(dex_mod,N)', pesada = 'base' (constante).
            ca_formula = ca_rhs
            mm = re.match(r"([0-9]+)", ca_rhs)
            if mm:
                ca_base = int(mm.group(1))

    return {
        "dano": (f"{dano_dado} {dano_tipo}" if dano_dado else None),
        "dano_dado": dano_dado,
        "dano_tipo": dano_tipo,
        "propriedades": propriedades,
        "prop_params": prop_params,
        "versatil_dado": prop_params.get("versatil"),
        "adaptavel_tipo": prop_params.get("adaptavel"),
        "maestrias": maestrias,
        "ca_base": ca_base,
        "ca_formula": ca_formula,
        "ca_limite_des": ca_limite_des,
        "forca_minima": forca_minima,
        "furtividade_desvantagem": furtividade_desv,
        "tipo_equip": tipo_equip,
        "is_escudo": is_escudo,
        "is_armadura": is_armadura,
    }


# ---- helpers de exibicao (reconstroem as strings que a ficha mostrava) ----
_PROP_LABEL = {
    "duas-maos": "duas mãos", "empunhadura-longa": "empunhadura longa",
    "arma-dupla": "arma dupla", "versatil": "versátil", "acuidade": "acuidade",
}


def dano_display(mec):
    if not mec.get("dano_dado"):
        return ""
    return "%s %s" % (mec["dano_dado"], mec.get("dano_tipo") or "")


def propriedades_display(mec):
    out = []
    for p in mec.get("propriedades", []):
        rot = _PROP_LABEL.get(p, p).capitalize()
        param = (mec.get("prop_params") or {}).get(p)
        out.append("%s (%s)" % (rot, param) if param else rot)
    return ", ".join(out)


def ca_display(mec):
    """String tipo '14 + mod Des (máx 2)' / '18' / '+2' a partir da ca_formula."""
    if mec.get("is_escudo"):
        return "+%s" % mec.get("ca_base")
    if not mec.get("is_armadura"):
        return ""
    f = (mec.get("ca_formula") or "").replace(" ", "")
    m = re.match(r"^(\d+)\+min\(dex[_-]mod,(\d+)\)$", f)
    if m:
        return "%s + mod Des (máx %s)" % (m.group(1), m.group(2))
    m = re.match(r"^(\d+)\+dex[_-]mod$", f)
    if m:
        return "%s + mod Des" % m.group(1)
    if re.match(r"^\d+$", f):
        return f
    return mec.get("ca_formula") or ""     # formula custom: mostra crua
