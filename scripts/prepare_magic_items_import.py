import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook, load_workbook


ROOT = Path(__file__).resolve().parents[1]
BASE_FILE = ROOT / "itemsbonfasporslot.xlsx"
SHOP_FILE = ROOT / "Loja de Itens - Bonfire Tales (1).xlsx"
OUTPUT_FILE = ROOT / "items_magicos_import_final.xlsx"
REPORT_FILE = ROOT / "relatorio_diferencas_itens.txt"


HEADERS = [
    "Nome",
    "Slug",
    "Tipo",
    "Raridade",
    "RaridadeNome",
    "Slot",
    "SlotNome",
    "RequerSintonizacao",
    "DetalhesSintonizacao",
    "Loja",
    "Preco",
    "TagsJSON",
    "DescricaoMarkdown",
    "Fonte",
    "IdOriginal",
    "NomeOriginalIngles",
    "StatusImportacao",
    "Observacoes",
]

RARITY_MAP = {
    "comum": "comum",
    "comum menor": "comum_menor",
    "comum maior": "comum_maior",
    "incomum": "incomum",
    "incomum menor": "incomum_menor",
    "incomum maior": "incomum_maior",
    "raro": "raro",
    "raro menor": "raro_menor",
    "raro maior": "raro_maior",
    "muito raro": "muito_raro",
    "muito raro menor": "muito_raro_menor",
    "muito raro maior": "muito_raro_maior",
    "lendario": "lendario",
    "lendario menor": "lendario_menor",
    "lendario maior": "lendario_maior",
    "artefato": "artefato",
}

RARITY_LABELS = {
    "comum": "Comum",
    "comum_menor": "Comum Menor",
    "comum_maior": "Comum Maior",
    "incomum": "Incomum",
    "incomum_menor": "Incomum Menor",
    "incomum_maior": "Incomum Maior",
    "raro": "Raro",
    "raro_menor": "Raro Menor",
    "raro_maior": "Raro Maior",
    "muito_raro": "Muito Raro",
    "muito_raro_menor": "Muito Raro Menor",
    "muito_raro_maior": "Muito Raro Maior",
    "lendario": "Lendário",
    "lendario_menor": "Lendário Menor",
    "lendario_maior": "Lendário Maior",
    "artefato": "Artefato",
}

SLOT_MAP = {
    "head": "cabeca",
    "face": "rosto",
    "neck": "pescoco",
    "back": "costas",
    "torso": "torso",
    "arms": "bracos",
    "gloves": "maos",
    "ring": "aneis",
    "waist": "cintura",
    "feet": "pes",
    "tattoo": "pele",
    "weapon": "arma",
    "armor": "armadura",
    "shield": "escudo",
    "ammunition": "municao",
    "potion": "pocao",
    "scroll": "pergaminho",
    "wand": "varinha",
    "rod": "cajado_bastao",
    "vehicle": "veiculo",
    "hovering": "flutuando",
    "accessory": "acessorio",
    "building": "edificacao",
    "held": "empunhado",
}

SLOT_LABELS = {
    "cabeca": "Cabeça",
    "face_olhos": "Face/Olhos",
    "rosto": "Rosto",
    "pescoco": "Pescoço",
    "costas": "Costas",
    "torso": "Torso",
    "bracos": "Braços",
    "maos": "Mãos",
    "dedos": "Dedos",
    "aneis": "Anéis",
    "cintura": "Cintura",
    "pes": "Pés",
    "pele": "Pele",
    "arma": "Arma",
    "armadura": "Armadura",
    "escudo": "Escudo",
    "municao": "Munição",
    "pocao": "Poção",
    "pergaminho": "Pergaminho",
    "varinha": "Varinha",
    "cajado_bastao": "Cajado/Bastão",
    "veiculo": "Veículo",
    "flutuando": "Flutuando",
    "acessorio": "Acessório",
    "edificacao": "Edificação",
    "empunhado": "Empunhado",
    "objeto": "Objeto",
    "item_menor": "Item Menor",
}

TYPE_REPLACEMENTS = [
    ("spellcasting focus", "foco de conjuração"),
    ("scale mail", "cota de escamas"),
    ("studded leather armor", "armadura de couro batido"),
    ("leather armor", "armadura de couro"),
    ("chain shirt", "camisão de cota de malha"),
    ("breastplate", "peitoral"),
    ("plate armor", "armadura de placas"),
    ("firearm", "arma de fogo"),
    ("renaissance", "renascentista"),
    ("wondrous item", "item maravilhoso"),
    ("generic variant", "variante genérica"),
    ("simple weapon", "arma simples"),
    ("martial weapon", "arma marcial"),
    ("melee weapon", "arma corpo a corpo"),
    ("ranged weapon", "arma a distância"),
    ("light armor", "armadura leve"),
    ("medium armor", "armadura média"),
    ("heavy armor", "armadura pesada"),
    ("weapon", "arma"),
    ("ammunition", "munição"),
    ("armor", "armadura"),
    ("shield", "escudo"),
    ("ring", "anel"),
    ("potion", "poção"),
    ("scroll", "pergaminho"),
    ("staff", "cajado"),
    ("wand", "varinha"),
    ("rod", "bastao"),
    ("tattoo", "tatuagem"),
    ("instrument", "instrumento"),
    ("vehicle", "veículo"),
    ("other", "outro"),
]

