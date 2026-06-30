# -*- coding: utf-8 -*-
"""Refina TbItemMundano usando ref/Livros/Items.csv.

O CSV tem dados mais completos em ingles. Este comando e conservador:
- casa itens por slug/nome e por aliases PT->EN para armas/ferramentas;
- preenche fonte/preco/peso quando faltam;
- gera um bloco "Dados oficiais" em portugues a partir dos campos estruturados;
- nao sobrescreve dano/propriedades/maestria/tags_json quando o banco ja tem
  versoes mais ricas (ex.: maestrias homebrew adicionais).
"""
import csv
import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify


CSV_DEFAULT = Path("ref/Livros/Items.csv")
OFFICIAL_BLOCK_RE = re.compile(r"\n*\s*### Dados oficiais\n.*\Z", re.S)
LOCAL_BLOCK_RE = re.compile(r"\n*\s*### Dados do item\n.*\Z", re.S)


ALIASES = {
    # Weapons.
    "arma-adaga": "Dagger",
    "arma-alabarda": "Halberd",
    "arma-arco-curto": "Shortbow",
    "arma-arco-longo": "Longbow",
    "arma-azagaia": "Javelin",
    "arma-besta-de-mao": "Hand Crossbow",
    "arma-besta-leve": "Light Crossbow",
    "arma-besta-pesada": "Heavy Crossbow",
    "arma-bordao": "Quarterstaff",
    "arma-chicote": "Whip",
    "arma-cimitarra": "Scimitar",
    "arma-clava": "Club",
    "arma-clava-grande": "Greatclub",
    "arma-dardo": "Dart",
    "arma-espada-curta": "Shortsword",
    "arma-espada-grande": "Greatsword",
    "arma-espada-longa": "Longsword",
    "arma-estilingue": "Sling",
    "arma-estrela-da-manha": "Morningstar",
    "arma-foice": "Sickle",
    "arma-glaive": "Glaive",
    "arma-lanca": "Spear",
    "arma-lanca-longa": "Lance",
    "arma-machadinha": "Handaxe",
    "arma-machado-batalha": "Battleaxe",
    "arma-machado-grande": "Greataxe",
    "arma-malho": "Maul",
    "arma-mangual": "Flail",
    "arma-martelo-batalha": "Warhammer",
    "arma-martelo-leve": "Light Hammer",
    "arma-maca": "Mace",
    "arma-mosquete": "Musket",
    "arma-picareta-guerra": "War Pick",
    "arma-pique": "Pike",
    "arma-pistola-pederneira": "Pistol",
    "arma-rapieira": "Rapier",
    "arma-tocha-acesa": "Torch",
    "arma-tridente": "Trident",
    # Tools and instruments.
    "ferr-alaude": "Lute",
    "ferr-baralho": "Playing Cards",
    "ferr-charamela": "Shawm",
    "ferr-conjunto-de-dados": "Dice Set",
    "ferr-ferramentas-de-carpinteiro": "Carpenter's Tools",
    "ferr-ferramentas-de-cartografo": "Cartographer's Tools",
    "ferr-ferramentas-de-curtidor": "Leatherworker's Tools",
    "ferr-ferramentas-de-entalhador": "Woodcarver's Tools",
    "ferr-ferramentas-de-ferreiro": "Smith's Tools",
    "ferr-ferramentas-de-funileiro": "Tinker's Tools",
    "ferr-ferramentas-de-joalheiro": "Jeweler's Tools",
    "ferr-ferramentas-de-ladrao": "Thieves' Tools",
    "ferr-ferramentas-de-navegacao": "Navigator's Tools",
    "ferr-ferramentas-de-oleiro": "Potter's Tools",
    "ferr-ferramentas-de-pedreiro": "Mason's Tools",
    "ferr-ferramentas-de-sapateiro": "Cobbler's Tools",
    "ferr-ferramentas-de-tecelao": "Weaver's Tools",
    "ferr-ferramentas-de-vidreiro": "Glassblower's Tools",
    "ferr-flauta": "Flute",
    "ferr-flauta-de-pa": "Pan Flute",
    "ferr-gaita-de-foles": "Bagpipes",
    "ferr-kit-de-disfarce": "Disguise Kit",
    "ferr-kit-de-envenenador": "Poisoner's Kit",
    "ferr-kit-de-falsificacao": "Forgery Kit",
    "ferr-kit-de-herborismo": "Herbalism Kit",
    "ferr-lira": "Lyre",
    "ferr-salterio": "Dulcimer",
    "ferr-suprimentos-de-alquimista": "Alchemist's Supplies",
    "ferr-suprimentos-de-caligrafo": "Calligrapher's Supplies",
    "ferr-suprimentos-de-cervejeiro": "Brewer's Supplies",
    "ferr-suprimentos-de-pintor": "Painter's Supplies",
    "ferr-tambor": "Drum",
    "ferr-trompa": "Horn",
    "ferr-utensilios-de-cozinheiro": "Cook's Utensils",
    "ferr-viola": "Viol",
}


