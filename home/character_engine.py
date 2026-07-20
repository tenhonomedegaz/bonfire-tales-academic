# -*- coding: utf-8 -*-
"""Motor de derivação da ficha de personagem.

Recebe um TbPersonagem e deriva o estado mecânico (atributos base+bônus, nível,
proficiência, PV, CA ciente de armadura, ataques, features ativas, recursos e os
efeitos PASSIVOS das tags_json).

Fases:
- ESTRUTURAL: atributos (BASE point-buy + Σ bônus de TbPersonagemAtributoBonus),
  nível total, bônus de proficiência, PV pelo dado de vida (campo OU tag
  `hit_dice`), features por nível DA classe (subclasse no nível de `subclass_choices`),
  traços raciais, antecedente, talentos e recursos. Multiclasse: `classlvl` por
  feature.
- TAGS (apply_tags): resolve `match(<escolha>){…}`/`define{}` e aplica efeitos
  PASSIVOS (PV/CA/velocidade/resistências/imunidades/sentidos/salvaguardas/
  perícias/proficiências/ataques/recursos-de-tag/vantagens). Efeitos ativos
  (trigger/instant/while_active/action/cast) NÃO entram na ficha estática.

Lacunas de dado conhecidas viram avisos em `state['avisos']`.
"""

import ast
import math
import operator
import re
import unicodedata

from .item_mecanica import mecanica_de_tags, dano_display, propriedades_display

# (campo no modelo, sigla PT, rótulo)
ATRIBUTOS = [
    ('forca', 'FOR', 'Força'),
    ('destreza', 'DES', 'Destreza'),
    ('constituicao', 'CON', 'Constituição'),
    ('inteligencia', 'INT', 'Inteligência'),
    ('sabedoria', 'SAB', 'Sabedoria'),
    ('carisma', 'CAR', 'Carisma'),
]

_ATTR_EN = {'FOR': 'str', 'DES': 'dex', 'CON': 'con', 'INT': 'int', 'SAB': 'wis', 'CAR': 'cha'}
_EN_SIG = {v: k for k, v in _ATTR_EN.items()}

# token de salvaguarda -> código EN canônico. Aceita siglas PT-BR e EN no tag
# saves-prof{} (o Bardo escreve {des, car}; as demais classes usam {dex, cha}…).
_SAVE_TOKEN_EN = {
    'for': 'str', 'des': 'dex', 'con': 'con', 'int': 'int', 'sab': 'wis', 'car': 'cha',
    'str': 'str', 'dex': 'dex', 'wis': 'wis', 'cha': 'cha',
    'forca': 'str', 'destreza': 'dex', 'constituicao': 'con',
    'inteligencia': 'int', 'sabedoria': 'wis', 'carisma': 'cha',
}

# Grants padrao do antecedente. Cada antecedente pode sobrescrever via
# `background-grants{...}` em tags_json; este valor e fallback de compatibilidade.
GRANTS_ANTECEDENTE = {
    'asi': '+2/+1 (à escolha)', 'pericias': 2, 'idioma_fixo': 'Comum',
    'idiomas_ou_ferramentas': 2, 'po_inicial': 100, 'po_mundano_min': 50,
    'talento_origem': 1, 'habilidade': 1,
}

# 18 perícias: slug -> (nome PT, atributo padrão)
DEFAULT_BACKGROUND_GRANT_TAG = (
    'background-grants{asi:+2/+1, pericia:2, idioma-fixo:Comum, '
    'idioma-ou-ferramenta:2, po:100, po-mundano-min:50, talento-origem:1, '
    'habilidade:1, equip-gold-alt:150}'
)
DEFAULT_GRANTS_ANTECEDENTE = dict(GRANTS_ANTECEDENTE, equip_gold_alt=150)
GRANTS_ANTECEDENTE = DEFAULT_GRANTS_ANTECEDENTE

_SKILL_INFO = {
    'atletismo': ('Atletismo', 'FOR'),
    'acrobacia': ('Acrobacia', 'DES'), 'furtividade': ('Furtividade', 'DES'),
    'prestidigitacao': ('Prestidigitação', 'DES'),
    'arcanismo': ('Arcanismo', 'INT'), 'historia': ('História', 'INT'),
    'investigacao': ('Investigação', 'INT'), 'natureza': ('Natureza', 'INT'),
    'religiao': ('Religião', 'INT'),
    'adestrar-animais': ('Adestrar Animais', 'SAB'), 'intuicao': ('Intuição', 'SAB'),
    'medicina': ('Medicina', 'SAB'), 'percepcao': ('Percepção', 'SAB'),
    'sobrevivencia': ('Sobrevivência', 'SAB'),
    'enganacao': ('Enganação', 'CAR'), 'intimidacao': ('Intimidação', 'CAR'),
    'atuacao': ('Atuação', 'CAR'), 'persuasao': ('Persuasão', 'CAR'),
}


def _norm_skill_slug(s):
    """Normaliza um slug de perícia para a chave canônica de _SKILL_INFO.

    Referência de perícia em posição de slug é o ÚNICO lugar onde '-' é o
    separador (ex.: 'adestrar-animais'). Conteúdo escrito com '_' por engano
    (adestrar_animais) casaria None em _SKILL_INFO e a perícia seria descartada
    em silêncio — normalizar '_'→'-' antes de qualquer lookup blinda contra isso.
    """
    s = (s or '').strip().lower()
    return s.replace('_', '-') if s not in _SKILL_INFO else s

_ACTIVE_BLOCKS = ('while_active', 'while', 'instant', 'cast', 'aura', 'effects')
# `while:<cond>{...}` (condição de estado — só ATIVA enquanto a condição vale, ex.:
# `while:in_sunlight{dadv:attack}`, `while:frenesi{...}`, `while:in:ability{...}{...}`)
# é ativo/runtime, não estático. Convenção do projeto: cada `while:<cond>{...}` vive
# na PRÓPRIA linha de tag (sem verbo estático irmão), então o marcador dropa só a
# linha condicional — impede vazamento de dadv/sense/save permanentes (Pressão Solar/
# Brumas de Velmourn/Segredos Sybaris/Alento Primordial).
_ACTIVE_MARKERS = ('trigger=', 'instant{', 'while_active{', 'while{', 'while:', 'cast{', 'action=', 'on:')
# slugs-placeholder/indireção que NÃO devem virar tipo literal na ficha. Incluem os
# nomes de VARIÁVEL das sub-escolhas de essência (sangue/alento/energia/polo/elemento/
# vertente) e o resíduo 'match'/'pick': quando a escolha FOI feita, `escolhas.get(v)`
# resolve o valor real ANTES desta checagem (resist:sangue -> resist:frio); quando NÃO
# foi feita, o literal cai aqui e é suprimido — a ficha nunca mostra 'sangue'/'alento'/
# 'match' cru (RELATORIO_R1 item 9). Nenhum é tipo de dano real, então é seguro.
_PLACEHOLDERS = ('all', 'source', 'elemento', 'pick', 'match', 'vertente',
                 'sangue', 'alento', 'alento_2', 'alento_3', 'energia', 'polo')

# dot-path de escopo de ataque (item/Estilo de Luta) -> escopo interno do perfil.
# Genérico (registry, sem if-por-tipo): unarmed/unarmed_strike colapsam em desarmado;
# weapon = qualquer arma; melee/ranged (e as formas weapon_melee/weapon_ranged) filtram
# o bônus ao perfil corpo a corpo / à distância.
_ATK_SCOPE = {
    'unarmed_strike': 'unarmed-strike', 'unarmed': 'unarmed-strike',
    'weapon': 'weapon',
    'melee': 'weapon-melee', 'weapon_melee': 'weapon-melee',
    'ranged': 'weapon-ranged', 'weapon_ranged': 'weapon-ranged',
}

# subcategoria de TbItemMundano (categoria='arma') -> (rótulo de proficiência exigido,
# is_ranged). Usa DES no ataque quando à distância; a proficiência casa contra os
# rótulos legíveis de _PROF_TOKEN_LABEL ('Armas Simples'/'Armas Marciais'/'Armas de Fogo').
_WEAPON_CATEGORY = {
    'arma_simples': ('Armas Simples', False),
    'arma_simples_dist': ('Armas Simples', True),
    'arma_marcial': ('Armas Marciais', False),
    'arma_marcial_dist': ('Armas Marciais', True),
    'arma_fogo': ('Armas de Fogo', True),
}


