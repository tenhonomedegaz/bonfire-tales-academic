"""Laboratorio de builds sem persistencia.

O estado autoral vive no navegador. Cada preview materializa uma ficha real dentro de
uma transacao marcada para rollback, executa o mesmo ``derive`` da ficha e devolve

  1. o HTML da FOLHA (os mesmos partials da aba Ficha, em modo leitura) e
  2. so os numeros que o EDITOR precisa (orcamento de ASI, grupos de escolha, avisos).

Nenhum TbPersonagem sobrevive ao request. O redesenho de julho tirou daqui a montagem
paralela da ficha em JSON: a visualizacao e a ficha real, renderizada no servidor.
"""

from django.db import transaction
from django.utils.text import slugify


class PathbuilderError(ValueError):
    pass


# tipos aceitos pelo endpoint de descricao (catalogo enxuto no cliente, texto sob demanda)
DETALHE_TIPOS = ("talento", "magia", "item_mundano", "item_magico", "subclasse")


def _preco_txt(value):
    value = str(value or "").strip()
    return value


def catalogos():
    """Catalogo do laboratorio: SO o suficiente para desenhar os cartoes de escolha.

    Descricao NAO vem aqui (580 magias + 954 itens magicos passariam de 1 MB): o cartao
    busca o texto sob demanda em ``pathbuilder_detalhe`` e guarda em cache no cliente.
    """
    from .character_engine import _subclass_min_level
    from .models import (
        TbClasse,
        TbItemMagico,
        TbItemMundano,
        TbMagia,
        TbSubclasse,
        TbTalento,
    )

    subclasses = {}
    for sub in TbSubclasse.objects.select_related("id_classe").order_by(
            "id_classe__nome", "nome"):
        subclasses.setdefault(sub.id_classe.slug, []).append({
            "slug": sub.slug,
            "nome": sub.nome,
            "meta": (sub.tagline or "").strip(),
        })

    classes = []
    for classe in TbClasse.objects.all().order_by("nome"):
        classes.append({
            "slug": classe.slug,
            "nome": classe.nome,
            "subclasse_nivel": _subclass_min_level(classe),
            "subclasses": subclasses.get(classe.slug, []),
        })

    # `grupo` = cabecalho da lista (nao se repete em `meta`, senao o payload dobra de peso)
    mundanos = [{
        "slug": item.slug,
        "nome": item.nome,
        "grupo": item.get_categoria_display(),
        "meta": " · ".join(x for x in [
            (item.subcategoria or "").strip(),
            _preco_txt(item.preco),
        ] if x),
        "equipavel": item.categoria in {"arma", "armadura"},
    } for item in TbItemMundano.objects.all().order_by("categoria", "nome")]

    magicos = [{
        "slug": item.slug,
        "nome": item.nome,
        "grupo": item.get_raridade_display(),
        "meta": " · ".join(x for x in [
            item.get_slot_display(),
            "sintonização" if item.requer_sintonizacao else "",
        ] if x),
        "equipavel": True,
        "requer_sintonizacao": bool(item.requer_sintonizacao),
    } for item in TbItemMagico.objects.all().order_by("raridade", "nome")]

    from .views import _talento_attr_options

    talentos = [{
        "slug": talento.slug,
        "nome": talento.nome,
        "grupo": (talento.tipo or "Talento").strip() or "Talento",
        "meta": (talento.pre_requisito or "").strip()[:80],
        "atributos": _talento_attr_options(talento),
    } for talento in TbTalento.objects.filter(tipo__iexact="geral").order_by("nome")]

    magias = [{
        "slug": magia.slug,
        "nome": magia.nome,
        "nome_ingles": (magia.nome_ingles or "").strip(),
        "nivel": int(magia.nivel or 0),
        "grupo": "Truques" if int(magia.nivel or 0) == 0 else "%dº nível" % magia.nivel,
        "meta": " · ".join(x for x in [
            (magia.escola or "").strip(),
            "concentração" if magia.concentracao else "",
            "ritual" if magia.ritual else "",
        ] if x),
    } for magia in TbMagia.objects.all().order_by("nivel", "nome")]

    return {
        "classes": classes,
        "talentos": talentos,
        "itens_mundanos": mundanos,
        "itens_magicos": magicos,
        "magias": magias,
    }


