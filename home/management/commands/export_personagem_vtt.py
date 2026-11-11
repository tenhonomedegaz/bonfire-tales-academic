# -*- coding: utf-8 -*-
"""Exporta personagens VIVOS (dado de usuário/memória) para o contrato FINO do VTT.

    manage.py export_personagem_vtt <personagem_id>            # JSON no stdout
    manage.py export_personagem_vtt <personagem_id> -o p.json  # JSON em arquivo
    manage.py export_personagem_vtt --todos -o DIR             # um arquivo por personagem

Doutrina da rodada (bonfire-vtt): o SITE exporta a saída CRUA do derive + PKs do
banco; TODO mapeamento para ids de habilidade do pack acontece no compilador do
VTT (tools/bonfire-compiler), dono das convenções de slug. Por isso o contrato é
FINO e estável (versao_contrato=1) e NADA aqui reprocessa tags — quem deriva é o
`character_engine.derive` (a MESMA fonte da ficha), e os totais multiclasse de
espaços de magia vêm de `views._spell_slot_totals` (a MESMA conta da aba Magias).

Evolução v1.1 (ADITIVA — pedidos B5 do VTT): derive.salvaguardas (6 entradas, a
MESMA conta da ficha em character_engine._saves), derive.pericias ganha o
atributo base de cada perícia (as 18 canônicas já saíam) e derive.idiomas (já
saía na v1 — mantido). O consumidor (personagem.mts do compilador) valida
versao_contrato com z.literal(1) — igualdade EXATA, não "mínimo compatível" —
então o topo continua 1 e a evolução aditiva é sinalizada por `versao_menor`.

Determinismo: chaves ordenadas, listas em ordem estável (por pk/id_fonte),
ensure_ascii=False, indent 2 e LF — re-exportar dado inalterado é byte-idêntico.

Lacunas de dado NUNCA derrubam o export: o que não dá para derivar vira uma
entrada em `avisos` e o resto sai (nada é inventado).
"""
import json
import re
import subprocess

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

VERSAO_CONTRATO = 1
# versao_menor: 0 = contrato v1 original; 1 = +salvaguardas, +atributo nas
# perícias. Só cresce em mudança ADITIVA (o consumidor zod é não-estrito e
# ignora campos que não conhece; breaking change exigiria subir VERSAO_CONTRATO
# em conjunto com o schema do compilador).
VERSAO_MENOR = 1

# Ordem CANÔNICA das siglas de atributo (a mesma da ficha/_ATTR_EN do derive):
# listas do contrato precisam de ordem estável para o re-export byte-idêntico.
_ORDEM_SIGLAS = ('FOR', 'DES', 'CON', 'INT', 'SAB', 'CAR')

# id_fonte sintéticos (recursos derivados sem linha própria no banco). O prefixo
# identifica a origem para o compilador: modelo real usa 'TbRecursoclasse:<pk>',
# recurso de tag usa 'tag:<slug>' (mesmo id dos cards da ficha).
_ID_ESPACO_MAGIA = 'espaco-magia:%d'
_ID_DADO_VIDA = 'dado-de-vida:d%d'

# mesmo padrão dos cards de recurso-de-tag da ficha (views._consumiveis_ficha_cards):
# valor "N (reset X)" vindo de define{...} nas tags.
_TAG_RES_RE = re.compile(r'^\s*(\d+)\s*\(reset\s+([^)]+)\)\s*$')


def _gerado_de():
    """Hash do commit do site, se barato de obter (git disponível). None = omite."""
    try:
        from django.conf import settings
        out = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True,
                             text=True, timeout=5, cwd=str(settings.BASE_DIR))
        h = (out.stdout or '').strip()
        return h if out.returncode == 0 and len(h) == 40 else None
    except Exception:
        return None


def _slug_pericia(nome):
    """Nome PT da perícia -> slug canônico de _SKILL_INFO (fallback: slug genérico)."""
    from home.character_engine import _SKILL_INFO, _slug
    nome2slug = {info[0]: sl for sl, info in _SKILL_INFO.items()}
    return nome2slug.get(nome) or _slug(nome)


