# -*- coding: utf-8 -*-
"""Motor de derivação da ficha de personagem.

Recebe um TbPersonagem e deriva o estado mecânico (atributos, nível,
proficiência, PV, features ativas, recursos…) a partir do conteúdo do banco.

Fases:
- ESTRUTURAL (este módulo): tudo que não depende das tags — atributos, nível
  total, bônus de proficiência, PV pelo dado de vida, features por nível de
  classe (subclasse só a partir do nível 3 DA CLASSE), traços raciais e
  recursos de classe. Multiclasse é suportado: cada classe tem seu próprio
  nível e sua própria subclasse.
- TAGS (a fazer): `apply_tags()` é o ponto de plugue para o avaliador das
  `tags_json` (perícias/resistências/efeitos via funções). Hoje ele só coleta
  as tags cruas das features ativas — o parser/avaliador entra quando o
  vocabulário (docs/criador-personagem/vocabulario-tags-json.md) for fechado e
  as tags estiverem no banco.

Lacunas de dado conhecidas viram avisos em `state['avisos']` (ex.: dado de vida
não cadastrado na classe → PV não calculável).
"""

import re

# (campo no modelo, sigla PT, rótulo)
ATRIBUTOS = [
    ('forca', 'FOR', 'Força'),
    ('destreza', 'DES', 'Destreza'),
    ('constituicao', 'CON', 'Constituição'),
    ('inteligencia', 'INT', 'Inteligência'),
    ('sabedoria', 'SAB', 'Sabedoria'),
    ('carisma', 'CAR', 'Carisma'),
]


def modificador(valor):
    """Modificador de atributo D&D: (valor - 10) // 2 (floor)."""
    return (int(valor) - 10) // 2


def bonus_proficiencia(nivel_total):
    """Fórmula padrão: 2 no nível 1, +1 a cada 4 níveis."""
    return 2 + (max(1, int(nivel_total)) - 1) // 4


def _dado_de_vida(texto):
    """Extrai o N de '1dN' (ex.: '1d10 por nível de Caçador' -> 10)."""
    if not texto:
        return None
    m = re.search(r'd\s*(\d+)', str(texto))
    return int(m.group(1)) if m else None


def _classe_principal(classes):
    if not classes:
        return None
    for c in classes:
        if getattr(c, 'principal', False):
            return c
    return classes[0]