def detalhe(tipo, slug):
    """Descricao de UMA entrada do catalogo (cartao expandido, sob demanda)."""
    from .models import (
        TbItemMagico,
        TbItemMundano,
        TbMagia,
        TbSubclasse,
        TbTalento,
    )

    slug = str(slug or "").strip()
    if tipo not in DETALHE_TIPOS or not slug:
        raise PathbuilderError("Detalhe indisponivel para este item.")

    if tipo == "talento":
        obj = TbTalento.objects.filter(slug=slug).first()
        if not obj:
            raise PathbuilderError("Talento nao encontrado.")
        return {"nome": obj.nome, "descricao": (obj.descricao or "").strip(),
                "linhas": [x for x in [
                    ("Tipo", (obj.tipo or "").strip()),
                    ("Pré-requisito", (obj.pre_requisito or "").strip()),
                ] if x[1]]}

    if tipo == "magia":
        obj = TbMagia.objects.filter(slug=slug).first()
        if not obj:
            raise PathbuilderError("Magia nao encontrada.")
        nivel = int(obj.nivel or 0)
        return {"nome": obj.nome, "descricao": (obj.descricao or "").strip(),
                "extra": (obj.em_niveis_superiores or "").strip(),
                "linhas": [x for x in [
                    ("Nível", "Truque" if nivel == 0 else "%dº" % nivel),
                    ("Escola", (obj.escola or "").strip()),
                    ("Execução", (obj.casting_time or "").strip()),
                    ("Alcance", (obj.alcance or "").strip()),
                    ("Duração", "%s%s" % ((obj.duracao or "").strip(),
                                          " (concentração)" if obj.concentracao else "")),
                    ("Componentes", (obj.componentes or "").strip()),
                ] if x[1]]}

    if tipo == "item_mundano":
        obj = TbItemMundano.objects.filter(slug=slug).first()
        if not obj:
            raise PathbuilderError("Item nao encontrado.")
        return {"nome": obj.nome, "descricao": (obj.descricao_markdown or "").strip(),
                "linhas": [x for x in [
                    ("Categoria", obj.get_categoria_display()),
                    ("Subcategoria", (obj.subcategoria or "").strip()),
                    ("Preço", _preco_txt(obj.preco)),
                    ("Peso", str(obj.peso or "").strip()),
                ] if x[1]]}

    if tipo == "item_magico":
        obj = TbItemMagico.objects.filter(slug=slug).first()
        if not obj:
            raise PathbuilderError("Item nao encontrado.")
        return {"nome": obj.nome, "descricao": (obj.descricao_markdown or "").strip(),
                "extra": (obj.detalhes_sintonizacao or "").strip(),
                "linhas": [x for x in [
                    ("Raridade", obj.get_raridade_display()),
                    ("Slot", obj.get_slot_display()),
                    ("Sintonização", "exige" if obj.requer_sintonizacao else ""),
                    ("Preço", _preco_txt(obj.preco)),
                ] if x[1]]}

    obj = TbSubclasse.objects.filter(slug=slug).first()
    if not obj:
        raise PathbuilderError("Subclasse nao encontrada.")
    return {"nome": obj.nome, "descricao": (obj.tagline or "").strip(), "linhas": []}


def default_build(creator_data):
    return {
        "modo": "sandbox",
        "classes": [{
            "slug": str(creator_data.get("classe") or ""),
            "nivel": 1,
            "subclasse": "",
        }],
        "atributos_bonus": {},
        "escolhas": {},
        "talentos": [],
        "itens": [],
        "magias": [],
    }


def _int_between(value, minimum, maximum, label):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise PathbuilderError("%s invalido." % label)
    if number < minimum or number > maximum:
        raise PathbuilderError(
            "%s deve ficar entre %d e %d." % (label, minimum, maximum))
    return number


