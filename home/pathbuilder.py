"""Laboratorio de builds sem persistencia.

O estado autoral vive no navegador. Cada preview materializa uma ficha real dentro de
uma transacao marcada para rollback, executa o mesmo ``derive`` da ficha e devolve apenas
dados serializaveis. Nenhum TbPersonagem sobrevive ao request.
"""

from django.db import transaction
from django.utils.text import slugify


class PathbuilderError(ValueError):
    pass


def catalogos():
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
        })

    classes = []
    for classe in TbClasse.objects.all().order_by("nome"):
        classes.append({
            "slug": classe.slug,
            "nome": classe.nome,
            "subclasse_nivel": _subclass_min_level(classe),
            "subclasses": subclasses.get(classe.slug, []),
        })

    mundanos = [{
        "slug": item.slug,
        "nome": item.nome,
        "categoria": item.get_categoria_display(),
        "equipavel": item.categoria in {"arma", "armadura"},
    } for item in TbItemMundano.objects.all().order_by("categoria", "nome")]

    magicos = [{
        "slug": item.slug,
        "nome": item.nome,
        "raridade": item.get_raridade_display(),
        "slot": item.get_slot_display(),
        "requer_sintonizacao": bool(item.requer_sintonizacao),
    } for item in TbItemMagico.objects.all().order_by("raridade", "nome")]

    talentos = [{
        "slug": talento.slug,
        "nome": talento.nome,
        "tipo": talento.tipo or "",
    } for talento in TbTalento.objects.all().order_by("tipo", "nome")]

    magias = [{
        "slug": magia.slug,
        "nome": magia.nome,
        "nivel": int(magia.nivel or 0),
        "escola": magia.escola or "",
    } for magia in TbMagia.objects.all().order_by("nivel", "nome")]

    return {
        "classes": classes,
        "talentos": talentos,
        "itens_mundanos": mundanos,
        "itens_magicos": magicos,
        "magias": magias,
    }


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

    slugs = [str(row.get("slug") or "") for row in requested if isinstance(row, dict)]
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


def _apply_talents(personagem, build):
    from .models import TbPersonagemTalento, TbTalento

    slugs = list(dict.fromkeys(str(value) for value in (build.get("talentos") or [])))
    if len(slugs) > 30:
        raise PathbuilderError("A build excede o limite de talentos do laboratorio.")
    talents = {obj.slug: obj for obj in TbTalento.objects.filter(slug__in=slugs)}
    if len(talents) != len(slugs):
        raise PathbuilderError("Um dos talentos selecionados nao existe.")
    owned = set(personagem.talentos.exclude(
        id_talento__isnull=True).values_list("id_talento_id", flat=True))
    for slug in slugs:
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
            )
        else:
            raise PathbuilderError("Tipo de item invalido.")


def _apply_spells(personagem, build):
    from .models import TbMagia, TbPersonagemMagia

    rows = build.get("magias") or []
    if not isinstance(rows, list) or len(rows) > 580:
        raise PathbuilderError("Lista de magias invalida.")
    slugs = list(dict.fromkeys(
        str(row.get("slug") or "") for row in rows if isinstance(row, dict)))
    spells = {obj.slug: obj for obj in TbMagia.objects.filter(slug__in=slugs)}
    if len(spells) != len(slugs):
        raise PathbuilderError("Uma das magias selecionadas nao existe.")
    existing = set(personagem.magias.exclude(
        id_magia__isnull=True).values_list("id_magia_id", flat=True))
    for row in rows:
        if not isinstance(row, dict):
            continue
        spell = spells[str(row.get("slug") or "")]
        if spell.id_magia in existing:
            continue
        TbPersonagemMagia.objects.create(
            id_personagem=personagem,
            id_magia=spell,
            nivel=spell.nivel,
            nome=spell.nome,
            preparada=bool(row.get("preparada", True)),
            origem="Pathbuilder",
        )
        existing.add(spell.id_magia)


def _pending_choices(personagem):
    from . import picks

    out = []
    for group in picks.resolve_personagem(personagem):
        if not group.get("pendentes"):
            continue
        out.append({
            "origem": group.get("origem") or "",
            "label": group.get("label") or group.get("tipo_display")
                     or group.get("tipo") or group.get("kind"),
            "pendentes": int(group.get("pendentes") or 0),
            "classe": group.get("classe") or "",
        })
    return out


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
        for chosen in group.get("escolhidas") or []:
            value = chosen.get("valor")
            if value is None and chosen.get("id_opcao") is not None:
                value = chosen["id_opcao"]
            if value is not None and str(value) not in known:
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