DAMAGE_TYPES = {
    "Bludgeoning": "Conc.",
    "Piercing": "Perf.",
    "Slashing": "Cort.",
}

PROPERTY_NAMES = {
    "Ammunition": "Munição",
    "Finesse": "Acuidade",
    "Heavy": "Pesada",
    "Light": "Leve",
    "Loading": "Carregar",
    "Range": "Alcance",
    "Reach": "Alcance",
    "Thrown": "Arremesso",
    "Two-Handed": "Duas Mãos",
    "Two Handed": "Duas Mãos",
    "Versatile": "Versátil",
}

MASTERY_NAMES = {
    "Cleave": "Fender",
    "Graze": "Raspar",
    "Nick": "Corte",
    "Push": "Empurrar",
    "Sap": "Minar",
    "Slow": "Lentidão",
    "Topple": "Derrubar",
    "Vex": "Vexar",
}

PROPERTY_HELP = {
    "Ammunition": "usa munição; o alcance indicado mostra distância normal/longa.",
    "Finesse": "pode usar Força ou Destreza no ataque e no dano.",
    "Heavy": "arma pesada.",
    "Light": "permite o ataque extra de arma leve como ação bônus, seguindo as regras de duas armas.",
    "Loading": "só permite disparar uma munição por ação, ação bônus ou reação.",
    "Reach": "aumenta o alcance corpo a corpo em 5 pés.",
    "Thrown": "pode ser arremessada; se for arma corpo a corpo, usa o mesmo atributo do ataque corpo a corpo.",
    "Two-Handed": "exige duas mãos para atacar.",
    "Versatile": "pode ser usada com uma ou duas mãos; o dado entre parênteses vale ao usar duas mãos.",
}

MASTERY_HELP = {
    "Cleave": "após acertar, pode atingir outra criatura próxima se a regra de maestria permitir.",
    "Graze": "mesmo errando, causa dano mínimo conforme a maestria.",
    "Nick": "facilita o ataque extra de arma leve sem consumir a ação bônus, conforme a maestria.",
    "Push": "pode empurrar o alvo ao acertar.",
    "Sap": "o alvo sofre Desvantagem no próximo ataque antes do início do seu próximo turno.",
    "Slow": "reduz temporariamente o deslocamento do alvo.",
    "Topple": "pode derrubar o alvo.",
    "Vex": "facilita obter Vantagem no próximo ataque contra o alvo.",
}