def _apply_classes(personagem, creator_data, build):
    from .character_engine import _subclass_min_level
    from .models import TbClasse, TbPersonagemClasse, TbSubclasse

    requested = build.get("classes") or []
    if not isinstance(requested, list) or not requested:
        raise PathbuilderError("A build precisa ter ao menos uma classe.")
    if len(requested) > 13:
        raise PathbuilderError("Quantidade de classes acima do catalogo do sistema.")
    if any(not isinstance(row, dict) for row in requested):
        raise PathbuilderError("Cada classe da build precisa ter slug e nivel.")

    slugs = [str(row.get("slug") or "") for row in requested]
    if len(slugs) != len(set(slugs)):
        raise PathbuilderError("A mesma classe nao pode aparecer duas vezes.")

    initial_slug = str(creator_data.get("classe") or "")
    if initial_slug not in slugs:
        raise PathbuilderError("A classe inicial precisa permanecer na build.")

    by_slug = {
        classe.slug: classe
        for classe in TbClasse.objects.filter(slug__in=slugs)
    }
    if len(by_slug) != len(slugs):
        raise PathbuilderError("Uma das classes selecionadas nao existe.")

    normalized = []
    total = 0
    for row in requested:
        slug = str(row.get("slug") or "")
        nivel = _int_between(row.get("nivel", 1), 1, 20, "Nivel de classe")
        total += nivel
        classe = by_slug[slug]
        subclasse = None
        sub_slug = str(row.get("subclasse") or "").strip()
        if sub_slug:
            subclasse = TbSubclasse.objects.filter(
                id_classe=classe, slug=sub_slug).first()
            if subclasse is None:
                raise PathbuilderError("Subclasse invalida para %s." % classe.nome)
            minimo = _subclass_min_level(classe)
            if minimo and nivel < minimo:
                raise PathbuilderError(
                    "%s exige nivel %d em %s." % (subclasse.nome, minimo, classe.nome))
        normalized.append((classe, subclasse, nivel))
    if total > 20:
        raise PathbuilderError("O nivel total da build nao pode passar de 20.")

    personagem.classes.all().delete()
    for classe, subclasse, nivel in normalized:
        TbPersonagemClasse.objects.create(
            id_personagem=personagem,
            id_classe=classe,
            id_subclasse=subclasse,
            nivel=nivel,
            principal=classe.slug == initial_slug,
        )
    personagem.nivel = total
    personagem.save(update_fields=["nivel", "atualizado_em"])


def _apply_attribute_bonus(personagem, build):
    from .models import TbPersonagemAtributoBonus

    values = build.get("atributos_bonus") or {}
    if not isinstance(values, dict):
        raise PathbuilderError("Bonus de atributos invalidos.")
    for sigla in ("FOR", "DES", "CON", "INT", "SAB", "CAR"):
        amount = _int_between(values.get(sigla, 0), 0, 10, "Bonus de %s" % sigla)
        if amount:
            TbPersonagemAtributoBonus.objects.create(
                id_personagem=personagem,
                atributo=sigla,
                valor=amount,
                origem="Pathbuilder",
                origem_tipo="pathbuilder",
            )


def _normalize_talents(build):
    rows = build.get("talentos") or []
    if not isinstance(rows, list) or len(rows) > 30:
        raise PathbuilderError("A build excede o limite de talentos do laboratorio.")
    normalized = []
    seen = set()
    for raw in rows:
        if isinstance(raw, dict):
            slug = str(raw.get("slug") or "").strip()
            atributo = str(raw.get("atributo") or "").strip().upper()
        else:
            # Compatibilidade com builds salvas antes de o +1 do talento ser modelado.
            slug = str(raw or "").strip()
            atributo = ""
        if not slug or slug in seen:
            continue
        seen.add(slug)
        normalized.append({"slug": slug, "atributo": atributo})
    return normalized


