# -*- coding: utf-8 -*-
"""Importa/atualiza criaturas oficiais a partir dos CSVs em ref/Livros.

O comando evita copiar prosa longa do livro para o banco. Em vez disso, ele
gera uma descricao tecnica em PT-BR a partir dos campos estruturados e cria
referencias mecanicas para magias encontradas no statblock.
"""

import csv
import re
import unicodedata
from contextlib import nullcontext
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from home.models import TbBestiario, TbMagia


CSV_PATH = Path("ref/Livros/Bestiary_selecao.csv")
SPELL_ALIGNMENT_PATHS = (
    Path("ref/Livros/magias_alinhado.csv"),
    Path("ref/Livros/magias_en_pt.csv"),
)

MANUAL_SPELL_ALIASES = {
    "alarm": ("Alarme", "alarme"),
    "beast sense": ("Sentido Bestial", "sentido-bestial"),
    "commune with nature": ("Comunhao com a Natureza", "comunhao-com-a-natureza"),
    "comprehend languages": ("Compreender Idiomas", "compreender-idiomas"),
    "locate animals or plants": ("Localizar Animais ou Plantas", "localizar-animais-ou-plantas"),
    "rary's telepathic bond": ("Ligacao Telepatica", "ligacao-telepatica"),
    "silence": ("Silencio", "silencio"),
    "tenser's floating disk": ("Disco Flutuante", "disco-flutuante"),
    "water walk": ("Andar sobre Agua", "andar-sobre-agua"),
}

SECOES = (
    ("Traits", "traits", "Tracos"),
    ("Actions", "actions", "Acoes"),
    ("Bonus Actions", "bonus_actions", "Acoes Bonus"),
    ("Reactions", "reactions", "Reacoes"),
    ("Legendary Actions", "legendary_actions", "Acoes Lendarias"),
    ("Mythic Actions", "mythic_actions", "Acoes Miticas"),
    ("Lair Actions", "lair_actions", "Acoes de Covil"),
    ("Regional Effects", "regional_effects", "Efeitos Regionais"),
)

SIZE_PT = {
    "Tiny": "Minimo",
    "Small": "Pequeno",
    "Medium": "Medio",
    "Large": "Grande",
    "Huge": "Enorme",
    "Gargantuan": "Colossal",
    "Varies": "Variavel",
}

TYPE_PT = {
    "Aberration": "Aberracao",
    "Beast": "Besta",
    "Celestial": "Celestial",
    "Construct": "Construto",
    "Dragon": "Dragao",
    "Elemental": "Elemental",
    "Fey": "Feerico",
    "Fiend": "Corruptor",
    "Giant": "Gigante",
    "Humanoid": "Humanoide",
    "Monstrosity": "Monstruosidade",
    "Ooze": "Limo",
    "Plant": "Planta",
    "Undead": "Morto-vivo",
}

ALIGNMENT_PT = {
    "unaligned": "sem alinhamento",
    "neutral": "neutro",
    "lawful good": "leal e bom",
    "neutral good": "neutro e bom",
    "chaotic good": "caotico e bom",
    "lawful neutral": "leal e neutro",
    "chaotic neutral": "caotico e neutro",
    "lawful evil": "leal e mau",
    "neutral evil": "neutro e mau",
    "chaotic evil": "caotico e mau",
    "any alignment": "qualquer alinhamento",
}

ABILITY_PT = {
    "STR": "FOR",
    "DEX": "DES",
    "CON": "CON",
    "INT": "INT",
    "WIS": "SAB",
    "CHA": "CAR",
}

FEATURE_PT = {
    "Spellcasting": "Conjuracao",
    "Innate Spellcasting": "Conjuracao Inata",
    "Multiattack": "Ataques Multiplos",
    "Legendary Resistance": "Resistencia Lendaria",
    "Magic Resistance": "Resistencia a Magia",
    "Magic Weapons": "Armas Magicas",
    "Pack Tactics": "Taticas de Matilha",
    "Keen Hearing": "Audicao Aguçada",
    "Keen Sight": "Visao Aguçada",
    "Keen Smell": "Faro Aguçado",
    "Spider Climb": "Escalada Aracnidea",
    "Sunlight Sensitivity": "Sensibilidade a Luz Solar",
}

