# -*- coding: utf-8 -*-
"""Gera tags_json para itens mundanos e magicos.

As tags sao derivadas de campos estruturados e texto importado. A ideia e manter
o backend lendo formulas genericas, sem criar excecoes por item especifico.
"""
import csv
import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify


MAGIC_CSV = Path("scratch/import_itens/itens_descricoes_en.csv")

DAMAGE_MAP = {
    "Conc.": "concussao",
    "Concussivo": "concussao",
    "Perf.": "perfurante",
    "Perfurante": "perfurante",
    "Cort.": "cortante",
    "Cortante": "cortante",
    "Acid": "acido",
    "Cold": "frio",
    "Fire": "fogo",
    "Force": "forca",
    "Lightning": "raio",
    "Necrotic": "necrotico",
    "Poison": "veneno",
    "Psychic": "psiquico",
    "Radiant": "radiante",
    "Thunder": "trovejante",
}

PROPERTY_MAP = {
    "Acuidade": "acuidade",
    "Adaptável": "adaptavel",
    "Alcance": "alcance",
    "Arremesso": "arremesso",
    "Carregar": "carregar",
    "Composto": "composto",
    "Duas Mãos": "duas-maos",
    "Empunhadura Longa": "empunhadura-longa",
    "Leve": "leve",
    "Munição": "municao",
    "Pareada": "pareada",
    "Pesada": "pesada",
    "Recarga": "recarga",
    "Técnica": "tecnica",
    "Versátil": "versatil",
}