def _apply_talents(personagem, build):
    from .models import TbPersonagemAtributoBonus, TbPersonagemTalento, TbTalento
    from .views import _talento_attr_options

    rows = _normalize_talents(build)
    slugs = [row["slug"] for row in rows]
    talents = {obj.slug: obj for obj in TbTalento.objects.filter(
        slug__in=slugs, tipo__iexact="geral")}
    if len(talents) != len(slugs):
        raise PathbuilderError("Um dos talentos livres selecionados nao existe.")
    owned = set(personagem.talentos.exclude(
        id_talento__isnull=True).values_list("id_talento_id", flat=True))
    issues = []
    for row in rows:
        slug = row["slug"]
        talento = talents[slug]
        if talento.id_talento in owned:
            continue
        TbPersonagemTalento.objects.create(
            id_personagem=personagem,
            id_talento=talento,
            categoria="pathbuilder",
            nivel=personagem.nivel,
            nome=talento.nome,
        )
        atributo = row["atributo"]
        permitidos = _talento_attr_options(talento)
        if not atributo:
            issues.append("Escolha o atributo de +1 concedido por %s." % talento.nome)
        elif atributo not in permitidos:
            issues.append("%s nao pode aumentar %s." % (talento.nome, atributo))
        else:
            TbPersonagemAtributoBonus.objects.create(
                id_personagem=personagem,
                atributo=atributo,
                valor=1,
                origem="Talento %s (Pathbuilder)" % talento.nome,
                origem_tipo="pathbuilder",
            )
    return issues


def _normalize_racial_talents(build):
    rows = build.get("talentos_raciais") or []
    if not isinstance(rows, list) or len(rows) > 20:
        raise PathbuilderError("Talentos raciais do laboratorio invalidos.")
    normalized = []
    seen = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        nivel = _int_between(raw.get("nivel"), 1, 20, "Nivel do talento racial")
        nome = str(raw.get("nome") or "").strip()
        if nivel in seen or not nome:
            continue
        seen.add(nivel)
        normalized.append({"nivel": nivel, "nome": nome})
    return sorted(normalized, key=lambda row: row["nivel"])


def _apply_racial_talents(personagem, build):
    """Aplica marcos raciais usando o mesmo resolvedor do level-up real."""
    from .views import _lvl_aplicar_talento_racial, _pendencias_talento_racial

    selected = {row["nivel"]: row["nome"] for row in _normalize_racial_talents(build)}
    initial = _pendencias_talento_racial(personagem)
    available_levels = {int(group["nivel"]) for group in initial}
    groups = []
    issues = []
    for initial_group in initial:
        nivel = int(initial_group["nivel"])
        # Recalcula a cada marco: uma escolha anterior remove duplicatas do universo
        # seguinte exatamente como no fluxo de level-up.
        current_group = next((group for group in _pendencias_talento_racial(personagem)
                              if int(group["nivel"]) == nivel), initial_group)
        nome = selected.get(nivel, "")
        groups.append({
            "nivel": nivel,
            "selecionado": nome,
            "opcoes": current_group.get("opcoes") or [],
        })
        if not nome:
            continue
        errors = _lvl_aplicar_talento_racial(
            personagem, {"nivel": nivel, "talento": nome})
        if errors:
            issues.append("Talento racial invalido no nivel %d: %s." % (nivel, nome))
    for nivel in sorted(set(selected) - available_levels):
        issues.append("O talento racial escolhido para o nivel %d nao esta liberado." % nivel)
    return groups, issues


def _apply_items(personagem, build):
    from .models import TbItemMagico, TbItemMundano, TbPersonagemItem

    rows = build.get("itens") or []
    if not isinstance(rows, list) or len(rows) > 100:
        raise PathbuilderError("Inventario do laboratorio invalido.")
    mundane_slugs = {
        str(row.get("slug") or "") for row in rows
        if isinstance(row, dict) and row.get("tipo") == "mundano"
    }
    magic_slugs = {
        str(row.get("slug") or "") for row in rows
        if isinstance(row, dict) and row.get("tipo") == "magico"
    }
    mundane = {obj.slug: obj for obj in TbItemMundano.objects.filter(slug__in=mundane_slugs)}
    magic = {obj.slug: obj for obj in TbItemMagico.objects.filter(slug__in=magic_slugs)}
    if len(mundane) != len(mundane_slugs) or len(magic) != len(magic_slugs):
        raise PathbuilderError("Um dos itens selecionados nao existe.")

    for row in rows:
        if not isinstance(row, dict):
            continue
        slug = str(row.get("slug") or "")
        qtd = _int_between(row.get("qtd", 1), 1, 999, "Quantidade do item")
        equipped = bool(row.get("equipado"))
        attuned = bool(row.get("sintonizado"))
        if row.get("tipo") == "mundano":
            item = mundane[slug]
            TbPersonagemItem.objects.create(
                id_personagem=personagem,
                qtd=qtd,
                nome=item.nome,
                custo=item.preco or "",
                peso=str(item.peso or ""),
                equipado=equipped,
                sintonizado=False,
                tags_json=item.tags_json or [],
                origem_tipo="pathbuilder",
            )
        elif row.get("tipo") == "magico":
            item = magic[slug]
            TbPersonagemItem.objects.create(
                id_personagem=personagem,
                qtd=qtd,
                nome=item.nome,
                custo=str(item.preco or ""),
                equipado=equipped,
                sintonizado=attuned,
                id_item_magico=item,
                origem_tipo="pathbuilder",
            )
        else:
            raise PathbuilderError("Tipo de item invalido.")


