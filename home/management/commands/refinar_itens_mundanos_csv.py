# -*- coding: utf-8 -*-
"""Refina TbItemMundano usando ref/Livros/Items.csv.

O CSV tem dados mais completos em ingles. Este comando e conservador:
- casa itens por slug/nome e por aliases PT->EN para armas/ferramentas;
- preenche preco/peso quando faltam;
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

TYPE_MAPPINGS_MUNDANO = {
    "Simple Weapon": "Arma Simples",
    "Martial Weapon": "Arma Marcial",
    "Melee Weapon": "Arma Corpo a Corpo",
    "Ranged Weapon": "Arma à Distância",
    "Weapon": "Arma",
    "Adventuring Gear": "Equipamento de Aventura",
    "Light Armor": "Armadura Leve",
    "Medium Armor": "Armadura Média",
    "Heavy Armor": "Armadura Pesada",
    "Spellcasting Focus": "Foco de Conjuração",
    "Artisan's Tools": "Ferramentas de Artesão",
    "Gaming Set": "Conjunto de Jogos",
    "Gaming Sets": "Conjunto de Jogos",
    "Musical Instrument": "Instrumento Musical",
    "Musical Instruments": "Instrumentos Musicais",
    "Mounts and Vehicles": "Montarias e Veículos",
    "Tack, Harness, and Drawn Vehicles": "Equipamento de Montaria e Tração",
    "Ammunition": "Munição",
    "Tools": "Ferramentas",
    "Tool": "Ferramenta",
    "Shield": "Escudo",
    "Armor (Shield)": "Armadura (Escudo)",
}

def translate_type_mundano(tipo_en):
    if not tipo_en:
        return "—"
    parts = [p.strip() for p in tipo_en.split(",")]
    parts_pt = []
    for part in parts:
        parts_pt.append(TYPE_MAPPINGS_MUNDANO.get(part, part))
    return ", ".join(parts_pt)

PROPERTY_HELP = {
    "Ammunition": "usa munição; o alcance indicado mostra distância normal/longa.",
    "Finesse": "pode usar Força ou Destreza no ataque e no dano.",
    "Heavy": "arma pesada.",
    "Light": "permite o ataque extra de arma leve como ação bônus, seguindo as regras de duas armas.",
    "Loading": "só permite disparar uma munição por ação, ação bônus ou reação.",
    "Reach": "aumenta o alcance corpo a corpo em 1,5 m (5 ft.).",
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
    "Write text with impressive flourishes that guard against forgery": "Escrever texto com floreios impressionantes que protegem contra falsificação",
    "Modify footwear to give Vantagem on the wearer's next Destreza (Acrobatics) teste": "Modificar calçados para dar Vantagem no próximo teste de Destreza (Acrobacia) do usuário",
    "Modify p\u00e9wear to give Vantagem on the wearer's next Destreza (Acrobatics) teste": "Modificar calçados para dar Vantagem no próximo teste de Destreza (Acrobacia) do usuário",
    "Modify footwear to give Vantagem on the wearer's next Destreza (Acrobatics)": "Modificar calçados para dar Vantagem no próximo teste de Destreza (Acrobacia) do usuário",
    "Discern what a glass object held in the past 24 hours": "Discernir o que um objeto de vidro continha nas últimas 24 horas",
    "Add a design to a leather item": "Adicionar um desenho a um item de couro",
    "Paint a recognizable image of something you've seen": "Pintar uma imagem reconhecível de algo que você viu",
    "Discern what a ceramic object held in the past 24 hours": "Discernir o que um objeto de cerâmica continha nas últimas 24 horas",
    "Pry open a door or container": "Forçar a abertura de uma porta ou recipiente",
    "Mend a tear in clothing": "Remendar um rasgo em roupas",
    "sew a Tiny design": "costurar um desenho Mínimo",
    "sew a Minimo design": "costurar um desenho Mínimo",
    "Any Melee weapon (except Club, Greatclub, Quarterstaff, and Whip), Medium armor (except Hide), Heavy armor, Ball Bearings, Bucket, Caltrops, Chain, Crowbar, Firearm Bullets, Grappling Hook, Iron Pot, Iron Spikes, Sling Bullets": "Qualquer arma Corpo a Corpo (exceto Porrete, Clava Grande, Bordão e Chicote), armadura Média (exceto Couro Batido), armadura Pesada, Esferas de Aço, Balde, Abrolhos, Corrente, Pé de Cabra, Balas de Arma de Fogo, Gancho de Escalada, Panela de Ferro, Cravos de Ferro, Balas de Estilingue",
    "Padded Armor, Basket, Bedroll, Blanket, Fine Clothes, Net, Robe, Rope, Sack, String, Tent, Traveler's Clothes": "Armadura Acolchoada, Cesto, Saco de Dormir, Cobertor, Roupas Finas, Rede, Manto, Corda, Saco, Barbante, Tenda, Roupas de Viajante",
    "Antitoxin, Candle, Healer's Kit, Potion of Healing": "Antídoto, Vela, Kit de Curandeiro, Poção de Cura",
    "Ink, Spell Scroll": "Tinta, Pergaminho de Magia",
    "Climber's Kit": "Kit de Escalada",
    "Glass Bottle, Magnifying Glass, Spyglass, Vial": "Garrafa de Vidro, Lente de Aumento, Luneta, Frasco",
    "Sling, Whip, Hide Armor, Leather Armor, Studded Leather Armor, Backpack, Crossbow Bolt Case, Map or Scroll Case, Parchment, Pouch, Quiver, Waterskin": "Estilingue, Chicote, Couro Batido, Couro, Couro Batido Tachado, Mochila, Estojo de Virotes, Estojo de Mapas ou Pergaminhos, Pergaminho, Algibeira, Aljava, Odre",
    "Druidic Focus, Holy Symbol": "Foco Druídico, Símbolo Sagrado",
    "Jug, Lamp": "Jarra, Lâmpada",
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
    
    def repl_range(match):
        prefix = match.group(1) or ""
        val1 = int(match.group(2))
        val2 = int(match.group(3))
        m1 = int(round(val1 * 0.3))
        if val1 == 5: m1 = 1.5
        elif val1 == 15: m1 = 4.5
        m2 = int(round(val2 * 0.3))
        if val2 == 5: m2 = 1.5
        elif val2 == 15: m2 = 4.5
        
        prefix_pt = "alcance " if "range" in prefix.lower() else ""
        m1_str = str(m1).replace(".", ",")
        m2_str = str(m2).replace(".", ",")
        return f"({prefix_pt}{m1_str}/{m2_str} m ({val1}/{val2} ft.))"
        
    out = re.sub(r"\((range\s+)?(\d+)/(\d+)\)", repl_range, out, flags=re.I)
    
    def repl_single(match):
        prefix = match.group(1) or ""
        val = int(match.group(2))
        m = int(round(val * 0.3))
        if val == 5: m = 1.5
        elif val == 15: m = 4.5
        prefix_pt = "alcance " if "range" in prefix.lower() else ""
        m_str = str(m).replace(".", ",")
        return f"({prefix_pt}{m_str} m ({val} ft.))"
        
    out = re.sub(r"\((range\s+)?(\d+)\)", repl_single, out, flags=re.I)
    
    for en, pt in PROPERTY_NAMES.items():
        out = re.sub(rf"\b{re.escape(en)}\b", pt, out)
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
        
    def repl_strength_requirement(match):
        score = match.group(1)
        feet = match.group(2)
        m = int(round(int(feet) * 0.3))
        if int(feet) == 5: m = 1.5
        elif int(feet) == 15: m = 4.5
        m_str = str(m).replace(".", ",")
        return f"Se quem veste tem um valor de Força menor que {score}, seu deslocamento é reduzido em {m_str} m ({feet} ft.)."
        
    out = re.sub(
        r"If the wearer has a For\u00e7a score lower than (\d+), their speed is reduced by (\d+)\s+p\u00e9s\.?",
        repl_strength_requirement,
        out,
        flags=re.I
    )
    
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
    lines.append(f"- **Tipo:** {translate_type_mundano(row.get('Type'))}")
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
                if changes:
                    updates.append((obj, changes))
                unmatched.append(obj.slug)
                stats["unmatched"] += 1
                continue

            stats["matched"] += 1
            changes = {}
            if row.get("Value") and obj.categoria != "arma" or (row.get("Value") and obj.slug in ALIASES):
                changes["preco"] = norm_money(row["Value"])
            if row.get("Weight"):
                w = parse_weight(row["Weight"])
                if w is not None and obj.peso != w:
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
