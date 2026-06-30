# -*- coding: utf-8 -*-
"""Gera tags_json basicas para criaturas do bestiario sem tags."""

import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from home.models import TbBestiario


SIZE_TAG = {
    "tiny": "miudo",
    "minimo": "miudo",
    "miudo": "miudo",
    "small": "pequeno",
    "pequeno": "pequeno",
    "medium": "medio",
    "medio": "medio",
    "large": "grande",
    "grande": "grande",
    "huge": "enorme",
    "enorme": "enorme",
    "gargantuan": "descomunal",
    "colossal": "descomunal",
    "colossal": "descomunal",
    "descomunal": "descomunal",
}

ABILITY_TAG = {
    "STR": "str",
    "DEX": "dex",
    "CON": "con",
    "INT": "int",
    "WIS": "wis",
    "CHA": "cha",
    "FOR": "str",
    "DES": "dex",
    "SAB": "wis",
    "CAR": "cha",
}

DAMAGE_TAG = {
    "acid": "acido",
    "acido": "acido",
    "bludgeoning": "concussao",
    "concussao": "concussao",
    "cold": "frio",
    "frio": "frio",
    "fire": "fogo",
    "fogo": "fogo",
    "force": "forca",
    "forca": "forca",
    "lightning": "raio",
    "raio": "raio",
    "necrotic": "necrotico",
    "necrotico": "necrotico",
    "piercing": "perfurante",
    "perfurante": "perfurante",
    "poison": "veneno",
    "veneno": "veneno",
    "psychic": "psiquico",
    "psiquico": "psiquico",
    "radiant": "radiante",
    "radiante": "radiante",
    "slashing": "cortante",
    "cortante": "cortante",
    "thunder": "trovejante",
    "trovejante": "trovejante",
}

CONDITION_TAG = {
    "blinded": "cego",
    "cego": "cego",
    "charmed": "enfeiticado",
    "enfeiticado": "enfeiticado",
    "deafened": "surdo",
    "surdo": "surdo",
    "exhaustion": "exaustao",
    "exaustao": "exaustao",
    "frightened": "amedrontado",
    "amedrontado": "amedrontado",
    "grappled": "agarrado",
    "agarrado": "agarrado",
    "incapacitated": "incapacitado",
    "incapacitado": "incapacitado",
    "invisible": "invisivel",
    "invisivel": "invisivel",
    "paralyzed": "paralisado",
    "paralisado": "paralisado",
    "petrified": "petrificado",
    "petrificado": "petrificado",
    "poisoned": "envenenado",
    "envenenado": "envenenado",
    "prone": "caido",
    "caido": "caido",
    "restrained": "restringido",
    "restringido": "restringido",
    "stunned": "atordoado",
    "atordoado": "atordoado",
    "unconscious": "inconsciente",
    "inconsciente": "inconsciente",
}

SKILL_TAG = {
    "acrobatics": "acrobacia",
    "acrobacia": "acrobacia",
    "animal handling": "adestrar-animais",
    "adestrar animais": "adestrar-animais",
    "arcana": "arcanismo",
    "arcanismo": "arcanismo",
    "athletics": "atletismo",
    "atletismo": "atletismo",
    "deception": "enganacao",
    "enganacao": "enganacao",
    "history": "historia",
    "historia": "historia",
    "insight": "intuicao",
    "intuicao": "intuicao",
    "intimidation": "intimidacao",
    "intimidacao": "intimidacao",
    "investigation": "investigacao",
    "investigacao": "investigacao",
    "medicine": "medicina",
    "medicina": "medicina",
    "nature": "natureza",
    "natureza": "natureza",
    "perception": "percepcao",
    "percepcao": "percepcao",
    "performance": "atuacao",
    "atuacao": "atuacao",
    "persuasion": "persuasao",
    "persuasao": "persuasao",
    "religion": "religiao",
    "religiao": "religiao",
    "sleight of hand": "prestidigitacao",
    "prestidigitacao": "prestidigitacao",
    "stealth": "furtividade",
    "furtividade": "furtividade",
    "survival": "sobrevivencia",
    "sobrevivencia": "sobrevivencia",
}

SENSE_TAG = {
    "darkvision": "darkvision",
    "blindsight": "blindsight",
    "truesight": "truesight",
    "tremorsense": "tremorsense",
}

MOVE_TAG = {
    "fly": "fly",
    "voo": "fly",
    "flying": "fly",
    "swim": "swim",
    "nadar": "swim",
    "swimming": "swim",
    "climb": "climb",
    "escalar": "climb",
    "climbing": "climb",
    "burrow": "burrow",
    "escavar": "burrow",
    "burrowing": "burrow",
}


def _clean_int(text):
    match = re.search(r"\d+", str(text or ""))
    return int(match.group(0)) if match else None


def _signed(value):
    value = str(value or "").strip()
    match = re.search(r"[-+]?\d+", value)
    if not match:
        return None
    number = int(match.group(0))
    return f"{number:+d}"


def _split_parts(text):
    text = str(text or "").replace(" and ", ", ").replace(" e ", ", ")
    return [p.strip() for p in re.split(r"[,;]", text) if p.strip()]


def _first_number_tag(text):
    number = _clean_int(text)
    return str(number) if number is not None else None


def _map_size(value):
    key = slugify(str(value or "")).replace("-", "")
    if key in SIZE_TAG:
        return SIZE_TAG[key]
    return SIZE_TAG.get(str(value or "").strip().lower())


