# -*- coding: utf-8 -*-
"""Carrega e indexa home/tag_library.json — a especificação do DSL de tags.

A biblioteca é a ÚNICA fonte de verdade do vocabulário. O validador/motor não
conhece nenhum verbo: ele pergunta aqui. Adicionar um verbo = editar o JSON.
"""
import json
import os
import re

LIB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tag_library.json")

_WORD = re.compile(r"[a-z0-9][a-z0-9_-]*")

# Qualificadores estruturais que aparecem como CHAVE dentro de (...) e blocos
# (range:, target:, willing, vs:, ...). São legítimos mas não são "primitivas"
# no JSON; listá-los aqui evita falso-positivo de "verbo desconhecido".
STRUCTURAL_QUALIFIERS = {
    "range", "target", "from", "by", "vs", "duration", "reset", "scope",
    "on_success", "on_fail", "on_hit", "on_miss", "keep", "dice", "unless",
    "until", "per", "threshold", "max_nivel", "same_roll", "same_cd", "step",
    "cost", "lista", "slots", "foco", "known_caster", "prepara", "qtd",
    "willing", "nonmagical", "magical", "see_or_hear", "can_see_or_hear",
    "can_see", "can_hear", "one_way", "two_way", "half", "none", "weapon_type",
    "source", "of", "in", "out", "self", "active", "concentration", "reaction",
    "catalog", "category", "subtype", "mundane", "armor", "weapon", "light", "medium", "heavy",
    "restriction", "requires", "max", "min", "and", "or", "not", "elemento",
    "pericias", "results", "table", "list", "always_prepared", "extra",
    "fora_do_limite", "incapacitated", "hidden", "plano_nativo",
    # chaves de modifiers{}/qualificadores e sinônimos (triagem 2026-06-18)
    "except", "also", "origem", "forma", "attacker", "instant_death",
    "spell_marca", "marked", "distinct",
    # escopos-locais de subclasse (define{}/forma) que o validador não resolve
    # por serem chaves de list{} ou redefinições (:=): tratados como locais.
    "weapon_integrada", "weapon_aprimorada", "arqueiro", "calice", "pesadelo",
    "balsamo", "mao_magica", "mao_arcana", "runes_known", "mente_aberta", "mente_fechada",
    "surpreendido", "die_if_0", "force_miss", "opportunity_attack",
    # variáveis de ESCOLHA de essência (set/pick/match/requires sobre elas) e formas
    "alento", "vertente", "descendencia", "sangue", "polo", "energia", "elemento",
    "wyvern", "draco", "long", "celestial", "infero", "lumen", "umbra",
    # qualificadores/modificadores 1-off de magia concedida (cast{}/modifiers{})
    "since_last_turn", "per_ray", "subsequent_action", "underwater_option",
    "extra_option", "elemental_upgrade", "context", "cast_any", "rebuild", "hover",
    "wall", "transformacao_draconica",
    # contextos de antecedente (pesquisa acadêmica, gate de tempo)
    "research", "time",
}

# 18 perícias canônicas (catálogo 'skill' é aberto/DB, mas a lista padrão é fechada;
# listá-las evita falso-positivo quando aparecem como token solto).
SKILLS = {
    "atletismo", "acrobacia", "furtividade", "prestidigitacao", "arcanismo",
    "historia", "investigacao", "natureza", "religiao", "adestrar_animais",
    "intuicao", "medicina", "percepcao", "sobrevivencia", "enganacao",
    "intimidacao", "atuacao", "persuasao",
}

_ATTRS = ("str", "dex", "con", "int", "wis", "cha")
_ROLL_SUFFIX = ("mod", "score", "save", "check", "atk")
# dex_mod, wis_save, cha_atk, ... + roll-ids avulsos (identificadores em snake_case)
ROLL_IDS = (
    {f"{a}_{s}" for a in _ATTRS for s in _ROLL_SUFFIX}
    | {
    "initiative", "death_save", "ability_check", "spell_attack", "spell_save",
})


def _base(token_key):
    """Palavra-base de uma chave que pode ser um padrão.
    'ally(range:<dist>)' -> 'ally'; 'target{acted}' -> 'target'."""
    m = _WORD.match(token_key.strip().lower())
    return m.group(0) if m else token_key.strip().lower()