def _apply_spells(personagem, build):
    from .pathbuilder_spells import apply_spell_selection

    try:
        apply_spell_selection(personagem, build)
    except ValueError as exc:
        raise PathbuilderError(str(exc)) from exc


def _groups_with_keys(personagem):
    from . import picks

    counters = {}
    groups = []
    for group in picks.resolve_personagem(personagem):
        signature = (
            group.get("kind") or "",
            group.get("persist_tipo") or group.get("tipo") or "",
            str(group.get("classe_id") or 0),
            slugify(group.get("origem") or "origem"),
        )
        occurrence = counters.get(signature, 0)
        counters[signature] = occurrence + 1
        group["pathbuilder_key"] = "%s|%s|%s|%s|%d" % (
            signature[0], signature[1], signature[2], signature[3], occurrence)
        groups.append(group)
    return groups


def _readback_values(group):
    values = []
    for row in group.get("escolhidas") or []:
        value = row.get("valor")
        if value is None and row.get("id_opcao") is not None:
            value = row["id_opcao"]
        if value is not None:
            values.append(str(value))
    return values


def _apply_choices(personagem, build):
    from . import picks

    incoming = build.get("escolhas") or {}
    if not isinstance(incoming, dict):
        raise PathbuilderError("Escolhas da build invalidas.")
    incoming = {
        str(key): list(dict.fromkeys(str(value) for value in values if value))
        for key, values in incoming.items() if isinstance(values, list)
    }
    for _pass in range(8):
        changed = False
        for group in _groups_with_keys(personagem):
            requested = incoming.get(group["pathbuilder_key"]) or []
            if not requested or not group.get("pendentes"):
                continue
            existing = set(_readback_values(group))
            values = [value for value in requested if value not in existing]
            if not values:
                continue
            pending = int(group.get("pendentes") or 0)
            if len(values) > pending:
                raise PathbuilderError("%s aceita somente %d nova(s) escolha(s)."
                                       % (group.get("label") or group["kind"], pending))
            validation_group = dict(group)
            validation_group["n"] = len(values)
            errors = picks.registry_entry(group["kind"])["validate"](
                validation_group, values)
            if errors:
                raise PathbuilderError(" ".join(errors))
            group["slot_base"] = int(group.get("prox_slot") or 0)
            picks.registry_entry(group["kind"])["persist"](personagem, group, values)
            changed = True
        if not changed:
            break


def _choice_options(group):
    options = []
    for option in group.get("universo") or []:
        base_value = str(option.get("slug")
                         if option.get("slug") is not None else option.get("id"))
        masteries = option.get("maestrias") or []
        if masteries:
            for mastery in masteries:
                options.append({
                    "valor": "%s|%s" % (base_value, mastery.get("slug")),
                    "nome": "%s - %s" % (
                        option.get("nome") or base_value,
                        mastery.get("nome") or mastery.get("slug")),
                    "descricao": mastery.get("efeito") or "",
                    "meta": option.get("cat") or "",
                })
        else:
            options.append({
                "valor": base_value,
                "nome": option.get("nome") or base_value,
                "ja_proficiente": bool(option.get("ja_proficiente")),
                "descricao": option.get("descricao") or option.get("efeito") or "",
                "meta": option.get("cat") or option.get("pre") or "",
            })
    return options