def _slug(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def _tag_name(name):
    """Nome canonico de verbo/identificador da linguagem de tags (snake_case).

    Identificadores da linguagem sao snake_case APENAS; '-' e operador matematico
    (subtracao), nunca separador de identificador.
    """
    return _slug(name).replace('-', '_')


def _tag_verb_rx(name):
    parts = [_tag_name(p) for p in str(name or '').replace('-', '_').split('_') if p]
    return r'_'.join(re.escape(p) for p in parts)


def _tag_block(tag, *heads):
    """Corpo de `head{...}` (identificador em snake_case)."""
    s = str(tag or '').strip()
    for head in heads:
        m = re.match(r'^%s\s*\{(.*)\}\s*$' % _tag_verb_rx(head), s, re.I | re.S)
        if m:
            return m.group(1)
    return None


def _iter_tag_blocks(tag, head):
    s = str(tag or '')
    rx = re.compile(r'\b%s\s*\{' % _tag_verb_rx(head), re.I)
    pos = 0
    while True:
        m = rx.search(s, pos)
        if not m:
            return
        open_pos = m.end() - 1
        close_pos = _match_close(s, open_pos)
        if close_pos < 0:
            return
        yield s[open_pos + 1:close_pos]
        pos = close_pos + 1


def _tag_levels(tags_json, verb):
    for tag in (tags_json or []):
        body = _tag_block(tag, verb)
        if body:
            return {int(n) for n in re.findall(r'\d+', body)}
    return set()


def _subclass_min_level(classe):
    """Primeiro nivel em que a subclasse fica ativa, vindo de `subclass-choices`."""
    levels = _tag_levels(getattr(classe, 'tags_json', None), 'subclass-choices')
    if levels:
        return min(levels)
    try:
        from .models import TbClassehabilidade
        nivel = (TbClassehabilidade.objects
                 .filter(id_classe=classe, id_subclasse__isnull=False)
                 .order_by('niveladquirido')
                 .values_list('niveladquirido', flat=True)
                 .first())
        return int(nivel) if nivel is not None else None
    except Exception:
        return None


def _subclass_unlocked(personagem_classe, nivel=None):
    if not getattr(personagem_classe, 'id_subclasse_id', None):
        return False
    nivel = int(nivel if nivel is not None else (personagem_classe.nivel or 0))
    min_level = _subclass_min_level(personagem_classe.id_classe)
    return min_level is not None and nivel >= min_level


def _coerce_int(v, default=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


_BACKGROUND_GRANT_KEYS = {
    'asi': 'asi',
    'pericia': 'pericias',
    'pericias': 'pericias',
    'idioma-fixo': 'idioma_fixo',
    'idiomas-fixo': 'idioma_fixo',
    'idioma-ou-ferramenta': 'idiomas_ou_ferramentas',
    'idiomas-ou-ferramentas': 'idiomas_ou_ferramentas',
    'idioma-ferramenta': 'idiomas_ou_ferramentas',
    'idiomas-ferramentas': 'idiomas_ou_ferramentas',
    'po': 'po_inicial',
    'po-inicial': 'po_inicial',
    'po-mundano-min': 'po_mundano_min',
    'talento-origem': 'talento_origem',
    'habilidade': 'habilidade',
    'equip-gold-alt': 'equip_gold_alt',
    'equip-ouro-alt': 'equip_gold_alt',
    'equipamento-ouro': 'equip_gold_alt',
}


def _parse_background_grants(tags_json):
    grants = {}
    for tag in (tags_json or []):
        body = _tag_block(tag, 'background_grants')
        if body is None:
            continue
        for part in [p.strip() for p in body.split(',') if p.strip()]:
            if ':' not in part:
                continue
            key, value = [x.strip() for x in part.split(':', 1)]
            out_key = _BACKGROUND_GRANT_KEYS.get(_slug(key))
            if not out_key:
                continue
            grants[out_key] = value if out_key == 'asi' else _coerce_int(value, value)
    return grants


def background_grants(antecedente=None):
    grants = dict(DEFAULT_GRANTS_ANTECEDENTE)
    if antecedente is not None:
        grants.update(_parse_background_grants(getattr(antecedente, 'tags_json', None) or []))
    return grants


def background_asi_values(grants):
    m = re.search(r'\+?\s*(\d+)\s*/\s*\+?\s*(\d+)', str((grants or {}).get('asi') or ''))
    return (int(m.group(1)), int(m.group(2))) if m else (2, 1)


def modificador(valor):
    return (int(valor) - 10) // 2


# Token de proficiência (tags prof{}/multiclass-prof{} da classe) -> (categoria, rótulo legível).
_PROF_TOKEN_LABEL = {
    'armadura_leve': ('armadura', 'Leve'), 'armadura_media': ('armadura', 'Média'),
    'armadura_pesada': ('armadura', 'Pesada'), 'escudos': ('armadura', 'Escudos'),
    'armas_simples': ('arma', 'Armas Simples'), 'armas_marciais': ('arma', 'Armas Marciais'),
    'armas_fogo': ('arma', 'Armas de Fogo'),
    'armas_marciais_acuidade_ou_leves': ('arma', 'Armas Marciais com Acuidade ou Leves'),
    'armas_marciais_leves': ('arma', 'Armas Marciais Leves'),
    'ferramentas_de_ladrao': ('ferramenta', 'Ferramentas de Ladr\u00e3o'),
    'ferramentas_de_funileiro': ('ferramenta', 'Ferramentas de Funileiro'),
}


def _proficiencias_classe(classes):
    """Proficiências de arma/armadura: PLENAS da classe PRINCIPAL (tag `prof{...}`) +
    subconjunto de MULTICLASSE das demais classes (tag `multiclass-prof{...}`), em rótulos
    legíveis. A regra de save (só da principal) é a mesma — ver _saves."""
    principal = _classe_principal(classes)

    def _toks(tags, key):
        out = []
        for t in (tags or []):
            body = _tag_block(t, key)
            if body is not None:
                out += [x.strip() for x in body.split(',') if x.strip()]
        return out

    c_arm, c_wpn, c_tool, mc_arm, mc_wpn, mc_tool = [], [], [], [], [], []
    for c in classes:
        tags = getattr(c.id_classe, 'tags_json', None) or []
        primaria = bool(principal) and c.id_classe_id == principal.id_classe_id
        alvo_arm, alvo_wpn, alvo_tool = (c_arm, c_wpn, c_tool) if primaria else (mc_arm, mc_wpn, mc_tool)
        for tk in _toks(tags, 'prof' if primaria else 'multiclass-prof'):
            lab = _PROF_TOKEN_LABEL.get(tk)
            if lab:
                {'armadura': alvo_arm, 'arma': alvo_wpn, 'ferramenta': alvo_tool}[lab[0]].append(lab[1])

    def _dedup(seq, excl=()):
        seen, out = set(excl), []
        for x in seq:
            if x not in seen:
                seen.add(x); out.append(x)
        return out
    return {
        'classe_armaduras': _dedup(c_arm), 'classe_armas': _dedup(c_wpn),
        'classe_ferramentas': _dedup(c_tool),
        'multiclasse_armaduras': _dedup(mc_arm, excl=c_arm), 'multiclasse_armas': _dedup(mc_wpn, excl=c_wpn),
        'multiclasse_ferramentas': _dedup(mc_tool, excl=c_tool),
    }


def bonus_proficiencia(nivel_total):
    try:
        from django.conf import settings
        tabela = getattr(settings, 'BONFIRE_PROFICIENCY_BY_LEVEL', None)
    except Exception:
        tabela = None
    if isinstance(tabela, dict):
        nivel = max(1, int(nivel_total))
        chaves = sorted(int(k) for k in tabela if int(k) <= nivel)
        if chaves:
            return int(tabela.get(chaves[-1], tabela.get(str(chaves[-1]))))
    elif isinstance(tabela, (list, tuple)):
        nivel = max(1, int(nivel_total))
        for item in sorted(tabela, key=lambda x: int(x[0]), reverse=True):
            if nivel >= int(item[0]):
                return int(item[1])
    return 2 + (max(1, int(nivel_total)) - 1) // 4


# ───────────────── Progressão por aventuras (tabelas Bonfire) ─────────────────
# (mín de aventuras, nível). 21 = Epic Boon (160), 22 = Lenda (200).
_AVENTURAS_NIVEL = [(0, 1), (1, 2), (3, 3), (6, 4), (9, 5), (13, 6), (17, 7), (22, 8),
                    (28, 9), (35, 10), (42, 11), (50, 12), (59, 13), (69, 14), (79, 15),
                    (90, 16), (102, 17), (114, 18), (127, 19), (140, 20), (160, 21), (200, 22)]
_RANK_FAIXA = [(1, 4, 'Obsidiana'), (5, 8, 'Ametista'), (9, 12, 'Topázio'), (13, 16, 'Esmeralda'),
               (17, 19, 'Âmbar'), (20, 20, 'Rubi'), (21, 21, 'Diamante'), (22, 22, 'Lenda')]
_RANK_OURO = {'Obsidiana': 120, 'Ametista': 250, 'Topázio': 400, 'Esmeralda': 650,
              'Âmbar': 800, 'Rubi': 1000, 'Diamante': 1200, 'Lenda': 1200}


def nivel_por_aventuras(n):
    """Nº de aventuras → nível (1..20; 21 = Epic Boon; 22 = Lenda)."""
    nivel = 1
    for minimo, nv in _AVENTURAS_NIVEL:
        if int(n or 0) >= minimo:
            nivel = nv
        else:
            break
    return nivel


def aventuras_para_nivel(nivel):
    """Mín de aventuras p/ atingir um nível (p/ backfill dos personagens existentes)."""
    melhor = 0
    for minimo, nv in _AVENTURAS_NIVEL:
        if nv <= int(nivel or 1):
            melhor = minimo
    return melhor


def rank_por_nivel(nivel):
    for lo, hi, nome in _RANK_FAIXA:
        if lo <= int(nivel) <= hi:
            return nome
    return 'Obsidiana'


def nivel_label(nivel):
    return {21: 'Epic Boon', 22: 'Lenda'}.get(int(nivel), str(nivel))


def ouro_por_aventura(nivel):
    """Ouro (PO) por aventura no rank do nível dado (tabela 2)."""
    return _RANK_OURO.get(rank_por_nivel(nivel), 0)


def ouro_de_progressao(n_aventuras):
    """Ouro (PO) ACUMULADO após `n_aventuras` jogadas — função PURA/testável.

    Regra SEQUENCIAL do PO: a k-ésima aventura paga a recompensa do rank do NÍVEL
    que o personagem detém AO JOGÁ-LA (= nível correspondente a k-1 aventuras já
    completas). Ao cruzar um limiar de rank no meio de uma missão múltipla, as
    aventuras anteriores ao cruzamento pagam o rank antigo e as seguintes o novo.

    O ouro de UM intervalo (base → base+n) é a diferença acumulada:
        ouro_de_progressao(base + n) - ouro_de_progressao(base)
    """
    n = max(0, int(n_aventuras or 0))
    return sum(ouro_por_aventura(nivel_por_aventuras(k)) for k in range(n))


def braseiros_por_aventura(nivel):
    """Braseiros por aventura = BP do personagem (2/3/4/5/6 por rank)."""
    return bonus_proficiencia(min(int(nivel), 20))


def _dado_de_vida(texto):
    if not texto:
        return None
    m = re.search(r'd\s*(\d+)', str(texto))
    return int(m.group(1)) if m else None


def _hit_dice_from_tag(classe):
    for tag in (getattr(classe, 'tags_json', None) or []):
        m = re.search(r'hit_dice:\s*\d*d(\d+)', str(tag))
        if m:
            return int(m.group(1))
    return None


def _dado_de_vida_classe(classe):
    return _dado_de_vida(getattr(classe, 'dado_vida', None)) or _hit_dice_from_tag(classe)


def _classe_principal(classes):
    if not classes:
        return None
    for c in classes:
        if getattr(c, 'principal', False):
            return c
    return classes[0]


def _calcular_pv(personagem, classes, con_mod, avisos):
    principal = _classe_principal(classes)
    total, faltou = 0, False
    for c in classes:
        die = _dado_de_vida_classe(c.id_classe)
        if die is None:
            faltou = True
            avisos.append(f"Dado de vida não cadastrado em '{c.id_classe.nome}' — PV parcial.")
            continue
        for nivel_idx in range(int(c.nivel or 0)):
            primeiro = (c is principal and nivel_idx == 0)
            total += die if primeiro else (die // 2 + 1)
            total += con_mod
    return {'valor': total, 'completo': not faltou}


# ───────────────────────── features (com classlvl) ──────────────────────
def _features_de_classe(classes):
    from .models import TbClassehabilidade
    out = []
    for c in classes:
        nivel = int(c.nivel or 0)
        for h in TbClassehabilidade.objects.filter(
                id_classe=c.id_classe, id_subclasse__isnull=True,
                niveladquirido__lte=nivel).order_by('niveladquirido', 'nome'):
            out.append(('classe', c.id_classe.nome, h, nivel))
        if _subclass_unlocked(c, nivel):
            for h in TbClassehabilidade.objects.filter(
                    id_subclasse=c.id_subclasse, niveladquirido__lte=nivel).order_by('niveladquirido', 'nome'):
                out.append(('subclasse', c.id_subclasse.nome, h, nivel))
    return out


def _tracos_raciais(personagem):
    from .models import TbTracoracial
    out = []
    if not personagem.id_raca_id:
        return out
    for t in TbTracoracial.objects.filter(id_raca=personagem.id_raca, talento_racial=False,
                                           id_linhagem__isnull=True, id_essencia__isnull=True):
        out.append(('raca', personagem.id_raca.nome, t, None))
    if personagem.id_linhagem_id:
        for t in TbTracoracial.objects.filter(id_linhagem=personagem.id_linhagem, talento_racial=False):
            out.append(('linhagem', personagem.id_linhagem.nome, t, None))
    if personagem.id_essencia_id:
        for t in TbTracoracial.objects.filter(id_essencia=personagem.id_essencia, talento_racial=False):
            out.append(('essencia', personagem.id_essencia.nome, t, None))
    return out


def _antecedente(personagem):
    """Antecedente como fonte de feature (a 'habilidade do antecedente' = suas
    tags_json), em paralelo a _tracos_raciais."""
    if not personagem.id_antecedente_id:
        return []
    a = personagem.id_antecedente
    return [('antecedente', a.nome, a, None)]


def _talentos(personagem):
    from .models import TbTracoracial
    from django.db.models import Q
    out = []
    for pt in personagem.talentos.select_related('id_talento').all():
        if pt.id_talento_id:
            out.append(('talento', pt.categoria or 'talento', pt.id_talento, None))
        else:
            # Talento racial salvo só por nome: resolve pela raça, linhagem (sub-raça)
            # OU essência do personagem; cai num fallback global por nome se preciso.
            cond = Q()
            if personagem.id_raca_id:
                cond |= Q(id_raca=personagem.id_raca_id)
            if getattr(personagem, 'id_linhagem_id', None):
                cond |= Q(id_linhagem=personagem.id_linhagem_id)
            if getattr(personagem, 'id_essencia_id', None):
                cond |= Q(id_essencia=personagem.id_essencia_id)
            tr = TbTracoracial.objects.filter(cond, nome=pt.nome).first() if cond else None
            if tr is None:
                tr = TbTracoracial.objects.filter(nome=pt.nome, talento_racial=True).first()
            if tr:
                out.append(('talento-racial', tr.nome, tr, None))
    return out


_TALENT_ATTR_FIELDS = {
    'FOR': 'atrib_forca',
    'DES': 'atrib_destreza',
    'CON': 'atrib_constituicao',
    'INT': 'atrib_inteligencia',
    'SAB': 'atrib_sabedoria',
    'CAR': 'atrib_carisma',
}


def _parse_talent_attr_details(texto):
    m = re.search(r'(?:asi_attr|talent_attr)\s*:\s*(FOR|DES|CON|INT|SAB|CAR)', str(texto or ''), re.I)
    return m.group(1).upper() if m else None


def _talent_attr_map(personagem):
    out = {}
    if personagem is None:
        return out
    for pt in personagem.talentos.select_related('id_talento').all():
        sig = _parse_talent_attr_details(pt.detalhes)
        if not sig:
            continue
        if pt.id_talento_id:
            out[('id', pt.id_talento_id)] = sig
            out[('slug', getattr(pt.id_talento, 'slug', ''))] = sig
        out[('nome', _slug(pt.nome))] = sig
    return out


def _feature_talent_attr_sig(obj, attr_map):
    if not attr_map or obj is None:
        return None
    obj_id = getattr(obj, 'id_talento', None)
    if obj_id and ('id', obj_id) in attr_map:
        return attr_map[('id', obj_id)]
    slug = getattr(obj, 'slug', '')
    if slug and ('slug', slug) in attr_map:
        return attr_map[('slug', slug)]
    nome = getattr(obj, 'nome', '')
    return attr_map.get(('nome', _slug(nome)))


RESOURCE_TIPO_TABLE_ONLY = 'table-only'
RESOURCE_TIPO_CONSUMABLE = 'consumable'
RESOURCE_TIPO_CHOICE = 'choice'
RESOURCE_TIPOS = (RESOURCE_TIPO_TABLE_ONLY, RESOURCE_TIPO_CONSUMABLE, RESOURCE_TIPO_CHOICE)


def _resource_tipo(r):
    tipo = getattr(r, 'tipo_efetivo', None)
    if tipo:
        return tipo
    tipo = getattr(r, 'tipo', None)
    if tipo in RESOURCE_TIPOS:
        return tipo
    if getattr(r, 'reset', None):
        return RESOURCE_TIPO_CONSUMABLE
    return RESOURCE_TIPO_TABLE_ONLY


# Total de recurso por FÓRMULA (decisão 9: descrição prevalece). Quando o valor-do-nível
# é uma fórmula de progressão (pb/lvl/classlvl), o motor a AVALIA em vez de usar uma tabela
# fixa; PB usa o nível TOTAL do personagem (multiclasse-safe). Valores numéricos/dados/
# distância ('2','+3','d6','10ft') passam intactos pelo fast-path.
_RES_FORMULA_RE = re.compile(r'(?<![a-z0-9_])(pb|classlvl|lvl)(?![a-z0-9_])')


def _pb_from_nivel(n):
    return 2 + (max(int(n or 1), 1) - 1) // 4


def _resource_value_at(r, nivel, total_nivel=None):
    vj = r.valores_json or {}
    val = None
    if vj:
        niveis = sorted(int(k) for k in vj if int(k) <= nivel)
        if niveis:
            val = vj[str(niveis[-1])]
    if val is None and r.nivel is not None and r.nivel <= nivel:
        val = r.valor
    if val is None:
        return None
    s = str(val).strip()
    if _RES_FORMULA_RE.search(s):
        tn = int(total_nivel) if total_nivel is not None else int(nivel)
        ev = _eval_formula(s, {'lvl': tn, 'classlvl': int(nivel), 'pb': _pb_from_nivel(tn)})
        if ev is not None:
            return str(int(ev)) if float(ev).is_integer() else str(ev)
    return val


def _recursos(classes):
    """Recursos de CLASSE (TbRecursoclasse). Ignora placeholders '-'/vazio/0."""
    from .models import TbRecursoclasse
    from django.db.models import Q
    recursos = {}
    total_nivel = sum(int(c.nivel or 0) for c in classes)

    def _vazio(v):
        return v is None or str(v).strip() in ('', '-', '0')

    for c in classes:
        nivel = int(c.nivel or 0)
        filtro = Q(id_classe=c.id_classe, id_subclasse__isnull=True)
        if _subclass_unlocked(c, nivel):
            filtro |= Q(id_subclasse=c.id_subclasse)
        legado = {}
        for r in TbRecursoclasse.objects.filter(filtro):
            _rs = _slug(r.nome)
            if 'bonus' in _rs and 'proficiencia' in _rs:
                continue  # PB é calculado pelo NÍVEL TOTAL do personagem, não é recurso de classe
            chave = f'{c.id_classe.nome}: {r.nome}'
            vj = r.valores_json or {}
            if vj:
                val = _resource_value_at(r, nivel, total_nivel)
                if not _vazio(val):
                    recursos[chave] = val
            elif r.nivel is not None and r.nivel <= nivel and not _vazio(r.valor):
                if r.nome not in legado or r.nivel > legado[r.nome][0]:
                    legado[r.nome] = (r.nivel, r.valor)
        for nome, (_lv, val) in legado.items():
            recursos[f'{c.id_classe.nome}: {nome}'] = val
    return recursos


def _recursos_por_tipo(classes):
    from .models import TbRecursoclasse
    from django.db.models import Q
    out = {tipo: [] for tipo in RESOURCE_TIPOS}
    total_nivel = sum(int(c.nivel or 0) for c in classes)

    def _vazio(v):
        return v is None or str(v).strip() in ('', '-', '0')

    seen = set()
    for c in classes:
        nivel = int(c.nivel or 0)
        filtro = Q(id_classe=c.id_classe, id_subclasse__isnull=True)
        if _subclass_unlocked(c, nivel):
            filtro |= Q(id_subclasse=c.id_subclasse)
        for r in TbRecursoclasse.objects.filter(filtro):
            _rs = _slug(r.nome)
            if 'bonus' in _rs and 'proficiencia' in _rs:
                continue
            val = _resource_value_at(r, nivel, total_nivel)
            if _vazio(val):
                continue
            key = (c.id_classe_id, r.id_subclasse_id, r.slug or r.nome)
            if key in seen:
                continue
            seen.add(key)
            tipo = _resource_tipo(r)
            out.setdefault(tipo, []).append({
                'slug': r.slug,
                'nome': r.nome,
                'classe': c.id_classe.nome,
                'subclasse': c.id_subclasse.nome if r.id_subclasse_id and c.id_subclasse_id else None,
                'valor': val,
                'tipo': tipo,
                'reset': r.reset or '',
            })
    return out


def _resource_max_at(r, nivel, total_nivel=None):
    """Máximo NUMÉRICO de um TbRecursoclasse no nível dado (valores_json ou valor). None se não-numérico."""
    val = _resource_value_at(r, nivel, total_nivel)
    try:
        return int(str(val).strip())
    except (ValueError, TypeError, AttributeError):
        m = re.match(r'^\s*([+-]?\d+)\s*(?:$|\(|\[)', str(val or ''))
        return int(m.group(1)) if m else None


def _recursos_consumiveis(personagem, classes):
    """Recursos CONSUMIVEIS (TbRecursoclasse tipo=consumable) com maximo numerico,
    mesclados com o uso atual (TbPersonagemRecurso). Para o tracker usar/recuperar da ficha."""
    from .models import TbRecursoclasse
    from django.db.models import Q
    if personagem is None:
        return []
    atuais = {pr.nome: pr for pr in personagem.recursos.all()}
    out, seen = [], set()
    total_nivel = sum(int(c.nivel or 0) for c in classes)
    for c in classes:
        nivel = int(c.nivel or 0)
        filtro = Q(id_classe=c.id_classe, id_subclasse__isnull=True)
        if _subclass_unlocked(c, nivel):
            filtro |= Q(id_subclasse=c.id_subclasse)
        for r in TbRecursoclasse.objects.filter(filtro):
            if _resource_tipo(r) != RESOURCE_TIPO_CONSUMABLE:
                continue
            mx = _resource_max_at(r, nivel, total_nivel)
            if mx is None or mx <= 0 or r.nome in seen:
                continue
            seen.add(r.nome)
            pr = atuais.get(r.nome)
            atual = min(pr.atual, mx) if pr else mx
            out.append({'slug': r.slug, 'nome': r.nome, 'classe': c.id_classe.nome,
                        'maximo': mx, 'atual': atual, 'reset': r.reset or 'manual'})
    return out


def _maestrias_armas(personagem):
    """Maestria de Arma = escolha de ARMA, não de maestria abstrata. Cada slot
    (TbPersonagemEscolha tipo='maestria', valor=slug/nome da arma) dá acesso a
    TODAS as maestrias daquela arma; no ataque o jogador usa 1. Retorna a lista de
    armas escolhidas com suas maestrias resolvidas (nome + efeito de TbOpcaojogo)."""
    from .models import TbItemMundano, TbOpcaojogo
    if personagem is None:
        return []
    picks = list(personagem.escolhas.filter(tipo='maestria').order_by('slot'))
    if not picks:
        return []
    mast = {o.slug: o for o in TbOpcaojogo.objects.filter(tipo='Maestria de Arma')}
    out = []
    for e in picks:
        val = (e.valor or '').strip()
        arma = (TbItemMundano.objects.filter(categoria='arma', slug=val).first()
                or TbItemMundano.objects.filter(categoria='arma', slug='arma-%s' % _slug(val)).first()
                or TbItemMundano.objects.filter(categoria='arma', nome__iexact=val).first())
        if not arma:
            out.append({'arma': val, 'encontrada': False, 'maestrias': []})
            continue
        mslugs = []
        for t in (arma.tags_json or []):
            m = re.search(r'maestrias\{([^}]*)\}', str(t))
            if m:
                mslugs = [x.strip() for x in m.group(1).split(',') if x.strip()]
        maestrias = [{'slug': s, 'nome': mast[s].nome if s in mast else s,
                      'efeito': (mast[s].descricao if s in mast else '') or ''} for s in mslugs]
        _mec = mecanica_de_tags(arma.tags_json, arma.subcategoria)
        out.append({'arma': arma.nome, 'slug': arma.slug, 'encontrada': True,
                    'dano': dano_display(_mec), 'propriedades': propriedades_display(_mec),
                    'maestrias': maestrias})
    return out


def _item_consumivel_meta(item, magico=None):
    """Retorna metadados de consumo para itens rastreados por quantidade.

    O caminho principal vem do catalogo estruturado de item magico (slot/tipo);
    tags explicitas permitem novos consumiveis sem mexer na ficha.
    """
    magico = magico if magico is not None else getattr(item, 'id_item_magico', None)
    tags = [str(t).lower() for t in (getattr(magico, 'tags_json', None) or [])]
    slot = (getattr(magico, 'slot', '') or '').strip().lower()
    tipo = _slug(getattr(magico, 'tipo', '') or '')
    explicit = any(('consumable' in t or 'consumivel' in t or 'consume:item' in t) for t in tags)
    catalog = bool(magico and (slot in {'pocao', 'pergaminho'} or tipo in {'pocao', 'pergaminho'}))
    return {
        'consumivel': bool(explicit or catalog),
        'consumivel_tipo': slot or tipo,
    }


def _inventario(personagem):
    """Itens do personagem (TbPersonagemItem) com estado de equipado. Item POSSUÍDO mas
    NÃO equipado não concede benefícios (armadura guardada = sem CA; idem itens mágicos)."""
    if personagem is None:
        return []
    out = []
    for it in personagem.inventario.select_related('id_item_magico').all().order_by('-equipado', 'nome'):
        magico = it.id_item_magico
        cons = _item_consumivel_meta(it, magico)
        _mec_inv = mecanica_de_tags(it.tags_json)
        out.append({'id': it.id, 'nome': it.nome, 'qtd': it.qtd, 'custo': it.custo, 'peso': it.peso,
                    'equipado': bool(it.equipado), 'tipo_equip': _mec_inv['tipo_equip'],
                    'pode_equipar': bool(_mec_inv['tipo_equip']) or bool(magico),
                    'magico': bool(magico),
                    'raridade': magico.get_raridade_display() if magico else None,
                    'requer_sintonizacao': bool(magico and magico.requer_sintonizacao),
                    'sintonizado': bool(it.sintonizado),
                    'tem_efeito': bool(magico and (magico.tags_json or [])),
                    'consumivel': cons['consumivel'],
                    'consumivel_tipo': cons['consumivel_tipo']})
    return out


def _features_de_itens(personagem):
    """Itens mágicos EQUIPADOS (e, se exigirem, SINTONIZADOS) viram features para o
    apply_tags. Item guardado/não-sintonizado não concede efeito."""
    if personagem is None:
        return []
    feats = []
    for it in personagem.inventario.select_related('id_item_magico').all():
        magico = it.id_item_magico
        if not magico or not it.equipado:
            continue
        if magico.requer_sintonizacao and not it.sintonizado:
            continue
        if magico.tags_json or []:
            feats.append(('item', it.nome, magico, None))
    return feats


def _features_de_opcoes(personagem):
    """Opções de jogo ESCOLHIDAS (TbPersonagemEscolha → TbOpcaojogo) viram features p/
    aplicar os efeitos PASSIVOS da opção (ex.: Estilo de Luta dá bônus passivo). Liga pelo
    `id_opcao` ou, em escolhas antigas sem vínculo, pelo `valor`=slug. classlvl=None."""
    if personagem is None:
        return []
    from .models import TbOpcaojogo
    feats, por_slug = [], None
    for e in personagem.escolhas.select_related('id_opcao').all():
        op = e.id_opcao
        if op is None and e.valor:
            if por_slug is None:
                por_slug = {o.slug: o for o in TbOpcaojogo.objects.all()}
            op = por_slug.get(e.valor)
        if op is not None and (op.tags_json or []):
            feats.append(('opcao', op.nome, op, None))
    return feats


def _magias_personagem(personagem):
    """Magias conhecidas/preparadas (TbPersonagemMagia) agrupadas por nível, p/ a ficha."""
    if personagem is None:
        return []
    out = []
    for mg in personagem.magias.select_related('id_magia').order_by('nivel', 'nome'):
        out.append({'nivel': mg.nivel, 'nome': mg.nome,
                    'escola': getattr(mg.id_magia, 'escola', '') or '', 'preparada': mg.preparada})
    return out


def _parse_spell_selection(resolved):
    """De uma tag `spell-selection:[a, b]{truque|nivel:N, qtd:K, …}` JÁ resolvida
    (match(vertente) substituído), extrai (slugs, nivel_de_magia, qtd)."""
    mlist = re.search(r'\[([^\]]*)\]', resolved)
    slugs = [s.strip() for s in mlist.group(1).split(',') if s.strip()] if mlist else []
    mbody = re.search(r'\]\s*\{([^}]*)\}', resolved)
    body = mbody.group(1) if mbody else ''
    if re.search(r'\btruque\b', body):
        nivel = 0
    else:
        mn = re.search(r'nivel\s*:\s*(\d+)', body)
        nivel = int(mn.group(1)) if mn else None
    mq = re.search(r'qtd\s*:\s*(\d+)', body)
    qtd = int(mq.group(1)) if mq else len(slugs)
    return slugs, nivel, qtd


_CAST_BLOCK_RE = re.compile(r'cast\{((?:[^{}]|\{[^{}]*\})*)\}')
# escopo de spell-selection que é uma CLASSE → nome como aparece em TbMagia.classes
def _spell_class_scope_map():
    """Escopos de magia vindos das classes cadastradas, sem mapa fixo no motor."""
    try:
        from .models import TbClasse
        out = {}
        for classe in TbClasse.objects.all():
            nome = classe.nome
            for key in (classe.slug, classe.nome, _slug(classe.slug), _slug(classe.nome)):
                if key:
                    out[str(key).strip().lower()] = nome
        return out
    except Exception:
        return {}


def spell_scope_names(scopes):
    scope_map = _spell_class_scope_map()
    out = []
    for scope in scopes:
        nome = scope_map.get(str(scope).strip().lower())
        if nome and nome not in out:
            out.append(nome)
    return out


def _qtd_de(body, nivel_total):
    """qtd da escolha: `qtd:K`, `qtd:{classlvl=L:n,…}` (soma cumulativa até o nível) ou
    `pick:K`. None se não houver."""
    m = re.search(r'qtd\s*:\s*\{([^}]*)\}', body)
    if m:
        return sum(int(v) for lv, v in re.findall(r'classlvl\s*=\s*(\d+)\s*:\s*(\d+)', m.group(1))
                   if int(lv) <= nivel_total) or None
    m = re.search(r'qtd\s*:\s*(\d+)', body) or re.search(r'\bpick\s*:\s*(\d+)', body)
    return int(m.group(1)) if m else None


def _nivel_filtro(body):
    """Nível de magia exigido pelo body: `truque`→0; `nivel:N`/`ciclo:N`→N; senão None."""
    if re.search(r'\btruque\b', body):
        return 0
    m = re.search(r'(?:nivel|ciclo)\s*:\s*(\d+)', body)
    return int(m.group(1)) if m else None


def _rotulo_escolha(nivel, qtd, classes=None, escola=None):
    nv = 'truque(s)' if nivel == 0 else (('magia(s) de %sº ciclo' % nivel) if nivel else 'magia(s)')
    extra = ''
    if escola:
        extra += ' de %s' % escola.title()
    if classes:
        extra += ' de %s' % '/'.join(classes)
    return '%d %s%s' % (qtd, nv, extra)


def _iter_spell_selections(s):
    """Gera (scope, scope_extra, body) de cada `spell-selection:` da tag, casando chaves.
    scope = identificador após o ':'; scope_extra = chaves do PRÓPRIO escopo (ex.:
    pick{lista:{…}}); body = o `{…}`/`(…)` seguinte (filtros/qtd)."""
    out = []
    for m in re.finditer(r'spell_selection:', s):
        i = m.end()
        mt = re.match(r'[a-z0-9_-]+', s[i:])
        if not mt:
            continue
        scope = mt.group(0)
        j = i + mt.end()
        scope_extra = ''
        # só `pick` tem chave de PARÂMETRO própria (pick{lista:…}) antes do body;
        # p/ os demais escopos a 1ª chave já é o body.
        if scope == 'pick' and j < len(s) and s[j] == '{':
            k = _match_close(s, j)
            if k > 0:
                scope_extra, j = s[j + 1:k], k + 1
        while j < len(s) and s[j] in ' \t':
            j += 1
        body = ''
        if j < len(s) and s[j] == '{':
            k = _match_close(s, j)
            if k > 0:
                body = s[j + 1:k]
        elif j < len(s) and s[j] == '(':
            depth, k = 0, j
            while k < len(s):
                if s[k] == '(':
                    depth += 1
                elif s[k] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            body = s[j + 1:k]
        out.append((scope, scope_extra, body))
    return out


def _grants_de_tag(tag, escolhas, catalog, nivel_total, is_spellcaster=False):
    """(fixas, escolha) de UMA tag. fixas=[(slug,nivel)] (magia específica garantida);
    escolha=None | dict normalizado:
      {'opcoes':[slug], 'qtd':K, 'rotulo':str}                 (lista concreta de opções)
      {'pool':{'classes':[Nome], 'nivel':N|None, 'escola':E|None}, 'qtd':K, 'rotulo':str}

    Concede: `cast{… spell:X … always-prepared}` (Marcas), `spell-selection:match(var){…}`
    (vertente/veste-lunar…), `spell-selection:<slug>{… always-prepared}` (magia única),
    `spell:X` concreto, e as LISTAS DE DECRETO `any{ a, b, … }, fora-do-limite` — adicionadas
    como conhecidas/sempre-preparadas se o personagem for conjurador (gate requires:spellcasting,
    `is_spellcaster`). Escolhas: `spell-selection:<classe>{… qtd:K …}` (pool de classe),
    `pick{lista:{a|b}}{… qtd:K}` (união), e a Marca Planar (`any{spell:pick{… match(pick:…)}}`).
    IGNORA cast ativo e `spell:pick{…}` não resolvido. Respeita `requires:lvl{N}`."""
    s = str(tag)
    m = re.search(r'requires:lvl\{(\d+)\}', s)
    if m and nivel_total < int(m.group(1)):
        return [], None
    # match(var){…} — concessão por escolha já feita (vertente, veste-lunar…)
    if re.search(r'spell_selection:match\(', s):
        slugs, nivel, qtd = _parse_spell_selection(_resolve_match(s, escolhas))
        slugs = [sl for sl in slugs if sl in catalog]
        if not slugs or nivel is None:
            return [], None
        if qtd >= len(slugs):
            return [(sl, nivel) for sl in slugs], None
        return [], {'opcoes': slugs, 'qtd': qtd, 'rotulo': _rotulo_escolha(nivel, qtd)}
    fixas, escolha = [], None
    for cm in _CAST_BLOCK_RE.finditer(s):
        blk = cm.group(1)
        if re.search(r'always_prepared', blk):
            for sm in re.finditer(r'spell:([a-z0-9-]+)', blk):
                if sm.group(1) in catalog:
                    fixas.append((sm.group(1), catalog[sm.group(1)]))
    s_wo = _CAST_BLOCK_RE.sub('', s)
    for scope, scope_extra, body in _iter_spell_selections(s_wo):
        full = scope_extra + ' ' + body
        # (a) escopo é uma MAGIA concreta sempre-preparada
        if scope in catalog:
            if re.search(r'always_prepared', body):
                fixas.append((scope, catalog[scope]))
            for sm in re.finditer(r'spell:([a-z0-9-]+)', full):   # magia-conhecida(spell:X)
                if sm.group(1) in catalog:
                    fixas.append((sm.group(1), catalog[sm.group(1)]))
            continue
        # (b) spell:X concreto (any{spell:X}, paladino{spell:X}) sem pick → grant
        concretos = [sm.group(1) for sm in re.finditer(r'spell:([a-z0-9-]+)', full)
                     if sm.group(1) in catalog]
        if concretos and 'pick' not in full:
            for sl in concretos:
                fixas.append((sl, catalog[sl]))
            continue
        # (c) Marca Planar: any{spell:pick{lista:cantrip, match(pick:<var>){…}}}
        if scope == 'any' and 'match(pick:' in full:
            mv = re.search(r'match\(pick:([a-z0-9_-]+)\)\s*\{', full)
            if mv and escolhas.get(mv.group(1)):
                bo = full.find('{', mv.end() - 1)
                ramo = _ramo(full[bo + 1:_match_close(full, bo)], escolhas[mv.group(1)])
                if ramo and ramo is not _NO_BRANCH:
                    opt = [x.strip() for x in re.split(r'[|,]', ramo.strip('{} '))
                           if x.strip() in catalog]
                    if opt:
                        escolha = {'opcoes': opt, 'qtd': 1,
                                   'rotulo': _rotulo_escolha(0, 1)}
                        break
            continue
        # (c2) LISTA DE DECRETO: any{ slug, slug, … } (fora-do-limite) — todas as magias
        # da lista entram como conhecidas/sempre-preparadas. Gate: se a tag exige
        # `requires:spellcasting`, só concede a conjuradores.
        if scope == 'any' and 'spell:' not in full and 'pick' not in full and 'efeito' not in full:
            lista = [x.strip() for x in re.split(r'[,|]', body) if x.strip() in catalog]
            if lista:
                if re.search(r'requires\s*:\s*spell_?casting', s) and not is_spellcaster:
                    continue
                for sl in lista:
                    fixas.append((sl, catalog[sl]))
                continue
        # (d) escolha qtd:K de uma classe / união de classes
        qtd = _qtd_de(body, nivel_total)
        if not qtd:
            continue
        classes = None
        scope_map = _spell_class_scope_map()
        if scope in scope_map:
            classes = [scope_map[scope]]
        elif scope == 'pick':
            lm = re.search(r'lista\s*:\s*\{([^{}]*)\}', scope_extra)
            if lm:
                classes = spell_scope_names(c.strip() for c in re.split(r'[|,]', lm.group(1)))
            else:
                rm = re.search(r'lista\s*:\s*match\(([a-z0-9_:-]+)\)\s*(\{.*)', scope_extra)
                if rm:
                    var = rm.group(1).split(':')[-1]
                    cl = _resolve_match('match(%s)%s' % (var, rm.group(2)),
                                        {var: escolhas.get(var)}).strip()
                    classes = spell_scope_names([cl])
        if classes:
            me = re.search(r'escola\s*:\s*([a-z_-]+)', body)
            esc = me.group(1) if (me and me.group(1) not in ('pick', 'ability')) else None
            nv = _nivel_filtro(body)
            escolha = {'pool': {'classes': sorted(set(classes)), 'nivel': nv, 'escola': esc},
                       'qtd': qtd, 'rotulo': _rotulo_escolha(nv, qtd, classes, esc)}
            break
    return fixas, escolha


def _norm_escola(e):
    return ''.join(c for c in unicodedata.normalize('NFD', (e or '').lower())
                   if unicodedata.category(c) != 'Mn')


def _resolve_pool(pool, catalog_rich):
    """Resolve um pool {classes, nivel, escola} para a lista ordenada de slugs candidatos."""
    cls, nv, esc = set(pool['classes']), pool['nivel'], _norm_escola(pool['escola']) if pool['escola'] else None
    out = []
    for slug, (nivel, escola, classes) in catalog_rich.items():
        if nv is not None and nivel != nv:
            continue
        if esc and escola != esc:
            continue
        if cls and not (cls & classes):
            continue
        out.append(slug)
    return sorted(out)


def _personagem_conjura(classes):
    """True se alguma classe/subclasse do personagem (ou habilidade de classe até o nível
    atual) carrega tag `spellcasting{…}` — i.e., é conjurador (p/ liberar as listas de
    decreto, que só entram na lista de magias de quem conjura)."""
    from .models import TbClassehabilidade
    for c in classes:
        cl = c.id_classe
        srcs = [cl] + ([c.id_subclasse] if c.id_subclasse_id else [])
        srcs += list(TbClassehabilidade.objects.filter(id_classe=cl, niveladquirido__lte=(c.nivel or 1)))
        for src in srcs:
            if any(_tag_block(t, 'spellcasting') is not None for t in (getattr(src, 'tags_json', None) or [])):
                return True
    return False


def _spell_mod(classes, atributos):
    """Modificador da habilidade de conjuração (`spellcasting{ability:X}`) do personagem,
    p/ resolver fórmulas passivas que citam `spell_mod` (ex.: Caçador/Instinto Afiado
    `str_save:+max(1, spell_mod)`). Se a classe oferece escolha (`ability:int|wis`), usa o
    MAIOR modificador; multiclasse: o maior entre as classes conjuradoras. 0 se não conjura.
    Só lê a habilidade de conjuração ATÉ o nível da classe (mesma janela de _personagem_conjura)."""
    from .models import TbClassehabilidade
    best = None
    for c in classes:
        cl = c.id_classe
        srcs = [cl] + ([c.id_subclasse] if c.id_subclasse_id else [])
        srcs += list(TbClassehabilidade.objects.filter(id_classe=cl, niveladquirido__lte=(c.nivel or 1)))
        for src in srcs:
            for t in (getattr(src, 'tags_json', None) or []):
                body = _tag_block(t, 'spellcasting')
                if body is None:
                    continue
                m = re.search(r'ability\s*:\s*([a-z|]+)', body)
                if not m:
                    continue
                mods = []
                for tok in m.group(1).split('|'):
                    sig = _EN_SIG.get(_SAVE_TOKEN_EN.get(tok.strip()))
                    if sig:
                        mods.append(atributos[sig]['mod'])
                if mods:
                    cand = max(mods)
                    best = cand if best is None else max(best, cand)
    return best or 0


def magias_concedidas(personagem):
    """Todas as magias ESPECÍFICAS concedidas à lista de magias por features ATIVAS do
    personagem (Essência/vertente, talentos pegos — Marcas, Juramento das Três Luas… —,
    classe/subclasse, antecedente, itens, opções). Itera a MESMA lista de features de
    `derive` (já filtrada por nível/escolha/talento-pego) e extrai grants/escolhas via
    `_grants_de_tag`. Escolhas (qtd<lista, ou pool de classe) viram pendências e ficam em
    TbPersonagemEscolha(tipo='magia-concedida', origem=fonte, slot=ordinal da escolha na
    feature, valor=slugs separados por vírgula). Retorna {'concedidas':[{slug,nivel,fonte}],
    'pendentes':[{fonte,slot,rotulo,qtd,opcoes,escolhidos}]}."""
    out = {'concedidas': [], 'pendentes': []}
    if personagem is None:
        return out
    from .models import TbMagia, TbPersonagemEscolha
    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse').order_by('-principal', 'id'))
    nivel_total = sum(int(c.nivel or 0) for c in classes) or int(personagem.nivel or 1)
    is_caster = _personagem_conjura(classes)
    features = (_features_de_classe(classes) + _tracos_raciais(personagem)
                + _antecedente(personagem) + _talentos(personagem)
                + _features_de_itens(personagem) + _features_de_opcoes(personagem))
    escolhas, _listas = _collect_escolhas(personagem, features)
    catalog, catalog_rich = {}, {}
    for sl, nv, esc, cl in TbMagia.objects.values_list('slug', 'nivel', 'escola', 'classes'):
        catalog[sl] = nv
        catalog_rich[sl] = (nv, _norm_escola(esc),
                            {x.strip() for x in (cl or '').split(',') if x.strip()})
    escolhidos = {}
    for e in TbPersonagemEscolha.objects.filter(id_personagem=personagem, tipo='magia-concedida'):
        escolhidos.setdefault((e.origem or '', e.slot), set()).update(
            x for x in (e.valor or '').split(',') if x)
    seen, ordem = set(), {}
    for (_o, _f, obj, _cl) in features:
        fonte = getattr(obj, 'nome', '') or ''
        for tag in (getattr(obj, 'tags_json', None) or []):
            fixas, escolha = _grants_de_tag(tag, escolhas, catalog, nivel_total, is_caster)
            for slug, nivel in fixas:
                if slug not in seen:
                    seen.add(slug)
                    out['concedidas'].append({'slug': slug, 'nivel': nivel, 'fonte': fonte})
            if not escolha:
                continue
            opcoes = escolha.get('opcoes')
            if opcoes is None and escolha.get('pool'):
                opcoes = _resolve_pool(escolha['pool'], catalog_rich)
            opcoes = [s for s in (opcoes or []) if s in catalog]
            if not opcoes:
                continue
            slot = ordem.get(fonte, 0)
            ordem[fonte] = slot + 1
            chosen = [s for s in opcoes if s in escolhidos.get((fonte, slot), set())][:escolha['qtd']]
            for s in chosen:
                if s not in seen:
                    seen.add(s)
                    out['concedidas'].append({'slug': s, 'nivel': catalog.get(s, 0), 'fonte': fonte})
            if len(chosen) < escolha['qtd']:
                out['pendentes'].append({'fonte': fonte, 'slot': slot, 'rotulo': escolha['rotulo'],
                                         'qtd': escolha['qtd'], 'opcoes': opcoes, 'escolhidos': chosen})
    return out


# compat: nome antigo
magias_essencia = magias_concedidas


# Concessões FIXAS (sem escolha) de opções de jogo e talentos. Regexes ESPECÍFICAS —
# nunca casam grant:reaction/grant:grapple/grant:move/grant:resource/grant:extra_action
# (verbos de runtime/combate, inertes na ficha). Slug em snake_case; a ponte _↔- resolve
# contra o slug hifenado do catálogo (posição de referência).
_GRANT_OPCAO_SINGLE_RE = re.compile(r'grant:opcao:([a-z0-9_]+):([a-z0-9_-]+)')
_GRANT_OPCAO_LIST_RE = re.compile(r'grant:opcao\{\s*([a-z0-9_]+)\s*:\s*\[([^\]]*)\]')
_GRANT_TALENTO_RE = re.compile(r'grant:talento\{\s*([a-z0-9_-]+)\s*((?:,[^}]*)?)\}')


def _ref_slug(s):
    """Slug de REFERÊNCIA canônico (hífen) p/ casar com o slug do catálogo."""
    return (s or '').strip().replace('_', '-')


def grants_fixos(personagem):
    """Concessões FIXAS (sem pick) das features ativas do personagem — o análogo de
    `magias_concedidas` para opções de jogo e talentos:
      grant:opcao:<tipo>:<slug>(mods)       uma opção específica (metamagia/manobra…)
      grant:opcao{<tipo>: [<slugs>], ...}   adicionada à lista conhecida FORA do painel de
                                            pick (não conta no limite, 'extra/fora do limite')
      grant:talento{<slug>[, no_asi]}       os benefícios de um talento específico, sem ASI

    Itera a MESMA lista de features de `derive`/`magias_concedidas` (já filtrada por
    nível/escolha/talento-pego) e resolve os slugs contra o catálogo ao vivo (TbOpcaojogo.slug
    / TbTalento.slug, ponte _↔-). Respeita `requires:lvl{N}`. Materialização idempotente e
    origem-rastreada em views._sync_grants_fixos (padrão de _sync_magias_concedidas). Retorna
    {'opcoes':[{slug,id_opcao,tipo,nome,fonte}], 'talentos':[{slug,id_talento,nome,no_asi,fonte}]}."""
    out = {'opcoes': [], 'talentos': []}
    if personagem is None:
        return out
    from .models import TbOpcaojogo, TbTalento
    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse').order_by('-principal', 'id'))
    nivel_total = sum(int(c.nivel or 0) for c in classes) or int(personagem.nivel or 1)
    features = (_features_de_classe(classes) + _tracos_raciais(personagem)
                + _antecedente(personagem) + _talentos(personagem)
                + _features_de_itens(personagem) + _features_de_opcoes(personagem))
    op_por_slug = {_ref_slug(o.slug): o for o in TbOpcaojogo.objects.all()}
    tal_por_slug = {_ref_slug(t.slug): t for t in TbTalento.objects.all() if t.slug}
    seen_op, seen_tal = set(), set()
    for (_o, _f, obj, _cl) in features:
        fonte = getattr(obj, 'nome', '') or ''
        for tag in (getattr(obj, 'tags_json', None) or []):
            s = str(tag)
            m = re.search(r'requires:lvl\{(\d+)\}', s)
            if m and nivel_total < int(m.group(1)):
                continue
            grants = [(mm.group(1), mm.group(2)) for mm in _GRANT_OPCAO_SINGLE_RE.finditer(s)]
            for lm in _GRANT_OPCAO_LIST_RE.finditer(s):
                for sl in re.split(r'[,\s]+', lm.group(2).strip()):
                    if sl:
                        grants.append((lm.group(1), sl))
            for tipo, slug in grants:
                op = op_por_slug.get(_ref_slug(slug))
                if not op or op.slug in seen_op:
                    continue
                seen_op.add(op.slug)
                out['opcoes'].append({'slug': op.slug, 'id_opcao': op.id_opcao,
                                      'tipo': tipo, 'nome': op.nome, 'fonte': fonte})
            for tm in _GRANT_TALENTO_RE.finditer(s):
                no_asi = 'no_asi' in (tm.group(2) or '')
                t = tal_por_slug.get(_ref_slug(tm.group(1)))
                if not t or t.slug in seen_tal:
                    continue
                seen_tal.add(t.slug)
                out['talentos'].append({'slug': t.slug, 'id_talento': t.id_talento,
                                        'nome': t.nome, 'no_asi': no_asi, 'fonte': fonte})
    return out


# ───────────────────────── FASE 2: interpretador de tags ────────────────
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {'max': max, 'min': min, 'round': round, 'abs': abs,
          'roundup': lambda x: math.ceil(x), 'rounddown': lambda x: math.floor(x)}
def _build_ctx(nivel_total, pb, atributos):
    ctx = {'lvl': int(nivel_total), 'classlvl': int(nivel_total), 'pb': int(pb)}
    for sig, en in _ATTR_EN.items():
        ctx[en + '_mod'] = atributos[sig]['mod']
        ctx[en + '_score'] = atributos[sig]['valor']
    return ctx


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_eval_node(a) for a in node.args])
    raise ValueError('nó não permitido na fórmula')


def _eval_formula(expr, ctx):
    """Fórmula aritmética (variáveis snake_case + max/min/round/roundup/rounddown),
    via AST (sem eval, sem potência). '-' é SEMPRE subtração — variáveis nunca são
    hifenadas ([a-z_][a-z0-9_]*). int ou None."""
    e = str(expr).strip()
    for var in sorted(ctx, key=len, reverse=True):
        e = re.sub(r'(?<![a-z0-9_])' + re.escape(var) + r'(?![a-z0-9_])', '(%d)' % ctx[var], e)
    if re.search(r'[A-Za-z_]', re.sub(r'\b(?:max|min|round|abs|roundup|rounddown)\b', '', e)):
        return None
    try:
        return int(_eval_node(ast.parse(e, mode='eval').body))
    except Exception:
        return None


def _read_expr(s, i):
    """Lê uma fórmula a partir de `i` respeitando profundidade de ()/[]/{}: para no
    primeiro `,` de nível 0 ou num fechamento que encerraria um bloco externo. Necessário
    p/ valores com vírgula interna, ex.: `max(1, spell_mod)`."""
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            if depth == 0:
                break
            depth -= 1
        elif c == ',' and depth == 0:
            break
        j += 1
    return s[i:j].strip()


def _match_close(s, i):
    depth = 0
    while i < len(s):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


_NO_BRANCH = object()


def _ramo(inner, escolhido):
    if escolhido is None:
        return _NO_BRANCH
    for m in re.finditer(r'(?:^|[,{]|\s)' + re.escape(escolhido) + r'\s*:', inner):
        j = m.end()
        while j < len(inner) and inner[j] == ' ':
            j += 1
        if j < len(inner) and inner[j] == '{':
            return inner[j + 1:_match_close(inner, j)]
        k, depth = j, 0
        while k < len(inner):
            c = inner[k]
            if c in '{[(':
                depth += 1
            elif c in '}])':
                depth -= 1
            elif c == ',' and depth == 0:
                break
            k += 1
        return inner[j:k].strip()
    return _NO_BRANCH


def _resolve_match(text, escolhas):
    """Substitui match(var){…} pelo ramo escolhido (ou 'default'); recursivo. Aceita a
    forma `match(pick:<var>){…}` (usada nas sub-escolhas de essência, ex.: Nephilim
    `resist:match(pick:energia){lumen:radiante, umbra:necrotico}`) — o `pick:` é só um
    prefixo de referência; a variável é a mesma chave de `escolhas`."""
    out = text
    for _ in range(40):
        m = re.search(r'match\((?:pick:)?([a-z0-9_]+)\)\s*\{', out)
        if not m:
            break
        var, bo = m.group(1), m.end() - 1
        bc = _match_close(out, bo)
        if bc < 0:
            break
        inner = out[bo + 1:bc]
        rep = _ramo(inner, escolhas.get(var))
        if rep is _NO_BRANCH:
            rep = _ramo(inner, 'default')
        if rep is _NO_BRANCH:
            rep = ''
        out = out[:m.start()] + rep + out[bc + 1:]
    return out


def _resolve_var(name, locais, escolhas):
    """Resolve o operando de resist:/immune:/cond_immune: contra as indireções de
    define{} (`locais`) E as sub-escolhas de essência (`escolhas`). `resist:<var>` onde
    <var> é uma escolha persistida (sangue/energia/…) vira o valor ESCOLHIDO
    (`resist:sangue` -> `resist:frio`); sem escolha, o nome cru cai em _PLACEHOLDERS e é
    suprimido — a ficha nunca mostra o literal."""
    v = locais.get(name, name)
    return escolhas.get(v, v)


def _apply_choice_subs(text, escolhas):
    """Materializa REFERÊNCIAS a sub-escolhas persistidas num texto de tag já com
    `match()` resolvido (roda logo após `_resolve_match`):
      (a) operando `…:pick:<var>` / `(pick:<var>)` -> valor escolhido
          (ex.: `resist:pick:elemento` -> `resist:fogo`);
      (b) DECLARAÇÃO autônoma `pick:<verbo>:<opções>[:N]` -> `<verbo>:<escolhido>`
          (ex.: `pick:save_prof:{int|wis|cha}:1` -> `save_prof:int`;
                 `pick:move:1(=move:{swim|climb})` -> `move:swim`).
    Sem escolha correspondente, o token fica INTACTO (inerte) — zero lixo na ficha.
    Genérico: o nome do kind é a chave em `escolhas` e, em (b), o próprio verbo-alvo."""
    if not escolhas:
        return text
    # (a) referência-operando (precedida por ':' '=' '('): vira só o valor escolhido.
    text = re.sub(r'(?<=[:=(])pick:([a-z0-9_]+)(?![:\w])',
                  lambda m: escolhas.get(m.group(1)) or m.group(0), text)
    # (b) declaração autônoma (fora de posição de operando): `<kind>:<escolhido>`.
    def _decl(m):
        val = escolhas.get(m.group(1))
        return ('%s:%s' % (m.group(1), val)) if val else m.group(0)
    return re.sub(
        r'(?<![:=(a-z0-9_-])pick:([a-z0-9_]+)'
        r'((?::(?:\{[^}]*\}|[A-Za-z0-9_+\-]+)|\([^)]*\))*)', _decl, text)


def _split_top(s, sep=','):
    """Divide `s` por `sep` só no nível 0 de ()/[]/{} (não quebra dentro de blocos)."""
    out, depth, buf = [], 0, []
    for c in s:
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth = max(0, depth - 1)
        if c == sep and depth == 0:
            out.append(''.join(buf)); buf = []
        else:
            buf.append(c)
    out.append(''.join(buf))
    return out


def _resolve_level_match(text, ctx):
    """Resolve `match(classlvl|lvl){ <cmp>:val, ..., default:val }` avaliando ramos
    com operador de comparação (`classlvl>=N`) contra o nível do ctx — o PRIMEIRO ramo
    satisfeito na ordem de declaração vence (cadeia de condição), senão `default`. Roda
    ANTES de _resolve_match (que só casa ramos por valor literal de escolha e colapsaria
    esta forma no default, perdendo a progressão por nível — ex.: sintonização do
    Artífice `attr_max:sintonizacao=match(classlvl){classlvl>=18:6, classlvl>=14:5,
    default:4}`). match() sem ramo de comparação é deixado intacto para _resolve_match."""
    if 'match(' not in text:
        return text
    pos = 0
    for _ in range(40):
        m = re.search(r'match\((classlvl|lvl)\)\s*\{', text[pos:])
        if not m:
            break
        var = m.group(1)
        start = pos + m.start()
        bo = pos + m.end() - 1
        bc = _match_close(text, bo)
        if bc < 0:
            break
        inner = text[bo + 1:bc]
        if not re.search(r'(?:classlvl|lvl)\s*(?:>=|<=|=|>|<)\s*\d+\s*:', inner):
            pos = bo + 1  # não é match de comparação por nível: deixa p/ _resolve_match
            continue
        lvl = int(ctx.get(var, ctx.get('lvl', 0)) or 0)
        chosen, default = None, None
        for part in _split_top(inner, ','):
            part = part.strip()
            mm = re.match(r'(?:classlvl|lvl)\s*(>=|<=|=|>|<)\s*(\d+)\s*:\s*(.+)$', part, re.S)
            if mm:
                op, n, val = mm.group(1), int(mm.group(2)), mm.group(3).strip()
                ok = {'>=': lvl >= n, '<=': lvl <= n, '=': lvl == n, '>': lvl > n, '<': lvl < n}[op]
                if ok and chosen is None:
                    chosen = val
            else:
                dm = re.match(r'default\s*:\s*(.+)$', part, re.S)
                if dm:
                    default = dm.group(1).strip()
        rep = chosen if chosen is not None else (default if default is not None else '')
        text = text[:start] + rep + text[bc + 1:]
        pos = start + len(rep)
    return text


def _split_qualifiers(expr):
    """Separa uma fórmula de qualificadores parentéticos à direita que carregam ':'
    (ex.: `(rounddown(pb/2))(unless:proficient)` -> ('(rounddown(pb/2))', {'unless:proficient'}).
    Um grupo `(...)` de nível 0 cujo interior tem ':' no nível 0 é qualificador; senão
    (ex.: `rounddown(pb/2)`) faz parte da fórmula e encerra a raspagem."""
    quals = set()
    e = expr.strip()
    while e.endswith(')'):
        depth = 0
        op = -1
        for i in range(len(e) - 1, -1, -1):
            c = e[i]
            if c == ')':
                depth += 1
            elif c == '(':
                depth -= 1
                if depth == 0:
                    op = i
                    break
        if op < 0:
            break
        inner = e[op + 1:-1]
        # qualificador = tem ':' de nível 0 no interior (unless:proficient, if:...)
        if len(_split_top(inner, ':')) > 1:
            quals.add(inner.strip())
            e = e[:op].strip()
        else:
            break
    return e, quals


_MODIFY_STATIC_FIELDS = frozenset()  # nenhum campo modify: atinge número ESTÁTICO do PC
# (todos os achados observados alteram alcance/aura/#ataques/upcast/recurso/companheiro/
#  ação — combate/runtime/VTT; ver plano_mestre cluster modify:). Deixado como registry
# vazio para que, se um modify:ability{...classe:<pc>}.<campo-estatico> surgir, baste
# adicionar o campo aqui — sem if-por-tipo espalhado.


def _iter_modify_spans(seg):
    """Gera (ini, fim) de cada token `modify:...` BALANCEADO em `seg` (para até vírgula
    de nível 0 ou fechamento do bloco externo). Uma feature altera OUTRA (cross-feature):
    o span inteiro é uma unidade e é CONSUMIDO (registrado + retirado da varredura) para
    não vazar seus verbos internos (resist:/str_score:/immune:) nos números estáticos."""
    for m in re.finditer(r'\bmodify:', seg):
        i = m.end()
        depth, j = 0, i
        while j < len(seg):
            c = seg[j]
            if c in '{([':
                depth += 1
            elif c in '})]':
                if depth == 0:
                    break
                depth -= 1
            elif c == ',' and depth == 0:
                break
            j += 1
        yield m.start(), j


def _parse_modify(seg, feature, lvl):
    """Extrai descritores de cada `modify:<tipo>[{ref}][.campo][{corpo}|:=valor](consts)`
    em `seg`. Cross-feature: NÃO materializa número estático do PC (nenhum campo observado
    é estático — todos combate/runtime/companheiro/VTT). Registrado inerte (modo=combate)
    para o VTT futuro (regra da ficha-de-log)."""
    out = []
    for a, b in _iter_modify_spans(seg):
        raw = seg[a:b].strip()
        mm = re.match(r'modify:([a-z_]+)(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\})?'
                      r'(?:\.([a-z0-9_.]+))?', raw)
        if not mm:
            continue
        ttype = mm.group(1)
        ref = (mm.group(2) or '').split(',')[0].strip() or None
        campo = mm.group(3) or None
        estatico = bool(campo and campo in _MODIFY_STATIC_FIELDS and ttype in ('ability', 'resource'))
        out.append({'feature': feature, 'alvo_tipo': ttype, 'alvo_ref': ref,
                    'campo': campo, 'raw': raw, 'nivel_feature': lvl,
                    'modo': 'estatico' if estatico else 'combate'})
    return out


def _strip_modify(seg):
    """Remove os tokens `modify:...` de `seg` (limpando vírgulas residuais). O descritor
    útil já foi extraído por _parse_modify; retirar o span impede que verbos internos do
    modify (resist:match, str_score:+4, immune:alento, ignore:resist:...) sejam varridos
    como estáticos do próprio personagem (vazamento cross-feature)."""
    spans = list(_iter_modify_spans(seg))
    if not spans:
        return seg
    for a, b in reversed(spans):
        seg = seg[:a] + seg[b:]
    seg = re.sub(r',\s*,', ',', seg)
    seg = re.sub(r'\{\s*,', '{', seg)
    seg = re.sub(r',\s*\}', '}', seg)
    seg = re.sub(r'^\s*,\s*', '', seg).strip()
    return seg


def _resource_speed_value(slug, recursos):
    """Valor numérico (ft) de um recurso de classe pelo slug, no nível já materializado
    em state['recursos'] (Monge `speed:+resource{passo_veloz}`). Casa pelo último
    componente da chave 'Classe: Nome' via ponte _<->-; extrai o 1º inteiro do valor."""
    alvo = _slug(slug)  # ponte _<->- (tag 'passo_veloz' vs chave 'Monge: Passo Veloz')
    achado = next((v for k, v in (recursos or {}).items() if _slug(k.split(':')[-1]) == alvo), None)
    if achado is None:
        return 0
    m = re.search(r'\d+', str(achado))
    return int(m.group(0)) if m else 0


_RE_NO_ARMOR_RESTRICTION = re.compile(r'restriction\{[^}]*equiped\{\s*(?:armadura|armor|escudo|shield)')


def _active_spans(tag):
    spans = []
    for kw in _ACTIVE_BLOCKS:
        for m in re.finditer(r'\b' + _tag_verb_rx(kw) + r'\s*\{', tag):
            bc = _match_close(tag, m.end() - 1)
            if bc > 0:
                spans.append((m.start(), bc))
    return spans


def _passive_segments(tag):
    """always-active{} fora de bloco ativo; ou a tag nua se não tem always-active
    nem marcador ativo."""
    spans = _active_spans(tag)
    segs, has_aa = [], False
    for m in re.finditer(r'\b' + _tag_verb_rx('always_active') + r'\s*\{', tag):
        if any(a <= m.start() <= b for a, b in spans):
            continue
        has_aa = True
        bc = _match_close(tag, m.end() - 1)
        if bc > 0:
            segs.append(tag[m.end():bc])
    if not has_aa and not any(mk in tag for mk in _ACTIVE_MARKERS):
        segs.append(tag)
    return segs


def _parse_defines(text):
    """(is_weapon, nome|None, corpo) de cada define{}/define:weapon{} (via _match_close)."""
    out = []
    for m in re.finditer(r'define(:weapon)?\s*\{', text):
        bc = _match_close(text, m.end() - 1)
        if bc < 0:
            continue
        body = text[m.end():bc].strip()
        nm = re.match(r'^([a-z0-9_-]+)\s*:\s*(.*)$', body, re.S)
        out.append((bool(m.group(1)), nm.group(1) if nm else None,
                    nm.group(2).strip() if nm else body))
    return out


def _strip_defines(text):
    """Remove os spans define{...}/define:weapon{...} do texto (via _match_close).
    Usado para tirar o CORPO do define da varredura de verbos passivos: o menu
    (list{}/table{}) de um define não é concessão estática e não deve vazar
    prof:/resist:/sense:/etc. (ex.: Máscara de Guerra listava as 4 perícias). O
    define já foi consumido por _parse_defines/_classify_define separadamente."""
    for _ in range(40):
        m = re.search(r'define(:weapon)?\s*\{', text)
        if not m:
            break
        bc = _match_close(text, m.end() - 1)
        if bc < 0:
            break  # chave não fecha: aborta para não remover demais
        text = text[:m.start()] + text[bc + 1:]
    return text


def _classify_define(is_weapon, nome, corpo, ctx):
    """Classifica o corpo de um define{}. 'slug'->indireção (resist:elemento),
    'pool'->recurso (max/reset), 'scalar'->número; demais ignorados na ficha."""
    if is_weapon:
        return ('weapon', None)
    if nome is None:
        return ('flag', None)
    if corpo.startswith('list{'):
        return ('list', None)
    if corpo.startswith('table{'):
        return ('table', None)
    if re.search(r'\b(?:max|uses|qtd)\s*:', corpo) and (re.search(r'\breset\s*:', corpo) or 'die' in corpo):
        mx = re.search(r'\b(?:max|uses|qtd)\s*:\s*([^,}]+)', corpo)
        rs = re.search(r'reset\s*:\s*([a-z_-]+)', corpo)
        return ('pool', {'max': _eval_formula(mx.group(1), ctx) if mx else None,
                         'reset': rs.group(1) if rs else None})
    if re.fullmatch(r'[a-z0-9_-]+', corpo):
        return ('slug', corpo)
    val = _eval_formula(corpo, ctx)
    return ('scalar', val) if val is not None else ('outro', None)


def _prog(expr, level):
    """De '{classlvl=5:2, classlvl=11:3}' devolve o valor do maior limiar <= level."""
    melhor = None
    for lv, v in re.findall(r'classlvl\s*=\s*(\d+)\s*:\s*([^,}]+)', expr):
        if int(lv) <= int(level) and (melhor is None or int(lv) >= melhor[0]):
            melhor = (int(lv), v.strip())
    return melhor[1] if melhor else None


def _die_size(s):
    """(faces, qtd) de 'XdY' para comparar dados; (0, 0) se não for dado."""
    m = re.search(r'(\d*)d(\d+)', str(s))
    return (int(m.group(2)), int(m.group(1) or 1)) if m else (0, 0)


# ── Guard do perfil de ATAQUE: a string de dano só pode conter componentes
# PARSEÁVEIS (dado NdM + modificadores numéricos + tipo de dano). Um valor de dano
# ESTÁTICO nunca renderiza expressão: `if(...)`/`else:`/comparações são coisa de
# runtime (combate/VTT). Se um resíduo não-parseável chegar aqui (tag mal-formada
# que escapou do validador), ele é DESCARTADO da string — jamais renderizado cru
# (bug do print: `if(unarmed_strike.dmg >= 1d6):` vazando no painel Ataques).
_DANO_ESTATICO_RX = re.compile(
    r'^(?P<die>\d*d\d+(?:\s*[+-]\s*\d+)*|\d+)'                 # NdM(+/-N)* ou nº plano
    r'(?:\s*\((?P<tipo>[a-zà-ÿ][a-zà-ÿ /|]*)\))?$', re.I)      # (tipo) opcional: só letras
_DANO_EXPR_RX = re.compile(r'if\s*\(|\belse\b|:=|==|>=|<=|[<>]|\bequiped\b')


def _sanitize_dano_dado(dado):
    """(dado_limpo, descartado|None). Só emite componentes parseáveis:
      • dado NdM (com modificadores numéricos internos) + tipo de dano opcional;
      • placeholder textual SEGURO (ex.: 'dado de artes marciais') — sem operadores.
    Expressão condicional / comparação é DESCARTADA (tenta salvar um dado NdM que
    inicie a string; senão vira '—'). O trecho descartado volta p/ nota de debug."""
    if not dado or dado == '—':
        return dado, None
    s = str(dado).strip()
    m = _DANO_ESTATICO_RX.match(s)
    if m:
        die = re.sub(r'\s+', '', m.group('die'))
        tipo = (m.group('tipo') or '').strip()
        return die + ('(%s)' % tipo if tipo else ''), None
    if _DANO_EXPR_RX.search(s):                    # vazamento de expressão/condicional
        m2 = re.match(r'(\d*d\d+)', s)             # salva um dado que INICIE a string
        return (m2.group(1), s) if m2 else ('—', s)
    return s, None                                 # placeholder textual seguro


def _num(x, default=0):
    """Coerção defensiva a int: o bônus de ACERTO da ficha é sempre numérico —
    nenhum resíduo não-numérico pode chegar à string de perfil de ataque."""
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def _collect_escolhas(personagem, features):
    """Devolve (escolhas, listas): `escolhas` = 1º valor por tipo (menor slot, p/
    match()); `listas` = todos os valores por tipo ordenados por slot (p/ pick:).
    Também injeta set:<var>=<valor> de traços passivos em ambos."""
    escolhas, listas = {}, {}
    if personagem is not None:
        for e in personagem.escolhas.all().order_by('tipo', 'slot'):
            listas.setdefault(e.tipo, []).append(e.valor)
            escolhas.setdefault(e.tipo, e.valor)
    for _o, _f, obj, _cl in features:
        for t in (getattr(obj, 'tags_json', None) or []):
            if not isinstance(t, str):
                continue
            for m in re.finditer(r'(?<![a-z_-])set:([a-z0-9_]+)\s*=\s*([a-z0-9_-]+)(?!\s*[:{])', t):
                escolhas.setdefault(m.group(1), m.group(2))
                listas.setdefault(m.group(1), [m.group(2)])
    return escolhas, listas


def _cond_nomes():
    """slug -> nome PT das condições (TbCondicao), p/ exibir imunidades legíveis."""
    from .models import TbCondicao
    return {c.slug: c.nome for c in TbCondicao.objects.all()}


def _armadura_equipada(personagem, dex_mod):
    """CA derivada de armadura/escudo equipados, lida das tags do item (mecanica_de_tags)."""
    tem_arm = tem_esc = False
    ca_arm, fonte = None, None
    esc_bonus = 0
    for it in personagem.inventario.filter(equipado=True):
        mec = mecanica_de_tags(it.tags_json)
        if mec['is_escudo']:
            tem_esc = True
            esc_bonus = max(esc_bonus, mec['ca_base'] if mec['ca_base'] is not None else 2)
        elif mec['is_armadura']:
            tem_arm = True
            # CA = fórmula do item avaliada com o DES do personagem (ex.: 14+min(dex_mod,2)).
            ca = _eval_formula(mec.get('ca_formula') or '', {'dex_mod': dex_mod})
            if ca is None:
                ca = (mec['ca_base'] if mec['ca_base'] is not None else 10) + dex_mod
            if ca_arm is None or ca > ca_arm:
                ca_arm, fonte = ca, it.nome
    return {'tem_armadura': tem_arm, 'tem_escudo': tem_esc, 'ca_armadura': ca_arm,
            'fonte': fonte, 'escudo_bonus': esc_bonus}


def apply_tags(state, features, personagem=None, escolhas=None):
    """Interpreta as tags_json e aplica os efeitos PASSIVOS. Coleta o que
    perícias/saves/idiomas/ataques precisam em state['_tag']."""
    base_ctx = state['_ctx']
    if escolhas is None:
        escolhas, _ = _collect_escolhas(personagem, features)

    coll = {'skill_prof': set(), 'save_prof': set(), 'all_saves': 0, 'save_bonus': {}, 'check_attr': {},
            'check_bonus': {}, 'idiomas': [], 'ferramentas': [], 'armaduras': [], 'armas': [],
            'initiative': 0, 'move_modes': {}, 'desvantagens': [],
            'n_ataques': 0, 'ataque_dado': {}, 'ataque_attr': {},
            'atk_bonus': {}, 'dmg_bonus': {},  # bônus PLANO de acerto/dano por escopo (item/Estilo)
            'armor_ca_bonus': 0, 'off_hand_full_mod': False,  # Defesa (soma na CA armada) / Combate c/ Duas Armas
            'skill_expertise': set(),  # Especialização por tag (dobro do PB) — espelha skill_prof
            'check_all': []}  # bônus global de teste de habilidade: (val, sig|None, unless_prof)
    hp_bonus, resist, imune, cond_imune, vantagens, notas = [], [], [], [], [], []
    sentidos, sentidos_incr, sentidos_incr_ifp, ca_cands, recursos_tag = {}, {}, {}, [], {}
    resist_condicionais = []  # (tipo, se_ja_tem, senao) -> avaliados após o loop principal
    modificadores = []  # modify:<X> cross-feature: registrados inertes (combate/VTT)
    sintonizacao_max = 3  # limite de sintonização (base 5e = 3); attr_max:sintonizacao eleva
    speed_bonus = 0
    brutas = []
    talent_attrs = _talent_attr_map(personagem)
    # status de armadura/escudo p/ gate de restriction{equiped{armadura|escudo}} nos
    # movimentos sem armadura (Monge: Passo Veloz / Movimento Acrobático só descalço).
    _equip0 = _armadura_equipada(personagem, base_ctx['dex_mod']) if personagem is not None else \
        {'tem_armadura': False, 'tem_escudo': False}
    _armado = bool(_equip0.get('tem_armadura') or _equip0.get('tem_escudo'))

    for origem, fonte, obj, classlvl in features:
        tags = [t for t in (getattr(obj, 'tags_json', None) or []) if isinstance(t, str)]
        if tags:
            brutas.append({'origem': origem, 'fonte': fonte, 'nome': getattr(obj, 'nome', ''), 'tags': tags})
        ctx = dict(base_ctx)
        if classlvl is not None:
            ctx['classlvl'] = int(classlvl)
        talent_sig = _feature_talent_attr_sig(obj, talent_attrs)
        if talent_sig:
            en = _ATTR_EN.get(talent_sig)
            if en:
                ctx['talent_attr_mod'] = ctx.get(en + '_mod', 0)
                ctx['talent_attr_score'] = ctx.get(en + '_score', 0)
                ctx['asi_attr_mod'] = ctx['talent_attr_mod']
                ctx['asi_attr_score'] = ctx['talent_attr_score']
        feat_nome = getattr(obj, 'nome', fonte)
        # _resolve_level_match ANTES de _resolve_match: avalia match(classlvl){cmp:val}
        # por nível (sintonização do Artífice) — senão _resolve_match colapsaria no default.
        resolvidas = [_apply_choice_subs(_resolve_match(_resolve_level_match(t, ctx), escolhas), escolhas)
                      for t in tags]
        segs = [seg for r in resolvidas for seg in _passive_segments(r)]

        # defines (só em contexto PASSIVO): slug -> locais (indireção); pool -> recurso
        locais = {}
        for seg in segs:
            for is_w, nm, corpo in _parse_defines(seg):
                kind, payload = _classify_define(is_w, nm, corpo, ctx)
                if kind == 'slug':
                    locais[nm] = corpo
                elif kind == 'pool' and payload['max'] is not None:
                    recursos_tag['%s: %s' % (feat_nome, nm)] = payload
        # tira o corpo dos define{} da varredura de verbos: o menu (list{}/table{})
        # não é concessão estática — sem isto, prof:/resist:/sense:/save_prof:/etc.
        # dentro de um define vazam para os números fixos (bug da Máscara de Guerra,
        # que dava Religião/Natureza/Arcanismo/Enganação de uma vez). O slug/pool
        # útil já foi lido acima; verbos-irmãos FORA do define são preservados.
        segs = [_strip_defines(seg) for seg in segs]

        # modify:<X> cross-feature (uma feature altera OUTRA): registrado inerte e
        # RETIRADO da varredura estática — nenhum campo observado (range/aura/upcast/
        # #ataques/recurso/companheiro/ação) é número estático do PC; consumir o span
        # também blinda contra vazamento dos verbos internos (resist:match, str_score:+4,
        # immune:alento) nos números fixos. Computa só se o campo estiver em
        # _MODIFY_STATIC_FIELDS (hoje vazio) — regra da ficha-de-log (combate inerte).
        feat_lvl = int(classlvl) if classlvl is not None else ctx.get('lvl', 0)
        for seg in segs:
            modificadores.extend(_parse_modify(seg, feat_nome, feat_lvl))
        segs = [_strip_modify(seg) for seg in segs]

        # gate de ESCUDO no nível da feature (ca= e restriction são tags irmãs). A
        # defesa-sem-armadura é IMPLICITAMENTE vetada por armadura (toda ca= é base
        # desarmada), então não precisa de gate de armadura explícito.
        feat_gate_shield = any(re.search(r'equiped\{\s*(?:escudo|shield)|requires:\s*\{?\s*!\s*(?:escudo|shield)|!\s*escudo', r) for r in resolvidas)

        for seg in segs:
            if seg:
                # passiva gateada por recurso (requires:resource{...}>=N) é CONDICIONAL:
                # não entra no número fixo — vira vantagem condicional. (corrige o all-saves
                # do Ladino/Trilha do Fantasma, aplicado incondicionalmente antes.)
                if re.search(r'requires:\s*resource\{', seg):
                    ms = re.search(r'all_saves:\s*\+([^\s,}]+)', seg)
                    vantagens.append((('+%s em todas as salvaguardas' % ms.group(1)) if ms
                                      else 'efeito') + ' (condicional: requer recurso) — %s' % feat_nome)
                    continue
                # gate de NÍVEL num segmento passivo: `requires:lvl>=N` / `requires:lvl{N}`
                # abaixo do nível total, o segmento inteiro não materializa (ex.: traço
                # racial `sense:devilsight(requires:lvl>=5)`). Nível total (mesma semântica
                # de requires:lvl{N} em _grants_de_tag).
                mlvl = re.search(r'requires:\s*lvl\s*(?:>=|=)\s*(\d+)|requires:\s*lvl\s*\{\s*(\d+)\s*\}', seg)
                if mlvl and ctx.get('lvl', 0) < int(mlvl.group(1) or mlvl.group(2)):
                    continue
                # PV
                for m in re.finditer(r'(?:attr:|buff:)?max_hp:?\s*\+\s*([^\s,}]+)', seg):
                    if 'on:' in seg[m.start():m.end() + 12]:
                        continue
                    val = _eval_formula(m.group(1), ctx)
                    if val is not None:
                        hp_bonus.append((feat_nome, val))
                # CA (defesa sem armadura) — candidata com gates da feature
                m = re.search(r'\bca\s*=\s*([0-9a-z_+\-*/(). ]+?)(?=[,}]|$)', seg)
                if m:
                    val = _eval_formula(m.group(1), ctx)
                    if val is not None:
                        ca_cands.append((val, feat_nome, feat_gate_shield))
                # Velocidade / modos. Gate de armadura: `restriction{equiped{armadura|
                # escudo}}` (Monge Passo Veloz / Movimento Acrobático) só vale descalço —
                # com armadura/escudo o segmento de deslocamento não aplica.
                _sem_armadura_ok = not (_RE_NO_ARMOR_RESTRICTION.search(seg) and _armado)
                if _sem_armadura_ok:
                    # `speed:+<valor>`: dígito (item `speed:+18`), `resource{slug}` (Passo
                    # Veloz — valor no nível) ou fórmula (`min(5*x,30)`; var runtime -> None).
                    for m in re.finditer(r'\bspeed:\s*\+\s*', seg):
                        val_s = _read_expr(seg, m.end())
                        mr = re.match(r'resource\{([a-z0-9_-]+)\}', val_s)
                        if mr:
                            v = _resource_speed_value(mr.group(1), state.get('recursos'))
                        else:
                            v = _eval_formula(re.sub(r'\s*ft\s*$', '', val_s), ctx)
                        if v:
                            speed_bonus += int(v)
                    for m in re.finditer(r'move:(climb|swim|fly|burrow|wall|liquid)(?:\(=\s*(?:speed|walk)\)|:=?\s*(?:speed|walk)|:\+?(\d+)\s*ft|\((\d+)\s*ft\))?', seg):
                        val = m.group(2) or m.group(3)
                        coll['move_modes'][m.group(1)] = (val + 'ft') if val else 'walk'
                # Resistências / imunidades
                # Resistência CONDICIONAL: "if(already:resist{X}): resist:A else: resist:B"
                # (ex.: Oread "Sangue Elemental"). Avaliada numa 2ª passada (resist_condicionais),
                # contra o conjunto FINAL de resistências — senão o regex genérico abaixo aplicaria
                # A e B ao mesmo tempo (bug do veneno+ácido).
                _cond = re.search(r'if\(already:resist\{([a-z0-9_-]+)\}\):\s*resist:([a-z0-9_-]+)\s*else:\s*resist:([a-z0-9_-]+)', seg)
                if _cond:
                    resist_condicionais.append((_cond.group(1), _cond.group(2), _cond.group(3)))
                    seg = seg[:_cond.start()] + seg[_cond.end():]
                # Resistência por FONTE (não por tipo de dano): `resist:source{magical_effect}`
                # (Mestre da Abjuração). Não é um tipo do catálogo de dano — vira NOTA passiva
                # ("resistência a dano de <fonte>") e é retirada para o regex genérico de
                # resist: não capturar o literal 'source'.
                for m in re.finditer(r'resist:source\{\s*([a-z0-9_, -]+?)\s*\}', seg):
                    fonte_r = m.group(1).replace('_', ' ').replace('-', ' ').strip()
                    notas.append('resistência a dano de %s (%s)' % (fonte_r, feat_nome))
                seg = re.sub(r'resist:source\{[^}]*\}', '', seg)
                for m in re.finditer(r'(?<![a-z_-])resist:([a-z0-9_-]+)', seg):
                    v = _resolve_var(m.group(1), locais, escolhas)
                    if v not in _PLACEHOLDERS and v not in resist:
                        resist.append(v)
                for m in re.finditer(r'(?<![a-z_-])immune:([a-z0-9_-]+)', seg):
                    v = _resolve_var(m.group(1), locais, escolhas)
                    if v not in _PLACEHOLDERS and v not in imune:
                        imune.append(v)
                for m in re.finditer(r'cond_immune:([a-z0-9_-]+)', seg):
                    v = _resolve_var(m.group(1), locais, escolhas)
                    if v not in _PLACEHOLDERS and v not in cond_imune:
                        cond_imune.append(v)
                # Sentidos. `sense:X(range:Nft)` = alcance ABSOLUTO (mantém o maior por
                # tipo). `sense:X(range:+Nft)` = incremento RELATIVO (soma ao alcance do
                # mesmo tipo já concedido — Vampiro DV/essência); com `if_present` só
                # aplica se o tipo já existe (senão é descartado).
                for m in re.finditer(r'sense:([a-z0-9_-]+)(\([^)]*\))?', seg):
                    t, args = m.group(1), (m.group(2) or '')
                    mr = re.search(r'(?:range|radius):(\+)?(\d+)\s*ft', args)
                    if mr and mr.group(1):  # incremento relativo (+Nft)
                        n = int(mr.group(2))
                        if 'if_present' in args:
                            sentidos_incr_ifp[t] = sentidos_incr_ifp.get(t, 0) + n
                        else:
                            sentidos_incr[t] = sentidos_incr.get(t, 0) + n
                    else:
                        rng = int(mr.group(2)) if mr else 0
                        sentidos[t] = max(sentidos.get(t, 0), rng)
                # Proficiências
                for m in re.finditer(r'(?<![a-z_-])prof:([a-z0-9_-]+)(?:\{([^}]+)\})?', seg):
                    chave, valor = m.group(1), m.group(2)
                    if valor:
                        alvo = {'armor': coll['armaduras'], 'weapon': coll['armas'],
                                'tool': coll['ferramentas'], 'idioma': coll['idiomas']}.get(chave)
                        if alvo is not None:
                            alvo.append(valor)
                    elif _norm_skill_slug(chave) in _SKILL_INFO:
                        coll['skill_prof'].add(_norm_skill_slug(chave))
                    elif chave.startswith('armadura'):
                        coll['armaduras'].append(chave)
                    elif chave.startswith('arma'):
                        coll['armas'].append(chave)
                # Especialização por tag: `expertise:<pericia>` (dobro do PB). Espelha o
                # caminho de prof: — só perícia canônica (expertise:tool{}/ferramentas caem
                # fora do catálogo de perícias e ficam inertes, como hoje). expertise IMPLICA
                # proficiência (regra 5e), então _pericias marca proficiente+expertise. Casa a
                # forma direta e a condicional `if(prof:X):expertise:X` (Cena é Corpo/Dom de Palco).
                for m in re.finditer(r'(?<![a-z_-])expertise:([a-z0-9_-]+)', seg):
                    sl = _norm_skill_slug(m.group(1))
                    if sl in _SKILL_INFO:
                        coll['skill_expertise'].add(sl)
                # Salvaguardas
                for m in re.finditer(r'(?<![a-z_-])save_prof:([a-z0-9_-]+)', seg):
                    coll['save_prof'].add(m.group(1))
                for m in re.finditer(r'all_saves:\s*\+([^\s,}]+)', seg):
                    val = _eval_formula(m.group(1), ctx)
                    if val is not None:
                        coll['all_saves'] += val
                # Salvaguarda de UMA habilidade: `<attr>_save:+<formula>` (ex.: Caçador/Instinto
                # Afiado `str_save:+max(1, spell_mod)`). Aceita siglas PT/EN (snake_case);
                # a fórmula pode ter vírgula interna (args de max/min) → lida por _read_expr.
                for m in re.finditer(r'(?<![a-z])([a-z]{3})_save:\s*\+', seg):
                    sig = _EN_SIG.get(_SAVE_TOKEN_EN.get(m.group(1)))
                    if not sig:
                        continue
                    val = _eval_formula(_read_expr(seg, m.end()), ctx)
                    if val is not None:
                        coll['save_bonus'][sig] = coll['save_bonus'].get(sig, 0) + val
                for m in re.finditer(r'(?<![a-z-])(?:buff:)?initiative:\s*\+([^\s,}]+)', seg):
                    val = _eval_formula(m.group(1), ctx)
                    if val is not None:
                        coll['initiative'] += val
                # Perícias (troca de atributo / bônus)
                for m in re.finditer(r'check_attr:([a-z0-9_-]+)\s*:?=\s*([a-z]{3})', seg):
                    if m.group(2) in _EN_SIG:
                        coll['check_attr'][m.group(1)] = _EN_SIG[m.group(2)]
                # `check_bonus:<pericia>[=|:]+<formula>` — a fórmula pode ter vírgula interna
                # (max(wis_mod, 1) — Ritos Sacros/Ordem Sagrada/Vínculo Natural): lida por
                # _read_expr (o regex antigo `[^\s,}]+` truncava em 'max(wis_mod' -> None).
                # `check_bonus:tool{...}` não casa (sem [=:] após 'tool'); dado (1d4 das Marcas)
                # cai em None por _eval_formula (roll-time -> VTT).
                for m in re.finditer(r'check_bonus:([a-z0-9_-]+)\s*[=:]\s*\+?', seg):
                    val = _eval_formula(_read_expr(seg, m.end()), ctx)
                    if val is not None:
                        coll['check_bonus'][m.group(1)] = coll['check_bonus'].get(m.group(1), 0) + val
                # Bônus GLOBAL de teste de habilidade: `ability_check:+F` / `all_checks:+F`
                # (todas as perícias) e `<attr>_check:+F` (só as do atributo). `(unless:
                # proficient)` restringe às NÃO-proficientes (Bardo Pau Pra Toda Obra =
                # +rounddown(pb/2) nas perícias sem proficiência). Fórmula com var runtime
                # (infusoes_corporais_ativas) -> None -> inerte.
                for m in re.finditer(r'(?<![a-z_])(all_checks|ability_check|(?:str|dex|con|int|wis|cha)_check):\+\s*', seg):
                    formula, quals = _split_qualifiers(_read_expr(seg, m.end()))
                    val = _eval_formula(formula, ctx)
                    if val is None:
                        continue
                    pref = m.group(1).split('_')[0]
                    sig = _EN_SIG.get(pref) if pref in _EN_SIG else None  # None = todas as perícias
                    unless_prof = any('unless' in q and 'proficient' in q for q in quals)
                    coll['check_all'].append((val, sig, unless_prof))
                # Limite de sintonização: `attr_max:sintonizacao=<N|match(classlvl){...}>`
                # (Artífice — base 5e é 3). match(classlvl) já foi avaliado por nível.
                for m in re.finditer(r'attr_max:sintonizacao\s*=\s*', seg):
                    v = _eval_formula(_read_expr(seg, m.end()), ctx)
                    if v is not None:
                        sintonizacao_max = max(sintonizacao_max, int(v))
                # Ataques: nº de ataques + perfis desarmado/natural
                for m in re.finditer(r'attacks:=\s*(\{[^}]*\}|[^,}\s]+)', seg):
                    raw = m.group(1)
                    if raw.startswith('{'):
                        v = _prog(raw, ctx['classlvl'])
                        val = int(v) if v and v.isdigit() else None
                    else:
                        val = _eval_formula(raw, ctx)
                    if val is not None:
                        coll['n_ataques'] = max(coll['n_ataques'], val)
                for m in re.finditer(r'(unarmed_strike|natural)\.dmg\s*[:=]+\s*(\{[^}]*\}[^,}]*|resource\{[^}]*\}|[^,}]+)', seg):
                    escopo, dado = m.group(1), m.group(2).strip()
                    escopo = escopo.replace('_', '-')
                    prog = re.match(r'\{[^}]*\}', dado)
                    if prog:
                        dado = _prog(prog.group(0), ctx['classlvl']) or dado
                    dado = re.sub(r'\s*\+\s*[a-z]{3}_mod', '', dado).strip()
                    ant = coll['ataque_dado'].get(escopo)
                    if ant is None or _die_size(dado) > _die_size(ant):
                        coll['ataque_dado'][escopo] = dado
                for m in re.finditer(r'(unarmed_strike|natural)\.(?:attr|dmg_attr|check_attr:atk):=\s*([a-z]{3})', seg):
                    if m.group(2) in _EN_SIG:
                        coll['ataque_attr'][m.group(1).replace('_', '-')] = _EN_SIG[m.group(2)]
                # Bônus PLANO de acerto/dano vindo de item mágico (Envoltórios, Tatuagem,
                # arma +N) OU de Estilo de Luta passivo (Arquearia/Duelo). Escopo por
                # dot-path — mapa genérico (sem if-por-tipo): 'unarmed-strike' (desarmado),
                # 'weapon' (qualquer arma), 'weapon-melee' (só corpo a corpo, Duelo),
                # 'weapon-ranged' (só à distância, Arquearia). _perfis_de_armas soma o
                # escopo genérico 'weapon' + o escopo específico do perfil.
                for m in re.finditer(r'(?<![a-z_])(unarmed_strike|unarmed|weapon|melee|ranged|weapon_melee|weapon_ranged)\.atk:\s*\+(\d+)', seg):
                    escopo = _ATK_SCOPE.get(m.group(1), 'weapon')
                    coll['atk_bonus'][escopo] = coll['atk_bonus'].get(escopo, 0) + int(m.group(2))
                for m in re.finditer(r'(?<![a-z_])(unarmed_strike|unarmed|weapon|melee|ranged|weapon_melee|weapon_ranged)\.dmg:\s*\+(\d+)', seg):
                    escopo = _ATK_SCOPE.get(m.group(1), 'weapon')
                    coll['dmg_bonus'][escopo] = coll['dmg_bonus'].get(escopo, 0) + int(m.group(2))
                # Combate com Duas Armas: `off_hand.dmg:+ability_mod` devolve o modificador
                # à mão secundária (que por padrão não soma mod positivo — regra 5e); um
                # `off_hand.dmg:+N` literal soma um bônus plano só ao perfil off_hand.
                for m in re.finditer(r'(?<![a-z_])off_hand\.dmg:\s*\+(ability_mod|\d+)', seg):
                    if m.group(1) == 'ability_mod':
                        coll['off_hand_full_mod'] = True
                    else:
                        coll['dmg_bonus']['off_hand'] = coll['dmg_bonus'].get('off_hand', 0) + int(m.group(1))
                # Defesa (Estilo de Luta) / infusões de armadura: `armor.ca:+N` SOMA à CA
                # armada final (empilha com armadura+escudo), diferente de `ca=` (base
                # desarmada, descartada com armadura). Aplicado só quando há armadura.
                for m in re.finditer(r'(?<![a-z_])armor\.ca:\s*\+(\d+)', seg):
                    coll['armor_ca_bonus'] += int(m.group(1))
                # Vantagens / desvantagens / falas
                for m in re.finditer(r'(?<![a-z_-])adv:([a-z0-9_-]+(?:\{[^}]*\})?(?:\([^)]*\))?)', seg):
                    vantagens.append('%s — %s' % (m.group(1), feat_nome))
                for m in re.finditer(r'(?<![a-z_-])(?:no_)?dadv:([a-z0-9_-]+(?:\{[^}]*\})?(?:\([^)]*\))?)', seg):
                    coll['desvantagens'].append('%s — %s' % (m.group(1), feat_nome))
                for m in re.finditer(r'(?<![a-z_-])speak:([a-z0-9_-]+)', seg):
                    notas.append('falar com %s (%s)' % (m.group(1), feat_nome))

    # ── aplica no state ──
    state['tags_brutas'] = brutas
    state['pv']['bonus_tags'] = hp_bonus
    state['pv']['maximo_calculado'] += sum(v for _, v in hp_bonus)

    # CA ciente de armadura
    dex_mod = base_ctx['dex_mod']
    equip = _armadura_equipada(personagem, dex_mod) if personagem is not None else \
        {'tem_armadura': False, 'tem_escudo': False, 'ca_armadura': None, 'fonte': None, 'escudo_bonus': 0}
    validas = [(v, n) for (v, n, gs) in ca_cands
               if not equip['tem_armadura'] and not (gs and equip['tem_escudo'])]
    desarmada = max(validas, key=lambda x: x[0], default=(10 + dex_mod, 'base sem armadura'))
    opcoes = [desarmada]
    if equip['ca_armadura'] is not None:
        opcoes.append((equip['ca_armadura'], 'armadura: %s' % (equip['fonte'] or '?')))
    melhor = max(opcoes, key=lambda x: x[0])
    ca_final = melhor[0]
    if equip['tem_escudo']:  # escudo: usa o ca_base do item (+2 padrão), não fixo
        ca_final += equip.get('escudo_bonus') or 2
    # Bônus plano que EMPILHA com a armadura (Defesa/infusões): só com armadura equipada.
    if equip['tem_armadura'] and coll.get('armor_ca_bonus'):
        ca_final += coll['armor_ca_bonus']
    state['ca'] = ca_final
    state['ca_fonte'] = melhor[1] + (' + escudo' if equip['tem_escudo'] else '') \
        + (' + %d (estilo/infusão)' % coll['armor_ca_bonus'] if (equip['tem_armadura'] and coll.get('armor_ca_bonus')) else '')

    mft = re.search(r'(\d+)\s*ft', state.get('velocidade') or '')
    if mft:
        total = int(mft.group(1)) + speed_bonus
        state['velocidade'] = '%g m / %d ft' % (round(total * 0.3, 1), total)
        state['velocidade_bonus'] = speed_bonus
    if coll['move_modes']:
        state['movimento_modos'] = coll['move_modes']
    # Resistências condicionais "se já tem X -> A, senão B" avaliadas contra o conjunto FINAL.
    for _tipo, _a, _b in resist_condicionais:
        _chosen = _a if _tipo in resist else _b
        if _chosen not in _PLACEHOLDERS and _chosen not in resist:
            resist.append(_chosen)
    state['resistencias'] = resist
    _cn = _cond_nomes()
    state['imunidades'] = imune + ['%s (condição)' % _cn.get(c, c.replace('-', ' ').capitalize()) for c in cond_imune]
    state['imunidades_condicao'] = [{'slug': c, 'nome': _cn.get(c, c.replace('-', ' ').capitalize())} for c in cond_imune]
    # Sentidos: alcance absoluto + incrementos relativos (incondicionais concedem o tipo;
    # `if_present` só soma se o tipo já existe por outra fonte). Ex.: base darkvision 60ft
    # + `sense:darkvision(range:+60ft, if_present)` -> 120ft.
    for t, add in sentidos_incr.items():
        sentidos[t] = sentidos.get(t, 0) + add
    for t, add in sentidos_incr_ifp.items():
        if t in sentidos:
            sentidos[t] += add
    state['sentidos'] = ['%s%s' % (t, ' %dft' % r if r else '') for t, r in sentidos.items()]
    state['sintonizacao_maxima'] = sintonizacao_max
    if modificadores:  # modify:<X> cross-feature (inertes, modo=combate) — para o VTT futuro
        state['modificadores'] = modificadores
    state['vantagens'] = vantagens
    if coll['desvantagens']:
        state['desvantagens_impostas'] = coll['desvantagens']
    state['notas_passivas'] = notas
    if recursos_tag:  # pools de talento/subclasse via define{} -> recursos
        for k, v in recursos_tag.items():
            state['recursos'][k] = '%s%s' % (v['max'], ' (reset %s)' % v['reset'] if v['reset'] else '')
    state['_tag'] = coll
    return state


def _arma_catalogo(nome):
    """Resolve um item de inventário ao catálogo TbItemMundano (categoria='arma')
    p/ ler a subcategoria (proficiência + à distância). Mesma ponte slug/nome de
    _maestrias_armas. None se for arma custom (não catalogada)."""
    from .models import TbItemMundano
    val = _slug(nome)
    return (TbItemMundano.objects.filter(categoria='arma', slug=val).first()
            or TbItemMundano.objects.filter(categoria='arma', slug='arma-%s' % val).first()
            or TbItemMundano.objects.filter(categoria='arma', nome__iexact=(nome or '').strip()).first())


def _mapa_maestria_por_arma(maestrias):
    """De state['maestrias_armas'] -> {slug/nome-normalizado: [nomes de maestria]}.
    Cada arma ESCOLHIDA como maestria dá acesso às maestrias daquela arma; o perfil
    de uma arma equipada exibe as maestrias se a arma foi escolhida (regra do projeto:
    a maestria é tag da arma)."""
    out = {}
    for w in (maestrias or []):
        nomes = [m.get('nome') for m in (w.get('maestrias') or []) if m.get('nome')]
        if not nomes:
            continue
        for chave in (w.get('slug'), _slug(w.get('arma') or '')):
            if chave:
                out[chave] = nomes
    return out


def _perfil_de_uma_arma(it, mec, atributos, pb, coll, prof_armas, maest_map):
    """Deriva UM perfil de ataque de arma equipada. Retorna (perfil_display, meta).
    Atributo: FOR; DES se à distância ou se acuidade (finesse -> maior mod entre
    FOR/DES). Acerto = mod + PB(se proficiente na categoria) + weapon.atk (genérico +
    escopo melee/ranged). Dano = dado + mod + weapon.dmg (idem). Maestria vai no perfil.
    meta carrega o que o perfil off_hand (mão secundária) precisa recomputar."""
    atk_b, dmg_b = coll.get('atk_bonus') or {}, coll.get('dmg_bonus') or {}
    props = set(mec.get('propriedades') or [])
    cat = _arma_catalogo(it.nome)
    subcat = (getattr(cat, 'subcategoria', '') or '') if cat else ''
    rot_prof, is_ranged = _WEAPON_CATEGORY.get(subcat, (None, 'municao' in props))
    finesse = 'acuidade' in props
    for_mod = atributos.get('FOR', {}).get('mod', 0)
    dex_mod = atributos.get('DES', {}).get('mod', 0)
    if is_ranged:
        sig, mod = 'DES', dex_mod
    elif finesse:  # acuidade: usa o MAIOR mod (regra 5e permite FOR ou DES)
        sig, mod = ('DES', dex_mod) if dex_mod >= for_mod else ('FOR', for_mod)
    else:
        sig, mod = 'FOR', for_mod
    proficiente = bool(rot_prof) and rot_prof in (prof_armas or set())
    escopo = 'weapon-ranged' if is_ranged else 'weapon-melee'
    ab = _num(atk_b.get('weapon', 0)) + _num(atk_b.get(escopo, 0))
    db = _num(dmg_b.get('weapon', 0)) + _num(dmg_b.get(escopo, 0))
    dado, _descartado = _sanitize_dano_dado(mec['dano_dado'])  # guard: só dado NdM parseável
    tipo = mec.get('dano_tipo') or ''
    slug_arma = getattr(cat, 'slug', None) or _slug(it.nome)
    maest = maest_map.get(slug_arma) or maest_map.get(_slug(it.nome)) or []
    cat_desconhecida = not rot_prof
    nota = ('categoria de arma desconhecida' if cat_desconhecida
            else ('não proficiente' if not proficiente else ''))
    perfil = {
        'escopo': escopo, 'nome': it.nome, 'atributo': sig, 'dado': dado,
        'tipo_dano': tipo, 'proficiente': proficiente,
        'bonus_ataque': _num(mod) + (_num(pb) if proficiente else 0) + ab,
        'dano': '%s %+d%s' % (dado, mod + db, ' %s' % tipo if tipo else '') if dado != '—' else '—',
        'maestria': ', '.join(maest), 'nota': nota,
    }
    meta = {'light_melee': (not is_ranged) and ('leve' in props),
            'mod': mod, 'ab_gen': atk_b.get('weapon', 0), 'cat_desconhecida': cat_desconhecida}
    return perfil, meta


def _perfis_de_armas(personagem, atributos, pb, coll, prof_armas, maestrias):
    """Perfis de ataque das ARMAS EQUIPADAS (mundanas ou mágicas com dado de arma).
    Retorna (perfis, avisos). Duas armas leves corpo a corpo -> perfil off_hand
    adicional sem mod positivo no dano (regra 5e), salvo Combate com Duas Armas."""
    if personagem is None:
        return [], []
    maest_map = _mapa_maestria_por_arma(maestrias)
    perfis, avisos, leves = [], [], []
    for it in personagem.inventario.select_related('id_item_magico').all():
        if not it.equipado:
            continue
        tags = list(it.tags_json or [])
        mag = it.id_item_magico
        if mag:  # arma mágica: dado/propriedades podem vir do catálogo mágico
            tags += [t for t in (mag.tags_json or []) if isinstance(t, str)]
        mec = mecanica_de_tags(tags)
        if not mec.get('dano_dado'):
            continue  # não é arma (escudo/armadura/maravilhoso/consumível)
        perfil, meta = _perfil_de_uma_arma(it, mec, atributos, pb, coll, prof_armas, maest_map)
        if meta['cat_desconhecida']:
            avisos.append('%s: categoria de arma não identificada no catálogo' % it.nome)
        perfis.append(perfil)
        if meta['light_melee']:
            leves.append((perfil, meta))
    # off_hand: 2+ armas leves corpo a corpo equipadas -> a última vira mão secundária.
    if len(leves) >= 2:
        base, meta = leves[-1]
        mod, dmg_b = meta['mod'], (coll.get('dmg_bonus') or {})
        off_mod = mod if coll.get('off_hand_full_mod') else min(mod, 0)
        db = dmg_b.get('weapon', 0) + dmg_b.get('off_hand', 0)
        tipo = base.get('tipo_dano') or ''
        dado = base['dado']
        perfis.append({
            'escopo': 'off_hand', 'nome': '%s (mão secundária)' % base['nome'],
            'atributo': base['atributo'], 'dado': dado, 'tipo_dano': tipo,
            'proficiente': base['proficiente'],
            'bonus_ataque': mod + (pb if base['proficiente'] else 0) + meta['ab_gen'],
            'dano': '%s %+d%s' % (dado, off_mod + db, ' %s' % tipo if tipo else ''),
            'maestria': base.get('maestria', ''), 'nota': base.get('nota', ''),
        })
    return perfis, avisos


def _ataques(coll, atributos, pb, recursos=None, personagem=None, prof_armas=None, maestrias=None):
    recursos = recursos or {}
    atk_bonus = coll.get('atk_bonus') or {}
    dmg_bonus = coll.get('dmg_bonus') or {}
    perfis, sanit_avisos = [], []
    for escopo in sorted(set(coll['ataque_dado']) | set(coll['ataque_attr'])):
        sig = coll['ataque_attr'].get(escopo, 'FOR')
        mod = _num(atributos.get(sig, {}).get('mod', 0))
        dado = coll['ataque_dado'].get(escopo, '—')
        mres = re.match(r'resource\{([a-z0-9_-]+)\}', dado or '')
        if mres:  # dado = dado do recurso (ex.: Artes Marciais -> 1d8)
            slug = mres.group(1)
            achado = next((v for k, v in recursos.items() if _slug(k.split(':')[-1]) == slug), None)
            dado = str(achado) if achado else 'dado de %s' % slug.replace('-', ' ')
        # GUARD: nunca renderiza dano cru/expressão. Só dado NdM + modificador numérico.
        dado, descartado = _sanitize_dano_dado(dado)
        if descartado is not None:
            sanit_avisos.append('perfil %s: trecho de dano não-parseável descartado (%r)'
                                % (escopo, descartado))
        ab = _num(atk_bonus.get(escopo, 0))  # bônus plano de item (Envoltórios/Tatuagem etc.)
        db = _num(dmg_bonus.get(escopo, 0))
        perfis.append({'escopo': escopo,
                       'nome': 'Ataque desarmado' if escopo == 'unarmed-strike' else 'Ataque natural',
                       'atributo': sig, 'dado': dado, 'bonus_ataque': mod + _num(pb) + ab,
                       'dano': '%s %+d' % (dado, mod + db) if dado != '—' else '—',
                       'maestria': '', 'nota': ''})
    # Perfis das ARMAS do inventário equipado (consome weapon.atk/weapon.dmg +
    # os Estilos de Luta melee/ranged/off_hand, e mostra as maestrias da arma).
    perfis_arma, avisos = _perfis_de_armas(personagem, atributos, pb, coll, prof_armas, maestrias)
    perfis += perfis_arma
    return {'quantidade': coll['n_ataques'] or 1, 'perfis': perfis, 'avisos': avisos + sanit_avisos}


def _saves(classes, atributos, pb, tag_prof=None, all_saves_bonus=0, save_bonus=None):
    prof = set()
    save_bonus = save_bonus or {}
    principal = _classe_principal(classes)
    if principal:
        for tag in (getattr(principal.id_classe, 'tags_json', None) or []):
            body = _tag_block(tag, 'saves_prof')
            if body is not None:
                raw = {x.strip().lower() for x in body.split(',') if x.strip()}
                prof = {_SAVE_TOKEN_EN.get(t, t) for t in raw}  # normaliza PT-BR/EN -> EN
    tag_prof = tag_prof or set()
    if 'all' in tag_prof:
        prof |= set(_ATTR_EN.values())
    prof |= {_SAVE_TOKEN_EN.get(p, p) for p in tag_prof
             if _SAVE_TOKEN_EN.get(p, p) in _EN_SIG}
    out = {}
    for sig, en in _ATTR_EN.items():
        p = en in prof
        out[sig] = {'proficiente': p,
                    'bonus': atributos[sig]['mod'] + (pb if p else 0) + all_saves_bonus + save_bonus.get(sig, 0)}
    return out


def _pericias_escolhidas(personagem):
    """Perícias escolhidas via `pick:pericia` (TbPersonagemEscolha tipo='pericia') como
    slugs canônicos de proficiência. É o READBACK do kind 'pericia' que alimenta o
    derive — mesmo papel de _features_de_opcoes para o kind 'opcao', mas o valor
    persistido é o slug da perícia (não uma TbOpcaojogo), então entra direto no
    conjunto de proficiências passadas a _pericias."""
    if personagem is None:
        return set()
    out = set()
    for e in personagem.escolhas.filter(tipo='pericia'):
        if e.valor:
            out.add(_norm_skill_slug(e.valor))
    return out


def _expertise_escolhidas(personagem):
    """Perícias marcadas para Especialização via `pick:pericia_expertise` (TbPersonagemEscolha
    tipo='pericia_expertise') como slugs canônicos. READBACK do kind 'pericia_expertise' —
    mesmo papel de _pericias_escolhidas para 'pericia', mas materializa expertise (dobro do
    PB) no derive. Complementa o campo manual TbPersonagemPericia.expertise (criador nv1)."""
    if personagem is None:
        return set()
    out = set()
    for e in personagem.escolhas.filter(tipo='pericia_expertise'):
        if e.valor:
            out.add(_norm_skill_slug(e.valor))
    return out


def _pericias(personagem, atributos, pb, tag_skill_prof=None, check_attr=None, check_bonus=None,
              tag_skill_expertise=None, check_all=None):
    tag_skill_prof = tag_skill_prof or set()
    tag_skill_expertise = tag_skill_expertise or set()
    check_attr = check_attr or {}
    check_bonus = check_bonus or {}
    check_all = check_all or []  # (val, sig|None, unless_prof): bônus global de teste
    base = {}
    # começa com TODAS as perícias canônicas (a ficha lista todas, proficientes ou não)
    for sl, info in _SKILL_INFO.items():
        base[sl] = {'nome': info[0], 'attr_def': info[1], 'proficiente': False, 'expertise': False}
    # sobrepõe os registros do personagem (proficiência/expertise/atributo custom)
    for per in personagem.pericias.all():
        sl = _slug(per.nome)
        d = base.get(sl) or {'nome': per.nome, 'attr_def': None, 'proficiente': False, 'expertise': False}
        if per.atributo in atributos:
            d['attr_def'] = per.atributo
        d['nome'] = per.nome
        d['proficiente'] = d['proficiente'] or per.proficiente
        d['expertise'] = d['expertise'] or per.expertise
        base[sl] = d
    for sl in tag_skill_prof:
        if sl in base:
            base[sl]['proficiente'] = True
        elif sl in _SKILL_INFO:
            base[sl] = {'nome': _SKILL_INFO[sl][0], 'attr_def': None, 'proficiente': True, 'expertise': False}
    # Especialização por tag (verbo expertise: e readback de pick:pericia_expertise): dobro
    # do PB. Expertise IMPLICA proficiência (5e), então marca ambos — senão _pericias somaria
    # só +pb (metade). Complementa o campo TbPersonagemPericia.expertise já lido acima.
    for sl in tag_skill_expertise:
        if sl in base:
            base[sl]['proficiente'] = True
            base[sl]['expertise'] = True
        elif sl in _SKILL_INFO:
            base[sl] = {'nome': _SKILL_INFO[sl][0], 'attr_def': None, 'proficiente': True, 'expertise': True}
    out = []
    for sl, d in base.items():
        sig = check_attr.get(sl) or d['attr_def'] or (_SKILL_INFO[sl][1] if sl in _SKILL_INFO else 'FOR')
        mod = atributos.get(sig, {}).get('mod', 0)
        bonus = mod + (pb if d['proficiente'] else 0) + (pb if d['expertise'] else 0) + check_bonus.get(sl, 0)
        # bônus GLOBAL de teste (ability_check/all_checks/<attr>_check): aplica ao atributo
        # da perícia (ou a todas se sig-filtro None); `unless_prof` só nas não-proficientes
        # (Pau Pra Toda Obra — não empilha com a proficiência).
        for val, sig_filt, unless_prof in check_all:
            if sig_filt is not None and sig_filt != sig:
                continue
            if unless_prof and (d['proficiente'] or d['expertise']):
                continue
            bonus += val
        out.append({'nome': d['nome'], 'atributo': sig, 'proficiente': d['proficiente'],
                    'expertise': d['expertise'], 'bonus': bonus})
    return sorted(out, key=lambda x: x['nome'])


def _proficiencias(personagem):
    idiomas, ferramentas, outras = [], [], []
    for p in personagem.proficiencias.all():
        if p.tipo == 'idioma':
            idiomas.append(p.nome)
        elif p.tipo == 'ferramenta':
            ferramentas.append(p.nome)
        else:
            outras.append('%s: %s' % (p.tipo, p.nome))
    return idiomas, ferramentas, outras


def _apply_attr_asi(features, escolhas, atributos):
    """Pré-passe: ASI passivo via tag (attr:<x>_score+N) — soma em valor+bonus e
    registra no breakdown (mantém base+Σbreakdown == valor); aplica o PISO
    `attr_set:<x>_score=N` (score := max(atual, N), regra 5e das Manoplas do Poder
    do Ogro / Cinto de Força de Gigante) DEPOIS dos aditivos; aplica o teto
    `attr_max:<x>_score=N`."""
    caps = {}
    floors = {}  # sig -> (N, feat_nome): maior piso pedido por atributo
    for _o, fonte, obj, _cl in features:
        feat_nome = getattr(obj, 'nome', fonte)
        for t in (getattr(obj, 'tags_json', None) or []):
            if not isinstance(t, str):
                continue
            for seg in _passive_segments(_resolve_match(t, escolhas)):
                for m in re.finditer(r'attr:([a-z]{3})_score\s*\+\s*(\d+)', seg):
                    sig = _EN_SIG.get(m.group(1))
                    if sig:
                        n = int(m.group(2))
                        atributos[sig]['valor'] += n
                        atributos[sig]['bonus'] += n
                        atributos[sig].setdefault('breakdown', []).append(
                            {'origem': feat_nome + ' (tag)', 'valor': n})
                # PISO/SET de atributo: fixa o score em N (só eleva; sem efeito se já maior).
                for m in re.finditer(r'attr_set:([a-z]{3})_score\s*=\s*(\d+)', seg):
                    sig = _EN_SIG.get(m.group(1))
                    if sig:
                        n = int(m.group(2))
                        atual = floors.get(sig)
                        if atual is None or n > atual[0]:
                            floors[sig] = (n, feat_nome)
                for m in re.finditer(r'attr_max:([a-z]{3})_score\s*=\s*(\d+)', seg):
                    sig = _EN_SIG.get(m.group(1))
                    if sig:
                        caps[sig] = min(caps.get(sig, 999), int(m.group(2)))
    # PISO aplicado APÓS os aditivos: alvo = max(valor_atual, N), sem ultrapassar um teto
    # existente; o delta entra no breakdown para manter valor == base + Σbreakdown.
    for sig, (n, feat_nome) in floors.items():
        alvo = min(n, caps[sig]) if sig in caps else n
        if atributos[sig]['valor'] < alvo:
            delta = alvo - atributos[sig]['valor']
            atributos[sig]['valor'] = alvo
            atributos[sig]['bonus'] += delta
            atributos[sig].setdefault('breakdown', []).append(
                {'origem': feat_nome + ' (tag)', 'valor': delta})
    for sig, cap in caps.items():
        if atributos[sig]['valor'] > cap:
            ajuste = cap - atributos[sig]['valor']
            atributos[sig]['valor'] = cap
            atributos[sig]['bonus'] += ajuste
            atributos[sig].setdefault('breakdown', []).append({'origem': 'teto %d' % cap, 'valor': ajuste})


def derive(personagem):
    """Deriva o estado completo (estrutural + tags passivas) de um TbPersonagem."""
    avisos = []

    # 1. Atributos: BASE (point-buy) + Σ bônus (TbPersonagemAtributoBonus) + breakdown
    bonus_por_attr = {}
    for b in personagem.atributo_bonus.all():
        bonus_por_attr.setdefault(b.atributo, []).append((b.origem, b.valor))
    atributos = {}
    for campo, sigla, rotulo in ATRIBUTOS:
        base = int(getattr(personagem, campo))
        fontes = bonus_por_attr.get(sigla, [])
        atributos[sigla] = {'base': base, 'bonus': sum(v for _, v in fontes),
                            'valor': base + sum(v for _, v in fontes), 'mod': 0, 'rotulo': rotulo,
                            'breakdown': [{'origem': o, 'valor': v} for o, v in fontes]}

    # 2. Classes / nível / features (inclui antecedente)
    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse').order_by('-principal', 'id'))
    nivel_total = sum(int(c.nivel or 0) for c in classes) or int(personagem.nivel or 1)
    features = (_features_de_classe(classes) + _tracos_raciais(personagem)
                + _antecedente(personagem) + _talentos(personagem)
                + _features_de_itens(personagem) + _features_de_opcoes(personagem))
    escolhas, listas = _collect_escolhas(personagem, features)

    # 3. Pré-passe de ASI passivo (tag) → mods / PB / PV / ctx
    _apply_attr_asi(features, escolhas, atributos)
    for sig in atributos:
        atributos[sig]['mod'] = modificador(atributos[sig]['valor'])
    con_mod = atributos['CON']['mod']
    pb = bonus_proficiencia(nivel_total)
    pv = _calcular_pv(personagem, classes, con_mod, avisos)
    ctx = _build_ctx(nivel_total, pb, atributos)
    _sm = _spell_mod(classes, atributos)
    ctx['spell_mod'] = _sm

    # aviso: antecedente preenchido mas sem tags (habilidade não aplicada)
    if personagem.id_antecedente_id and not (personagem.id_antecedente.tags_json or []):
        avisos.append(f"Antecedente '{personagem.id_antecedente.nome}' sem tags_json — habilidade não aplicada.")

    state = {
        '_ctx': ctx,
        'personagem': {'id': personagem.id_personagem, 'nome': personagem.nome},
        'nivel_total': nivel_total,
        'bonus_proficiencia': pb,
        'atributos': atributos,
        'pv': {'maximo_calculado': pv['valor'], 'pv_completo': pv['completo'],
               'atual': personagem.pv_atual, 'temporario': personagem.pv_temporario},
        'iniciativa': atributos['DES']['mod'] + int(personagem.iniciativa_bonus or 0),
        'ca': personagem.ca,
        'velocidade': personagem.velocidade,
        'classes': [{'classe': c.id_classe.nome, 'subclasse': c.id_subclasse.nome if c.id_subclasse_id else None,
                     'nivel': c.nivel, 'principal': c.principal} for c in classes],
        'features': [{'origem': o, 'fonte': f, 'nome': getattr(obj, 'nome', ''),
                      'nivel': getattr(obj, 'niveladquirido', getattr(obj, 'nivel_requisito', None)),
                      'descricao': (getattr(obj, 'descricao', '') or getattr(obj, 'descricao_markdown', '') or '')}
                     for (o, f, obj, _cl) in features if not getattr(obj, 'table_only', False)],
        'recursos': _recursos(classes),
        'recursos_por_tipo': _recursos_por_tipo(classes),
        'maestrias_armas': _maestrias_armas(personagem),
        'magias': _magias_personagem(personagem),
        'inventario': _inventario(personagem),
        'grants_antecedente': background_grants(personagem.id_antecedente) if personagem.id_antecedente_id else None,
        'picks': listas,
        'avisos': avisos,
    }

    # Progressão por aventuras: nº de aventuras define o nível-TETO + rank.
    av = int(getattr(personagem, 'aventuras', 0) or 0)
    nivel_av = nivel_por_aventuras(av)
    state['progressao'] = {
        'aventuras': av, 'nivel_aventuras': nivel_av, 'nivel_label': nivel_label(nivel_av),
        'nivel_max': min(nivel_av, 20), 'rank': rank_por_nivel(nivel_av),
        'braseiros': int(getattr(personagem, 'braseiros', 0) or 0),
        'no_teto': nivel_total >= min(nivel_av, 20),
        # Ouro (PO) acumulado esperado pela progressão de aventuras (linha informativa;
        # NÃO é a carteira — compras/vendas continuam vivendo em carteira_pc/TbTransacao).
        'ouro_esperado_po': ouro_de_progressao(av),
    }

    apply_tags(state, features, personagem, escolhas)

    # pós-tags
    tag = state['_tag']
    state['saves'] = _saves(classes, atributos, pb, tag['save_prof'], tag['all_saves'], tag['save_bonus'])
    state['pericias'] = _pericias(personagem, atributos, pb,
                                  tag['skill_prof'] | _pericias_escolhidas(personagem),
                                  tag['check_attr'], tag['check_bonus'],
                                  tag_skill_expertise=(tag['skill_expertise'] | _expertise_escolhidas(personagem)),
                                  check_all=tag['check_all'])
    idiomas, ferramentas, outras = _proficiencias(personagem)
    state['idiomas'] = sorted(set(idiomas) | set(tag['idiomas']))
    _pc = _proficiencias_classe(classes)
    state['ferramentas'] = sorted(set(ferramentas) | set(tag['ferramentas']) | set(_pc['classe_ferramentas']))
    state['proficiencias_armadura'] = _pc['classe_armaduras'] + sorted(set(tag['armaduras']))
    state['proficiencias_arma'] = _pc['classe_armas'] + sorted(set(tag['armas']))
    # Perfil de ataque de arma precisa do conjunto de proficiências de arma (rótulos de
    # categoria da classe/multiclasse + concedidas por tag) para decidir se soma o PB.
    prof_armas = (set(_pc['classe_armas']) | set(_pc['multiclasse_armas']) | set(tag['armas']))
    state['ataques'] = _ataques(tag, atributos, pb, state['recursos'], personagem,
                                prof_armas, state.get('maestrias_armas'))
    state['prof_multiclasse_armadura'] = _pc['multiclasse_armaduras']
    state['prof_multiclasse_arma'] = _pc['multiclasse_armas']
    state['prof_multiclasse_ferramenta'] = _pc['multiclasse_ferramentas']
    state['outras_proficiencias'] = outras
    state['iniciativa'] += tag['initiative']

    # Maestria de arma é TROCÁVEL se a habilidade que a concede (pick:arma) tiver a tag 'trocavel'.
    state['maestria_trocavel'] = any(
        any('pick:arma' in str(t) for t in (getattr(obj, 'tags_json', None) or []))
        and any(str(t).strip() == 'trocavel' for t in (getattr(obj, 'tags_json', None) or []))
        for (_o, _f, obj, _cl) in features)

    # Mochila: carteira (PC -> PO/PP/PC) + peso total carregado.
    _cpc = int(getattr(personagem, 'carteira_pc', 0) or 0)
    state['carteira'] = {'pc_total': _cpc, 'po': _cpc // 100, 'pp': (_cpc % 100) // 10, 'pc': _cpc % 10}

    def _peso_item(it):
        try:
            return float(str(it.get('peso') or 0).replace(',', '.').split()[0]) * (it.get('qtd') or 1)
        except (ValueError, AttributeError, IndexError):
            return 0.0
    state['peso_total'] = round(sum(_peso_item(it) for it in state['inventario']), 2)

    state.pop('_ctx', None)
    state.pop('_tag', None)
    return state