CREATURE_ALIASES = {
    "Animated Object": ("objeto-animado", "Objeto Animado"),
    "Giant Insect": ("inseto-gigante", "Inseto Gigante"),
    "Riding Horse": ("cavalo-de-montaria", "Cavalo de Montaria"),
    "Skeleton": ("esqueleto", "Esqueleto"),
    "Unicorn": ("unicornio", "Unicornio"),
    "Warhorse": ("cavalo-de-guerra", "Cavalo de Guerra"),
    "Zombie": ("zumbi", "Zumbi"),
}

TAG_CREATURE_ALIASES = {
    slugify(en): pt_slug for en, (pt_slug, _nome) in CREATURE_ALIASES.items()
}

NAME_REPLACEMENTS = (
    ("Ancient", "Anciao"),
    ("Adult", "Adulto"),
    ("Young", "Jovem"),
    ("Wyrmling", "Filhote"),
    ("Black", "Negro"),
    ("Blue", "Azul"),
    ("Brass", "Latao"),
    ("Bronze", "Bronze"),
    ("Copper", "Cobre"),
    ("Gold", "Dourado"),
    ("Green", "Verde"),
    ("Red", "Vermelho"),
    ("Silver", "Prateado"),
    ("White", "Branco"),
    ("Amethyst", "Ametista"),
    ("Crystal", "Cristal"),
    ("Emerald", "Esmeralda"),
    ("Sapphire", "Safira"),
    ("Topaz", "Topazio"),
    ("Dragon", "Dragao"),
    ("Aarakocra", "Aarakocra"),
    ("Aeromancer", "Aeromante"),
    ("Skirmisher", "Escaramucador"),
    ("Aberrant", "Aberrante"),
    ("Cultist", "Cultista"),
    ("Spirit", "Espirito"),
    ("Abjurer", "Abjurador"),
    ("Conjurer", "Conjurador"),
    ("Diviner", "Adivinho"),
    ("Enchanter", "Encantador"),
    ("Evoker", "Evocador"),
    ("Illusionist", "Ilusionista"),
    ("Necromancer", "Necromante"),
    ("Transmuter", "Transmutador"),
    ("Wizard", "Mago"),
    ("Abominable", "Abominavel"),
    ("Assassin", "Assassino"),
    ("Archmage", "Arquimago"),
    ("Berserker", "Furioso"),
    ("Veteran", "Veterano"),
    ("Noble", "Nobre"),
    ("Acolyte", "Acolito"),
    ("Apprentice", "Aprendiz"),
    ("Warlock", "Bruxo"),
    ("Druid", "Druida"),
    ("Bard", "Bardo"),
    ("Monk", "Monge"),
    ("Paladin", "Paladino"),
    ("Ranger", "Guardiao"),
    ("Rogue", "Ladino"),
    ("Pirate", "Pirata"),
    ("Thug", "Capanga"),
    ("Cult", "Culto"),
    ("Skeleton", "Esqueleto"),
    ("Zombie", "Zumbi"),
    ("Ghost", "Fantasma"),
    ("Ghoul", "Carniçal"),
    ("Giant", "Gigante"),
    ("Dire", "Atroz"),
    ("Swarm", "Enxame"),
    ("Commoner", "Plebeu"),
    ("Guard", "Guarda"),
    ("Knight", "Cavaleiro"),
    ("Mage", "Mago"),
    ("Priest", "Sacerdote"),
    ("Warrior", "Guerreiro"),
    ("Scout", "Batedor"),
    ("Spy", "Espiao"),
    ("Bandit", "Bandido"),
    ("Captain", "Capitao"),
    ("Horse", "Cavalo"),
    ("Wolf", "Lobo"),
    ("Bear", "Urso"),
    ("Lion", "Leao"),
    ("Tiger", "Tigre"),
    ("Rat", "Rato"),
    ("Bat", "Morcego"),
    ("Spider", "Aranha"),
    ("Snake", "Serpente"),
    ("Eagle", "Aguia"),
    ("Hawk", "Falcao"),
    ("Owl", "Coruja"),
    ("Raven", "Corvo"),
)