def _choice_groups(personagem, build):
    incoming = build.get("escolhas") or {}
    groups = []
    for group in _groups_with_keys(personagem):
        options = _choice_options(group)
        known = {row["valor"] for row in options}
        resolvidas = []
        for chosen in group.get("escolhidas") or []:
            value = chosen.get("valor")
            if value is None and chosen.get("id_opcao") is not None:
                value = chosen["id_opcao"]
            if value is None:
                continue
            resolvidas.append({"valor": str(value),
                               "nome": chosen.get("nome") or str(value)})
            if str(value) not in known:
                options.append({
                    "valor": str(value),
                    "nome": chosen.get("nome") or str(value),
                    "descricao": "",
                    "meta": "Selecionada",
                })
        groups.append({
            "key": group["pathbuilder_key"],
            "origem": group.get("origem") or "",
            "label": group.get("label") or group.get("tipo_display")
                     or group.get("tipo") or group.get("kind"),
            "kind": group.get("kind") or "",
            "limite": int(group.get("n") or 0),
            "usados": int(group.get("usados") or 0),
            "pendentes": int(group.get("pendentes") or 0),
            "classe": group.get("classe") or "",
            "resolvidas": resolvidas,
            "selecionadas": list(dict.fromkeys(
                str(value) for value in incoming.get(group["pathbuilder_key"], []) if value)),
            "opcoes": options,
        })
    return groups


def _attack_rows(ficha):
    attacks = ficha.get("ataques") or []
    if isinstance(attacks, dict):
        return attacks.get("perfis") or []
    return attacks if isinstance(attacks, list) else []


def _average_damage(expression):
    import re

    total = 0.0
    matched = False
    for count, sides in re.findall(r"(\d+)d(\d+)", str(expression or "").lower()):
        total += int(count) * (int(sides) + 1) / 2.0
        matched = True
    return round(total, 1) if matched else None


def _combat_metrics(ficha):
    attacks = _attack_rows(ficha)
    bonuses = [int(row["bonus_ataque"]) for row in attacks
               if row.get("bonus_ataque") is not None]
    averages = [_average_damage(row.get("dano") or row.get("dado")) for row in attacks]
    averages = [value for value in averages if value is not None]
    return {
        "melhor_bonus_ataque": max(bonuses) if bonuses else None,
        "maior_dano_medio": max(averages) if averages else None,
        "quantidade_ataques": len(attacks),
    }


def _orcamento(personagem, ficha, build):
    """ORCAMENTO da build — o editor gasta, nao adivinha.

    O antigo laboratorio deixava o jogador somar +1 de atributo a mao e SO DEPOIS
    reclamava ("os ASIs restantes representam 4 pontos; a build distribuiu 2"). Aqui o
    numero de slots de ASI, quantos foram gastos em talento e quantos pontos sobram vem
    do servidor, e a UI bloqueia o botao quando o saldo zera.
    """
    from .views import _asi_slots

    slots = len(_asi_slots(personagem))
    talentos = len(_normalize_talents(build))
    pontos_usados = sum(int(value or 0)
                        for value in (build.get("atributos_bonus") or {}).values())
    slots_em_pontos = max(0, slots - talentos)
    sint_usada = sum(1 for item in (build.get("itens") or []) if item.get("sintonizado"))
    return {
        "asi_slots": slots,
        "asi_em_talento": talentos,
        "asi_em_pontos": slots_em_pontos,
        "pontos_disponiveis": slots_em_pontos * 2,
        "pontos_usados": pontos_usados,
        "pontos_restantes": slots_em_pontos * 2 - pontos_usados,
        "sintonizacao_usada": sint_usada,
        "sintonizacao_maxima": int(ficha.get("sintonizacao_maxima") or 3),
    }


