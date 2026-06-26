# -*- coding: utf-8 -*-
"""Validador das tags_json — o "Excel" do DSL.

Para cada tag, reporta diagnósticos com nível:
  ERROR  — a fórmula está quebrada: delimitador aberto, referência inexistente
           (ability/spell/resource/opção/maestria/bestiário), valor fora de um
           catálogo FECHADO.
  WARN   — verbo/escopo desconhecido (não está na biblioteca), inconsistência
           de padrão (attack:magico).
  INFO   — caractere inesperado, observações.

Sintaxe e vocabulário saem de Library (tag_library.json). Referências saem do
banco via DataIndex (opcional: sem ele, pula os #REF!).
"""
import re
import unicodedata
from collections import namedtuple

from .lexer import tokenize, check_balance, find_other

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"

Diagnostic = namedtuple("Diagnostic", "level code message fragment")

# blocos cujo CORPO é uma lista de efeitos (recursão de validação de heads)
WRAPPER_BLOCKS = {
    "instant", "while-active", "always-active", "effects", "aura", "aoe",
    "restriction", "modifiers", "cast", "while",
}

_NUMERIC = re.compile(r"^\d")


def _slug(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _frag(line, pos, span=14):
    a = max(0, pos - span)
    return ("…" if a else "") + line[a:pos + span] + ("…" if pos + span < len(line) else "")


# ───────────────────────── árvore de tokens ─────────────────────────
def build_tree(tokens):
    """Lista aninhada: ('tok',type,val) | ('grp','{'|'(',[filhos])."""
    pos = 0

    def parse():
        nonlocal pos
        out = []
        while pos < len(tokens):
            t = tokens[pos]
            if t.type in ("LBRACE", "LPAREN", "LBRACK"):
                kind = {"LBRACE": "{", "LPAREN": "(", "LBRACK": "["}[t.type]
                pos += 1
                out.append(("grp", kind, parse()))
            elif t.type in ("RBRACE", "RPAREN", "RBRACK"):
                pos += 1
                return out
            else:
                out.append(("tok", t.type, t.value))
                pos += 1
        return out

    return parse()


def _split(nodes, ttype):
    parts = [[]]
    for n in nodes:
        if n[0] == "tok" and n[1] == ttype:
            parts.append([])
        else:
            parts[-1].append(n)
    return [p for p in parts if p]


def _read_head(seg):
    """Coleta o scope-path inicial (WORD (.WORD)*). Retorna (palavras, índice_após)."""
    words = []
    i = 0
    while i < len(seg) and seg[i][0] == "tok" and seg[i][1] == "WORD":
        words.append(seg[i][2])
        i += 1
        if (i + 1 < len(seg) and seg[i][0] == "tok" and seg[i][1] == "DOT"
                and seg[i + 1][0] == "tok" and seg[i + 1][1] == "WORD"):
            i += 1  # consome o DOT; o loop pega o próximo WORD
            continue
        break
    return words, i


def _walk_heads(nodes, lib, unknown, locals_=frozenset(), top=True):
    for clause in _split(nodes, "COMMA"):
        for seg in _split(clause, "ARROW"):
            if not seg:
                continue
            words, hend = _read_head(seg)
            base = words[-1].lower() if words else None
            if words and not _NUMERIC.match(words[0]) and words[0].lower() not in locals_:
                if len(words) == 1:
                    w = words[0].lower()
                    if not lib.head_known(w):
                        unknown.setdefault(w, [0, "verbo"])[0] += 1
                else:
                    for s in words[:-1]:
                        sl = s.lower()
                        if sl not in locals_ and not lib.scope_known(sl) and not lib.head_known(sl):
                            unknown.setdefault(sl, [0, "escopo"])[0] += 1
                    eff = words[-1].lower()
                    if not _NUMERIC.match(eff) and not lib.head_known(eff):
                        unknown.setdefault(eff, [0, "verbo"])[0] += 1  # '1' de .1/turn = limiter
            # recursão SÓ no bloco PRÓPRIO do head (grp '{' imediatamente após o
            # head). Evita recursar em ref aninhada: cast:ability{X} -> o {X} é da
            # ability, não do cast, então 'X' não é lido como verbo.
            blk = seg[hend] if hend < len(seg) else None
            if blk and blk[0] == "grp" and blk[1] == "{" and (base in WRAPPER_BLOCKS or base is None):
                _walk_heads(blk[2], lib, unknown, locals_, top=False)


# ───────────────────────── checagens por regex ──────────────────────
# nomes criados por define{<nome>: ...} ou define:weapon{<nome>: ...} — locais válidos,
# não verbos. Coletados em TODAS as linhas do registro (podem ser usados noutra linha).
_RE_DEFINE = re.compile(r"define\s*(?::\s*weapon\s*)?\{\s*([a-z0-9][a-z0-9-]*)\s*:")
# formas de DECLARAR um pool INTERNO (recurso de fórmula/fixo que NÃO vai na
# TB_RecursoClasse — só vão na tabela recursos que escalam por nível): definido
# via define{}, resource{X}(max:...), max:X=..., ou mark{X,...}.
_RE_POOL_DECL = re.compile(r"resource\{([a-z0-9-]+)\}\s*\(")
_RE_MAX_DECL = re.compile(r"\bmax:([a-z0-9-]+)\s*=")
_RE_MARK_DECL = re.compile(r"mark\{\s*([a-z0-9-]+)\s*,")
_RE_EQUIPED = re.compile(r"equiped\{([a-z0-9-]+)\}")  # itens com cargas (kit-de-curandeiro)

def collect_locals(tags):
    out = set()
    for line in (tags or []):
        if isinstance(line, str):
            out.update(m.group(1) for m in _RE_DEFINE.finditer(line))
    return out


_RE_ABILITY = re.compile(r"ability\s*\{([^{}]*)\}")
_RE_SPELL = re.compile(r"\bspell\s*:\s*([a-z0-9][a-z0-9-]*)")
_RE_RES_BRACE = re.compile(r"\bresource\s*\{\s*([a-z0-9-]+)\s*\}")
_RE_RES_KV = re.compile(r"\bresource-(?:cost|restore)\s*:\s*([a-z0-9-]+)")

# palavras-chave de SELEÇÃO de magia (spell:pick{lista|escola|nivel}) — não são slugs.
# A forma canônica é cast{spell:pick{...}}; reportadas à parte, não como #REF!.
# seletores semânticos de spell: (não são slugs de TbMagia): a magia em contexto.
_SPELL_NONSLUG = {"pick", "lista", "truque", "escola", "ability", "nivel", "qualquer",
                  "any", "active", "picked", "spell-selection", "elemental",
                  "livro-de-rituais", "cantrip", "escolhido", "caminho-final-preparada", "school"}
_RE_MASTERY = re.compile(r"add-mastery\s*:\s*([a-z0-9-]+)")
_RE_OPCAO = re.compile(r"\bopcao\s*:\s*([a-z0-9-]+)")
_RE_BESTIARY = re.compile(r"bestiary\s*\{\s*([a-z0-9-]+)\s*\}")
_RE_CLASSE = re.compile(r"\bclasse\s*:\s*([a-z0-9-]+)")

_SRC_RE = re.compile(r"\b(classe|talento|raca|linhagem|essencia|bestiary|dominio)\s*:\s*([a-z0-9-]+)")


def _check_references(line, lib, data, locals_=frozenset()):
    if data is None:
        return []
    out = []
    # ability{nome, fonte:slug}
    for m in _RE_ABILITY.finditer(line):
        inner = m.group(1)
        name = inner.split(",")[0].strip()
        if not name or name.startswith("<"):
            continue
        nm = _slug(name)
        if nm in locals_:
            continue
        sm = _SRC_RE.search(inner)
        src_t, src_s = (sm.group(1), sm.group(2)) if sm else (None, None)
        # ability{X, talento:Y} aponta p/ sub-feature descrita no markdown do talento —
        # não é #REF! contra TbClassehabilidade (decisão da triagem 2026-06-18).
        if src_t in ("talento", "raca", "essencia", "linhagem", "bestiary", "dominio"):
            continue  # sub-feature de talento/domínio ou traço de criatura — não é #REF! de classe
        if nm not in data.ability_names:
            out.append(Diagnostic(ERROR, "ref-ability",
                       f"ability '{name}' não existe no banco (#REF!)", m.group(0)))
        elif (src_t == "classe" and src_s and nm in data.ability_classe_names
              and (src_s, nm) not in data.ability_by_classe):
            out.append(Diagnostic(INFO, "ref-ability-classe",
                       f"ability '{name}' existe, mas não na classe '{src_s}' (conferir fonte)", m.group(0)))
    # spell:slug
    for m in _RE_SPELL.finditer(line):
        slug = m.group(1)
        if slug in _SPELL_NONSLUG or line[m.end():m.end() + 1] in "{(":
            continue  # spell:pick{...} / spell:x(...) — não é slug solto
        if slug not in data.spell_slugs:
            out.append(Diagnostic(ERROR, "ref-spell",
                       f"spell '{slug}' não existe (TbMagia.slug) (#REF!)", m.group(0)))
    # resource{slug} / resource-cost|restore:slug
    for rx in (_RE_RES_BRACE, _RE_RES_KV):
        for m in rx.finditer(line):
            if line[m.end():m.end() + 1] == "{":
                continue  # resource-cost:ability{...} = ref aninhada, não slug
            if not data.resource_exists(m.group(1), lib):
                out.append(Diagnostic(ERROR, "ref-resource",
                           f"recurso '{m.group(1)}' não existe em TB_RecursoClasse nem é universal (#REF!)", m.group(0)))
    # add-mastery:slug  ('wielded' = herda a maestria da arma-base; nº = nº de maestrias)
    for m in _RE_MASTERY.finditer(line):
        v = m.group(1)
        if v not in data.masteries and v not in ("wielded",) and not v.isdigit():
            out.append(Diagnostic(ERROR, "ref-mastery",
                       f"maestria '{v}' não existe em TB_OpcaoJogo[Maestria de Arma] (#REF!)", m.group(0)))
    # opcao:tipo  ('item-magico'/'itens' = referência ao catálogo TbItemMagico, não TB_OpcaoJogo)
    for m in _RE_OPCAO.finditer(line):
        if m.group(1) not in data.opcao_tipos and m.group(1) not in ("item-magico", "itens"):
            out.append(Diagnostic(WARN, "ref-opcao",
                       f"tipo de opção '{m.group(1)}' não casa com TB_OpcaoJogo.Tipo", m.group(0)))
    # bestiary{slug}
    for m in _RE_BESTIARY.finditer(line):
        if data.bestiary_slugs and m.group(1) not in data.bestiary_slugs:
            out.append(Diagnostic(ERROR, "ref-bestiary",
                       f"criatura '{m.group(1)}' não existe no Bestiário (#REF!)", m.group(0)))
    # classe:slug (fora de ability{}, já coberto lá)
    for m in _RE_CLASSE.finditer(line):
        if m.group(1) not in data.classe_slugs:
            out.append(Diagnostic(WARN, "ref-classe",
                       f"classe '{m.group(1)}' não casa com TbClasse.slug", m.group(0)))
    return out


_CAT_RE = re.compile(r"\b(resist|immune|vuln|cond-immune|dmg-type|ignore-resist|convert-dmg-type|apply|cleanse|size|add-property|sense)\s*:\s*=?\s*([a-zà-ÿ][a-zà-ÿ-]*)")
_CAT_MAP = {
    "resist": "damage-type", "immune": "damage-type", "vuln": "damage-type",
    "dmg-type": "damage-type", "ignore-resist": "damage-type", "convert-dmg-type": "damage-type",
    "cond-immune": "condition", "apply": "condition", "cleanse": "condition",
    "size": "size", "add-property": "weapon-property", "sense": "sense-type",
}
_CAT_SPECIAL = {
    # selectors/keywords + alvos de imunidade que NÃO são tipos de dano mas valem
    # com resist:/immune: (imunidade a escola/efeito/magia, p/ ex.).
    "damage-type": {"all", "source", "last-damage-type", "weapon-type", "magical-effect",
                    "magical", "pick", "self", "allies", "elemento", "any", "dmg",
                    "read-thoughts", "adivinhacao", "magic-effect", "max-hp-reduction",
                    "non-magical-damage", "envelhecimento-magico", "trigger-dmg-type",
                    "elemento-ascendencia", "elixir-proprio", "dragao", "misseis-magicos",
                    # variáveis de ESCOLHA de essência (o tipo é definido pela escolha):
                    "alento", "alento-", "sangue", "vertente", "elemento", "item-alquimico"},
    "condition": {"pick", "magia", "reaction", "concentration", "active", "spell", "same-condition"},
    "size": set(),
    "weapon-property": set(),
    "sense-type": {"see-through-objects", "see-through", "see-through-fog"},
}


def _check_catalogs(line, lib, locals_=frozenset()):
    out = []
    for m in _CAT_RE.finditer(line):
        nxt = line[m.end():m.end() + 1]
        if nxt and nxt in "{(":
            continue  # apply:ability{...} / resist:match(...) = ref/função, não valor literal
        # (nxt vazio = token no fim da linha; '' in "{(" era True e pulava a validação)
        verb, val = m.group(1), m.group(2).lower()
        cat = _CAT_MAP[verb]
        valores = lib.catalogs.get(cat)
        if valores is None:           # catálogo aberto: não dá pra fechar
            continue
        if val in valores or val in _CAT_SPECIAL.get(cat, ()) or val in locals_:
            continue  # valor de catálogo, especial, ou estado local (define{})
        out.append(Diagnostic(WARN, "cat-valor",
                   f"'{val}' não está no catálogo {cat} (#NAME?)", m.group(0)))
    return out


_RE_MAGICO = re.compile(r"(attack\s*:\s*magico|\.magico)\b")


def _check_style(line, lib):
    out = []
    if _RE_MAGICO.search(line):
        out.append(Diagnostic(WARN, "padr-attack-magic",
                   "use 'attack:magic' (taxonomia de ataque é inglês), não 'magico'", "magico"))
    return out


# ───────────────────────── API pública ──────────────────────────────
def validate_tag_line(line, lib, data=None, locals_=frozenset()):
    diags = []
    if not isinstance(line, str) or not line.strip():
        return diags
    tokens = tokenize(line)

    bal = check_balance(tokens, line)
    for pos, msg in bal:
        diags.append(Diagnostic(ERROR, "desbalanceado", f"delimitador: {msg}", _frag(line, pos)))
    if bal:
        return diags  # fórmula quebrada: não adianta validar o resto

    for pos, ch in find_other(tokens):
        diags.append(Diagnostic(INFO, "char-inesperado", f"caractere inesperado '{ch}'", _frag(line, pos)))

    unknown = {}
    _walk_heads(build_tree(tokens), lib, unknown, locals_)
    for head, (count, kind) in sorted(unknown.items()):
        diags.append(Diagnostic(WARN, "verbo-desconhecido",
                     f"{kind} '{head}' não está na biblioteca (x{count})", head))

    diags += _check_references(line, lib, data, locals_)
    diags += _check_catalogs(line, lib, locals_)
    diags += _check_style(line, lib)
    return diags


def validate_tags_json(tags, lib, data=None):
    """tags = lista de strings (uma TbX.tags_json). Retorna [Diagnostic]."""
    out = []
    if not tags:
        return out
    if isinstance(tags, str):
        tags = [tags]
    locals_ = collect_locals(tags)
    for line in tags:
        out.extend(validate_tag_line(line, lib, data, locals_))
    return out


# ───────────────────────── índice do banco (#REF!) ──────────────────
class DataIndex:
    """Carrega do banco os conjuntos referenciáveis (golden rule §4)."""

    def __init__(self):
        self.ability_names = set()
        self.ability_by_classe = set()
        self.ability_classe_names = set()  # slugs que SÃO hab-de-classe (alguma classe)
        self.spell_slugs = set()
        self.classe_slugs = set()
        self.resources = set()
        self.masteries = set()
        self.opcao_tipos = set()
        self.bestiary_slugs = set()
        self.internal_pools = set()   # pools de fórmula/fixos declarados nas tags

    def resource_exists(self, slug, lib):
        if slug in self.resources or slug in lib.recursos_universais:
            return True
        if slug in self.internal_pools or slug in self.ability_names or slug == "uses":
            return True  # pool interno (define/max/mark), uso da própria habilidade, item, 'uses'=auto
        if slug in ("all", "spell-slot", "pact-slot", "spell-slots"):
            return True
        return bool(_NUMERIC.match(slug))  # '1','2'...'9' = nível de espaço

    @classmethod
    def build(cls):
        self = cls()

        def safe(fn):
            try:
                fn()
            except Exception as exc:        # modelo ausente/vazio: segue
                print(f"  [DataIndex] aviso: {exc}")

        def classes():
            from home.models import TbClasse
            for c in TbClasse.objects.all():
                self.classe_slugs.add(_slug(getattr(c, "slug", None) or c.nome))
        safe(classes)

        def abilities():
            from home.models import TbClassehabilidade
            for h in TbClassehabilidade.objects.select_related("id_classe").all():
                nm = _slug(h.nome)
                self.ability_names.add(nm)
                cl = getattr(h, "id_classe", None)
                if cl is not None:
                    cs = _slug(getattr(cl, "slug", None) or getattr(cl, "nome", "") or "")
                    if cs:
                        self.ability_by_classe.add((cs, nm))
        safe(abilities)

        def more_ability_sources():
            from home.models import TbTalento, TbTracoracial
            for t in TbTalento.objects.all():
                self.ability_names.add(_slug(t.nome))
            for t in TbTracoracial.objects.all():
                self.ability_names.add(_slug(t.nome))
        safe(more_ability_sources)

        def spells():
            from home.models import TbMagia
            for m in TbMagia.objects.all():
                self.spell_slugs.add(_slug(getattr(m, "slug", None) or m.nome))
        safe(spells)

        def resources():
            from home.models import TbRecursoclasse
            for r in TbRecursoclasse.objects.all():
                if r.nome:
                    self.resources.add(_slug(r.nome))
        safe(resources)

        def opcoes():
            from home.models import TbOpcaojogo
            for o in TbOpcaojogo.objects.all():
                self.opcao_tipos.add(_slug(o.tipo))
                # opções (segredos/manobras/etc.) podem ser referenciadas por ability{}
                self.ability_names.add(_slug(o.nome))
                if "maestria" in (o.tipo or "").lower():
                    self.masteries.add(_slug(o.nome.split("(")[0]))
        safe(opcoes)

        def bestiary():
            from home.models import TbBestiario
            for b in TbBestiario.objects.all():
                if getattr(b, "slug", None):
                    self.bestiary_slugs.add(_slug(b.slug))
        safe(bestiary)

        def pools():
            from home.models import TbClassehabilidade, TbTalento, TbOpcaojogo
            for Model in (TbClassehabilidade, TbTalento, TbOpcaojogo):
                for x in Model.objects.all():
                    for line in (x.tags_json or []):
                        if not isinstance(line, str):
                            continue
                        for rx in (_RE_DEFINE, _RE_POOL_DECL, _RE_MAX_DECL, _RE_MARK_DECL, _RE_EQUIPED):
                            self.internal_pools.update(m.group(1) for m in rx.finditer(line))
        safe(pools)

        # quais slugs são habilidade-DE-CLASSE (existem em alguma classe): distingue
        # de opções/talentos/traços, que entram em ability_names mas não têm classe —
        # logo ability{opcao, classe:X} não deve acusar "classe errada" (não tem classe).
        self.ability_classe_names = {a for (_, a) in self.ability_by_classe}

        return self