PHRASE_TRANSLATIONS = {
    "Identify a substance": "Identificar uma substância",
    "start a fire": "iniciar fogo",
    "Detect Poison": "Detectar Veneno",
    "Identify Alcohol": "Identificar bebida alcoólica",
    "Fortify Drink": "Fortificar bebida",
    "Map a course": "Traçar uma rota",
    "Craft a Map": "Criar um mapa",
    "Pick a lock": "Abrir uma fechadura",
    "disarm a trap": "desarmar uma armadilha",
    "Cover Injuries": "Disfarçar ferimentos",
    "Apply Makeup": "Aplicar maquiagem",
    "Copy handwriting": "Copiar caligrafia",
    "Mimic a seal": "Imitar um selo",
    "Identify a plant": "Identificar uma planta",
    "apply herbs": "aplicar ervas",
    "Appraise a gem": "Avaliar uma gema",
    "Shape stone": "Moldar pedra",
    "Repair shoes": "Reparar calçados",
    "Start a fire": "Iniciar fogo",
    "Pick a lock": "Abrir fechadura",
    "Play music": "Tocar música",
    "Determine whether someone is cheating": "Descobrir se alguém está trapaceando",
    "Discern whether someone is cheating": "Descobrir se alguém está trapaceando",
    "win the game": "vencer o jogo",
    "Play a known tune": "Tocar uma melodia conhecida",
    "improvise a song": "improvisar uma música",
}

TYPE_CATS = [
    ("Poison", "veneno"),
    ("Explosive", "explosivo"),
    ("Ammunition", "municao"),
    ("Armor", "armadura"),
    ("Weapon", "arma"),
    ("Instrument", "ferramenta"),
    ("Artisan's Tools", "ferramenta"),
    ("Gaming Set", "ferramenta"),
    ("Tool", "ferramenta"),
    ("Spellcasting Focus", "foco"),
    ("Mount", "montaria"),
    ("Vehicle", "veiculo"),
    ("Trade Good", "mercadoria"),
    ("Food and Drink", "comida"),
    ("Pack", "pacote"),
]


def ascii_slug(value):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def norm_money(value):
    if not value:
        return None
    text = str(value).strip()
    text = text.replace(" gp", " GP").replace(" sp", " SP").replace(" cp", " CP").replace(" ep", " EP")
    text = re.sub(r"\bGP\b", "PO", text)
    text = re.sub(r"\bSP\b", "PP", text)
    text = re.sub(r"\bCP\b", "PC", text)
    text = re.sub(r"\bEP\b", "PE", text)
    return text