def _bloco_derive(state):
    """Serializa a fatia FINA do derive que o token precisa (números prontos)."""
    atributos = {sig: {'valor': a['valor'], 'mod': a['mod']}
                 for sig, a in (state.get('atributos') or {}).items()}
    # v1.1: cada perícia leva o atributo BASE efetivo (o mesmo `sig` que a ficha
    # usa na conta — já considera override manual e check_attr de tag).
    pericias = [{'id': _slug_pericia(p['nome']), 'nome': p['nome'],
                 'atributo': p.get('atributo'),
                 'proficiente': bool(p['proficiente']), 'bonus': int(p['bonus'])}
                for p in (state.get('pericias') or [])]
    # v1.1: salvaguardas — a MESMA conta da ficha (character_engine._saves:
    # mod + PB se proficiente + bônus de tag), em ordem canônica de siglas.
    saves = state.get('saves') or {}
    salvaguardas = [{'atributo': sig,
                     'proficiente': bool(saves[sig].get('proficiente')),
                     'bonus': int(saves[sig].get('bonus') or 0)}
                    for sig in _ORDEM_SIGLAS if sig in saves]
    # Percepção passiva = 10 + bônus da perícia Percepção (mesma conta do JS da
    # ficha); sem a perícia na lista, cai em 10 + mod de SAB.
    sab_mod = int(((state.get('atributos') or {}).get('SAB') or {}).get('mod') or 0)
    perc = next((p['bonus'] for p in pericias if p['id'] == 'percepcao'), sab_mod)
    return {
        'atributos': atributos,
        'pb': int(state.get('bonus_proficiencia') or 0),
        'ca': int(state.get('ca') or 10),
        'pv_max': int((state.get('pv') or {}).get('maximo_calculado') or 0),
        'percepcao_passiva': 10 + int(perc),
        'deslocamento': state.get('velocidade') or '',
        'iniciativa': int(state.get('iniciativa') or 0),
        'salvaguardas': salvaguardas,
        'pericias': pericias,
        'idiomas': list(state.get('idiomas') or []),
        'resistencias': list(state.get('resistencias') or []),
        'imunidades': list(state.get('imunidades') or []),
    }


def _recursos_espacos_magia(personagem, classes, avisos):
    """Espaços de magia por círculo com os totais MULTICLASSE que o site já computa
    (views._spell_slot_totals — a mesma conta da aba Magias da ficha)."""
    from home import views as site_views
    out = []
    try:
        casters = []
        for pc in classes:
            info = site_views._classe_spellcasting_info(
                pc.id_classe, nivel_habilidades=int(pc.nivel or 1),
                subclasse=site_views._caster_subclasse(pc))
            if info:
                casters.append({'pc': pc, 'info': info})
        totals = site_views._spell_slot_totals(casters) if casters else {}
        for circulo in sorted(totals):
            total = int(totals[circulo] or 0)
            if total <= 0:
                continue
            out.append({'id_fonte': _ID_ESPACO_MAGIA % circulo,
                        'nome': 'Espaços de Magia (%dº círculo)' % circulo,
                        'circulo': circulo, 'max': total, 'reset': 'long-rest'})
    except Exception as e:  # dado quebrado não derruba o export
        avisos.append('Espaços de magia não exportados: %s' % e)
    return out


def _recursos_dados_de_vida(classes, avisos):
    """Dados de vida: total = nível da classe, agregados por tamanho do dado."""
    from home.character_engine import _dado_de_vida_classe
    por_dado = {}
    for c in classes:
        die = _dado_de_vida_classe(c.id_classe)
        if die is None:
            avisos.append("Dado de vida não cadastrado em '%s' — dados de vida parciais."
                          % c.id_classe.nome)
            continue
        por_dado[die] = por_dado.get(die, 0) + int(c.nivel or 0)
    return [{'id_fonte': _ID_DADO_VIDA % die, 'nome': 'Dados de Vida (d%d)' % die,
             'dado': 'd%d' % die, 'max': n, 'reset': 'long-rest'}
            for die, n in sorted(por_dado.items()) if n > 0]