SCHOOL_WIZARD_WORDS = {
    "Abjurer",
    "Conjurer",
    "Diviner",
    "Enchanter",
    "Evoker",
    "Illusionist",
    "Necromancer",
    "Transmuter",
}

BESTIARY_REF_RE = re.compile(r"\bbestiary\s*\{\s*([a-z0-9-]+)\s*\}", re.I)


def _repo_path(path):
    return Path(path)


def _norm(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", texto.lower())


def _split_lista(valor):
    return [parte.strip() for parte in re.split(r"[;,]\s*", valor or "") if parte.strip()]


def _int_or_none(valor):
    valor = (valor or "").strip()
    if not valor:
        return None
    match = re.search(r"\d+", valor)
    return int(match.group(0)) if match else None


def _traduz_nome_criatura(nome_en):
    if nome_en in CREATURE_ALIASES:
        return CREATURE_ALIASES[nome_en][1]

    palavras = nome_en.split()
    if len(palavras) == 3 and palavras[2] == "Dragon":
        cor = dict(NAME_REPLACEMENTS).get(palavras[1], palavras[1])
        idade = dict(NAME_REPLACEMENTS).get(palavras[0], palavras[0])
        return f"Dragao {cor} {idade}".strip()

    if len(palavras) == 2 and palavras[1] == "Wizard" and palavras[0] in SCHOOL_WIZARD_WORDS:
        escola = dict(NAME_REPLACEMENTS).get(palavras[0], palavras[0])
        return f"Mago {escola}"

    partes = []
    mapa = dict(NAME_REPLACEMENTS)
    for palavra in palavras:
        limpo = palavra.strip(",")
        partes.append(mapa.get(limpo, limpo))
    return " ".join(partes)


def _slug_criatura(nome_en):
    if nome_en in CREATURE_ALIASES:
        return CREATURE_ALIASES[nome_en][0]
    return slugify(nome_en)


def _traduz_feature(nome):
    base = re.sub(r"\s*\([^)]*\)\s*$", "", nome or "").strip()
    return FEATURE_PT.get(base, base)


def _linha_pt(rotulo, valor):
    valor = (valor or "").strip()
    return f"- **{rotulo}:** {valor}" if valor else None


def _load_spell_alignment():
    alinhamento = {}
    for path in SPELL_ALIGNMENT_PATHS:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                en = (row.get("en") or row.get("magia_en") or "").strip()
                if not en:
                    continue
                candidatos = [
                    row.get("final"),
                    row.get("nome_pt"),
                    row.get("adaptado"),
                    row.get("traduzido"),
                    row.get("traduzido_literal"),
                ]
                pt = next((c.strip() for c in candidatos if c and c.strip()), en)
                chave = en.lower()
                alinhamento[chave] = {
                    "name_en": en,
                    "name_pt": pt,
                    "slug": slugify(pt),
                    "resolved": False,
                }
    return alinhamento


def _resolve_spell_alignment(alinhamento):
    magias = list(TbMagia.objects.only("nome", "slug"))
    por_nome = {_norm(m.nome): m.slug for m in magias}
    por_slug = {m.slug for m in magias}

    for info in alinhamento.values():
        manual = MANUAL_SPELL_ALIASES.get(info["name_en"].lower())
        if manual and manual[1] in por_slug:
            info["name_pt"] = manual[0]
            info["slug"] = manual[1]
            info["resolved"] = True
            continue

        candidatos = [info["name_pt"], info["name_en"]]
        for candidato in candidatos:
            if _norm(candidato) in por_nome:
                info["slug"] = por_nome[_norm(candidato)]
                info["resolved"] = True
                break
            candidato_slug = slugify(candidato)
            if candidato_slug in por_slug:
                info["slug"] = candidato_slug
                info["resolved"] = True
                break
    return alinhamento


def _spell_catalog(alinhamento):
    catalog = []
    for key, info in alinhamento.items():
        catalog.append(
            {
                "en_lower": key,
                "name_en": info["name_en"],
                "name_pt": info["name_pt"],
                "slug": info["slug"],
                "resolved": info["resolved"],
            }
        )
    return sorted(catalog, key=lambda item: len(item["en_lower"]), reverse=True)


def _is_boundary(texto, idx, end):
    before = texto[idx - 1] if idx > 0 else " "
    after = texto[end] if end < len(texto) else " "
    return not before.isalnum() and not after.isalnum()


def _extract_spell_refs(texto, catalog):
    texto = texto or ""
    lower = texto.lower()
    matches = []
    ocupado = [False] * len(lower)

    for info in catalog:
        needle = info["en_lower"]
        start = lower.find(needle)
        while start >= 0:
            end = start + len(needle)
            if _is_boundary(lower, start, end) and not any(ocupado[start:end]):
                for pos in range(start, end):
                    ocupado[pos] = True
                matches.append((start, info))
            start = lower.find(needle, start + 1)

    refs = []
    vistos = set()
    for _pos, info in sorted(matches, key=lambda item: item[0]):
        if info["slug"] in vistos:
            continue
        vistos.add(info["slug"])
        refs.append(
            {
                "name_en": info["name_en"],
                "name": info["name_pt"],
                "slug": info["slug"],
                "resolved": info["resolved"],
            }
        )
    return refs


def _tags_for_spell_refs(refs, uso=None):
    tags = []
    for ref in refs:
        if uso == "at-will":
            tags.append(f"cast{{spell:{ref['slug']}, at-will}}")
        elif uso:
            tags.append(f"cast{{spell:{ref['slug']}, uses{{{uso}, reset:long-rest}}}}")
        else:
            tags.append(f"cast{{spell:{ref['slug']}}}")
    return tags


def _spell_uses(texto, catalog):
    usos = []
    for linha in (texto or "").splitlines():
        match = re.match(r"\s*(At will|(\d+)/(?:day|rest)(?: each)?):\s*(.+)$", linha, re.I)
        if not match:
            continue
        label = match.group(1)
        quantidade = match.group(2)
        refs = _extract_spell_refs(match.group(3), catalog)
        if not refs:
            continue
        uso_tag = "at-will" if label.lower().startswith("at will") else quantidade
        usos.append(
            {
                "label_en": label,
                "label": "A vontade" if uso_tag == "at-will" else f"{quantidade}/dia",
                "uses": None if uso_tag == "at-will" else int(quantidade),
                "spells": refs,
                "tags": _tags_for_spell_refs(refs, uso_tag),
            }
        )
    return usos


def _split_secao(texto, catalog):
    texto = (texto or "").strip()
    if not texto:
        return []

    blocos = []
    atual = None
    partes = re.split(r"(?m)(?=^[A-Z][A-Za-z' -]+(?:\s*\([^)]*\))?\.\s+)", texto)
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        match = re.match(r"^([A-Z][A-Za-z' -]+(?:\s*\([^)]*\))?)\.\s*(.*)$", parte, re.S)
        if match:
            if atual:
                blocos.append(atual)
            nome_en = match.group(1).strip()
            corpo = match.group(2).strip()
            refs = _extract_spell_refs(corpo, catalog)
            atual = {
                "name_en": nome_en,
                "name": _traduz_feature(nome_en),
                "entries": _entries_resumo(nome_en, refs),
            }
            if refs:
                atual["spell_refs"] = refs
                atual["tags"] = _tags_for_spell_refs(refs)
            usos = _spell_uses(corpo, catalog)
            if usos:
                atual["spell_uses"] = usos
                tags = atual.setdefault("tags", [])
                for uso in usos:
                    tags.extend(uso["tags"])
                uso_slugs = {ref["slug"] for uso in usos for ref in uso.get("spells", [])}
                atual["tags"] = [
                    tag
                    for tag in tags
                    if tag not in {f"cast{{spell:{slug}}}" for slug in uso_slugs}
                ]
        elif atual:
            refs = _extract_spell_refs(parte, catalog)
            if refs:
                atual.setdefault("spell_refs", []).extend(refs)
                atual.setdefault("tags", []).extend(_tags_for_spell_refs(refs))

    if atual:
        blocos.append(atual)

    for bloco in blocos:
        if "tags" in bloco:
            bloco["tags"] = sorted(set(bloco["tags"]))
        if "spell_refs" in bloco:
            bloco["spell_refs"] = _dedupe_refs(bloco["spell_refs"])
    return blocos


def _entries_resumo(nome_en, refs):
    if refs:
        nomes = ", ".join(ref["name"] for ref in refs)
        return [f"Referencia magica importada: {nomes}."]
    return [f"Efeito importado como bloco tecnico: {_traduz_feature(nome_en)}."]


def _dedupe_refs(refs):
    vistos = set()
    out = []
    for ref in refs:
        if ref["slug"] in vistos:
            continue
        vistos.add(ref["slug"])
        out.append(ref)
    return out


def _build_statblock(row, catalog):
    nome_en = row["Name"].strip()
    nome_pt = _traduz_nome_criatura(nome_en)

    statblock = {
        "name": nome_pt,
        "name_en": nome_en,
        "source": row.get("Source", "").strip(),
        "page": row.get("Page", "").strip(),
        "size": SIZE_PT.get(row.get("Size", "").strip(), row.get("Size", "").strip()),
        "size_en": row.get("Size", "").strip(),
        "type": TYPE_PT.get(row.get("Type", "").strip(), row.get("Type", "").strip()),
        "type_en": row.get("Type", "").strip(),
        "alignment": ALIGNMENT_PT.get(row.get("Alignment", "").strip().lower(), row.get("Alignment", "").strip()),
        "alignment_en": row.get("Alignment", "").strip(),
        "ac": _int_or_none(row.get("AC")),
        "ac_text": row.get("AC", "").strip(),
        "hp": row.get("HP", "").strip(),
        "speed": row.get("Speed", "").strip(),
        "abilities": {
            "str": _int_or_none(row.get("Strength")),
            "dex": _int_or_none(row.get("Dexterity")),
            "con": _int_or_none(row.get("Constitution")),
            "int": _int_or_none(row.get("Intelligence")),
            "wis": _int_or_none(row.get("Wisdom")),
            "cha": _int_or_none(row.get("Charisma")),
        },
        "saving_throws": _traduz_abilities(row.get("Saving Throws", "")),
        "skills": _split_lista(row.get("Skills", "")),
        "damage_vulnerabilities": _split_lista(row.get("Damage Vulnerabilities", "")),
        "damage_resistances": _split_lista(row.get("Damage Resistances", "")),
        "damage_immunities": _split_lista(row.get("Damage Immunities", "")),
        "condition_immunities": _split_lista(row.get("Condition Immunities", "")),
        "senses": row.get("Senses", "").strip(),
        "languages": row.get("Languages", "").strip(),
        "cr": row.get("CR", "").strip(),
        "environment": _split_lista(row.get("Environment", "")),
        "treasure": row.get("Treasure", "").strip(),
    }

    tags = set()
    spell_refs = []
    for csv_key, json_key, _label in SECOES:
        blocos = _split_secao(row.get(csv_key, ""), catalog)
        statblock[json_key] = blocos
        for bloco in blocos:
            tags.update(bloco.get("tags", []))
            spell_refs.extend(bloco.get("spell_refs", []))
            for uso in bloco.get("spell_uses", []):
                tags.update(uso.get("tags", []))
                spell_refs.extend(uso.get("spells", []))

    statblock["spell_refs"] = _dedupe_refs(spell_refs)
    statblock["tags"] = _normaliza_tags_spell(tags)
    return statblock


def _normaliza_tags_spell(tags):
    tags = set(tags)
    especificas = set()
    for tag in tags:
        match = re.match(r"cast\{spell:([^,}]+),", tag)
        if match:
            especificas.add(match.group(1))
    for slug in especificas:
        tags.discard(f"cast{{spell:{slug}}}")
    return sorted(tags)


def _traduz_abilities(valor):
    texto = valor or ""
    for en, pt in ABILITY_PT.items():
        texto = re.sub(rf"\b{en}\b", pt, texto)
    return texto.strip()


def _descricao_markdown(row, statblock):
    nome = statblock["name"]
    nome_en = statblock["name_en"]
    origem = " ".join(p for p in [statblock.get("source"), f"p. {statblock.get('page')}" if statblock.get("page") else ""] if p)

    linhas = [
        f"### {nome}",
        f"*{nome_en}*" if nome != nome_en else "",
        "",
        _linha_pt("Fonte", origem),
        _linha_pt("Tipo", f"{statblock.get('size')} {statblock.get('type')}, {statblock.get('alignment')}".strip(", ")),
        _linha_pt("ND", statblock.get("cr")),
        _linha_pt("CA", statblock.get("ac_text")),
        _linha_pt("PV", statblock.get("hp")),
        _linha_pt("Deslocamento", statblock.get("speed")),
        _linha_pt("Salvaguardas", statblock.get("saving_throws")),
        _linha_pt("Pericias", ", ".join(statblock.get("skills") or [])),
        _linha_pt("Resistencias", ", ".join(statblock.get("damage_resistances") or [])),
        _linha_pt("Imunidades a dano", ", ".join(statblock.get("damage_immunities") or [])),
        _linha_pt("Imunidades a condicao", ", ".join(statblock.get("condition_immunities") or [])),
        _linha_pt("Sentidos", statblock.get("senses")),
        _linha_pt("Idiomas", statblock.get("languages")),
    ]

    spell_lines = []
    for ref in statblock.get("spell_refs", []):
        spell_lines.append(f"- `spell:{ref['slug']}` - {ref['name']}")
    if spell_lines:
        linhas.extend(["", "#### Magias referenciadas", *spell_lines])

    for _csv_key, json_key, label in SECOES:
        blocos = statblock.get(json_key) or []
        if not blocos:
            continue
        linhas.extend(["", f"#### {label}"])
        for bloco in blocos:
            detalhe = ""
            if bloco.get("spell_refs"):
                detalhe = " (" + ", ".join(ref["name"] for ref in bloco["spell_refs"]) + ")"
            linhas.append(f"- **{bloco['name']}**{detalhe}")

    return "\n".join(linha for linha in linhas if linha is not None)


def _fields_for_row(row, catalog):
    nome_en = row["Name"].strip()
    nome_pt = _traduz_nome_criatura(nome_en)
    statblock = _build_statblock(row, catalog)
    return _slug_criatura(nome_en), {
        "nome": nome_pt,
        "tipo": statblock["type"],
        "tamanho": statblock["size"],
        "nd": statblock["cr"],
        "alinhamento": statblock["alignment"],
        "source": statblock["source"],
        "ca": statblock["ac"],
        "pv": statblock["hp"],
        "statblock_json": statblock,
        "tags_json": statblock.get("tags", []),
        "descricao_markdown": _descricao_markdown(row, statblock),
        "comunidade": False,
    }


def _read_rows(path, fontes):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if fontes:
        permitidas = {fonte.strip() for fonte in fontes if fonte.strip()}
        rows = [row for row in rows if row.get("Source", "").strip() in permitidas]
    return rows


def _fix_spell_creature_refs(apply):
    existing = set(TbBestiario.objects.values_list("slug", flat=True))
    alteradas = 0
    missing = {}

    for magia in TbMagia.objects.only("nome", "slug", "tags_json"):
        tags = magia.tags_json or []
        if not isinstance(tags, list):
            continue

        novas_tags = []
        mudou = False
        for tag in tags:
            novo = tag
            if isinstance(tag, str):
                for ref in BESTIARY_REF_RE.findall(tag):
                    if ref in existing:
                        continue
                    destino = TAG_CREATURE_ALIASES.get(ref)
                    if destino and destino in existing:
                        novo = re.sub(
                            rf"\bbestiary\s*\{{\s*{re.escape(ref)}\s*\}}",
                            f"bestiary{{{destino}}}",
                            novo,
                            flags=re.I,
                        )
                        mudou = True
                    else:
                        missing.setdefault(ref, set()).add(magia.slug)
            novas_tags.append(novo)

        if mudou:
            alteradas += 1
            if apply:
                magia.tags_json = novas_tags
                magia.save(update_fields=["tags_json"])

    return alteradas, missing


class Command(BaseCommand):
    help = "Importa o bestiario selecionado, alinhando magias e referencias mecanicas."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=str(CSV_PATH), help="Caminho do CSV de bestiario.")
        parser.add_argument("--apply", action="store_true", help="Grava as alteracoes no banco.")
        parser.add_argument("--limite", type=int, default=0, help="Limita a quantidade de linhas processadas.")
        parser.add_argument(
            "--fontes",
            nargs="*",
            default=[],
            help="Filtra fontes. Vazio importa todas as fontes do CSV.",
        )
        parser.add_argument(
            "--sem-fix-magias",
            action="store_true",
            help="Nao tenta corrigir bestiary{} em tags_json de TbMagia.",
        )
        parser.add_argument(
            "--sem-db",
            action="store_true",
            help="Preview sem consultar o banco. Incompativel com --apply.",
        )

    def handle(self, *args, **options):
        path = _repo_path(options["csv"])
        if not path.exists():
            raise SystemExit(f"CSV nao encontrado: {path}")

        apply = options["apply"]
        sem_db = options["sem_db"]
        if apply and sem_db:
            raise SystemExit("--sem-db e apenas para preview; remova --sem-db para usar --apply.")

        alinhamento = _load_spell_alignment()
        if not sem_db:
            alinhamento = _resolve_spell_alignment(alinhamento)
        catalog = _spell_catalog(alinhamento)

        rows = _read_rows(path, options["fontes"])
        if options["limite"]:
            rows = rows[: options["limite"]]

        criadas = atualizadas = 0
        unresolved_spells = set()
        exemplos = []

        with transaction.atomic() if apply else nullcontext():
            for row in rows:
                slug, fields = _fields_for_row(row, catalog)
                statblock = fields["statblock_json"]
                for ref in statblock.get("spell_refs", []):
                    if not sem_db and not ref.get("resolved"):
                        unresolved_spells.add(f"{ref['name_en']} -> {ref['slug']}")

                existing = None
                if not sem_db:
                    existing = (
                        TbBestiario.objects.filter(slug=slug).first()
                        or TbBestiario.objects.filter(statblock_json__name_en=row["Name"].strip()).first()
                    )

                if apply:
                    if existing:
                        for key, value in fields.items():
                            setattr(existing, key, value)
                        existing.slug = slug
                        existing.save()
                        atualizadas += 1
                    else:
                        TbBestiario.objects.create(slug=slug, **fields)
                        criadas += 1
                else:
                    if existing:
                        atualizadas += 1
                    else:
                        criadas += 1

                if len(exemplos) < 10:
                    exemplos.append(f"{row['Name']} -> {fields['nome']} [{slug}]")

        spell_ref_updates = missing_refs = None
        if not sem_db and not options["sem_fix_magias"]:
            spell_ref_updates, missing_refs = _fix_spell_creature_refs(apply)

        modo = "APLICADO" if apply else "PREVIEW"
        self.stdout.write(self.style.SUCCESS(f"{modo}: {len(rows)} criaturas processadas."))
        self.stdout.write(f"Criadas: {criadas} | Atualizadas: {atualizadas}")
        if exemplos:
            self.stdout.write("Exemplos:")
            for item in exemplos:
                self.stdout.write(f"  - {item}")

        if sem_db:
            self.stdout.write("")
            self.stdout.write("Modo sem DB: slugs de magia foram estimados pelo CSV de alinhamento.")

        if unresolved_spells:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"Magias citadas sem match exato no banco: {len(unresolved_spells)}"))
            for item in sorted(unresolved_spells)[:25]:
                self.stdout.write(f"  - {item}")

        if spell_ref_updates is not None:
            self.stdout.write("")
            self.stdout.write(f"Tags de magia com bestiary{{}} corrigiveis: {spell_ref_updates}")
            if missing_refs:
                self.stdout.write(self.style.WARNING("Referencias bestiary{} ainda sem criatura correspondente:"))
                for ref, magias in sorted(missing_refs.items())[:25]:
                    self.stdout.write(f"  - {ref}: {', '.join(sorted(magias)[:8])}")