class Library:
    def __init__(self, path=LIB_PATH):
        self.path = path
        with open(path, encoding="utf-8") as fh:
            self.raw = json.load(fh)
        self._index()

    # ---- helpers -----------------------------------------------------------
    def _keys(self, group):
        return [k for k in (self.raw.get(group) or {}) if not k.startswith("_")]

    # ---- índice ------------------------------------------------------------
    def _index(self):
        raw = self.raw

        # primitivas: chaves = heads; 'no-*' é prefixo-curinga
        self.primitives = set()
        self.wildcards = []            # ex.: 'no-' (de 'no-*')
        for k in self._keys("primitives"):
            if k.endswith("*"):
                self.wildcards.append(k[:-1])
            else:
                self.primitives.add(k)

        self.ops = set(self._keys("ops"))
        self.events = {_base(k) for k in self._keys("events")}
        self.selectors = set(self._keys("selectors"))
        self.references = set(self._keys("references"))
        self.tags_de_classe = set(self._keys("tags_de_classe"))
        self.recursos_universais = set(self._keys("recursos_universais"))
        self.conditions = {_base(k) for k in self._keys("conditions")}
        self.forbidden_heads = {
            k: v for k, v in (raw.get("forbidden_heads") or {}).items()
            if not k.startswith("_")
        }
        self.forbidden_operands = {
            k: v for k, v in (raw.get("forbidden_operands") or {}).items()
            if not k.startswith("_")
        }
        self.forbidden_prefixes = {
            k: v for k, v in (raw.get("forbidden_prefixes") or {}).items()
            if not k.startswith("_")
        }

        fns = raw.get("functions", {})
        self.functions = {
            k for k in fns
            if not k.startswith("_")
            and k not in ("operadores", "variaveis_de_formula", "limiters")
        }
        self.variaveis = {k for k in fns.get("variaveis_de_formula", {}) if not k.startswith("_")}
        self.limiters = {_base(k) for k in fns.get("limiters", {}) if not k.startswith("_")}

        # scopes (achatado: melee, weapon, str-atk, off-hand, ...)
        self.scopes = set()
        for vals in (raw.get("scopes") or {}).values():
            if isinstance(vals, dict):
                self.scopes.update(vals.keys())

        # catálogos: fechados (têm 'valores') vs abertos (têm 'fonte'/'fonte_db')
        self.catalogs = {}             # nome -> set(valores)
        self.open_catalogs = set()
        self.catalog_lang = {}
        for cat, info in (raw.get("catalogs") or {}).items():
            if cat.startswith("_") or not isinstance(info, dict):
                continue
            self.catalog_lang[cat] = info.get("lang")
            if info.get("valores"):
                self.catalogs[cat] = set(info["valores"])
            else:
                self.open_catalogs.add(cat)

        # todos os valores de catálogos FECHADOS (fogo, amedrontado, medio, ...):
        # são tokens válidos (aparecem em match{}/resist:{a,b}), não verbos.
        self.catalog_values = set()
        for vals in self.catalogs.values():
            self.catalog_values |= vals

        # conjunto do que pode INICIAR uma cláusula/efeito. Inclui não-verbos que
        # legitimamente aparecem em posição de head dentro de blocos/listas:
        # escopos (str-atk), variáveis (classlvl), eventos (end), roll-ids
        # (dex-save), perícias (medicina) e valores de catálogo (radiante).
        self.known_heads = (
            self.primitives | self.functions | self.tags_de_classe
            | self.references | self.selectors | self.conditions
            | self.scopes | self.variaveis | self.events
            | self.catalog_values | SKILLS | ROLL_IDS
            | STRUCTURAL_QUALIFIERS
        )

    # ---- consultas ---------------------------------------------------------
    def head_known(self, head):
        head = head.lower()
        if head in self.known_heads:
            return True
        return any(head.startswith(w) for w in self.wildcards)

    def scope_known(self, seg):
        seg = seg.lower()
        return seg in self.scopes or seg in self.selectors

    # ---- auto-auditoria da biblioteca -------------------------------------
    def lint(self):
        """Audita a consistência interna do tag_library.json.
        Retorna lista de (nivel, mensagem)."""
        out = []
        raw = self.raw
        valid_ops = self.ops | {None}

        # 1. toda primitiva aponta para uma op existente
        for k, v in (raw.get("primitives") or {}).items():
            if k.startswith("_") or not isinstance(v, dict):
                continue
            if "op" in v and v["op"] not in valid_ops:
                out.append(("ERROR", f"primitives.{k}: op '{v['op']}' não existe em 'ops'."))
            val = v.get("value")
            if isinstance(val, dict) and val.get("catalog"):
                cat = val["catalog"]
                if cat not in self.catalogs and cat not in self.open_catalogs:
                    out.append(("ERROR", f"primitives.{k}: catalog '{cat}' não existe em 'catalogs'."))

        # 2. catálogos lang:en devem ter valores ASCII; lang:pt é livre
        acc = re.compile(r"[^\x00-\x7f]")
        for cat, vals in self.catalogs.items():
            if self.catalog_lang.get(cat) == "en":
                for x in vals:
                    if acc.search(x):
                        out.append(("WARN", f"catalogs.{cat} (lang:en): valor com acento/não-ASCII '{x}'."))

        # 3. regra de idioma: heads/keywords estruturais devem ser inglês (ASCII)
        for grp in ("primitives", "events", "selectors", "ops", "references", "tags_de_classe"):
            for k in self._keys(grp):
                if acc.search(k):
                    out.append(("WARN", f"{grp}: chave '{k}' tem acento (keyword estrutural deveria ser inglês)."))

        # 4. variáveis de fórmula referenciadas pelos docs mas ausentes? (heurístico leve)
        # 5. open_questions abertas (informativo)
        for q in (raw.get("open_questions") or []):
            out.append(("INFO", f"open_question: {q}"))

        return out