def _rules_diagnostics(personagem, ficha, build, groups, racial_groups, orcamento,
                       extra_issues=None, spell_issues=None):
    from .character_engine import _subclass_min_level

    spell_issues = list(spell_issues or [])
    issues = list(extra_issues or []) + spell_issues
    for pc in personagem.classes.select_related("id_classe", "id_subclasse"):
        minimum = _subclass_min_level(pc.id_classe)
        if minimum and int(pc.nivel or 0) >= minimum and not pc.id_subclasse_id:
            issues.append("Escolha a subclasse de %s liberada no nivel %d."
                          % (pc.id_classe.nome, minimum))
    pending = sum(int(group.get("pendentes") or 0) for group in groups)
    if pending:
        for group in groups:
            if group.get("pendentes"):
                issues.append("Resolva %d escolha(s) de %s (%s)." % (
                    group['pendentes'], group['label'],
                    group.get('origem') or group.get('classe') or 'personagem'))
    racial_pending = sum(1 for group in racial_groups if not group.get("selecionado"))
    if racial_pending:
        issues.append("Escolha %d talento(s) racial(is) liberado(s) por nivel." % racial_pending)
    if orcamento["asi_em_talento"] > orcamento["asi_slots"]:
        issues.append("A build usa %d talento(s) livre(s), mas possui %d slot(s) de ASI."
                      % (orcamento["asi_em_talento"], orcamento["asi_slots"]))
    if orcamento["pontos_usados"] != orcamento["pontos_disponiveis"]:
        issues.append("Os ASIs restantes representam %d ponto(s); a build distribuiu %d."
                      % (orcamento["pontos_disponiveis"], orcamento["pontos_usados"]))
    if orcamento["sintonizacao_usada"] > orcamento["sintonizacao_maxima"]:
        issues.append("A build sintoniza %d itens; o limite derivado e %d."
                      % (orcamento["sintonizacao_usada"], orcamento["sintonizacao_maxima"]))
    armor = [item for item in (ficha.get("inventario") or [])
             if item.get("equipado")
             and str(item.get("tipo_equip") or "").startswith("armadura")]
    shields = [item for item in (ficha.get("inventario") or [])
               if item.get("equipado") and item.get("tipo_equip") == "escudo"]
    if len(armor) > 1:
        issues.append("Ha mais de uma armadura equipada.")
    if len(shields) > 1:
        issues.append("Ha mais de um escudo equipado.")
    for sigla, data in (ficha.get("atributos") or {}).items():
        if int((data or {}).get("valor") or 0) > 20:
            issues.append("%s ultrapassa o limite normal de atributo 20." % sigla)
    return {"modo": str(build.get("modo") or "sandbox"),
            "valida": not issues, "problemas": issues, "magias": spell_issues}


def _folha_html(personagem, ficha, magias_info):
    """A PREVIA E A FICHA: renderiza os partials da aba Ficha em modo leitura.

    Roda DENTRO da transacao desfeita (as querysets do template sao avaliadas aqui), e
    devolve exatamente o markup denso da folha real — banner, atributos, selos de CA/PV,
    ataques, caracteristicas. Zero markup paralelo, zero drift."""
    from django.template.loader import render_to_string

    from .views import _consumiveis_ficha_cards, _mochila_ficha, _raca_linha_ficha

    return render_to_string("home/partials/_pathbuilder_folha.html", {
        "p": personagem,
        "ficha": ficha,
        "mochila": _mochila_ficha(personagem, ficha),
        "consumiveis_cards": _consumiveis_ficha_cards(personagem, ficha),
        "magias_info": magias_info,
        "raca_linha": _raca_linha_ficha(personagem),
        "pode_editar": False,
        "folha_readonly": True,
        "appearance": {},
    })