WEAPON_NAMES = {
    "Battleaxe": "machado de batalha",
    "Club": "clava",
    "Dagger": "adaga",
    "Dart": "dardo",
    "Flail": "mangual",
    "Greatclub": "clava grande",
    "Greataxe": "machado grande",
    "Greatsword": "espada grande",
    "Javelin": "azagaia",
    "Longbow": "arco longo",
    "Longsword": "espada longa",
    "Mace": "maça",
    "Morningstar": "morgenstern",
    "Musket": "mosquete",
    "Pistol": "pistola",
    "Quarterstaff": "bordão",
    "Rapier": "rapieira",
    "Scimitar": "cimitarra",
    "Shortbow": "arco curto",
    "Shortsword": "espada curta",
    "Sickle": "foice",
    "Sling": "funda",
    "Spear": "lança",
    "Trident": "tridente",
    "War Pick": "picareta de guerra",
    "Warhammer": "martelo de guerra",
    "Whip": "chicote",
}

ATTUNEMENT_REPLACEMENTS = [
    ("requires attunement by an ", "por "),
    ("requires attunement by a ", "por "),
    ("requires attunement by the ", "pelo "),
    ("requires attunement by ", "por "),
    ("requires attunement", ""),
    ("attunement optional", "opcional"),
    ("artificer", "artifice"),
    ("bard", "bardo"),
    ("cleric", "clérigo"),
    ("druid", "druida"),
    ("fighter", "guerreiro"),
    ("monk", "monge"),
    ("paladin", "paladino"),
    ("ranger", "caçador"),
    ("sorcerer", "feiticeiro"),
    ("warlock", "bruxo"),
    ("wizard", "mago"),
    ("spellcaster", "conjurador"),
    ("humanoid", "humanoide"),
    ("creature", "criatura"),
    ("member", "membro"),
    ("specific individual", "indivíduo específico"),
    ("good alignment", "alinhamento bom"),
    ("evil alignment", "alinhamento maligno"),
    ("non-evil", "não maligno"),
    ("non-good", "não bom"),
    ("small", "pequeno"),
    ("dwarf", "anão"),
    ("elf", "elfo"),
    (" or ", " ou "),
    (" and ", " e "),
]

SHOP_TYPE_MAP = {
    "consumivel": "consumível",
    "consumível": "consumível",
}


def normalize(value):
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("'", "")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slugify_pt(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or ""


def rows_by_header(path):
    worksheet = load_workbook(path, data_only=True, read_only=True).active
    headers = [cell for cell in next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True))]
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        if any(value is not None for value in row):
            yield dict(zip(headers, row))


def group_by_name(rows, column):
    grouped = defaultdict(list)
    for row in rows:
        key = normalize(row.get(column))
        if key:
            grouped[key].append(row)
    return grouped


def rarity_code(value):
    return RARITY_MAP.get(normalize(value), "")


def translate_type(value):
    text = str(value or "").strip()
    if not text:
        return ""
    for english, portuguese in sorted(WEAPON_NAMES.items(), key=lambda item: len(item[0]), reverse=True):
        text = re.sub(rf"\b{re.escape(english)}\b", portuguese, text, flags=re.IGNORECASE)
    text = text.lower()
    for english, portuguese in TYPE_REPLACEMENTS:
        text = re.sub(rf"\b{re.escape(english)}\b", portuguese, text, flags=re.IGNORECASE)
    text = text.replace("(", "").replace(")", "")
    return re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", text)).strip(" ,")


def translate_attunement(value):
    text = str(value or "").strip()
    if not text:
        return "Nao", ""
    lower = text.lower()
    translated = lower
    for english, portuguese in ATTUNEMENT_REPLACEMENTS:
        translated = translated.replace(english, portuguese)
    translated = re.sub(r"\s+", " ", translated).strip(" ,.;")
    return "Sim", translated.capitalize() if translated else ""


def slot_code(row):
    slot_ficha = normalize(row.get("SlotFicha")).replace(" ", "_")
    if slot_ficha:
        return "armadura" if slot_ficha == "corpo" else slot_ficha
    slot = str(row.get("SlotCodigo") or "").strip().lower()
    return SLOT_MAP.get(slot, "objeto")