def parse_weight(value):
    if not value:
        return None
    text = str(value).strip()
    text = (text.replace("¼", ".25").replace("Ľ", ".25")
                .replace("½", ".5").replace("˝", ".5")
                .replace("¾", ".75").replace("ľ", ".75"))
    m = re.search(r"([\d.]+)", text.replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def translate_damage(value):
    if not value:
        return None
    text = str(value)
    if text.startswith("AC "):
        return text.replace("AC ", "CA ").replace("Dex", "Des")
    for en, pt in DAMAGE_TYPES.items():
        text = re.sub(rf"\b{re.escape(en)}\b", pt, text)
    return text.replace("ft.", "pés").replace("Speed:", "Deslocamento:").strip()


def split_csv_list(text):
    if not text:
        return []
    parts = []
    buff = []
    depth = 0
    for ch in str(text):
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        if ch == "," and depth == 0:
            part = "".join(buff).strip()
            if part:
                parts.append(part)
            buff = []
        else:
            buff.append(ch)
    part = "".join(buff).strip()
    if part:
        parts.append(part)
    return parts


def translate_property(prop):
    out = prop.replace("\u00a0", " ")
    for en, pt in PROPERTY_NAMES.items():
        out = re.sub(rf"\b{re.escape(en)}\b", pt, out)
    out = out.replace("ft.", "pés")
    return out


def translate_properties(value):
    parts = [translate_property(p) for p in split_csv_list(value)]
    return ", ".join(parts) if parts else None


def translate_mastery(value):
    if not value:
        return None
    text = str(value).replace("Mastery:", "").strip()
    translated = MASTERY_NAMES.get(text, text)
    return f"{translated} ({text})" if translated != text else text


def official_category(type_text):
    for needle, cat in TYPE_CATS:
        if needle in (type_text or ""):
            return cat
    return "equipamento_aventura"


def official_subcategory(type_text):
    text = type_text or ""
    if "Simple Weapon" in text and "Ranged Weapon" in text:
        return "arma_simples_dist"
    if "Simple Weapon" in text:
        return "arma_simples"
    if "Martial Weapon" in text and "Ranged Weapon" in text:
        return "arma_marcial_dist"
    if "Martial Weapon" in text:
        return "arma_marcial"
    if "Firearm" in text:
        return "arma_fogo"
    if "Light Armor" in text:
        return "leve"
    if "Medium Armor" in text:
        return "media"
    if "Heavy Armor" in text:
        return "pesada"
    if "Shield" in text:
        return "escudo"
    if "Artisan's Tools" in text:
        return "ferramenta_artesao"
    if "Gaming Set" in text:
        return "conjunto_jogo"
    if "Instrument" in text:
        return "instrumento"
    if "Tool" in text:
        return "ferramenta_outras"
    if "Vehicle (Air)" in text:
        return "aereo"
    if "Vehicle (Water)" in text:
        return "aquatico"
    if "Vehicle (Land)" in text:
        return "terrestre"
    if "Poison" in text:
        m = re.search(r"Poison \(([^)]+)\)", text)
        return f"veneno_{ascii_slug(m.group(1))}" if m else "veneno"
    if "Tack and Harness" in text:
        return "arreios"
    if "Generic Variant" in text:
        return "variante"
    return None


def strip_generated_blocks(text):
    text = OFFICIAL_BLOCK_RE.sub("", text or "").strip()
    return LOCAL_BLOCK_RE.sub("", text).strip()


def interesting_text(text):
    if not text:
        return ""
    # Keep this concise; the CSV text is often a long rules glossary repeated
    # for every weapon property.
    paragraphs = [p.strip() for p in str(text).split("\n\n") if p.strip()]
    kept = []
    for p in paragraphs:
        if p.startswith(("Artisan's Tool.", "Tool.", "Tool (", "Gaming Set.", "If you have proficiency with a tool")):
            continue
        if p.startswith(("Ability:", "Utilize:", "Craft:", "Disassemble:", "Range.", "Light.", "Finesse.", "Heavy.", "Two-Handed.", "Versatile.", "Thrown.", "Loading.", "Mastery:")):
            kept.append(p)
        elif len(p) <= 420:
            kept.append(p)
        if len(kept) >= 4:
            break
    return "\n\n".join(kept)


def translate_light_text(text):
    if not text:
        return ""
    out = text.replace("Ability:", "Atributo:")
    out = out.replace("Utilize:", "Usar:")
    out = out.replace("Craft:", "Criar:")
    out = out.replace("Disassemble:", "Desmontar:")
    out = out.replace("Intelligence", "Inteligência")
    out = out.replace("Dexterity", "Destreza")
    out = out.replace("Strength", "Força")
    out = out.replace("Wisdom", "Sabedoria")
    out = out.replace("Charisma", "Carisma")
    out = out.replace("Constitution", "Constituição")
    out = out.replace("DC ", "CD ")
    out = out.replace("feet", "pés").replace("foot", "pé").replace("ft.", "pés")
    out = out.replace("Disadvantage", "Desvantagem").replace("Advantage", "Vantagem")
    out = out.replace("Dexterity (Stealth)", "Destreza (Furtividade)")
    out = out.replace("Stealth", "Furtividade")
    out = out.replace(" saving throw", " teste de resistência")
    out = out.replace(" action", " ação")
    out = out.replace(" checks", " testes")
    out = out.replace(" check", " teste")
    out = out.replace("Furtividade) testes", "Furtividade)")
    out = out.replace(" on Destreza", " em Destreza")
    out = out.replace(", or ", ", ou ")
    for en, pt in PHRASE_TRANSLATIONS.items():
        out = out.replace(en, pt)
    craft_names = {
        "Acid": "Ácido",
        "Alchemist's Fire": "Fogo Alquímico",
        "Component Pouch": "Bolsa de Componentes",
        "Oil": "Óleo",
        "Paper": "Papel",
        "Perfume": "Perfume",
    }
    for en, pt in craft_names.items():
        out = out.replace(en, pt)
    return out


def property_quick_rules(properties):
    out = []
    for part in split_csv_list(properties):
        name = re.sub(r"\s*\(.*\)", "", part).replace("\u00a0", " ").strip()
        help_text = PROPERTY_HELP.get(name)
        if help_text:
            out.append(f"- **{translate_property(part)}:** {help_text}")
    return out


def mastery_quick_rule(mastery):
    if not mastery:
        return None
    name = str(mastery).replace("Mastery:", "").strip()
    help_text = MASTERY_HELP.get(name)
    if not help_text:
        return None
    return f"- **{translate_mastery(mastery)}:** {help_text}"


def build_official_block(obj, row):
    lines = ["### Dados oficiais"]
    if row.get("Name") and ascii_slug(row["Name"]) != ascii_slug(obj.nome):
        lines.append(f"*{row['Name']}*")
    lines.append(f"- **Fonte:** {row.get('Source') or '—'}" + (f" p. {row.get('Page')}" if row.get("Page") else ""))
    lines.append(f"- **Tipo:** {row.get('Type') or '—'}")
    if row.get("Value"):
        lines.append(f"- **Preço:** {norm_money(row.get('Value'))}")
    if row.get("Weight"):
        lines.append(f"- **Peso:** {row.get('Weight')}")
    if row.get("Damage"):
        lines.append(f"- **Dano/CA:** {translate_damage(row.get('Damage'))}")
    if row.get("Properties"):
        lines.append(f"- **Propriedades:** {translate_properties(row.get('Properties'))}")
    if row.get("Mastery"):
        lines.append(f"- **Maestria:** {translate_mastery(row.get('Mastery'))}")
    type_text = row.get("Type") or ""
    if "Weapon" in type_text:
        quick = property_quick_rules(row.get("Properties"))
        mastery = mastery_quick_rule(row.get("Mastery"))
        if mastery:
            quick.append(mastery)
        if quick:
            lines.extend(["", "#### Regras rápidas", *quick])
    elif "Armor" in type_text:
        details = translate_light_text(interesting_text(row.get("Text")))
        if details:
            lines.extend(["", "#### Uso", details.replace("The wearer has", "Quem veste tem")])
    elif any(k in type_text for k in ("Tool", "Instrument", "Gaming Set", "Artisan's Tools")):
        details = translate_light_text(interesting_text(row.get("Text")))
        if details:
            lines.extend(["", "#### Uso", details])
    elif not (obj.descricao_markdown or "").strip():
        details = translate_light_text(interesting_text(row.get("Text")))
        if details:
            lines.extend(["", "#### Uso", details])
    return "\n".join(lines).strip()


def build_local_item_block(obj):
    lines = ["### Dados do item"]
    lines.append("- **Fonte:** Bonfire")
    lines.append(f"- **Categoria:** {obj.get_categoria_display()}")
    if obj.subcategoria:
        lines.append(f"- **Subcategoria:** {obj.subcategoria}")
    if obj.preco:
        lines.append(f"- **Preço:** {obj.preco}")
    if obj.peso is not None:
        lines.append(f"- **Peso:** {obj.peso:g} lb.")
    if obj.dano:
        lines.append(f"- **Dano:** {obj.dano}")
    if obj.propriedades:
        lines.append(f"- **Propriedades:** {obj.propriedades}")
    if obj.maestria:
        lines.append(f"- **Maestrias:** {obj.maestria}")
    return "\n".join(lines).strip()


def candidate_keys(obj):
    keys = [obj.slug, ascii_slug(obj.nome)]
    if obj.slug.startswith("arma-"):
        keys.append(obj.slug[5:])
    if obj.slug.startswith("ferr-"):
        keys.append(obj.slug[5:])
    alias = ALIASES.get(obj.slug)
    if alias:
        keys.insert(0, ascii_slug(alias))
    return [k for k in keys if k]


class Command(BaseCommand):
    help = "Refina TbItemMundano a partir de ref/Livros/Items.csv."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(CSV_DEFAULT))
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--overwrite-empty-combat", action="store_true", default=True)

    def handle(self, *args, **opts):
        from home.models import TbItemMundano

        path = Path(opts["csv"])
        if not path.exists():
            raise CommandError(f"CSV nao encontrado: {path}")

        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        by_slug = {ascii_slug(r.get("Name")): r for r in rows}

        stats = {"matched": 0, "updated": 0, "unmatched": 0, "created": 0}
        unmatched = []
        updates = []

        for obj in TbItemMundano.objects.order_by("categoria", "nome"):
            row = None
            for key in candidate_keys(obj):
                row = by_slug.get(key)
                if row:
                    break
            if not row:
                changes = {}
                if obj.categoria == "arma":
                    base = strip_generated_blocks(obj.descricao_markdown or "")
                    new_desc = (base + "\n\n" + build_local_item_block(obj)).strip() if base else build_local_item_block(obj)
                    if new_desc != (obj.descricao_markdown or "").strip():
                        changes["descricao_markdown"] = new_desc
                    if not obj.fonte:
                        changes["fonte"] = "Bonfire"
                if changes:
                    updates.append((obj, changes))
                unmatched.append(obj.slug)
                stats["unmatched"] += 1
                continue

            stats["matched"] += 1
            changes = {}
            if not obj.fonte and row.get("Source"):
                changes["fonte"] = row["Source"]
            if not obj.preco and row.get("Value"):
                changes["preco"] = norm_money(row["Value"])
            if obj.peso is None and row.get("Weight"):
                w = parse_weight(row["Weight"])
                if w is not None:
                    changes["peso"] = w
            if not obj.subcategoria:
                sub = official_subcategory(row.get("Type"))
                if sub:
                    changes["subcategoria"] = sub

            cat = official_category(row.get("Type"))
            if obj.categoria == "equipamento_aventura" and cat != "equipamento_aventura":
                changes["categoria"] = cat

            if opts["overwrite_empty_combat"]:
                if not obj.dano and row.get("Damage") and "Weapon" in row.get("Type", ""):
                    changes["dano"] = translate_damage(row["Damage"])
                if not obj.propriedades and row.get("Properties"):
                    changes["propriedades"] = translate_properties(row["Properties"])
                if not obj.maestria and row.get("Mastery"):
                    changes["maestria"] = translate_mastery(row["Mastery"])

            base = strip_generated_blocks(obj.descricao_markdown or "")
            should_add_block = (
                obj.categoria in {"arma", "armadura", "ferramenta"}
                or not base
                or not obj.fonte
            )
            if should_add_block:
                block = build_official_block(obj, row)
                new_desc = (base + "\n\n" + block).strip() if base else block
                if new_desc != (obj.descricao_markdown or "").strip():
                    changes["descricao_markdown"] = new_desc

            if changes:
                updates.append((obj, changes))

        if opts["apply"]:
            with transaction.atomic():
                for obj, changes in updates:
                    for field, value in changes.items():
                        setattr(obj, field, value)
                    obj.save(update_fields=list(changes.keys()))
                    stats["updated"] += 1
        else:
            stats["updated"] = len(updates)

        self.stdout.write(
            self.style.SUCCESS(
                "%s matched=%d updated=%d unmatched=%d"
                % ("APPLY" if opts["apply"] else "PREVIEW", stats["matched"], stats["updated"], stats["unmatched"])
            )
        )
        if unmatched:
            self.stdout.write("Unmatched sample: " + ", ".join(unmatched[:40]))