def _summary(ficha, personagem, build, racial_groups=None, extra_issues=None):
    """SO o que o EDITOR consome. A folha vai em `ficha_html` (markup da ficha real)."""
    from .views import _magias_sheet_info

    from .pathbuilder_spells import spell_review

    spell_issues, spell_sources = spell_review(personagem, ficha)
    magias_info = _magias_sheet_info(personagem, ficha, [])
    choice_groups = _choice_groups(personagem, build)
    orcamento = _orcamento(personagem, ficha, build)
    pathbuilder_bonus = {sigla: 0 for sigla in ("FOR", "DES", "CON", "INT", "SAB", "CAR")}
    for atributo, valor in personagem.atributo_bonus.filter(
            origem_tipo="pathbuilder").values_list("atributo", "valor"):
        if atributo in pathbuilder_bonus:
            pathbuilder_bonus[atributo] += int(valor or 0)

    summary = {
        "nome": personagem.nome,
        "nivel": ficha.get("nivel_total"),
        "pb": ficha.get("bonus_proficiencia"),
        "pv": (ficha.get("pv") or {}).get("maximo_calculado"),
        "ca": ficha.get("ca"),
        "iniciativa": ficha.get("iniciativa"),
        "velocidade": ficha.get("velocidade"),
        "classes": ficha.get("classes") or [],
        # Atributos e talentos: o editor precisa do valor final para mostrar o efeito da
        # distribuicao no proprio botao (+1 mostra 16 -> 17), nao para desenhar ficha.
        "atributos": [{
            "sig": sigla,
            "valor": ((ficha.get("atributos") or {}).get(sigla) or {}).get("valor"),
            "mod": ((ficha.get("atributos") or {}).get(sigla) or {}).get("mod", 0),
        } for sigla in ("FOR", "DES", "CON", "INT", "SAB", "CAR")],
        "atributos_bonus_aplicados": {
            sigla: int((build.get("atributos_bonus") or {}).get(sigla) or 0)
            for sigla in ("FOR", "DES", "CON", "INT", "SAB", "CAR")
        },
        "atributos_pathbuilder_aplicados": pathbuilder_bonus,
        "features": [{
            "nome": row.get("nome") or "",
            "origem": row.get("origem") or "",
            "fonte": row.get("fonte") or "",
            "nivel": row.get("nivel"),
        } for row in (ficha.get("features") or [])],
        "inventario": ficha.get("inventario") or [],
        "magias": ficha.get("magias") or [],
        "magias_fontes": spell_sources,
        "ataques": _attack_rows(ficha),
        "avisos": ficha.get("avisos") or [],
        "escolhas_grupos": choice_groups,
        "talentos_raciais_grupos": racial_groups or [],
        # Resumo das pendencias: SEM repetir o universo de opcoes (o grupo da Maestria de
        # Arma tem 128 — duplicar dobrava o payload de cada preview a troco de nada).
        "escolhas_pendentes": [{
            "key": group["key"],
            "label": group["label"],
            "classe": group["classe"],
            "origem": group["origem"],
            "pendentes": group["pendentes"],
        } for group in choice_groups if group.get("pendentes")],
        # SO o cabecalho da conjuracao: a lista completa (com descricao de cada magia)
        # ficaria em ~120 KB por request e ja esta renderizada na folha.
        "conjuracao": {
            "spellcasters": [{
                "classe": row.get("classe"),
                "ability": row.get("ability"),
                "cd": row.get("cd"),
                "ataque": row.get("ataque"),
                "prepara": row.get("prepara"),
            } for row in (magias_info.get("spellcasters") or [])],
            "slots": magias_info.get("slots") or [],
            "total": magias_info.get("total") or 0,
        },
        "orcamento": orcamento,
        "metricas_combate": _combat_metrics(ficha),
        "ficha_html": _folha_html(personagem, ficha, magias_info),
    }
    summary["validacao"] = _rules_diagnostics(
        personagem, ficha, build, choice_groups, racial_groups or [], orcamento,
        extra_issues=extra_issues, spell_issues=spell_issues)
    return summary


def simulate_build(user, creator_data, build):
    """Retorna a build derivada e garante rollback mesmo em caso de sucesso."""
    from .character_engine import derive
    from .views import _criador_persistir, _criador_resolver

    resolved, errors = _criador_resolver(creator_data)
    if errors:
        raise PathbuilderError(" ".join(errors))

    try:
        with transaction.atomic():
            personagem = _criador_persistir(user, creator_data, resolved)
            _apply_classes(personagem, creator_data, build)
            talent_issues = _apply_talents(personagem, build)
            _apply_attribute_bonus(personagem, build)
            racial_groups, racial_issues = _apply_racial_talents(personagem, build)
            _apply_items(personagem, build)
            _apply_choices(personagem, build)
            _apply_spells(personagem, build)
            ficha = derive(personagem)
            result = _summary(
                ficha, personagem, build, racial_groups,
                extra_issues=talent_issues + racial_issues)
            transaction.set_rollback(True)
    except PathbuilderError:
        raise
    return result
