# -*- coding: utf-8 -*-
"""Remove residuos de importacao/traducao do banco de conteudo.

Este comando cobre os restos que sobram depois dos importadores principais:
nomes/labels de criaturas em ingles, frases tecnicas frequentes nos statblocks
e titulos de referencia em itens magicos. Nao usa nem preserva source/page como
conteudo do jogo.
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from home.management.commands.importar_bestiario_csv import (
    SIZE_PT,
    _descricao_markdown,
    _traduz_alinhamento,
    _traduz_dano_condicao,
    _traduz_feature,
    _traduz_nome_criatura,
    _traduz_tipo,
)


ITEM_REPLACES = (
    ("Plate Armor of Etherealness", "Armadura de Placas da Eterealidade"),
    ("Orrery of the Wanderer", "Orrery do Andarilho"),
    ("The Witherbloom Primer", "A Cartilha de Witherbloom"),
    ("Witherbloom College", "Colégio Witherbloom"),
    ("Turn Undead", "Expulsar Mortos-vivos"),
    ("Turn the Unholy", "Expulsar Profanos"),
    ("Finesse", "Acuidade"),
    ("Icewind Dale: Rime of the Frostmaiden", "Vale do Vento Gélido: Canção da Donzela do Gelo"),
    ("The Everlight", "A Luz Eterna"),
    ("Chroma Conclave", "Conclave Cromático"),
    ("The Whispered One", "O Sussurrado"),
)


CREATURE_REPLACES = (
    ("natural armor", "armadura natural"),
    ("Natural Armor", "armadura natural"),
    ("plate armor", "armadura de placas"),
    ("Plate Armor", "armadura de placas"),
    ("psychic defense", "defesa psíquica"),
    ("Psychic Defense", "defesa psíquica"),
    ("unimpeded by magical darkness", "sem impedimento por escuridão mágica"),
    ("one language of its creator's choice", "um idioma à escolha de seu criador"),
    ("one language of its creator", "um idioma de seu criador"),
    ("plus up to five other languages", "mais até cinco outros idiomas"),
    ("plus five other languages", "mais cinco outros idiomas"),
    ("plus four other languages", "mais quatro outros idiomas"),
    ("plus three other languages", "mais três outros idiomas"),
    ("plus two other languages", "mais dois outros idiomas"),
    ("plus one other language", "mais um outro idioma"),
    ("all languages", "todos os idiomas"),
    ("the spell's level", "o nível da magia"),
    ("per spell level", "por nível da magia"),
    ("requires level 4+ spell", "requer magia de nível 4+"),
    ("that is nonmagical", "que não seja mágico"),
    ("cold form only", "apenas forma de frio"),
    ("with Mind Blank", "com Mente Vazia"),
    ("damage of the type matching the animated breath's form", "dano do tipo correspondente à forma do sopro animado"),
    ("damage of the type matching the animated form", "dano do tipo correspondente à forma animada"),
    ("Celestial, Fey, or Fiend", "Celestial, Feérico ou Corruptor"),
    ("celestial, fey, or fiend", "celestial, feérico ou corruptor"),
    ("construct", "Construto"),
    ("elemental", "Elemental"),
)


CURRENT_NAME_REPLACES = (
    ("Firenewt Bruxo of Imix", "Tritão de Fogo Bruxo de Imix"),
    ("Frost Gigante", "Gigante do Gelo"),
    ("Merfolk Escaramucador", "Tritão Escaramuçador"),
    ("Lizardfolk", "Povo-Lagarto"),
    ("Bugbear Stalker", "Bugbear Espreitador"),
    ("Shield Guardian", "Guardião de Escudo"),
    ("Guardian Naga", "Naga Guardiã"),
    ("Flail Snail", "Caracol Mangual"),
    ("Clockwork Bronze Batedor", "Batedor Mecânico de Bronze"),
    ("Clockwork Iron Cobra", "Cobra Mecânica de Ferro"),
    ("Clockwork Oaken Bolter", "Atirador Mecânico de Carvalho"),
    ("Clockwork Stone Defender", "Defensor Mecânico de Pedra"),
)


def _replace_many(text, replaces):
    if not isinstance(text, str) or not text:
        return text
    out = text
    for src, dst in replaces:
        out = out.replace(src, dst)
    out = re.sub(r"\bor\s+([\d.,]+)\s+in lair\b", r"ou \1 no covil", out, flags=re.I)
    out = re.sub(r"\bexhaustion\b", "exaustão", out, flags=re.I)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _clean_item_text(text):
    return _replace_many(text, ITEM_REPLACES)


def _clean_creature_text(text):
    out = _replace_many(text, CREATURE_REPLACES)
    out = _replace_many(out, CURRENT_NAME_REPLACES)
    out = _traduz_dano_condicao(out)
    return out


def _traduz_tamanho(valor):
    valor = _text_value(valor)
    return SIZE_PT.get(valor, valor)


def _text_value(valor):
    if valor is None:
        return ""
    if isinstance(valor, dict):
        for key in ("type", "name", "value", "text"):
            if valor.get(key):
                return _text_value(valor[key])
        return ", ".join(_text_value(v) for v in valor.values() if _text_value(v))
    if isinstance(valor, list):
        return ", ".join(_text_value(v) for v in valor if _text_value(v))
    return str(valor).strip()


def _traduz_tipo_seguro(valor):
    return _traduz_tipo(_text_value(valor))


def _traduz_alinhamento_seguro(valor):
    return _traduz_alinhamento(_text_value(valor))


def _normalize_display_fields(sb):
    text_keys = (
        "ac_text",
        "hp",
        "speed",
        "saving_throws",
        "senses",
        "languages",
        "cr",
    )
    list_keys = (
        "skills",
        "damage_resistances",
        "damage_immunities",
        "condition_immunities",
    )
    for key in text_keys:
        if key in sb:
            sb[key] = _clean_creature_text(_text_value(sb.get(key)))
    for key in list_keys:
        value = sb.get(key)
        if isinstance(value, list):
            sb[key] = [_clean_creature_text(_text_value(item)) for item in value if _text_value(item)]
        elif value:
            sb[key] = [_clean_creature_text(_text_value(value))]
    return sb


def _clean_statblock(value, parent_key=None):
    if isinstance(value, list):
        return [_clean_statblock(item, parent_key=parent_key) for item in value]
    if not isinstance(value, dict):
        if isinstance(value, str):
            if parent_key == "name":
                return _traduz_feature(value)
            if parent_key in {"type", "type_en"}:
                return _traduz_tipo_seguro(value)
            if parent_key in {"size", "size_en"}:
                return _traduz_tamanho(value)
            if parent_key in {"alignment", "alignment_en"}:
                return _traduz_alinhamento_seguro(value)
            return _clean_creature_text(value)
        return value

    out = {}
    for key, raw in value.items():
        if key in {"source", "source_en", "page"}:
            continue
        out[key] = _clean_statblock(raw, parent_key=key)

    if out.get("name_en"):
        out["name"] = _traduz_nome_criatura(out["name_en"]) if parent_key is None else _traduz_feature(out["name_en"])
    elif isinstance(out.get("name"), str):
        out["name"] = _clean_creature_text(_traduz_feature(out["name"]))

    if out.get("type_en"):
        out["type"] = _traduz_tipo_seguro(out["type_en"])
    elif isinstance(out.get("type"), str):
        out["type"] = _traduz_tipo_seguro(out["type"])

    if out.get("size_en"):
        out["size"] = _traduz_tamanho(out["size_en"])
    elif isinstance(out.get("size"), str):
        out["size"] = _traduz_tamanho(out["size"])

    if out.get("alignment_en"):
        out["alignment"] = _traduz_alinhamento_seguro(out["alignment_en"])
    elif isinstance(out.get("alignment"), str):
        out["alignment"] = _traduz_alinhamento_seguro(out["alignment"])

    return out


class Command(BaseCommand):
    help = "Limpa residuos de ingles/source em itens magicos, mundanos e bestiario."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        from home.models import TbBestiario, TbItemMagico, TbItemMundano

        updates = []

        for obj in TbItemMagico.objects.all():
            changes = {}
            nome = _clean_item_text(obj.nome)
            desc = _clean_item_text(obj.descricao_markdown)
            if nome != obj.nome:
                changes["nome"] = nome
            if desc != (obj.descricao_markdown or "").strip():
                changes["descricao_markdown"] = desc
            if changes:
                updates.append((obj, changes))

        for obj in TbItemMundano.objects.all():
            desc = _clean_item_text(obj.descricao_markdown)
            if desc != (obj.descricao_markdown or "").strip():
                updates.append((obj, {"descricao_markdown": desc}))

        for obj in TbBestiario.objects.all():
            changes = {}
            sb = _clean_statblock(obj.statblock_json or {})
            nome = _clean_creature_text(_traduz_nome_criatura(sb.get("name_en") or obj.nome))
            tipo = _traduz_tipo_seguro(sb.get("type_en") or sb.get("type") or obj.tipo or "")
            tamanho = _traduz_tamanho(sb.get("size_en") or sb.get("size") or obj.tamanho or "")
            alinhamento = _traduz_alinhamento_seguro(sb.get("alignment_en") or sb.get("alignment") or obj.alinhamento or "")

            sb["name"] = nome
            sb["type"] = tipo
            sb["size"] = tamanho
            sb["alignment"] = alinhamento
            sb = _normalize_display_fields(sb)

            desc = _clean_creature_text(_descricao_markdown({}, sb))
            if nome != obj.nome:
                changes["nome"] = nome
            if tipo != (obj.tipo or ""):
                changes["tipo"] = tipo
            if tamanho != (obj.tamanho or ""):
                changes["tamanho"] = tamanho
            if alinhamento != (obj.alinhamento or ""):
                changes["alinhamento"] = alinhamento
            if sb != (obj.statblock_json or {}):
                changes["statblock_json"] = sb
            if desc != (obj.descricao_markdown or "").strip():
                changes["descricao_markdown"] = desc
            if changes:
                updates.append((obj, changes))

        if opts["apply"]:
            with transaction.atomic():
                for obj, changes in updates:
                    for field, value in changes.items():
                        setattr(obj, field, value)
                    obj.save(update_fields=list(changes.keys()))

        self.stdout.write(self.style.SUCCESS(
            "%s updates=%d" % ("APPLY" if opts["apply"] else "PREVIEW", len(updates))
        ))