def price_value(value):
    text = str(value or "").strip()
    if not text or "quest" in text.lower():
        return ""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def safe_int(value):
    if value in (None, ""):
        return ""
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def unique_slug(nome, used_slugs):
    slug_base = slugify_pt(nome)
    if not slug_base:
        return ""
    slug = slug_base
    counter = 2
    while slug in used_slugs:
        slug = f"{slug_base}-{counter}"
        counter += 1
    used_slugs.add(slug)
    return slug


def tags_for(item):
    tags = []
    for key in ("Raridade", "Slot", "Loja"):
        value = str(item.get(key) or "").strip()
        if value:
            tags.append(f"{key.lower()}:{value}")
    if item.get("RequerSintonizacao") == "Sim":
        tags.append("sintonizacao")
    tipo = str(item.get("Tipo") or "").strip()
    if tipo:
        tags.extend(f"tipo:{part.strip()}" for part in tipo.split(",") if part.strip())
    return json.dumps(tags, ensure_ascii=False)


def build_from_base(base, shop, status, observations, used_slugs):
    nome = str(base.get("NomeTraduzido") or "").strip()
    slot = slot_code(base)
    requer_sintonizacao, detalhes_sintonizacao = translate_attunement(base.get("Attunement"))
    raridade = rarity_code(shop.get("Rarity")) if shop else ""
    item = {
        "Nome": nome,
        "Slug": unique_slug(nome, used_slugs),
        "Tipo": translate_type(base.get("Tipo")),
        "Raridade": raridade,
        "RaridadeNome": RARITY_LABELS.get(raridade, str(shop.get("Rarity") or "").strip() if shop else ""),
        "Slot": slot,
        "SlotNome": SLOT_LABELS.get(slot, str(base.get("SlotNome") or "").strip()),
        "RequerSintonizacao": requer_sintonizacao,
        "DetalhesSintonizacao": detalhes_sintonizacao,
        "Loja": str(shop.get("Loja") or "").strip() if shop else "",
        "Preco": price_value(shop.get("Preço")) if shop else "",
        "DescricaoMarkdown": "",
        "Fonte": str(base.get("Source") or "").strip(),
        "IdOriginal": safe_int(base.get("Id_Item")),
        "NomeOriginalIngles": "",
        "StatusImportacao": status,
        "Observacoes": observations,
    }
    item["TagsJSON"] = tags_for(item)
    return item


def build_from_shop(shop, status, observations, used_slugs):
    # A loja so tem o nome em ingles para estes itens; fica registrado para revisao manual.
    nome = str(shop.get("Name") or "").strip()
    raridade = rarity_code(shop.get("Rarity"))
    tipo = SHOP_TYPE_MAP.get(normalize(shop.get("Tipo")), str(shop.get("Tipo") or "").strip().lower())
    item = {
        "Nome": nome,
        "Slug": unique_slug(nome, used_slugs),
        "Tipo": tipo,
        "Raridade": raridade,
        "RaridadeNome": RARITY_LABELS.get(raridade, str(shop.get("Rarity") or "").strip()),
        "Slot": "",
        "SlotNome": "",
        "RequerSintonizacao": "Nao",
        "DetalhesSintonizacao": "",
        "Loja": str(shop.get("Loja") or "").strip(),
        "Preco": price_value(shop.get("Preço")),
        "DescricaoMarkdown": "",
        "Fonte": "",
        "IdOriginal": "",
        "NomeOriginalIngles": str(shop.get("Name") or "").strip(),
        "StatusImportacao": status,
        "Observacoes": observations,
    }
    item["TagsJSON"] = tags_for(item)
    return item


def append_sheet_rows(worksheet, items):
    worksheet.append(HEADERS)
    for item in items:
        worksheet.append([item.get(header, "") for header in HEADERS])

    worksheet.freeze_panes = "A2"
    widths = {
        "A": 38,
        "B": 38,
        "C": 32,
        "D": 18,
        "E": 18,
        "F": 18,
        "G": 18,
        "H": 20,
        "I": 36,
        "J": 20,
        "K": 12,
        "L": 58,
        "M": 22,
        "N": 12,
        "O": 12,
        "P": 32,
        "Q": 20,
        "R": 58,
    }
    for column, width in widths.items():
        worksheet.column_dimensions[column].width = width


def write_workbook(items):
    ready_items = [item for item in items if item["StatusImportacao"] == "pronto"]
    review_items = [item for item in items if item["StatusImportacao"] != "pronto"]

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Itens Magicos"
    append_sheet_rows(worksheet, ready_items)

    review_sheet = workbook.create_sheet("Revisar Manualmente")
    append_sheet_rows(review_sheet, review_items)

    workbook.save(OUTPUT_FILE)