def _damage_tags(prefix, entries):
    tags = []
    for entry in entries or []:
        lower = str(entry or "").lower()
        qualifier = "(non-magical)" if "nonmagical" in lower or "non-magical" in lower else ""
        for raw, tag in DAMAGE_TAG.items():
            if re.search(rf"\b{re.escape(raw)}\b", lower):
                tags.append(f"{prefix}:{tag}{qualifier}")
    return tags


def _condition_tags(entries):
    tags = []
    for entry in entries or []:
        lower = str(entry or "").lower()
        for raw, tag in CONDITION_TAG.items():
            if re.search(rf"\b{re.escape(raw)}\b", lower):
                tags.append(f"cond-immune:{tag}")
    return tags


def _save_tags(text):
    tags = []
    for ability, value in re.findall(r"\b(STR|DEX|CON|INT|WIS|CHA|FOR|DES|SAB|CAR)\b\s*([+-]\d+)", str(text or ""), re.I):
        ab = ABILITY_TAG.get(ability.upper())
        if ab:
            tags.append(f"save:{ab}={value}")
    return tags


def _skill_tags(text):
    tags = []
    for part in _split_parts(text):
        match = re.match(r"(.+?)\s*([+-]\d+)\b", part)
        if not match:
            continue
        name, value = match.group(1).strip().lower(), match.group(2)
        slug = SKILL_TAG.get(name) or SKILL_TAG.get(slugify(name).replace("-", " "))
        if slug:
            tags.append(f"check-bonus:{slug}={value}")
    return tags


def _speed_tags(text):
    tags = []
    for part in _split_parts(text):
        lower = part.lower()
        value = _first_number_tag(lower)
        if not value:
            continue
        move = None
        for raw, tag in MOVE_TAG.items():
            if re.search(rf"\b{re.escape(raw)}\b", lower):
                move = tag
                break
        if move:
            tags.append(f"move:{move}")
            tags.append(f"speed:{move}:={value}ft")
        else:
            tags.append(f"speed:{value}ft")
    return tags


def _sense_tags(text):
    tags = []
    lower = str(text or "").lower()
    for raw, tag in SENSE_TAG.items():
        for match in re.finditer(rf"\b{re.escape(raw)}\b\s*(\d+)\s*ft", lower):
            tags.append(f"sense:{tag}(range:{match.group(1)}ft)")
    passive = re.search(r"passive\s+perception\s+(\d+)", lower)
    if passive:
        tags.append(f"sense:passive-perception({passive.group(1)})")
    return tags


def _base_tags(obj):
    sb = obj.statblock_json if isinstance(obj.statblock_json, dict) else {}
    tags = []

    size = _map_size(sb.get("size") or sb.get("size_en") or obj.tamanho)
    if size:
        tags.append(f"size:{size}")

    ac_value = sb.get("ac")
    if isinstance(ac_value, list) and ac_value:
        first_ac = ac_value[0]
        ac = first_ac.get("ac") if isinstance(first_ac, dict) else _clean_int(first_ac)
    else:
        ac = ac_value or obj.ca
    if ac:
        tags.append(f"ca={ac}")

    hp = _clean_int(sb.get("hp") or obj.pv)
    if hp is not None:
        tags.append(f"hp:={hp}")

    tags.extend(_speed_tags(sb.get("speed")))
    tags.extend(_save_tags(sb.get("saving_throws")))
    tags.extend(_skill_tags(", ".join(sb.get("skills") or [])))
    tags.extend(_damage_tags("vuln", sb.get("damage_vulnerabilities")))
    tags.extend(_damage_tags("resist", sb.get("damage_resistances")))
    tags.extend(_damage_tags("immune", sb.get("damage_immunities")))
    tags.extend(_condition_tags(sb.get("condition_immunities")))
    tags.extend(_sense_tags(sb.get("senses")))

    for tag in sb.get("tags") or []:
        if isinstance(tag, str) and tag.strip():
            tags.append(tag.strip())

    return sorted(dict.fromkeys(tags))


class Command(BaseCommand):
    help = "Preenche tags_json basicas em criaturas do bestiario que ainda nao tem tags."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Grava as tags no banco.")
        parser.add_argument("--force", action="store_true", help="Regenera tambem criaturas que ja possuem tags.")
        parser.add_argument("--max", type=int, default=12, help="Quantidade de exemplos no relatorio.")

    @transaction.atomic
    def handle(self, *args, **options):
        apply = options["apply"]
        force = options["force"]
        exemplos = []
        processadas = com_tags = sem_dados = 0

        qs = TbBestiario.objects.all().order_by("slug")
        for obj in qs:
            if obj.tags_json and not force:
                continue
            processadas += 1
            tags = _base_tags(obj)
            if not tags:
                sem_dados += 1
                continue
            com_tags += 1
            if len(exemplos) < options["max"]:
                exemplos.append((obj.slug, obj.nome, tags[:10]))
            if apply:
                obj.tags_json = tags
                sb = obj.statblock_json if isinstance(obj.statblock_json, dict) else {}
                if sb:
                    sb["tags"] = tags
                    obj.statblock_json = sb
                    obj.save(update_fields=["tags_json", "statblock_json"])
                else:
                    obj.save(update_fields=["tags_json"])

        modo = "APLICADO" if apply else "PREVIEW"
        self.stdout.write(self.style.SUCCESS(f"{modo}: processadas={processadas} com_tags={com_tags} sem_dados={sem_dados}"))
        for slug, nome, tags in exemplos:
            self.stdout.write(f"  - {slug} | {nome}: {', '.join(tags)}")