def _calcular_pv(personagem, classes, con_mod, avisos):
    """PV pelo dado de vida.

    - 1º nível da classe principal = dado cheio (1d10 -> 10).
    - Demais níveis (qualquer classe) = dado/2 + 1 (1d10 -> 6, 1d12 -> 7).
    - Cada nível soma o modificador de Constituição.
    """
    principal = _classe_principal(classes)
    total = 0
    faltou = False
    for c in classes:
        die = _dado_de_vida(getattr(c.id_classe, 'dado_vida', None))
        if die is None:
            faltou = True
            avisos.append(
                f"Dado de vida não cadastrado em '{c.id_classe.nome}' — PV parcial."
            )
            continue
        for nivel_idx in range(int(c.nivel or 0)):
            primeiro = (c is principal and nivel_idx == 0)
            total += die if primeiro else (die // 2 + 1)
            total += con_mod
    return {'valor': total, 'completo': not faltou}


def _features_de_classe(classes):
    """Habilidades ativas por classe, respeitando o nível DA classe e a regra
    da subclasse (só a partir do 3º nível da classe)."""
    from .models import TbClassehabilidade
    out = []
    for c in classes:
        nivel = int(c.nivel or 0)
        base = TbClassehabilidade.objects.filter(
            id_classe=c.id_classe, id_subclasse__isnull=True,
            niveladquirido__lte=nivel,
        ).order_by('niveladquirido', 'nome')
        for h in base:
            out.append(('classe', c.id_classe.nome, h))
        if c.id_subclasse_id and nivel >= 3:
            sub = TbClassehabilidade.objects.filter(
                id_subclasse=c.id_subclasse, niveladquirido__lte=nivel,
            ).order_by('niveladquirido', 'nome')
            for h in sub:
                out.append(('subclasse', c.id_subclasse.nome, h))
    return out


def _tracos_raciais(personagem):
    """Traços passivos da raça + linhagem/essência escolhidas (talentos não —
    esses são escolhas explícitas)."""
    from .models import TbTracoracial
    out = []
    if not personagem.id_raca_id:
        return out
    base = TbTracoracial.objects.filter(
        id_raca=personagem.id_raca, talento_racial=False,
        id_linhagem__isnull=True, id_essencia__isnull=True,
    )
    for t in base:
        out.append(('raca', personagem.id_raca.nome, t))
    if personagem.id_linhagem_id:
        for t in TbTracoracial.objects.filter(id_linhagem=personagem.id_linhagem, talento_racial=False):
            out.append(('linhagem', personagem.id_linhagem.nome, t))
    if personagem.id_essencia_id:
        for t in TbTracoracial.objects.filter(id_essencia=personagem.id_essencia, talento_racial=False):
            out.append(('essencia', personagem.id_essencia.nome, t))
    return out


def _recursos(classes):
    """Valor atual de cada recurso de classe: a maior linha com nível <= nível
    da classe (inclui recursos de subclasse quando aplicável)."""
    from .models import TbRecursoclasse
    from django.db.models import Q
    recursos = {}
    for c in classes:
        nivel = int(c.nivel or 0)
        filtro = Q(id_classe=c.id_classe, id_subclasse__isnull=True)
        if c.id_subclasse_id and nivel >= 3:
            filtro |= Q(id_subclasse=c.id_subclasse)
        qs = TbRecursoclasse.objects.filter(filtro, nivel__lte=nivel).order_by('nome', 'nivel')
        atual = {}
        for r in qs:
            atual[r.nome] = r.valor  # a última (maior nível <= nivel) vence
        for nome, valor in atual.items():
            recursos[f'{c.id_classe.nome}: {nome}'] = valor
    return recursos


def apply_tags(state, features):
    """Ponto de plugue para o avaliador das tags_json (FASE 2).

    Hoje só coleta as tags cruas das features ativas em `state['tags_brutas']`.
    Quando o vocabulário fechar e as tags estiverem no banco, este método
    interpreta as funções (if/save/roll/match/…) e aplica os efeitos em
    state['pericias'], state['resistencias'], state['movimentos'], etc.
    """
    brutas = []
    for origem, fonte, obj in features:
        tags = getattr(obj, 'tags_json', None)
        if tags:
            brutas.append({'origem': origem, 'fonte': fonte,
                           'nome': getattr(obj, 'nome', ''), 'tags': tags})
    state['tags_brutas'] = brutas
    return state


def derive(personagem):
    """Deriva o estado completo (estrutural) de um TbPersonagem."""
    avisos = []

    # 1. Atributos e modificadores
    atributos = {}
    for campo, sigla, rotulo in ATRIBUTOS:
        valor = getattr(personagem, campo)
        atributos[sigla] = {'valor': valor, 'mod': modificador(valor), 'rotulo': rotulo}
    con_mod = atributos['CON']['mod']

    # 2. Classes e nível total
    classes = list(
        personagem.classes.select_related('id_classe', 'id_subclasse').order_by('-principal', 'id')
    )
    nivel_total = sum(int(c.nivel or 0) for c in classes) or int(personagem.nivel or 1)
    pb = bonus_proficiencia(nivel_total)

    # 3. PV
    pv = _calcular_pv(personagem, classes, con_mod, avisos)

    # 4. Features ativas
    features_classe = _features_de_classe(classes)
    tracos = _tracos_raciais(personagem)
    features = features_classe + tracos

    # 5. Recursos
    recursos = _recursos(classes)

    # 6. Iniciativa / saves base (proficiência de save vem da classe/tag — TODO)
    iniciativa = atributos['DES']['mod'] + int(personagem.iniciativa_bonus or 0)

    state = {
        'personagem': {'id': personagem.id_personagem, 'nome': personagem.nome},
        'nivel_total': nivel_total,
        'bonus_proficiencia': pb,
        'atributos': atributos,
        'pv': {
            'maximo_calculado': pv['valor'], 'pv_completo': pv['completo'],
            'atual': personagem.pv_atual, 'temporario': personagem.pv_temporario,
        },
        'iniciativa': iniciativa,
        'ca': personagem.ca,
        'velocidade': personagem.velocidade,
        'classes': [
            {'classe': c.id_classe.nome, 'subclasse': c.id_subclasse.nome if c.id_subclasse_id else None,
             'nivel': c.nivel, 'principal': c.principal} for c in classes
        ],
        'features': [
            {'origem': o, 'fonte': f, 'nome': getattr(obj, 'nome', ''),
             'nivel': getattr(obj, 'niveladquirido', getattr(obj, 'nivel_requisito', None))}
            for (o, f, obj) in features
        ],
        'recursos': recursos,
        'avisos': avisos,
    }

    apply_tags(state, features)
    return state