def write_report(base_rows, shop_rows, base_group, shop_group, matched_keys, only_base, only_shop, items):
    status_counts = Counter(item["StatusImportacao"] for item in items)
    duplicate_base = {key: rows for key, rows in base_group.items() if len(rows) > 1}
    duplicate_shop = {key: rows for key, rows in shop_group.items() if len(rows) > 1}

    lines = [
        "Relatorio de diferencas entre as planilhas de itens",
        "===================================================",
        "",
        f"Planilha de slots: {BASE_FILE.name}",
        f"Planilha de loja: {SHOP_FILE.name}",
        "",
        f"Linhas na planilha de slots: {len(base_rows)}",
        f"Linhas na planilha de loja: {len(shop_rows)}",
        f"Itens casados por nome ingles: {len(matched_keys)}",
        f"Itens apenas na planilha de slots: {len(only_base)}",
        f"Itens apenas na planilha de loja: {len(only_shop)}",
        f"Linhas geradas em {OUTPUT_FILE.name}: {len(items)}",
        "",
        "Status das linhas geradas:",
    ]
    lines.extend(f"- {status}: {count}" for status, count in sorted(status_counts.items()))

    lines.extend([
        "",
        "Itens presentes apenas na planilha de slots",
        "--------------------------------------------",
    ])
    for key in sorted(only_base):
        for row in base_group[key]:
            lines.append(f"- {row.get('Nome')} -> {row.get('NomeTraduzido')}")
    if not only_base:
        lines.append("- Nenhum")

    lines.extend([
        "",
        "Itens presentes apenas na planilha de loja",
        "------------------------------------------",
    ])
    for key in sorted(only_shop):
        for row in shop_group[key]:
            lines.append(f"- {row.get('Name')} | {row.get('Rarity') or 'sem raridade'} | {row.get('Loja') or 'sem loja'} | {row.get('Preço') or 'sem preco'}")
    if not only_shop:
        lines.append("- Nenhum")

    lines.extend([
        "",
        "Nomes duplicados na planilha de slots",
        "-------------------------------------",
    ])
    for rows in duplicate_base.values():
        lines.append(f"- {rows[0].get('Nome')} ({len(rows)} linhas)")
    if not duplicate_base:
        lines.append("- Nenhum")

    lines.extend([
        "",
        "Nomes duplicados na planilha de loja",
        "-----------------------------------",
    ])
    for rows in duplicate_shop.values():
        lines.append(f"- {rows[0].get('Name')} ({len(rows)} linhas)")
    if not duplicate_shop:
        lines.append("- Nenhum")

    REPORT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    base_rows = list(rows_by_header(BASE_FILE))
    shop_rows = list(rows_by_header(SHOP_FILE))
    base_group = group_by_name(base_rows, "Nome")
    shop_group = group_by_name(shop_rows, "Name")

    matched_keys = sorted(set(base_group) & set(shop_group))
    only_base = sorted(set(base_group) - set(shop_group))
    only_shop = sorted(set(shop_group) - set(base_group))
    used_slugs = set()
    items = []

    for key in matched_keys:
        base_matches = base_group[key]
        shop_matches = shop_group[key]
        for index, base in enumerate(base_matches):
            shop = shop_matches[min(index, len(shop_matches) - 1)]
            observations = []
            if len(base_matches) > 1:
                observations.append("Nome duplicado na planilha de slots; conferir variante.")
            if len(shop_matches) > 1:
                observations.append("Nome duplicado na planilha de loja; conferir preco/loja.")
            items.append(build_from_base(base, shop, "pronto", " ".join(observations), used_slugs))

    for key in only_base:
        for base in base_group[key]:
            items.append(build_from_base(
                base,
                None,
                "revisar_manual",
                "Item existe apenas na planilha de slots; preencher Raridade, Loja e Preco antes de importar.",
                used_slugs,
            ))

    for key in only_shop:
        for shop in shop_group[key]:
            items.append(build_from_shop(
                shop,
                "revisar_manual",
                "Item existe apenas na planilha de loja; preencher Nome em portugues e Slot antes de importar.",
                used_slugs,
            ))

    items.sort(key=lambda item: (item["StatusImportacao"] != "pronto", normalize(item["Nome"])))
    write_workbook(items)
    write_report(base_rows, shop_rows, base_group, shop_group, matched_keys, only_base, only_shop, items)

    print(f"Itens gerados: {len(items)}")
    print(f"Prontos para importacao: {sum(1 for item in items if item['StatusImportacao'] == 'pronto')}")
    print(f"Para revisar manualmente: {sum(1 for item in items if item['StatusImportacao'] != 'pronto')}")
    print(f"Planilha final: {OUTPUT_FILE}")
    print(f"Relatorio: {REPORT_FILE}")


if __name__ == "__main__":
    main()