def _recursos_consumiveis_export(personagem, classes, state, avisos):
    """Recursos CONSUMÍVEIS: os de classe (TbRecursoclasse, com PK) + os de tag
    (define{max, reset} de habilidades — mesmo recorte dos cards da ficha)."""
    from home.character_engine import _recursos_consumiveis
    from home.models import TbRecursoclasse
    out, vistos_nomes, vistos_slugs = [], set(), set()

    # PK por nome dentro das classes do personagem (o helper deduplica por nome,
    # então a primeira linha que casa serve de id_fonte).
    pk_por_nome = {}
    for r in (TbRecursoclasse.objects
              .filter(id_classe__in=[c.id_classe_id for c in classes])
              .order_by('id_recurso')):
        pk_por_nome.setdefault(r.nome, r.id_recurso)

    try:
        for r in _recursos_consumiveis(personagem, classes):
            vistos_nomes.add(r['nome'])
            vistos_slugs.add(r.get('slug') or '')
            pk = pk_por_nome.get(r['nome'])
            if pk is None:
                avisos.append("Recurso '%s' sem PK localizável — exportado sem id_fonte de banco."
                              % r['nome'])
            out.append({'id_fonte': ('TbRecursoclasse:%d' % pk) if pk else 'TbRecursoclasse:?',
                        'nome': r['nome'], 'max': int(r['maximo']),
                        'reset': r.get('reset') or 'manual'})
    except Exception as e:
        avisos.append('Recursos de classe não exportados: %s' % e)

    # recursos definidos por TAG (state['recursos'] com valor 'N (reset X)') —
    # mesmo filtro anti-duplicata de views._consumiveis_ficha_cards.
    for nome, val in sorted((state.get('recursos') or {}).items()):
        nome_limpo = str(nome or '').strip()
        if (not nome_limpo or nome_limpo in vistos_nomes
                or nome_limpo.split(':')[-1].strip() in vistos_nomes):
            continue
        tag_slug = slugify(nome_limpo.split(':')[-1].strip() or nome_limpo)
        if tag_slug in vistos_slugs:
            continue
        m = _TAG_RES_RE.match(str(val or '').strip())
        if not m or int(m.group(1)) <= 0:
            continue
        out.append({'id_fonte': 'tag:%s' % slugify(nome_limpo), 'nome': nome_limpo,
                    'max': int(m.group(1)), 'reset': m.group(2).strip()})
    return out


def _habilidades(personagem, classes):
    """Toda feature ATIVA (o MESMO conjunto do derive: classe/subclasse, traços,
    antecedente, talentos, itens equipados, opções escolhidas) — só PK + nome;
    nenhum reprocessamento de tag (o compilador do VTT é quem mapeia)."""
    from home.character_engine import _features_do_personagem
    out, vistos = [], set()
    for (origem, _fonte, obj, _cl) in _features_do_personagem(personagem, classes):
        if getattr(obj, 'table_only', False):
            continue  # linha só-de-tabela (progressão) não é habilidade jogável
        fonte = '%s:%s' % (type(obj).__name__, obj.pk)
        if (fonte, origem) in vistos:
            continue
        vistos.add((fonte, origem))
        out.append({'fonte': fonte, 'nome': getattr(obj, 'nome', '') or str(_fonte),
                    'origem': origem})
    return sorted(out, key=lambda h: (h['fonte'], h['origem']))


def _magias(personagem):
    """Magias do personagem direto do banco. origem: 'concedida' = materializada por
    feature (_sync_magias_concedidas marca sempre_preparada); 'classe' = o resto."""
    out = []
    for m in personagem.magias.select_related('id_magia').order_by('id'):
        out.append({'magia_pk': m.id_magia_id, 'nome': m.nome,
                    'circulo': int(m.nivel or 0),
                    'origem': 'concedida' if m.sempre_preparada else 'classe',
                    'preparada': bool(m.preparada)})
    return out