def norm_slug(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def money_tag(value):
    if not value:
        return None
    text = str(value).strip().lower().replace(",", ".")
    text = text.replace(" ", "-")
    text = text.replace("po", "po").replace("pp", "pp").replace("pc", "pc").replace("pe", "pe")
    return re.sub(r"[^a-z0-9.-]+", "-", text).strip("-")


def weight_tag(value):
    if value is None:
        return None
    return ("%g-lb" % float(value)).replace(".", "p")


def clean_official_block(text):
    if not text:
        return text
    cleaned = re.sub(r"\s*### Dados oficiais[\s\S]*$", "", str(text), flags=re.I)
    cleaned = re.sub(r"\s*#### Regras rápidas[\s\S]*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*Tipo:\*\*[\s\S]*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*- \*\*(?:Tipo|Preço|Peso|Dano/CA|Propriedades|Maestria):\*\*[\s\S]*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def damage_tag(dano):
    if not dano:
        return None
    text = str(dano)
    m = re.search(r"(\d+d\d+|\d+)\s*([A-Za-zÀ-ÿ.]+)?", text)
    if not m:
        return None
    dice = m.group(1)
    dtype = None
    for key, val in DAMAGE_MAP.items():
        if key.lower().replace(".", "") in text.lower().replace(".", ""):
            dtype = val
            break
    return f"dmg:{dice}({dtype})" if dtype else f"dmg:{dice}"


def property_tags(propriedades):
    if not propriedades:
        return []
    out = []
    for raw in str(propriedades).split(","):
        part = raw.strip()
        if not part:
            continue
        base = re.sub(r"\s*\(.*\)", "", part).strip()
        if norm_slug(base) in {"nenhuma", "none"}:
            continue
        slug = PROPERTY_MAP.get(base) or norm_slug(base)
        if slug:
            out.append(f"add-property:{slug}")
        rng = re.search(r"\((\d+)\s*/\s*(\d+)\s*p", part)
        if rng:
            out.append(f"range:{rng.group(1)}/{rng.group(2)}ft")
        rec = re.search(r"Recarga\s*\((\d+)\)", part, re.I)
        if rec:
            out.append(f"reload:{rec.group(1)}")
    return out


def attack_kind_tags(item, propriedades):
    tags = ["attack:weapon"]
    sub = norm_slug(item.subcategoria or "")
    prop = norm_slug(propriedades or "")
    is_ranged = "dist" in sub or "fogo" in sub or "municao" in prop
    is_thrown = "arremesso" in prop
    if is_ranged:
        tags.append("attack:ranged")
    else:
        tags.append("attack:melee")
    if is_thrown:
        tags.append("attack:ranged")
    if "arma-simples" in sub:
        tags.append("requires:prof-arma-simples")
    elif "arma-marcial" in sub:
        tags.append("requires:prof-arma-marcial")
    elif "arma-fogo" in sub:
        tags.append("requires:prof-arma-fogo")
    return tags


def mastery_tags(item):
    tags = [t for t in (item.tags_json or []) if isinstance(t, str) and t.startswith("maestrias{")]
    if tags:
        return tags
    if not item.maestria:
        return []
    slugs = []
    for raw in str(item.maestria).split(","):
        m = re.search(r"\(([^)]+)\)", raw)
        en = norm_slug(m.group(1)) if m else None
        pt = norm_slug(re.sub(r"\s*\([^)]*\)", "", raw).strip())
        slugs.append(f"{pt}-{en}" if en and not pt.endswith(en) else pt)
    return ["maestrias{" + ", ".join(s for s in slugs if s) + "}"] if slugs else []


MANUAL_MUNDANE_TAGS = {
    "acid": [
        "consumable", "action=action", "attack:ranged", "range:20ft",
        "dmg:2d6(acido)",
    ],
    "holy-water": [
        "consumable", "action=action", "attack:ranged", "range:20ft",
        "target:creature(tipo:corruptor|morto-vivo)", "dmg:2d6(radiante)",
    ],
    "alchemist-s-fire": [
        "consumable", "action=action", "attack:ranged", "range:20ft",
        "dmg:1d4(fogo)", "apply:queimando(dmg:1d4(fogo), trigger=turn-start, extinguish{action=action, save{dex, cd=10}})",
    ],
    "oil": [
        "consumable", "action=action", "attack:ranged", "range:20ft",
        "aoe{cube:5ft, trigger=ignited, dmg:5(fogo), duration:2rounds}",
    ],
    "healer-s-kit": [
        "charges:10(reset:none)", "action=action", "resource-cost:charges:1", "stabilize",
    ],
    "antitoxin": [
        "consumable", "action=bonus-action", "adv:save{vs:veneno}(duration:1h)",
    ],
    "portable-ram": [
        "adv:str-check{break-door}", "str-check:+4(requires:assisted)",
    ],
    "hunting-trap": [
        "action=action", "trigger=step-on", "save{dex, cd=13}",
        "on-fail:{dmg:1d4(perfurante), speed:=0}", "escape{action=action, save{str, cd=13}}",
    ],
    "caltrops": [
        "consumable", "action=action", "aoe{cube:5ft, save{dex, cd=15}, on-fail:{dmg:1(perfurante), speed:*0.5}, avoid:half-speed}",
    ],
    "ball-bearings": [
        "consumable", "action=action", "aoe{cube:10ft, save{dex, cd=10}, on-fail:apply:caido, avoid:half-speed}",
    ],
    "torch": [
        "light:bright(radius:20ft)", "light:dim(radius:+20ft)", "duration:1h", "dmg:1(fogo)(as:improvised-weapon)",
    ],
    "bomb": [
        "consumable", "action=action", "range:60ft",
        "aoe{radius:5ft, save{dex, cd=12}, dmg:3d6(fogo), on-success:half}",
    ],
    "smoke-grenade": [
        "consumable", "action=action", "range:60ft",
        "aoe{radius:20ft, obscured:heavy, duration:1min, dispersed-by:strong-wind}",
    ],
    "gunpowder-keg": [
        "consumable", "trigger=ignite-or-fire-damage",
        "aoe{radius:10ft, save{dex, cd=12}, dmg:7d6(fogo), on-success:half, spreads-around-corners, ignites:flammable}",
    ],
    "gunpowder-powder-horn": [
        "consumable", "charges:10(reset:none)", "trigger=ignite-or-fire-damage",
        "aoe{radius:5ft, save{dex, cd=12}, dmg:3d6(fogo), on-success:half}",
    ],
    "net": [
        "action=action", "attack:ranged", "range:5ft", "target:creature(size<=large)",
        "save{dex, cd=8+dex-mod+pb}", "on-fail:apply:agarrado", "escape{action=action, save{str, cd=10}}",
    ],
    "rope": ["object-hp:2", "break{save{str, cd=17}}"],
    "silk-rope-50-feet": ["object-hp:2", "break{save{str, cd=17}}"],
    "chain": ["break{save{str, cd=20}}"],
    "manacles": [
        "apply:restringido(hands-only)", "escape{save{dex, cd=20}}", "break{save{str, cd=25}}",
        "unlock{tools:ladrao, save{dex, cd=15}}",
    ],
}


POISON_TAGS = {
    "basic-poison": ["consumable", "action=action", "apply-poison:weapon-or-ammo(qtd:3)", "trigger=hit", "save{con, cd=10}", "on-fail:dmg:1d4(veneno)", "duration:1min"],
    "assassin-s-blood": ["consumable", "save{con, cd=10}", "on-fail:{dmg:1d12(veneno), apply:envenenado(duration:24h)}"],
    "burnt-othur-fumes": ["consumable", "save{con, cd=13}", "on-fail:{dmg:3d6(veneno), restriction{heal}}", "repeat-save:turn-start(on-fail:dmg:1d6(veneno), end-after:3success)"],
    "carrion-crawler-mucus": ["consumable", "save{con, cd=13}", "on-fail:{apply:envenenado(duration:1min), apply:paralisado(while:envenenado)}", "repeat-save:turn-end"],
    "essence-of-ether": ["consumable", "save{con, cd=15}", "on-fail:{apply:envenenado(duration:8h), apply:inconsciente(while:envenenado, until:damage-or-shaken)}"],
    "lolth-s-sting": ["consumable", "trigger=hit", "save{con, cd=13}", "on-fail:{dmg:1d6(veneno), apply:envenenado(duration:1min), restriction{heal}}", "repeat-save:turn-end"],
    "malice": ["consumable", "save{con, cd=15}", "on-fail:apply:cego(duration:1h)"],
    "midnight-tears": ["consumable", "trigger=midnight-after-ingested", "save{con, cd=17}", "on-fail:dmg:9d6(veneno)", "on-success:half"],
    "oil-of-taggit": ["consumable", "save{con, cd=13}", "on-fail:{apply:envenenado(duration:24h), apply:inconsciente(while:envenenado, until:damage)}"],
    "pale-tincture": ["consumable", "save{con, cd=16}", "on-fail:{dmg:1d6(veneno), apply:envenenado, restriction{heal:this-damage}}", "repeat-save:24h(on-fail:dmg:1d6(veneno), end-after:3success)"],
    "purple-worm-poison": ["consumable", "trigger=hit", "save{con, cd=19}", "on-fail:dmg:12d6(veneno)", "on-success:half"],
    "serpent-venom": ["consumable", "trigger=hit", "save{con, cd=11}", "on-fail:dmg:3d6(veneno)", "on-success:half"],
    "torpor": ["consumable", "save{con, cd=15}", "on-fail:{apply:envenenado(duration:4d6h), apply:incapacitado(while:envenenado)}"],
    "truth-serum": ["consumable", "save{con, cd=11}", "on-fail:{apply:envenenado(duration:1h), restriction{lie}}"],
    "wyvern-poison": ["consumable", "trigger=hit", "save{con, cd=15}", "on-fail:dmg:7d6(veneno)", "on-success:half"],
}


def mundane_tags(item):
    if item.slug in POISON_TAGS:
        tags = POISON_TAGS[item.slug][:]
    else:
        tags = MANUAL_MUNDANE_TAGS.get(item.slug, [])[:]

    if item.categoria == "arma":
        tags.extend(attack_kind_tags(item, item.propriedades))
        dt = damage_tag(item.dano)
        if dt:
            tags.append(dt)
        tags.extend(property_tags(item.propriedades))
        tags.extend(mastery_tags(item))
    elif item.categoria == "armadura":
        if item.ca_base is not None:
            if item.tipo_equip == "escudo":
                tags.append(f"ca:+{item.ca_base}")
            else:
                tags.append(f"ca={item.ca_base}")
        if item.ca_limite_des is not None:
            tags.append(f"dex-ca-max:{item.ca_limite_des}")
        if item.forca_minima is not None:
            tags.append(f"requires:str-score>={item.forca_minima}")
        if item.furtividade_desvantagem:
            tags.append("dadv:furtividade")
    elif item.categoria in {"municao", "veneno", "explosivo", "comida"}:
        if "consumable" not in tags:
            tags.append("consumable")

    # Keep non-duplicated manual tags not generated above.
    generated_prefixes = (
        "item:", "categoria:", "subcategoria:", "preco:", "peso:", "raridade:", "slot:", "loja:", "tipo:",
        "dmg:", "add-property:", "range:", "reload:", "ca=", "ca:+", "dex-ca-max:", "dadv:",
        "requires:", "charges:", "action=", "attack:", "stabilize", "consumable",
        "aoe{", "apply:",
    )
    for t in item.tags_json or []:
        if isinstance(t, str) and t not in tags and not t.startswith(generated_prefixes):
            tags.append(t)
    deduped = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped


def load_spell_map():
    from home.models import TbMagia

    by_name = {norm_slug(m.nome): m.slug for m in TbMagia.objects.all()}
    out = {}
    for p in (Path("ref/Livros/magias_en_pt.csv"), Path("ref/Livros/magias_alinhado.csv")):
        if not p.exists():
            continue
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                en = row.get("magia_en") or row.get("en")
                pt = row.get("nome_pt") or row.get("final") or row.get("adaptado")
                slug = by_name.get(norm_slug(pt or ""))
                if en and slug:
                    out[en.lower()] = slug
    return out


def magic_rows():
    if not MAGIC_CSV.exists():
        return {}
    with MAGIC_CSV.open(encoding="utf-8-sig", newline="") as fh:
        return {row["db_slug"]: row for row in csv.DictReader(fh) if row.get("db_slug")}


def magic_tags(item, row, spell_map):
    tags = []
    if item.requer_sintonizacao:
        tags.append("sintonizacao")
        if item.detalhes_sintonizacao:
            tags.append(f"requires:{norm_slug(item.detalhes_sintonizacao)}")
    desc_en = (row or {}).get("description_en", "") or ""
    desc_pt = item.descricao_markdown or ""
    if (
        item.slot in {"pocao", "pergaminho", "municao"}
        or re.search(r"\b(consumed|expend|disappears|crumbles|vanishes|loses its magic|lose its magic)\b", desc_en, re.I)
        or re.search(r"\b(consumid[ao]s?|gasta[rs]?|desaparece|some|se desfaz|vira p[oó]|perde sua magia|perde a magia)\b", desc_pt, re.I)
    ):
        tags.append("consumable")

    text = desc_en
    low = text.lower()
    for n in sorted({int(x) for x in re.findall(r"\+(\d+) bonus to (?:AC|Armor Class)", text, re.I)}):
        tags.append(f"ca:+{n}")
    for n in sorted({int(x) for x in re.findall(r"\+(\d+) bonus to attack (?:rolls? )?and damage", text, re.I)}):
        tags.extend([f"weapon.atk:+{n}", f"weapon.dmg:+{n}"])
    for n in sorted({int(x) for x in re.findall(r"\+(\d+) bonus to attack rolls and damage rolls made with your Unarmed Strikes", text, re.I)}):
        tags.extend([f"unarmed.atk:+{n}", f"unarmed.dmg:+{n}"])
    for n in sorted({int(x) for x in re.findall(r"\+(\d+) bonus to spell attack rolls", text, re.I)}):
        tags.append(f"spell.atk:+{n}")
    for n in sorted({int(x) for x in re.findall(r"\+(\d+) bonus .*?(?:saving throw DCs|spell save DC)", text, re.I)}):
        tags.append(f"spell-save-cd:+{n}")
    m = re.search(r"\b(?:has|have|starts with)\s+(\d+)\s+charges?", text, re.I)
    if not m:
        m = re.search(r"\b(\d+)\s+charges?", text, re.I)
    if m:
        reset = "dawn" if "dawn" in low else "daily" if "daily" in low else "none"
        tags.append(f"charges:{m.group(1)}(reset:{reset})")
    for en, slug in spell_map.items():
        if re.search(r"\bcast\s+(?:the\s+)?%s\b" % re.escape(en), low):
            if "at will" in low:
                tags.append(f"cast{{spell:{slug}, modifiers{{no-slot}}, at-will}}")
            elif "charges" in low:
                tags.append(f"cast{{spell:{slug}, modifiers{{no-slot}}, resource-cost:charges:1, uses{{1, reset:day}}}}")
            else:
                tags.append(f"cast{{spell:{slug}, modifiers{{no-slot}}, uses{{1, reset:day}}}}")

    generated_prefixes = (
        "item:", "raridade:", "slot:", "loja:", "tipo:",
        "requires:", "consumable", "ca:", "weapon.", "unarmed.", "spell.",
        "spell-save-cd:", "charges:", "cast{",
    )
    for t in item.tags_json or []:
        if isinstance(t, str) and t not in tags and not t.startswith(generated_prefixes):
            tags.append(t)
    deduped = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped


class Command(BaseCommand):
    help = "Gera tags_json para TbItemMundano e TbItemMagico."

    def add_arguments(self, parser):
        parser.add_argument("--tipo", choices=["mundano", "magico", "todos"], default="todos")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        from home.models import TbItemMagico, TbItemMundano

        updates = []
        desc_updates = []
        if opts["tipo"] in {"mundano", "todos"}:
            for obj in TbItemMundano.objects.all():
                tags = mundane_tags(obj)
                if obj.tags_json != tags:
                    updates.append((obj, tags))
                clean_desc = clean_official_block(obj.descricao_markdown)
                if clean_desc != (obj.descricao_markdown or ""):
                    desc_updates.append((obj, clean_desc))
        if opts["tipo"] in {"magico", "todos"}:
            rows = magic_rows()
            spells = load_spell_map()
            for obj in TbItemMagico.objects.all():
                tags = magic_tags(obj, rows.get(obj.slug), spells)
                if obj.tags_json != tags:
                    updates.append((obj, tags))

        if opts["apply"]:
            with transaction.atomic():
                for obj, tags in updates:
                    obj.tags_json = tags
                    obj.save(update_fields=["tags_json"])
                for obj, desc in desc_updates:
                    obj.descricao_markdown = desc
                    obj.save(update_fields=["descricao_markdown"])

        self.stdout.write(self.style.SUCCESS(
            "%s tag_updates=%d desc_updates=%d" % (
                "APPLY" if opts["apply"] else "PREVIEW",
                len(updates),
                len(desc_updates),
            )
        ))