def _rules_diagnostics(personagem, ficha, build, groups):
    from .character_engine import _subclass_min_level
    from .views import _asi_slots

    issues = []
    for pc in personagem.classes.select_related("id_classe", "id_subclasse"):
        minimum = _subclass_min_level(pc.id_classe)
        if minimum and int(pc.nivel or 0) >= minimum and not pc.id_subclasse_id:
            issues.append("Escolha a subclasse de %s liberada no nivel %d."
                          % (pc.id_classe.nome, minimum))
    pending = sum(int(group.get("pendentes") or 0) for group in groups)
    if pending:
        issues.append("Resolva %d escolha(s) declarada(s) pelas tags." % pending)
    slots = len(_asi_slots(personagem))
    talents = len(build.get("talentos") or [])
    points = sum(int(value or 0)
                 for value in (build.get("atributos_bonus") or {}).values())
    if talents > slots:
        issues.append("A build usa %d talento(s) livre(s), mas possui %d slot(s) de ASI."
                      % (talents, slots))
    expected = max(0, slots - talents) * 2
    if points != expected:
        issues.append("Os ASIs restantes representam %d ponto(s); a build distribuiu %d."
                      % (expected, points))
    attuned = sum(1 for item in (build.get("itens") or []) if item.get("sintonizado"))
    attunement_max = int(ficha.get("sintonizacao_maxima") or 3)
    if attuned > attunement_max:
        issues.append("A build sintoniza %d itens; o limite derivado e %d."
                      % (attuned, attunement_max))
    armor = [item for item in (ficha.get("inventario") or [])
             if item.get("equipado")
             and str(item.get("tipo_equip") or "").startswith("armadura")]
    shields = [item for item in (ficha.get("inventario") or [])
               if item.get("equipado") and item.get("tipo_equip") == "escudo"]
    if len(armor) > 1:
        issues.append("Ha mais de uma armadura equipada.")
    if len(shields) > 1:
        issues.append("Ha mais de um escudo equipado.")
    return {"modo": str(build.get("modo") or "sandbox"),
            "valida": not issues, "problemas": issues}


def _summary(ficha, personagem, build):
    from .views import _magias_sheet_info
    attributes = []
    for sigla in ("FOR", "DES", "CON", "INT", "SAB", "CAR"):
        attr = (ficha.get("atributos") or {}).get(sigla) or {}
        save = (ficha.get("saves") or {}).get(sigla) or {}
        attributes.append({
            "sig": sigla,
            "valor": attr.get("valor"),
            "mod": attr.get("mod", 0),
            "save": save.get("bonus", 0),
            "save_prof": bool(save.get("proficiente")),
        })
    skills = [{
        "nome": row.get("nome"),
        "bonus": row.get("bonus"),
        "expertise": bool(row.get("expertise")),
    } for row in (ficha.get("pericias") or [])
        if row.get("proficiente") or row.get("expertise")]
    features = [{
        "nome": row.get("nome") or "",
        "origem": row.get("origem") or "",
        "fonte": row.get("fonte") or "",
        "nivel": row.get("nivel"),
    } for row in (ficha.get("features") or [])]
    choice_groups = _choice_groups(personagem, build)
    summary = {
        "nome": personagem.nome,
        "nivel": ficha.get("nivel_total"),
        "pb": ficha.get("bonus_proficiencia"),
        "pv": (ficha.get("pv") or {}).get("maximo_calculado"),
        "ca": ficha.get("ca"),
        "iniciativa": ficha.get("iniciativa"),
        "velocidade": ficha.get("velocidade"),
        "classes": ficha.get("classes") or [],
        "atributos": attributes,
        "pericias": skills,
        "features": features,
        "recursos": ficha.get("recursos") or {},
        "inventario": ficha.get("inventario") or [],
        "magias": ficha.get("magias") or [],
        "ataques": _attack_rows(ficha),
        "resistencias": ficha.get("resistencias") or [],
        "imunidades": ficha.get("imunidades") or [],
        "sentidos": ficha.get("sentidos") or [],
        "prof_armadura": ficha.get("proficiencias_armadura") or [],
        "prof_arma": ficha.get("proficiencias_arma") or [],
        "avisos": ficha.get("avisos") or [],
        "escolhas_grupos": choice_groups,
        "escolhas_pendentes": [
            group for group in choice_groups if group.get("pendentes")
        ],
        "conjuracao": _magias_sheet_info(personagem, ficha, []),
        "metricas_combate": _combat_metrics(ficha),
    }
    summary["validacao"] = _rules_diagnostics(
        personagem, ficha, build, choice_groups)
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
            _apply_attribute_bonus(personagem, build)
            _apply_talents(personagem, build)
            _apply_items(personagem, build)
            _apply_spells(personagem, build)
            _apply_choices(personagem, build)
            ficha = derive(personagem)
            result = _summary(ficha, personagem, build)
            transaction.set_rollback(True)
    except PathbuilderError:
        raise
    return result