def exportar_personagem(personagem, gerado_de=None):
    """Monta o dict do contrato v1 para UM personagem. Nunca lança por dado quebrado:
    o que faltar vira aviso e o restante sai."""
    from home.character_engine import derive
    avisos = []

    classes = list(personagem.classes.select_related('id_classe', 'id_subclasse')
                   .order_by('-principal', 'id'))
    state = None
    try:
        state = derive(personagem)
        avisos.extend(state.get('avisos') or [])
    except Exception as e:
        avisos.append('derive falhou — exportado só o esqueleto do banco: %s' % e)

    nivel_total = (int(state['nivel_total']) if state
                   else (sum(int(c.nivel or 0) for c in classes) or int(personagem.nivel or 1)))

    bloco_personagem = {
        'pk': personagem.pk,
        'nome': personagem.nome,
        'nivel_total': nivel_total,
        'classes': [{'classe_pk': c.id_classe_id, 'nome': c.id_classe.nome,
                     'nivel': int(c.nivel or 0)} for c in classes],
        'raca_pk': personagem.id_raca_id,
        'raca_nome': personagem.id_raca.nome if personagem.id_raca_id else None,
    }
    if personagem.id_essencia_id:
        bloco_personagem['essencia'] = {'pk': personagem.id_essencia_id,
                                        'nome': personagem.id_essencia.nome}

    recursos = _recursos_espacos_magia(personagem, classes, avisos)
    recursos += _recursos_dados_de_vida(classes, avisos)
    recursos += _recursos_consumiveis_export(personagem, classes, state or {}, avisos)
    recursos.sort(key=lambda r: (r['id_fonte'], r['nome']))

    # Moedas: carteira exata em PC + decomposição (a mesma do derive/ficha).
    if state:
        cart = state.get('carteira') or {}
        moedas = {'pc_total': cart.get('pc_total', 0), 'po': cart.get('po', 0),
                  'pp': cart.get('pp', 0), 'pc': cart.get('pc', 0)}
    else:
        from home.moeda import decompor
        _neg, po, pp, pc = decompor(int(personagem.carteira_pc or 0))
        moedas = {'pc_total': int(personagem.carteira_pc or 0), 'po': po, 'pp': pp, 'pc': pc}

    pv_max = int((state.get('pv') or {}).get('maximo_calculado') or 0) if state \
        else int(personagem.pv_maximo or 0)

    data = {
        'versao_contrato': VERSAO_CONTRATO,
        'versao_menor': VERSAO_MENOR,
        'personagem': bloco_personagem,
        'derive': _bloco_derive(state) if state else None,
        'recursos': recursos,
        'habilidades': _habilidades(personagem, classes),
        'magias': _magias(personagem),
        # A ficha só exporta uma concessão já registrada no livro de recursos.
        'inspiracao': bool(personagem.recursos.filter(
            chave='heroic_inspiration', atual=1, maximo=1).exclude(origem='').exists()),
        'moedas': moedas,
        # Estado inicial NEUTRO de sessão (o VTT é quem evolui isso em mesa).
        'estado_mesa': {'pv_atual': pv_max, 'pv_temp': 0, 'morte_s': 0, 'morte_f': 0},
        'avisos': avisos,
    }
    if gerado_de:
        data['gerado_de'] = gerado_de
    return data


def serializar(data):
    """JSON canônico do contrato: chaves ordenadas, UTF-8 real, indent 2, LF final."""
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


class Command(BaseCommand):
    help = ('Exporta personagem(ns) vivo(s) do banco para o contrato fino do VTT '
            '(JSON determinístico; ver bonfire-vtt/tools/bonfire-compiler).')

    def add_arguments(self, parser):
        parser.add_argument('personagem_id', nargs='?', type=int,
                            help='PK do personagem (omitir com --todos).')
        parser.add_argument('-o', '--output', default=None,
                            help='Arquivo de saída (ou DIRETÓRIO com --todos). Sem -o: stdout.')
        parser.add_argument('--todos', action='store_true',
                            help='Exporta TODOS os personagens, um arquivo por PK, no diretório -o.')

    def _resumo(self, data):
        p = data['personagem']
        return ('pk=%s nome=%r nivel=%s recursos=%d habilidades=%d magias=%d avisos=%d'
                % (p['pk'], p['nome'], p['nivel_total'], len(data['recursos']),
                   len(data['habilidades']), len(data['magias']), len(data['avisos'])))

    def handle(self, *args, **opt):
        import os
        from home.models import TbPersonagem
        gerado_de = _gerado_de()

        if opt['todos']:
            out_dir = opt['output'] or os.path.join('scratch', 'vtt_personagens')
            os.makedirs(out_dir, exist_ok=True)
            for personagem in TbPersonagem.objects.order_by('id_personagem'):
                data = exportar_personagem(personagem, gerado_de=gerado_de)
                caminho = os.path.join(out_dir, 'personagem_%d.json' % personagem.pk)
                with open(caminho, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write(serializar(data))
                self.stdout.write(self._resumo(data))
            self.stdout.write(self.style.SUCCESS('Exportados em %s' % out_dir))
            return

        if not opt['personagem_id']:
            raise CommandError('Informe o personagem_id (ou use --todos).')
        personagem = TbPersonagem.objects.filter(pk=opt['personagem_id']).first()
        if personagem is None:
            raise CommandError('Personagem %s não existe.' % opt['personagem_id'])
        data = exportar_personagem(personagem, gerado_de=gerado_de)
        texto = serializar(data)
        if opt['output']:
            with open(opt['output'], 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(texto)
            self.stdout.write(self.style.SUCCESS(
                '%s -> %s' % (self._resumo(data), opt['output'])))
        else:
            self.stdout.write(texto)
