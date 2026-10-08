# -*- coding: utf-8 -*-
"""Regressão do Criador de Personagem + Progressão por Aventuras.

Cobre os BUGS e VALIDAÇÕES corrigidos após a auditoria ponta-a-ponta (criador100):
  - BUG-1: multiclasse fura o teto de aventuras.
  - BUG-2: "equipamento inicial" vira ouro em silêncio nas classes sem kit.
  - BUG-4 (verificação): caminho essência/vertente → magia no N1.
  - VALIDAÇÕES: talento de origem obrigatório, point-buy completo, nome longo,
    cross-field raça×essência e raça×linhagem.
  - Progressão: aplicar_aventuras (+1, +N cruzando limiar) e permissão staff-only;
    subir-nível respeitando o teto.

Roda contra o conteúdo real (fixture `conteudo.json`) — as mesmas 4 raças / 13 classes /
30 antecedentes / 580 magias usadas pela auditoria.
"""
import json
import os
import re
import subprocess

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from home import views, point_buy
from home.character_engine import (
    background_grants, background_asi_values, _SKILL_INFO,
    nivel_por_aventuras, ouro_de_progressao, rank_por_nivel, aventuras_para_nivel,
)
from home.models import (
    TbClasse, TbAntecedente, TbTalento, TbItemMundano, TbOpcaojogo,
    TbPersonagem, TbPersonagemClasse, TbPersonagemMagia, TbPersonagemItem,
    TbPersonagemTalento, TbPersonagemPericia, TbClassehabilidade,
    TbPersonagemAventura, TbRegra,
)

# Array-padrão 15/14/13/12/10/8 = exatos 27 pontos de point-buy.
_SCORES = {'FOR': 8, 'DES': 14, 'CON': 13, 'INT': 15, 'SAB': 10, 'CAR': 12}


class _CriadorBase(TestCase):
    # Carrega o conteúdo real por CAMINHO EXPLÍCITO (não por nome). O nome
    # 'conteudo.json' é ambíguo: existe tanto em home/fixtures/ (tags com underscore,
    # o formato que o character_engine lê) quanto na raiz do repo (tags com hífen,
    # export de produção). O engine só entende underscore, então fixamos o arquivo bom.
    @classmethod
    def setUpTestData(cls):
        # A migration 0093 cria esta regra com PK local; o fixture possui a mesma slug
        # com o PK oficial. Remover a semente evita conflito de unicidade no banco de teste.
        TbRegra.objects.filter(slug='aumento-de-atributo').delete()
        call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)

    def _novo_usuario(self, username, staff=False):
        u = User.objects.create_user(username=username, password='x')
        if staff:
            u.is_staff = True
            u.save(update_fields=['is_staff'])
        return u

    def _payload(self, classe_slug, raca_slug='anao', antec_slug='acolito',
                 linhagem_slug=None, essencia_slug=None, vertente=None,
                 equip_classe='ouro', **overrides):
        """Monta um payload de criação VÁLIDO adaptado ao conteúdo (usa os mesmos
        helpers da view para casar as contagens de perícias/magias/escolhas)."""
        classe = TbClasse.objects.get(slug=classe_slug)
        antec = TbAntecedente.objects.get(slug=antec_slug)
        g = background_grants(antec)
        asi_major, asi_minor = background_asi_values(g)

        pn, plista = views._parse_skills_lvl1(classe.tags_json)
        pool = plista or list(_SKILL_INFO.keys())
        pericias_classe = pool[:pn]
        bg_skill_n = int(g.get('pericias') or 0)
        pericias_antec = [s for s in _SKILL_INFO if s not in pericias_classe][:bg_skill_n]
        lt = ['Anão', 'Élfico', 'Orc', 'Comum'][:int(g.get('idiomas_ou_ferramentas') or 0)]
        talento = TbTalento.objects.filter(tipo__iexact='origem').first()

        payload = {
            'nome': 'Herói de Teste (%s)' % classe_slug,
            'scores': dict(_SCORES),
            'asi': {'mais2': 'CON', 'mais1': 'DES'},
            'raca': raca_slug, 'classe': classe_slug, 'antecedente': antec_slug,
            'linhagem': linhagem_slug, 'essencia': essencia_slug, 'vertente': vertente,
            'pericias_classe': pericias_classe, 'pericias_antecedente': pericias_antec,
            'idiomas_ferramentas': lt,
            'talento_origem': talento.id_talento if talento else None,
            'equip_classe': equip_classe,
        }

        from home.models import TbRaca, TbLinhagem, TbEssencia
        raca = TbRaca.objects.get(slug=raca_slug)
        linhagem = (TbLinhagem.objects.filter(
            slug=linhagem_slug, id_raca=raca).first()
            if linhagem_slug else None)
        essencia = (TbEssencia.objects.filter(slug=essencia_slug).first()
                    if essencia_slug and raca.permite_essencia else None)
        talentos_raciais = views._talentos_raciais_criador(
            raca, linhagem, essencia, vertente)
        if talentos_raciais:
            payload['talento_raca'] = talentos_raciais[0].nome

        mn = views._classe_maestria_n(classe, 1)
        if mn:
            # Maestria de Arma em 2 níveis: cada slot é `'<arma>|<maestria>'` (arma + UMA
            # maestria dela). Usa a 1ª maestria de cada arma do universo do REGISTRY.
            # o universo é o da CLASSE (só armas com que ela tem proficiência — regra 5e:
            # maestria só em arma que se sabe empunhar); sem o ctx o helper montaria um
            # payload com armas de fogo e o próprio servidor recusaria.
            from home.picks import _arma_universe
            payload['maestrias'] = [
                (w['slug'] + '|' + w['maestrias'][0]['slug']) if w.get('maestrias') else w['slug']
                for w in _arma_universe({'classe': classe, 'nivel': 1})[:mn]]

        esc1 = views._classe_escolhas_nv1(classe)
        if esc1['estilo_n']:
            payload['estilo_luta'] = TbOpcaojogo.objects.filter(tipo='Estilo de Luta').first().slug
        if esc1['expertise_n']:
            payload['expertise'] = (pericias_classe + pericias_antec)[:esc1['expertise_n']]

        # Demais escolhas declaradas em pick:* saem do mesmo registry usado pelo
        # criador. Arma, estilo e expertise continuam nos campos legados acima
        # porque parte desta suíte prova a compatibilidade desses clientes.
        from home import picks as pick_registry
        generic_payload = []
        for group in pick_registry.resolve_builder(classe):
            if group['kind'] == 'arma' or group['kind'] == 'pericia_expertise':
                continue
            if (group['kind'] == 'opcao'
                    and pick_registry.normalize_slug(group.get('tipo'))
                    == pick_registry.normalize_slug('estilo_de_luta')):
                continue
            values = [
                str(option.get('slug') if option.get('slug') is not None else option.get('id'))
                for option in group['universo'][:int(group['n'])]
            ]
            generic_payload.append({
                'kind': group['kind'],
                'tipo': group.get('tipo'),
                'valores': values,
            })
        if generic_payload:
            payload['picks'] = generic_payload

        conj = views._classe_conjuracao(classe)
        if conj:
            base = {s: int(_SCORES[s]) for s in point_buy.SIGLAS}
            n_mag = views._spell_count_nv1(conj, base, 'CON', 'DES', (asi_major, asi_minor))
            payload['truques'] = [t['slug'] for t in conj['truques']][:conj['truques_n']]
            payload['magias'] = [m['slug'] for m in conj['magias_nv1']][:n_mag]
            if conj.get('pool') == 'spellbook':
                n_preparadas = views._prepared_count_nv1(
                    conj, base, 'CON', 'DES', (asi_major, asi_minor))
                payload['magias_preparadas'] = payload['magias'][:n_preparadas]

        # Picks raciais de FERRAMENTA de traços-base NÃO-talento (ex.: Humano 'Jeitinho
        # Humano' pick:ferramenta:2) precisam ser resolvidos na criação — o front manda
        # NOMES em escolhas_raca. Sem isso o traço reaparece como pendência no level-up.
        # (Traços-TALENTO como o Anão 'Artesão Primoroso' são resolvidos na seleção do
        # talento racial, não aqui.)
        from home.models import TbTracoracial, TbItemMundano
        ferr_n = 0
        for tr in TbTracoracial.objects.filter(
                id_raca=raca, id_linhagem__isnull=True, id_essencia__isnull=True,
                nivel_requisito__lte=1).exclude(talento_racial=True):
            for tag in (tr.tags_json or []):
                for m in re.finditer(r'pick:ferramenta:(\d+)\b', str(tag)):
                    ferr_n += int(m.group(1))
        if ferr_n and 'escolhas_raca' not in overrides:
            tool_names = list(TbItemMundano.objects.filter(
                categoria='ferramenta').order_by('nome').values_list('nome', flat=True)[:ferr_n])
            er = dict(payload.get('escolhas_raca') or {})
            er.setdefault('ferramentas', tool_names)
            payload['escolhas_raca'] = er

        payload.update(overrides)
        return payload

    def _post_criar(self, user, payload):
        self.client.force_login(user)
        return self.client.post(reverse('criar_personagem'),
                                data=json.dumps(payload),
                                content_type='application/json')


class SanguePlanarBrowserTests(StaticLiveServerTestCase):
    def test_tres_menus_aparecem_no_criador_real(self):
        if not os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'):
            self.skipTest('Playwright não configurado neste ambiente')
        TbRegra.objects.filter(slug='aumento-de-atributo').delete()
        call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)
        user = User.objects.create_user(username='planar-browser', password='x')
        self.client.force_login(user)
        env = os.environ.copy()
        env.update({
            'PATHBUILDER_E2E_URL': self.live_server_url,
            'PATHBUILDER_E2E_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
            'PATHBUILDER_E2E_COOKIE_VALUE': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
        })
        script = os.path.join(os.path.dirname(__file__), 'js_tests', 'planar_creation.e2e.cjs')
        with self.settings(HUNTER_CREATOR_RULESET_CHECKSUM=''):
            browser = subprocess.run(['node', script], env=env, capture_output=True,
                                     text=True, timeout=90)
        self.assertEqual(browser.returncode, 0, browser.stdout + browser.stderr)
        self.assertIn('Q15: three level-one menus rendered', browser.stdout)


class CriacaoArquetiposTests(_CriadorBase):
    """Criação N1 dos 3 arquétipos: personagem válido + derive OK."""

    def _cria_ok(self, payload):
        user = self._novo_usuario('dono-%s' % payload['classe'], staff=True)
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        p = TbPersonagem.objects.get(pk=body['id'])
        self.assertEqual(p.nivel, 1)
        # deriva sem exceção e com números básicos coerentes
        from home.character_engine import derive
        ficha = derive(p)
        self.assertGreaterEqual(int(ficha['pv']['maximo_calculado']), 1)
        self.assertGreaterEqual(int(ficha['ca']), 10)
        return p, ficha

    def test_guerreiro_marcial(self):
        p, ficha = self._cria_ok(self._payload('guerreiro'))
        self.assertEqual(p.classes.first().id_classe.slug, 'guerreiro')
        # estilo de luta gravado — agora pelo resolvedor genérico (kind `opcao`), que grava
        # o slug da tag (underscore 'estilo_de_luta'), FONTE ÚNICA com o editar-ficha.
        self.assertTrue(p.escolhas.filter(tipo='estilo_de_luta').exists())

    def test_mago_conjurador(self):
        payload = self._payload('mago')
        p, ficha = self._cria_ok(payload)
        # 3 truques materializados a partir das escolhas
        self.assertEqual(p.magias.filter(nivel=0).count(), 3)
        # O contrato do grimório separa aquisição de preparação: seis magias
        # pertencem ao livro, mas somente o subconjunto escolhido começa preparado.
        livro = p.magias.filter(nivel=1, origem='Mago')
        self.assertEqual(livro.count(), 6)
        self.assertEqual(
            set(livro.filter(preparada=True).values_list('id_magia__slug', flat=True)),
            set(payload['magias_preparadas']))
        self.assertEqual(livro.filter(preparada=False).count(), 3)

    def test_mistico_salva_pela_rota_json(self):
        p, ficha = self._cria_ok(self._payload('mistico'))
        self.assertEqual(p.classes.first().id_classe.slug, 'mistico')
        self.assertGreaterEqual(p.magias.count(), 1)

    def test_talento_com_escolha_de_magia_e_persistido(self):
        talento = TbTalento.objects.create(
            nome='Talento de Teste Arcano', slug='talento-teste-arcano', tipo='origem',
            etiqueta='conjuracao', descricao='Escolha uma magia.',
            tags_json=['spell_selection:mago{nivel:1, qtd:1, always_prepared, spell_mod:int}'])
        payload = self._payload('mistico', talento_origem=talento.id_talento)
        resolved, erros = views._criador_resolver(payload)
        self.assertFalse(erros, erros)
        user = self._novo_usuario('talento-magia')

        from django.db import transaction
        with transaction.atomic():
            temp = views._criador_persistir(user, payload, resolved)
            grupos = temp._criador_spell_groups
            self.assertTrue(grupos)
            transaction.set_rollback(True)

        payload['magias_concedidas'] = [{
            'fonte': grupo['fonte'], 'slot': grupo['slot'],
            'magias': [grupo['opcoes'][0]['slug']],
        } for grupo in grupos]
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        personagem = TbPersonagem.objects.get(pk=resp.json()['id'])
        self.assertTrue(personagem.escolhas.filter(tipo='magia-concedida').exists())

    def test_feiticeiro_com_essencia(self):
        # raça + essência + vertente (linhagem e essência são mutuamente exclusivas —
        # ver LinhagemEssenciaExclusivasTests — então este caminho usa só essência).
        payload = self._payload(
            'feiticeiro', raca_slug='anao', essencia_slug='draconica', vertente='Vermelho')
        payload.setdefault('escolhas_raca', {})['menus'] = [{
            'tipo': 'alento_elemental', 'fonte': 'Alento Elemental', 'valores': ['fogo']}]
        p, ficha = self._cria_ok(payload)
        self.assertEqual(p.id_essencia.slug, 'draconica')
        self.assertIsNone(p.id_linhagem)
        self.assertTrue(p.escolhas.filter(tipo='vertente').exists())

    def test_nephilim_resolve_tres_menus_no_nivel_um_sem_levelup_artificial(self):
        from django.db import transaction

        payload = self._payload('guerreiro', raca_slug='anao', essencia_slug='nephilim')
        owner = self._novo_usuario('nephilim-nivel-um')
        count_before = TbPersonagem.objects.count()
        incomplete = self._post_criar(owner, payload)
        self.assertFalse(incomplete.json().get('ok'))
        self.assertTrue(any('Sangue Planar' in error
                            for error in incomplete.json().get('erros', [])))
        self.assertEqual(TbPersonagem.objects.count(), count_before)
        payload.setdefault('escolhas_raca', {})['menus'] = [
            {'tipo': 'polo', 'fonte': 'Sangue Planar', 'valores': ['celestial']},
            {'tipo': 'energia', 'fonte': 'Sangue Planar', 'valores': ['lumen']},
            {'tipo': 'elemento', 'fonte': 'Sangue Planar', 'valores': ['fogo']},
        ]
        resolved, errors = views._criador_resolver(payload)
        self.assertFalse(errors, errors)
        with transaction.atomic():
            temporary = views._criador_persistir(owner, payload, resolved)
            payload['magias_concedidas'] = [{
                'fonte': group['fonte'], 'slot': group['slot'],
                'magias': [group['opcoes'][0]['slug']],
            } for group in temporary._criador_spell_groups]
            transaction.set_rollback(True)

        response = self._post_criar(owner, payload)
        self.assertTrue(response.json().get('ok'), response.content)
        character = TbPersonagem.objects.get(pk=response.json()['id'])
        self.assertEqual(character.nivel, 1)
        self.assertEqual(dict(character.escolhas.filter(
            origem='Sangue Planar', tipo__in=['polo', 'energia', 'elemento'])
            .values_list('tipo', 'valor')),
            {'polo': 'celestial', 'energia': 'lumen', 'elemento': 'fogo'})
        levelup = self.client.get(reverse('personagem_subir_nivel', args=[character.pk]))
        self.assertEqual(levelup.status_code, 200)
        self.assertFalse(any(group['pendentes'] for group in levelup.context['opcao_grupos']
                             if group['kind'] in ('polo', 'energia', 'elemento')))
        self.assertEqual(levelup.context['magias_concedidas_pend'], [])

    def test_feiticeiro_com_linhagem(self):
        # raça + linhagem (sem essência) — o outro lado da exclusividade mútua.
        p, ficha = self._cria_ok(self._payload(
            'feiticeiro', raca_slug='anao', linhagem_slug='montanha'))
        self.assertEqual(p.id_linhagem.slug, 'montanha')
        self.assertIsNone(p.id_essencia)

    def test_talento_de_origem_materializado(self):
        p, _ = self._cria_ok(self._payload('guerreiro'))
        self.assertTrue(TbPersonagemTalento.objects.filter(
            id_personagem=p, categoria='origem').exists())

    def test_bardo_persiste_tres_ferramentas_via_pick_generico(self):
        p, _ = self._cria_ok(self._payload('bardo'))
        self.assertEqual(p.escolhas.filter(tipo='ferramenta').count(), 3)
        self.assertEqual(p.proficiencias.filter(tipo='ferramenta').count(), 3)

    def test_clerigo_persiste_ordem_sagrada_via_menu_generico(self):
        p, _ = self._cria_ok(self._payload('clerigo'))
        self.assertTrue(p.escolhas.filter(tipo='ordem_sagrada').exists())


class Bug3MaestriaDeArmaTests(_CriadorBase):
    """BUG-3 (gap de conteúdo): Guerreiro, Bárbaro e Ladino têm a feature de
    Maestria de Arma descrita no N1, mas até então a tag `pick:arma:N` não
    resolvia a contagem (o slug do recurso usa hífen em TbRecursoclasse mas as
    tags referenciam com underscore — `_choice_resource_limit` não casava as
    duas formas e devolvia N=0 em silêncio). Ancora o N correto de cada classe
    (igual ao Caçador, o gabarito) e prova que a ficha nasce com a feature +
    as armas escolhidas materializadas — não só o count."""

    def _cria_ok(self, payload):
        user = self._novo_usuario('dono-%s' % payload['classe'], staff=True)
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        p = TbPersonagem.objects.get(pk=body['id'])
        from home.character_engine import derive
        return p, derive(p)

    def test_guerreiro_maestria_de_arma(self):
        classe = TbClasse.objects.get(slug='guerreiro')
        self.assertEqual(views._classe_maestria_n(classe, 1), 3,
                          'Disciplina Marcial: "Escolha três tipos de armas" no N1.')
        p, ficha = self._cria_ok(self._payload('guerreiro'))
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), 3)
        self.assertEqual(len(ficha['maestrias_armas']), 3)
        self.assertTrue(all(m['encontrada'] for m in ficha['maestrias_armas']), ficha['maestrias_armas'])
        # 2 níveis: UMA maestria escolhida por arma (não todas), nenhuma pendente.
        self.assertTrue(all(m['maestria'] for m in ficha['maestrias_armas']), ficha['maestrias_armas'])
        self.assertFalse(ficha['maestria_pendente'])
        self.assertTrue(all('|' in e.valor for e in p.escolhas.filter(tipo='maestria')))
        self.assertTrue(any(f['nome'] == 'Disciplina Marcial' for f in ficha['features']), ficha['features'])

    def test_barbaro_maestria_de_arma(self):
        classe = TbClasse.objects.get(slug='barbaro')
        self.assertEqual(views._classe_maestria_n(classe, 1), 2,
                          'Maestria em Armas: "dois tipos de armas" no N1.')
        p, ficha = self._cria_ok(self._payload('barbaro'))
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), 2)
        self.assertEqual(len(ficha['maestrias_armas']), 2)
        self.assertTrue(all(m['encontrada'] for m in ficha['maestrias_armas']), ficha['maestrias_armas'])
        self.assertTrue(any(f['nome'] == 'Maestria em Armas' for f in ficha['features']), ficha['features'])

    def test_ladino_maestria_de_arma(self):
        classe = TbClasse.objects.get(slug='ladino')
        self.assertEqual(views._classe_maestria_n(classe, 1), 2,
                          'Maestria em Armas do Ladino: "duas armas à sua escolha" no N1.')
        p, ficha = self._cria_ok(self._payload('ladino'))
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), 2)
        self.assertEqual(len(ficha['maestrias_armas']), 2)
        self.assertTrue(all(m['encontrada'] for m in ficha['maestrias_armas']), ficha['maestrias_armas'])
        self.assertTrue(any(f['nome'] == 'Maestria em Armas do Ladino' for f in ficha['features']), ficha['features'])

    def test_cacador_continua_gabarito(self):
        # regressão: o gabarito não pode quebrar com a normalização hífen/underscore.
        classe = TbClasse.objects.get(slug='cacador')
        self.assertEqual(views._classe_maestria_n(classe, 1), 3)

    def test_maestria_de_arma_obrigatoria_no_servidor(self):
        # sem escolher as armas, o servidor rejeita (não confia só no JS).
        payload = self._payload('guerreiro')
        payload.pop('maestrias', None)
        user = self._novo_usuario('sem-maestria', staff=True)
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertFalse(body.get('ok', True))
        self.assertTrue(any('Maestria de Arma' in e for e in body.get('erros', [])), body)


class Maestria2NiveisTests(_CriadorBase):
    """Bug do beta (achado 5): `pick:arma` concedia TODAS as maestrias da arma. Regra real:
    escolher a ARMA e UMA maestria DELA. Contrato do kind 'arma' em 2 níveis — universo expõe as
    maestrias como sub-opções; valor persistido = `'<arma>|<maestria>'`; derive/perfil mostram SÓ
    a maestria escolhida; escolhas legadas só-arma ficam PENDENTES e reabrem no painel."""

    def _guerreiro(self, nivel=1, apelido='m2n'):
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('%s-%d' % (apelido, nivel)), nome='Guerreiro M2N',
            nivel=nivel, forca=15, destreza=14, constituicao=13,
            inteligencia=12, sabedoria=10, carisma=8)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='guerreiro'),
            nivel=nivel, principal=True)
        return p

    def _armas_com_maestrias(self):
        # universo do GUERREIRO (a classe destes testes): só armas com que ele tem
        # proficiência — é o mesmo recorte que o criador e o wizard oferecem.
        from home.picks import _arma_universe
        classe = TbClasse.objects.get(slug='guerreiro')
        return [w for w in _arma_universe({'classe': classe, 'nivel': 1})
                if w.get('maestrias')]

    def _arma_com_maestrias(self):
        armas = self._armas_com_maestrias()
        return next((w for w in armas if len(w['maestrias']) >= 2), armas[0])

    # ── universo: 2º nível exposto ────────────────────────────────────────
    def test_universe_expoe_maestrias_como_subopcoes(self):
        from home.picks import _arma_universe, weapon_mastery_slugs
        from home.models import TbItemMundano
        univ = _arma_universe({})
        self.assertTrue(univ)
        for w in univ:
            arma = TbItemMundano.objects.get(slug=w['slug'])
            slugs = [m['slug'] for m in w['maestrias']]
            self.assertEqual(slugs, weapon_mastery_slugs(arma), w['slug'])
            self.assertTrue(all('slug' in m and 'nome' in m for m in w['maestrias']))

    # ── ponte de slug: nome/efeito legíveis apesar do '_' na tag da arma ──
    def test_universe_resolve_nome_e_efeito_pela_ponte_de_slug(self):
        """As tags `maestrias{...}` das armas usam '_' (minar_sap) — AUTORIDADE do projeto — e
        o catálogo TbOpcaojogo usa '-' (minar-sap). O seletor tem de resolver o NOME legível e o
        EFEITO no LOOKUP (ponte '_'→'-'); nunca exibir o slug cru com campos vazios."""
        from home.picks import _arma_universe
        from home.models import TbOpcaojogo
        w = next(w for w in _arma_universe({}) if w['slug'] == 'arma-espada-longa')
        m = next(m for m in w['maestrias'] if m['slug'] == 'minar_sap')   # slug cru = autoridade
        self.assertIn('Minar', m['nome'])                 # radio mostra 'Minar' (nome legível)
        self.assertNotEqual(m['nome'], m['slug'])         # não é o slug cru 'minar_sap'
        self.assertEqual(m['nome'], TbOpcaojogo.objects.get(slug='minar-sap').nome)
        self.assertTrue(m['efeito'].strip())              # efeito resolvido, não-vazio

    # ── validate: exige UMA maestria da arma ──────────────────────────────
    def test_validate_exige_maestria_pertencente_a_arma(self):
        from home import picks
        g = next(x for x in picks.resolve_builder(
            TbClasse.objects.get(slug='guerreiro'), kinds={'arma'}))
        self.assertEqual(g['n'], 3)
        w = self._arma_com_maestrias()
        outra = next(x for x in g['universo'] if x['slug'] != w['slug'] and x['maestrias'])
        terceira = next(x for x in g['universo']
                        if x['slug'] not in (w['slug'], outra['slug']) and x['maestrias'])
        m0 = w['maestrias'][0]['slug']
        bons = ['%s|%s' % (w['slug'], m0),
                '%s|%s' % (outra['slug'], outra['maestrias'][0]['slug']),
                '%s|%s' % (terceira['slug'], terceira['maestrias'][0]['slug'])]
        self.assertEqual(picks.PICK_REGISTRY['arma']['validate'](g, bons), [])
        # arma sem a maestria (só-arma) é rejeitada — a 2ª escolha é obrigatória
        so_arma = [w['slug'], outra['slug'], terceira['slug']]
        self.assertTrue(picks.PICK_REGISTRY['arma']['validate'](g, so_arma))
        # maestria que não pertence à arma é rejeitada
        ruim = ['%s|%s' % (w['slug'], 'maestria-inexistente-xyz'), bons[1], bons[2]]
        self.assertTrue(picks.PICK_REGISTRY['arma']['validate'](g, ruim))

    # ── persist + readback: 1 linha por slot, valor combinado ─────────────
    def test_persist_e_readback_combinado(self):
        from home import picks
        p = self._guerreiro()
        g = next(x for x in picks.resolve_builder(
            TbClasse.objects.get(slug='guerreiro'), kinds={'arma'}))
        w = self._arma_com_maestrias()
        val = '%s|%s' % (w['slug'], w['maestrias'][0]['slug'])
        picks.PICK_REGISTRY['arma']['persist'](p, g, [val])
        e = p.escolhas.filter(tipo='maestria').get()
        self.assertEqual(e.valor, val)
        rb = picks.PICK_REGISTRY['arma']['readback'](p, g)[0]
        self.assertEqual(rb['arma'], w['slug'])
        self.assertEqual(rb['maestria'], w['maestrias'][0]['slug'])
        self.assertFalse(rb['pendente'])

    # ── derive: SÓ a maestria escolhida (não todas) ───────────────────────
    def test_derive_mostra_so_a_maestria_escolhida(self):
        from home.character_engine import derive, _mapa_maestria_por_arma
        from home.models import TbPersonagemEscolha
        p = self._guerreiro()
        w = self._arma_com_maestrias()
        self.assertGreaterEqual(len(w['maestrias']), 2, 'arma de teste com 2+ maestrias')
        escolhida = w['maestrias'][0]
        TbPersonagemEscolha.objects.create(
            id_personagem=p, tipo='maestria', slot=0,
            valor='%s|%s' % (w['slug'], escolhida['slug']))
        ficha = derive(p)
        ma = ficha['maestrias_armas'][0]
        self.assertEqual(ma['maestria']['slug'], escolhida['slug'])
        self.assertFalse(ma['maestria_pendente'])
        self.assertEqual([m['slug'] for m in ma['maestrias']], [escolhida['slug']])
        # o mapa que alimenta o perfil de ataque traz SÓ a escolhida
        mp = _mapa_maestria_por_arma(ficha['maestrias_armas'])
        self.assertEqual(mp.get(w['slug']), [escolhida['nome']])
        self.assertFalse(ficha['maestria_pendente'])

    # ── legado: escolha só-arma vira PENDENTE, ficha não quebra ───────────
    def test_legado_so_arma_fica_pendente(self):
        from home.character_engine import derive, _mapa_maestria_por_arma
        from home.models import TbPersonagemEscolha
        p = self._guerreiro()
        w = self._arma_com_maestrias()
        TbPersonagemEscolha.objects.create(
            id_personagem=p, tipo='maestria', slot=0, valor=w['slug'])  # LEGADO: sem '|'
        ficha = derive(p)                                               # não lança
        ma = ficha['maestrias_armas'][0]
        self.assertTrue(ma['encontrada'])
        self.assertIsNone(ma['maestria'])
        self.assertTrue(ma['maestria_pendente'])
        self.assertTrue(ficha['maestria_pendente'])
        # perfil de ataque não recebe maestria de arma pendente
        self.assertEqual(_mapa_maestria_por_arma(ficha['maestrias_armas']), {})

    # ── a sub-escolha se completa/troca no ENDPOINT GENÉRICO ──────────────
    # O painel dedicado /trocar-maestria/ foi aposentado na onda D: a Maestria de Arma é
    # uma escolha como as outras, no seletor de dois níveis da aba Magias & Opções.
    def _grupo_arma(self, p):
        from home import views
        return next(g for g in views._opcoes_ficha(p) if g['kind'] == 'arma')

    def _trocar_opcao(self, p, grupo, escolha_id, val, esperado=200):
        self.client.force_login(p.dono)
        resp = self.client.post(
            reverse('personagem_trocar_opcao', args=[p.pk]),
            {'grupo': grupo['chave'], 'escolha': escolha_id, 'val': val},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, esperado, resp.content[:400])
        return resp.json()

    def test_rota_antiga_do_painel_redireciona_para_a_ficha(self):
        p = self._guerreiro()
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('personagem_trocar_maestria', args=[p.pk]))
        self.assertEqual(resp.status_code, 301)          # aposentada, permanente
        self.assertIn('aba=magias', resp['Location'])

    def test_endpoint_generico_completa_pendente(self):
        from home.character_engine import derive
        from home.models import TbPersonagemEscolha
        p = self._guerreiro()
        w = self._arma_com_maestrias()
        escolhida = w['maestrias'][0]
        TbPersonagemEscolha.objects.create(
            id_personagem=p, tipo='maestria', slot=0, valor=w['slug'])  # legado pendente
        grupo = self._grupo_arma(p)
        linha = grupo['escolhidas'][0]
        self.assertTrue(linha['pendente'])
        body = self._trocar_opcao(p, grupo, linha['id'],
                                  '%s|%s' % (w['slug'], escolhida['slug']))
        self.assertTrue(body['ok'], body)
        # a linha LEGADA (gravada sem `origem`) é reescrita, não duplicada
        e = p.escolhas.filter(tipo='maestria').get()
        self.assertEqual(e.valor, '%s|%s' % (w['slug'], escolhida['slug']))
        self.assertFalse(derive(p)['maestria_pendente'])

    def test_endpoint_generico_recusa_maestria_de_outra_arma(self):
        from home.models import TbPersonagemEscolha
        p = self._guerreiro()
        w = self._arma_com_maestrias()
        w_slugs = {m['slug'] for m in w['maestrias']}
        outra = next(x for x in self._armas_com_maestrias()
                     if x['slug'] != w['slug'] and x['maestrias'][0]['slug'] not in w_slugs)
        TbPersonagemEscolha.objects.create(
            id_personagem=p, tipo='maestria', slot=0, valor=w['slug'])
        grupo = self._grupo_arma(p)
        # o PAR não existe no universo (a maestria é de outra arma) -> recusado, nada muda
        body = self._trocar_opcao(p, grupo, grupo['escolhidas'][0]['id'],
                                  '%s|%s' % (w['slug'], outra['maestrias'][0]['slug']),
                                  esperado=400)
        self.assertEqual(body['msg'], 'fora_do_universo')
        e = p.escolhas.filter(tipo='maestria').get()
        self.assertEqual(e.valor, w['slug'])     # inalterado (segue pendente)

    # ── ponta-a-ponta pelo criador: nasce com a maestria escolhida ────────
    def test_criador_persiste_par_arma_maestria(self):
        from home.character_engine import derive
        payload = self._payload('guerreiro')       # já monta 'maestrias' combinado
        resp = self._post_criar(self._novo_usuario('e2e-m2n', staff=True), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        escs = p.escolhas.filter(tipo='maestria')
        self.assertEqual(escs.count(), 3)
        self.assertTrue(all('|' in e.valor for e in escs))
        ficha = derive(p)
        self.assertTrue(all(m['maestria'] and not m['maestria_pendente']
                            for m in ficha['maestrias_armas']))

    # ══ regra da staff (Gaz+Arna): a MESMA ARMA pode ocupar slots diferentes p/ aprender
    #    uma 2ª maestria dela; a duplicata proibida é o PAR (arma, maestria), não a arma. ══
    def test_validate_mesma_arma_duas_maestrias_ok(self):
        from home import picks
        from home.picks import _arma_universe
        w = self._arma_com_maestrias()
        self.assertGreaterEqual(len(w['maestrias']), 2)
        m0, m1 = w['maestrias'][0]['slug'], w['maestrias'][1]['slug']
        g = {'n': 2, 'universo': _arma_universe({})}
        # mesma arma, maestrias DIFERENTES -> aceito (aprende as duas, uma por ataque)
        self.assertEqual(picks.PICK_REGISTRY['arma']['validate'](
            g, ['%s|%s' % (w['slug'], m0), '%s|%s' % (w['slug'], m1)]), [])

    def test_validate_mesmo_par_duas_vezes_recusado(self):
        from home import picks
        from home.picks import _arma_universe
        w = self._arma_com_maestrias()
        m0 = w['maestrias'][0]['slug']
        g = {'n': 2, 'universo': _arma_universe({})}
        # mesmo PAR (arma+maestria) repetido -> recusado (não completa 2 pares distintos)
        self.assertTrue(picks.PICK_REGISTRY['arma']['validate'](
            g, ['%s|%s' % (w['slug'], m0), '%s|%s' % (w['slug'], m0)]))

    def test_validate_legado_uma_arma_uma_maestria_intacto(self):
        from home import picks
        from home.picks import _arma_universe
        w = self._arma_com_maestrias()
        m0 = w['maestrias'][0]['slug']
        g = {'n': 1, 'universo': _arma_universe({})}
        self.assertEqual(picks.PICK_REGISTRY['arma']['validate'](
            g, ['%s|%s' % (w['slug'], m0)]), [])

    def test_derive_e_perfil_listam_as_duas_maestrias_da_mesma_arma(self):
        from home.character_engine import derive, _mapa_maestria_por_arma
        from home.models import TbPersonagemEscolha
        p = self._guerreiro()
        w = self._arma_com_maestrias()
        m0, m1 = w['maestrias'][0], w['maestrias'][1]
        TbPersonagemEscolha.objects.create(id_personagem=p, tipo='maestria', slot=0,
                                           valor='%s|%s' % (w['slug'], m0['slug']))
        TbPersonagemEscolha.objects.create(id_personagem=p, tipo='maestria', slot=1,
                                           valor='%s|%s' % (w['slug'], m1['slug']))
        ficha = derive(p)
        entradas = [e for e in ficha['maestrias_armas'] if e.get('slug') == w['slug']]
        self.assertEqual(len(entradas), 2)                      # a arma aparece nos 2 slots
        self.assertTrue(all(e['encontrada'] and e['maestria'] for e in entradas))
        self.assertFalse(ficha['maestria_pendente'])
        # perfil de ataque lista AS DUAS maestrias aprendidas da arma
        mp = _mapa_maestria_por_arma(ficha['maestrias_armas'])
        self.assertEqual(set(mp.get(w['slug']) or []), {m0['nome'], m1['nome']})

    def _dois_slots_legado(self, p, w):
        from home.models import TbPersonagemEscolha
        TbPersonagemEscolha.objects.create(id_personagem=p, tipo='maestria', slot=0, valor=w['slug'])
        TbPersonagemEscolha.objects.create(id_personagem=p, tipo='maestria', slot=1, valor=w['slug'])

    def test_endpoint_generico_mesma_arma_dois_slots_maestrias_diferentes(self):
        from home.character_engine import derive
        p = self._guerreiro()
        w = self._arma_com_maestrias()
        m0, m1 = w['maestrias'][0]['slug'], w['maestrias'][1]['slug']
        self._dois_slots_legado(p, w)                          # 2 slots pendentes, MESMA arma
        for maestria in (m0, m1):
            grupo = self._grupo_arma(p)
            linha = next(e for e in grupo['escolhidas'] if e['pendente'])
            body = self._trocar_opcao(p, grupo, linha['id'],
                                      '%s|%s' % (w['slug'], maestria))
            self.assertTrue(body['ok'], body)
        vals = sorted(e.valor for e in p.escolhas.filter(tipo='maestria'))
        self.assertEqual(vals, sorted(['%s|%s' % (w['slug'], m0), '%s|%s' % (w['slug'], m1)]))
        self.assertFalse(derive(p)['maestria_pendente'])

    def test_endpoint_generico_recusa_par_duplicado(self):
        p = self._guerreiro()
        w = self._arma_com_maestrias()
        m0 = w['maestrias'][0]['slug']
        self._dois_slots_legado(p, w)
        grupo = self._grupo_arma(p)
        self.assertTrue(self._trocar_opcao(p, grupo, grupo['escolhidas'][0]['id'],
                                           '%s|%s' % (w['slug'], m0))['ok'])
        # o PAR (arma, maestria) é único: repetir o mesmo par no outro slot é recusado
        grupo = self._grupo_arma(p)
        outra_linha = next(e for e in grupo['escolhidas'] if e['pendente'])
        body = self._trocar_opcao(p, grupo, outra_linha['id'],
                                  '%s|%s' % (w['slug'], m0), esperado=400)
        self.assertEqual(body['msg'], 'duplicada')
        vals = sorted(e.valor for e in p.escolhas.filter(tipo='maestria'))
        self.assertEqual(vals, sorted(['%s|%s' % (w['slug'], m0), w['slug']]))

    def test_criador_e2e_mesma_arma_duas_maestrias(self):
        from home.character_engine import derive
        payload = self._payload('guerreiro')                   # guerreiro: 3 slots de maestria
        w = self._arma_com_maestrias()
        outra = next(x for x in self._armas_com_maestrias() if x['slug'] != w['slug'])
        payload['maestrias'] = ['%s|%s' % (w['slug'], w['maestrias'][0]['slug']),
                                '%s|%s' % (w['slug'], w['maestrias'][1]['slug']),
                                '%s|%s' % (outra['slug'], outra['maestrias'][0]['slug'])]
        resp = self._post_criar(self._novo_usuario('e2e-2mast', staff=True), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), 3)
        ficha = derive(p)
        entradas = [e for e in ficha['maestrias_armas'] if e.get('slug') == w['slug']]
        self.assertEqual(len(entradas), 2)                     # a mesma arma nasceu com 2 maestrias
        self.assertTrue(all(e['maestria'] and not e['maestria_pendente'] for e in entradas))


class MaestriaExigeProficienciaTests(_CriadorBase):
    """BUG (staff): o Bárbaro escolhendo Maestria de Arma via ARMAS DE FOGO (Bacamarte,
    Mosquete, Pistolas) — armas com que não tem proficiência nenhuma.

    Regra 5e/PO: maestria só se aprende em arma com que se TEM proficiência. O universo do
    `pick:arma` passa a ser filtrado pela proficiência REAL do motor (categorias da
    classe/multiclasse + grants `prof:weapon{...}` das tags ativas) — nunca por uma lista
    fixa de categorias por classe. Vale para os três clientes do MESMO registry: criador
    (`resolve_builder`), wizard de level-up e aba Magias & Opções (`resolve_personagem`).

    Escolha JÁ persistida numa arma sem proficiência (dado legado) continua na ficha, com
    aviso; só o universo de escolha NOVA é filtrado."""

    # ── helpers ──────────────────────────────────────────────────────────
    def _fogo(self):
        return {w.slug for w in TbItemMundano.objects.filter(categoria='arma',
                                                             subcategoria='arma_fogo')}

    def _de_subcat(self, subcat):
        return {w.slug for w in TbItemMundano.objects.filter(categoria='arma',
                                                             subcategoria=subcat)}

    def _universo_criador(self, classe_slug):
        from home import picks
        classe = TbClasse.objects.get(slug=classe_slug)
        g = next(g for g in picks.resolve_builder(classe, kinds={'arma'}))
        return {w['slug'] for w in g['universo']}

    def _universo_personagem(self, p):
        from home import picks
        g = next(g for g in picks.resolve_personagem(p, kinds={'arma'}))
        return {w['slug'] for w in g['universo']}

    def _criar(self, classe_slug, raca_slug='anao', apelido=''):
        user = self._novo_usuario('prof-%s-%s' % (classe_slug, apelido or 'x'), staff=True)
        resp = self._post_criar(user, self._payload(classe_slug, raca_slug=raca_slug))
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        return TbPersonagem.objects.get(pk=resp.json()['id'])

    # ── o bug ────────────────────────────────────────────────────────────
    def test_barbaro_nao_ve_armas_de_fogo_no_universo(self):
        """Bárbaro é proficiente em simples + marciais (tag `prof{...}` da classe) — e em
        NENHUMA arma de fogo. As 4+ armas de fogo do catálogo saem do seletor, nos dois
        clientes (criador e personagem/level-up), e o resto do catálogo continua lá."""
        fogo = self._fogo()
        self.assertTrue(fogo, 'catálogo precisa ter armas de fogo para o teste valer')
        criador = self._universo_criador('barbaro')
        self.assertFalse(criador & fogo, sorted(criador & fogo))
        self.assertTrue(self._de_subcat('arma_marcial') <= criador)
        self.assertTrue(self._de_subcat('arma_simples') <= criador)

        p = self._criar('barbaro')
        do_personagem = self._universo_personagem(p)
        self.assertFalse(do_personagem & fogo, sorted(do_personagem & fogo))
        self.assertEqual(criador, do_personagem,
                         'criador e ficha/level-up vêm do MESMO registry')

    def test_bacamarte_nao_entra_nem_por_post_direto(self):
        """O cliente não é a autoridade: POST direto pedindo maestria numa arma de fogo é
        recusado pelo servidor (a arma não está no universo, o validate não fecha a conta)."""
        bacamarte = TbItemMundano.objects.get(slug='arma-bacamarte')
        from home.picks import weapon_mastery_slugs
        maestria = weapon_mastery_slugs(bacamarte)[0]
        payload = self._payload('barbaro')
        payload['maestrias'] = ['%s|%s' % (bacamarte.slug, maestria)] * 2
        resp = self._post_criar(self._novo_usuario('post-fogo', staff=True), payload)
        self.assertEqual(resp.status_code, 400, resp.content[:400])
        self.assertTrue(any('Maestria de Arma' in e for e in resp.json().get('erros', [])),
                        resp.json())

    # ── controles positivos: a proficiência é LIDA, não assumida ─────────
    def test_guerreiro_com_prof_marcial_ve_todas_as_marciais(self):
        criador = self._universo_criador('guerreiro')
        self.assertTrue(self._de_subcat('arma_marcial') <= criador)
        self.assertTrue(self._de_subcat('arma_marcial_dist') <= criador)
        self.assertFalse(criador & self._fogo())

    def test_cacador_ve_armas_de_fogo_porque_a_classe_concede(self):
        """Prova que não há blacklist de armas de fogo: o Caçador declara `armas_fogo` na
        tag `prof{...}` e vê as mesmas armas que o Bárbaro não vê."""
        criador = self._universo_criador('cacador')
        self.assertTrue(self._fogo() <= criador, sorted(self._fogo() - criador))

    def test_ladino_so_ve_marciais_com_acuidade_ou_leves(self):
        """Proficiência COMPOSTA (`armas_marciais_acuidade_ou_leves`): a categoria vem da
        tag e a propriedade também — Rapieira (acuidade) entra, Alabarda (nem acuidade nem
        leve) não, e nada de arma de fogo."""
        criador = self._universo_criador('ladino')
        self.assertIn('arma-rapieira', criador)
        self.assertNotIn('arma-alabarda', criador)
        self.assertNotIn('arma-espada-longa', criador)     # marcial sem acuidade/leve
        self.assertTrue(self._de_subcat('arma_simples') <= criador)
        self.assertFalse(criador & self._fogo())

    def test_proficiencia_especifica_de_traco_racial_entra_no_universo(self):
        """Grant de ARMA ESPECÍFICA por traço (`prof:weapon{espada_longa}` da 'Disciplina das
        Lâminas Ancestrais' élfica) abre exatamente aquelas armas para um Ladino, que pela
        categoria não as teria — sem abrir as outras marciais."""
        from home.models import TbPersonagemTalento
        p = self._criar('ladino', raca_slug='elfo', apelido='elfo')
        sem_traco = self._universo_personagem(p)
        self.assertNotIn('arma-espada-longa', sem_traco)
        self.assertNotIn('arma-arco-longo', sem_traco)

        TbPersonagemTalento.objects.create(
            id_personagem=p, nome='Disciplina das Lâminas Ancestrais',
            categoria='talento-racial')
        com_traco = self._universo_personagem(p)
        self.assertIn('arma-espada-longa', com_traco)          # concedida nominalmente
        self.assertIn('arma-arco-longo', com_traco)            # idem (marcial à distância)
        self.assertNotIn('arma-alabarda', com_traco)           # não foi concedida
        self.assertFalse(com_traco & self._fogo())

    def test_talento_de_categoria_abre_armas_de_fogo_para_o_barbaro(self):
        """Mesmo caminho pela CATEGORIA: o talento 'Mestre Pistoleiro' declara
        `prof:weapon{armas_de_fogo}` e o Bárbaro passa a poder aprender maestria nelas."""
        from home.models import TbPersonagemTalento
        p = self._criar('barbaro', apelido='pistoleiro')
        self.assertFalse(self._universo_personagem(p) & self._fogo())
        TbPersonagemTalento.objects.create(
            id_personagem=p, id_talento=TbTalento.objects.get(nome='Mestre Pistoleiro'),
            categoria='geral')
        self.assertTrue(self._fogo() <= self._universo_personagem(p))

    def test_grant_composto_da_subclasse_respeita_escopo_e_exclusoes(self):
        """`prof:weapon{marcial, melee, not:{pesada, duas_maos}}` (Mago Dança da Lâmina) é
        lido inteiro: só marciais CORPO A CORPO e sem as propriedades proibidas."""
        from home.character_engine import weapon_allowed, weapon_proficiency_matchers
        from home.item_mecanica import mecanica_de_tags
        hab = TbClassehabilidade.objects.get(nome='Treinamento Marcial e Coreográfico')
        matchers = weapon_proficiency_matchers(
            classe=TbClasse.objects.get(slug='mago'),
            sources=[('classe', hab.nome, hab, 3)])

        def permite(slug):
            w = TbItemMundano.objects.get(slug=slug)
            return weapon_allowed(matchers, w.subcategoria, w.slug, w.nome,
                                  mecanica_de_tags(w.tags_json, w.subcategoria)
                                  .get('propriedades'))
        self.assertTrue(permite('arma-espada-longa'))    # marcial, melee, sem exclusões
        self.assertTrue(permite('arma-adaga'))           # simples (proficiência-base do Mago)
        self.assertFalse(permite('arma-alabarda'))       # pesada + duas mãos
        self.assertFalse(permite('arma-arco-longo'))     # à distância (escopo `melee`)

    # ── dado legado + guardas ────────────────────────────────────────────
    def test_escolha_legada_sem_proficiencia_continua_na_ficha_com_aviso(self):
        """Linha JÁ gravada numa arma sem proficiência não explode e não desaparece: o
        readback a devolve marcada (`sem_proficiencia`), o derive continua listando a
        maestria e a arma só não volta ao universo de escolha nova."""
        from home import picks, views
        from home.character_engine import derive
        from home.models import TbPersonagemEscolha
        p = self._criar('barbaro', apelido='legado')
        bacamarte = TbItemMundano.objects.get(slug='arma-bacamarte')
        maestria = picks.weapon_mastery_slugs(bacamarte)[0]
        legada = TbPersonagemEscolha.objects.filter(id_personagem=p, tipo='maestria').first()
        legada.valor = '%s|%s' % (bacamarte.slug, maestria)
        legada.save(update_fields=['valor'])

        grupo = next(g for g in picks.resolve_personagem(p, kinds={'arma'}))
        linha = next(e for e in grupo['escolhidas'] if e['id'] == legada.id)
        self.assertTrue(linha['sem_proficiencia'])
        self.assertIn(bacamarte.nome, linha['nome'])
        self.assertFalse(linha['pendente'], 'o par está completo; o que falta é proficiência')
        # as demais linhas (armas legítimas) NÃO são marcadas
        self.assertFalse(any(e['sem_proficiencia'] for e in grupo['escolhidas']
                             if e['id'] != legada.id))
        # derive segue de pé e mostra a maestria da arma legada
        ficha = derive(p)
        self.assertTrue(any(m.get('slug') == bacamarte.slug
                            for m in ficha['maestrias_armas']), ficha['maestrias_armas'])
        # e a seção da ficha renderiza o aviso sem quebrar
        cartao = next(g for g in views._opcoes_ficha(p) if g['kind'] == 'arma')
        self.assertTrue(any(e['sem_proficiencia'] for e in cartao['escolhidas']))

    def test_proficiencia_ilegivel_nao_zera_o_universo(self):
        """FAIL-OPEN: proficiência declarada que não casa com arma nenhuma do catálogo
        (grant opaco tipo `prof:weapon{bound}`) não pode fazer o grupo — e a pendência —
        desaparecer da ficha. Aí o universo volta a ser o catálogo inteiro."""
        from types import SimpleNamespace
        from home.picks import _arma_universe
        total = len(_arma_universe({}))
        fake = SimpleNamespace(nome='Classe Opaca', tags_json=['prof{armas_de_ectoplasma}'])
        self.assertEqual(len(_arma_universe({'classe': fake, 'nivel': 1})), total)

    def test_sem_contexto_o_universo_continua_completo(self):
        """Sem personagem nem classe não há proficiência para ler — o universo é o catálogo
        inteiro (é o que os chamadores de inspeção/catálogo esperam)."""
        from home.picks import _arma_universe
        self.assertEqual(len(_arma_universe({})),
                         TbItemMundano.objects.filter(categoria='arma').count())


class Bug4VertenteMagiaTests(_CriadorBase):
    """BUG-4 (verificação): o caminho essência/vertente → magia é CONSISTENTE no N1.

    A auditoria observou que, no feiticeiro dracônico N1, nenhuma magia
    `sempre_preparada` foi materializada — e que isso é legítimo (a essência não
    concede magia bônus no nível 1). Este teste ancora esse comportamento: o que
    `magias_concedidas` reporta é exatamente o que `_sync_magias_concedidas`
    materializa (sem grants-fantasma), e as magias da ficha vieram das ESCOLHAS."""

    def test_sync_bate_com_magias_concedidas(self):
        from home.character_engine import magias_concedidas
        user = self._novo_usuario('dono-bug4', staff=True)
        # essência (sem linhagem: as duas são mutuamente exclusivas)
        payload = self._payload('feiticeiro', raca_slug='anao',
                                essencia_slug='draconica', vertente='Vermelho')
        payload.setdefault('escolhas_raca', {})['menus'] = [{
            'tipo': 'alento_elemental', 'fonte': 'Alento Elemental', 'valores': ['fogo']}]
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])

        self.assertEqual(p.escolhas.get(tipo='alento_elemental').valor, 'fogo')
        concedidas = {c['slug'] for c in magias_concedidas(p)['concedidas']}
        materializadas = {m.id_magia.slug for m in TbPersonagemMagia.objects.filter(
            id_personagem=p, sempre_preparada=True).select_related('id_magia')}
        # o path é consistente: sync materializa exatamente o que o motor concede
        self.assertEqual(materializadas, concedidas)
        # e as magias escolhidas no criador estão lá (não-sempre-preparadas)
        escolhidas = TbPersonagemMagia.objects.filter(id_personagem=p, sempre_preparada=False)
        self.assertEqual(escolhidas.count(), len(payload['truques']) + len(payload['magias']))
        count = p.magias.count()
        views._sync_magias_concedidas(p)
        views._sync_magias_concedidas(p)
        self.assertEqual(p.magias.count(), count)


    def test_alento_missing_or_invalid_is_rejected(self):
        payload = self._payload('feiticeiro', raca_slug='anao',
                                essencia_slug='draconica', vertente='Vermelho')
        for values in ([], ['invalid'], ['fogo', 'agua'], ['fogo', 'fogo']):
            payload.setdefault('escolhas_raca', {})['menus'] = [{
                'tipo': 'alento_elemental', 'fonte': 'Alento Elemental', 'valores': values}]
            _, errors = views._criador_resolver(payload)
            self.assertTrue(errors, values)

class ValidacaoServerSideTests(_CriadorBase):
    """Validações server-side que faltavam (nunca confiar só no JS)."""

    def _staff(self):
        return self._novo_usuario('validador', staff=True)

    def test_talento_de_origem_obrigatorio(self):
        payload = self._payload('guerreiro')
        payload['talento_origem'] = None
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Talento de Origem', ' '.join(resp.json()['erros']))
        self.assertFalse(TbPersonagem.objects.exists())

    def test_talento_racial_obrigatorio(self):
        payload = self._payload('guerreiro')
        payload['talento_raca'] = ''
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Talento Racial', ' '.join(resp.json()['erros']))
        self.assertFalse(TbPersonagem.objects.exists())

    def test_point_buy_incompleto_rejeitado(self):
        payload = self._payload('guerreiro')
        payload['scores'].pop('INT')  # atributo faltando
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('seis atributos', ' '.join(resp.json()['erros']))

    def test_point_buy_sem_pontos_distribuidos_rejeitado(self):
        payload = self._payload('guerreiro')
        payload['scores'] = {sigla: 8 for sigla in point_buy.SIGLAS}
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        erros = ' '.join(resp.json()['erros'])
        self.assertIn('Compra de pontos incompleta', erros)
        self.assertIn('faltam 27 pontos', erros)
        self.assertFalse(TbPersonagem.objects.exists())

    def test_point_buy_generico_com_um_ponto_restante_rejeitado(self):
        payload = self._payload(
            'cacador', raca_slug='elfo', antec_slug='guardiao-da-natureza',
            linhagem_slug='lunareth',
        )
        # Uma distribuição visualmente plausível, mas ainda em 26/27. Este era o
        # caso que recebia check verde mesmo sem concluir a etapa.
        payload['scores'] = {
            'FOR': 13, 'DES': 12, 'CON': 12,
            'INT': 12, 'SAB': 12, 'CAR': 13,
        }
        payload['asi'] = {'modo': '2/1', 'attrs': ['DES', 'CON']}
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('falta 1 ponto', ' '.join(resp.json()['erros']))
        self.assertFalse(TbPersonagem.objects.exists())

    def test_finalizar_point_buy_libera_pv_e_ca_na_mesma_build(self):
        from home.models import TbTalento

        payload = self._payload(
            'cacador', raca_slug='elfo', antec_slug='guardiao-da-natureza',
            linhagem_slug='lunareth',
        )
        # Reproduz exatamente os atributos finais e o talento mostrados no relato:
        # 13/15/13/12/12/13 após +2 DES/+1 CON, com base 27/27.
        payload['scores'] = {
            'FOR': 13, 'DES': 13, 'CON': 12,
            'INT': 12, 'SAB': 12, 'CAR': 13,
        }
        payload['asi'] = {'modo': '2/1', 'attrs': ['DES', 'CON']}
        payload['talento_origem'] = TbTalento.objects.get(
            slug='assecla-do-reinado-draconico').id_talento
        user = self._staff()
        self.client.force_login(user)
        resp = self.client.post(
            reverse('criar_personagem_preview'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ready'], body)
        self.assertEqual(body['preview']['pv'], 11)
        self.assertEqual(body['preview']['ca'], 12)
        self.assertFalse(TbPersonagem.objects.exists())

    def test_preview_cacador_calcula_vitais_com_escolhas_futuras_pendentes(self):
        """A prévia de PV/CA não depende de o jogador ter preenchido a etapa Classe.

        Reproduz o fluxo que antes era alcançável pelos números do stepper: raça,
        classe e antecedente definidos, mas perícias, maestrias e ferramenta do
        Caçador ainda vazias. Essas pendências bloqueiam avançar/criar, não o cálculo
        dos vitais que orienta as escolhas seguintes.
        """
        payload = self._payload('cacador', raca_slug='anao')
        payload.update({
            'pericias_classe': [],
            'picks': [],
            'maestrias': [],
            'escolhas_classe_prof': [],
            'truques': [],
            'magias': [],
            'talento_origem': None,
            'talento_raca': '',
        })
        user = self._staff()
        self.client.force_login(user)
        resp = self.client.post(
            reverse('criar_personagem_preview'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ready'], body)
        self.assertIsInstance(body['preview']['pv'], int)
        self.assertIsInstance(body['preview']['ca'], int)
        self.assertFalse(TbPersonagem.objects.exists())

    def test_criador_e_pathbuilder_tem_contratos_de_destino_isolados(self):
        user = self._staff()
        self.client.force_login(user)

        creator_page = self.client.get(reverse('criacao_ficha'))
        self.assertContains(creator_page, 'data-mode="creator"')
        self.assertContains(creator_page, 'action="%s"' % reverse('criar_personagem'))
        self.assertIn('no-store', creator_page.get('Cache-Control', ''))

        pathbuilder_page = self.client.get(reverse('pathbuilder'))
        self.assertContains(pathbuilder_page, 'data-mode="pathbuilder"')
        self.assertContains(pathbuilder_page, 'action="%s"' % reverse('pathbuilder_iniciar'))
        self.assertIn('no-store', pathbuilder_page.get('Cache-Control', ''))

        path_response = self.client.post(
            reverse('pathbuilder_iniciar'),
            data=json.dumps(self._payload('cacador')),
            content_type='application/json',
        )
        self.assertEqual(path_response.status_code, 200, path_response.content)
        self.assertEqual(path_response.json()['mode'], 'pathbuilder')
        self.assertFalse(TbPersonagem.objects.exists())

        create_response = self.client.post(
            reverse('criar_personagem'),
            data=json.dumps(self._payload('cacador')),
            content_type='application/json',
        )
        self.assertEqual(create_response.status_code, 200, create_response.content)
        self.assertEqual(create_response.json()['mode'], 'creator')
        self.assertTrue(TbPersonagem.objects.filter(pk=create_response.json()['id']).exists())

    def test_preview_nao_calcula_pv_ca_com_point_buy_incompleto(self):
        payload = self._payload('guerreiro')
        payload['scores'] = {sigla: 8 for sigla in point_buy.SIGLAS}
        user = self._staff()
        self.client.force_login(user)
        resp = self.client.post(
            reverse('criar_personagem_preview'),
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertFalse(body['ready'])
        self.assertIn('Compra de pontos incompleta', ' '.join(body['erros']))
        self.assertFalse(TbPersonagem.objects.exists())

    def test_nome_longo_rejeitado(self):
        payload = self._payload('guerreiro')
        payload['nome'] = 'x' * 151
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Nome muito longo', ' '.join(resp.json()['erros']))

    def test_essencia_em_raca_que_nao_permite(self):
        # força uma raça a NÃO permitir essência e tenta atribuir uma
        from home.models import TbRaca
        TbRaca.objects.filter(slug='orc').update(permite_essencia=False)
        payload = self._payload('feiticeiro', raca_slug='orc', essencia_slug='draconica')
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('não permite', ' '.join(resp.json()['erros']))

    def test_linhagem_de_outra_raca_rejeitada(self):
        # 'montanha' é linhagem de anão; casar com raça humano deve falhar
        payload = self._payload('guerreiro', raca_slug='humano', linhagem_slug='montanha')
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('linhagem', ' '.join(resp.json()['erros']).lower())


class LinhagemEssenciaExclusivasTests(_CriadorBase):
    """BUG (beta da staff): dava para escolher LINHAGEM e ESSÊNCIA ao mesmo tempo e
    finalizar a criação assim — as duas são mutuamente exclusivas por regra (o
    personagem tem linhagem OU essência, nunca as duas). O JS já desmarca uma ao
    escolher a outra (ver home/static/js/criador.js), mas o servidor precisa recusar
    de qualquer forma — o guard vive em `_criador_resolver`, FONTE ÚNICA compartilhada
    pelo criar_personagem_view e pelo criar_personagem_preview_view, então cobre os
    dois. Não há fluxo de EDIÇÃO que troque linhagem/essência depois de criado (os
    campos só são gravados em `_criador_persistir`, na criação)."""

    def _staff(self):
        return self._novo_usuario('validador-excl', staff=True)

    def test_ambos_preenchidos_e_recusado_e_nada_persiste(self):
        payload = self._payload('feiticeiro', raca_slug='anao', linhagem_slug='montanha',
                                essencia_slug='draconica', vertente='Vermelho')
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertFalse(body.get('ok', True))
        self.assertTrue(any('linhagem' in e.lower() and 'essência' in e.lower()
                            for e in body.get('erros', [])), body)
        self.assertFalse(TbPersonagem.objects.exists())

    def test_so_linhagem_e_aceito(self):
        payload = self._payload('feiticeiro', raca_slug='anao', linhagem_slug='montanha')
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        self.assertEqual(p.id_linhagem.slug, 'montanha')
        self.assertIsNone(p.id_essencia)

    def test_so_essencia_e_aceito(self):
        payload = self._payload('feiticeiro', raca_slug='anao',
                                essencia_slug='draconica', vertente='Vermelho')
        payload['escolhas_raca'] = {'menus': [
            {'tipo': 'alento_elemental', 'fonte': 'Alento Elemental', 'valores': ['fogo']},
        ]}
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        self.assertEqual(p.id_essencia.slug, 'draconica')
        self.assertIsNone(p.id_linhagem)

    def test_preview_com_ambos_nao_fica_pronto(self):
        # a rota de preview aceita subconjuntos inválidos p/ atualizar a cada escolha
        # (ignora pendências de CONTAGEM de propósito), mas linhagem+essência é uma
        # violação ESTRUTURAL: o preview barra o "ready" explicitamente (não só o
        # criar_personagem_view) e, de qualquer forma, a transação é sempre revertida.
        payload = self._payload('feiticeiro', raca_slug='anao', linhagem_slug='montanha',
                                essencia_slug='draconica', vertente='Vermelho')
        self.client.force_login(self._staff())
        resp = self.client.post(reverse('criar_personagem_preview'),
                                data=json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(resp.json().get('ready'), resp.json())
        self.assertFalse(TbPersonagem.objects.exists())

    @override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='')
    def test_smoke_pagina_do_criador_carrega(self):
        # smoke: a página do criador continua respondendo 200 depois da troca
        # automática linhagem<->essência no JS (nada quebrou o template/contexto).
        self.client.force_login(self._staff())
        resp = self.client.get(reverse('criacao_ficha'))
        self.assertEqual(resp.status_code, 200)

    def test_criador_exige_login_desde_a_primeira_etapa(self):
        self.client.logout()
        resp = self.client.get(reverse('criacao_ficha'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])


class VampirismoCriadorTests(_CriadorBase):
    def test_essencia_suprime_talento_racial_da_raca_por_tag(self):
        from home.models import TbRaca, TbEssencia, TbTracoracial

        raca = TbRaca.objects.get(slug='humano')
        essencia = TbEssencia.objects.get(slug='vampirismo')
        policy = 'suppress:pick{talento_racial, source:raca}'
        self.assertIn(policy, essencia.tags_json)
        # SQLite não suporta o lookup JSONField `__contains`; checa em Python (o dado é a
        # política CRUA `suppress:pick{...}` na essência, não embrulhada em always_active{}).
        wrapped = 'always_active{ %s }' % policy
        self.assertFalse(any(
            wrapped in (tr.tags_json or [])
            for tr in TbTracoracial.objects.filter(id_essencia=essencia)))
        self.assertEqual(
            views._talentos_raciais_criador(
                raca, essencia=essencia, escolha_essencia='corvinus'),
            [],
        )
        policies = views._criador_catalogos()[
            'pick_suppressions_essencia']['vampirismo']
        self.assertIn(
            {'pick': 'talento_racial', 'source': 'raca', 'vertente': ''},
            policies,
        )

    def test_nova_maldicao_usa_a_mesma_politica_sem_slug_especial(self):
        from home.models import TbRaca, TbEssencia

        maldicao = TbEssencia.objects.create(
            nome='Licantropia de Teste',
            slug='licantropia-de-teste',
            tags_json=['suppress:pick{talento_racial, source:raca}'],
        )
        raca = TbRaca.objects.get(slug='humano')

        self.assertEqual(
            views._talentos_raciais_criador(raca, essencia=maldicao),
            [],
        )
        self.assertIn(
            {'pick': 'talento_racial', 'source': 'raca', 'vertente': ''},
            views._criador_catalogos()['pick_suppressions_essencia'][
                maldicao.slug],
        )

    def _vampiro(self, race_slug):
        from home.character_engine import derive
        from home.models import (
            TbRaca, TbEssencia, TbPersonagemEscolha,
        )

        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('vamp-' + race_slug),
            nome='Vampiro ' + race_slug,
            nivel=1,
            id_raca=TbRaca.objects.get(slug=race_slug),
            id_essencia=TbEssencia.objects.get(slug='vampirismo'),
            forca=10, destreza=14, constituicao=14,
            inteligencia=10, sabedoria=12, carisma=14,
        )
        TbPersonagemClasse.objects.create(
            id_personagem=p,
            id_classe=TbClasse.objects.get(slug='guerreiro'),
            nivel=1,
            principal=True,
        )
        TbPersonagemEscolha.objects.create(
            id_personagem=p,
            origem='Essência: Vampirismo',
            tipo='vertente',
            slot=0,
            valor='corvinus',
        )
        return derive(p)

    def test_visao_vampirica_sem_visao_anterior_fica_em_60ft(self):
        self.assertIn('darkvision 60ft', self._vampiro('humano')['sentidos'])

    def test_visao_vampirica_com_visao_anterior_recebe_mais_30ft(self):
        self.assertIn('darkvision 90ft', self._vampiro('anao')['sentidos'])


class EquipamentoInicialTests(_CriadorBase):
    """Equipamento de classe é resolvido pelas tags e vira inventário real."""

    def test_kit_inicial_cria_itens_do_catalogo_e_equipa_armadura(self):
        user = self._novo_usuario('dono-equip', staff=True)
        payload = self._payload('guerreiro', equip_classe='inicial')
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        personagem = TbPersonagem.objects.get(pk=resp.json()['id'])
        itens = TbPersonagemItem.objects.filter(id_personagem=personagem)
        self.assertTrue(itens.filter(id_item_mundano__slug='chain-mail', equipado=True).exists())
        self.assertTrue(itens.filter(id_item_mundano__slug='shield', equipado=True).exists())
        self.assertFalse(itens.filter(nome__icontains='Equipamento inicial da classe').exists())
        self.assertEqual(personagem.carteira_pc, 112 * 100)  # antecedente 100 + kit 12

    def test_classe_sem_schema_bloqueia_criacao(self):
        classe = TbClasse.objects.get(slug='guerreiro')
        classe.tags_json = [
            tag for tag in (classe.tags_json or [])
            if not str(tag).startswith('starting_equipment{')
        ]
        classe.save(update_fields=['tags_json'])
        user = self._novo_usuario('dono-equip-invalido', staff=True)
        payload = self._payload('guerreiro', equip_classe='inicial')
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('equipamento inicial', ' '.join(resp.json()['erros']).lower())
        self.assertFalse(TbPersonagem.objects.filter(dono=user).exists())

    def test_alternativa_em_ouro_nao_duplica_valor_do_antecedente(self):
        user = self._novo_usuario('dono-equip-ouro', staff=True)
        resp = self._post_criar(user, self._payload('guerreiro', equip_classe='ouro'))
        self.assertEqual(resp.status_code, 200, resp.content)
        personagem = TbPersonagem.objects.get(pk=resp.json()['id'])
        self.assertEqual(personagem.carteira_pc, 250 * 100)  # antecedente 100 + classe 150
        self.assertFalse(TbPersonagemItem.objects.filter(id_personagem=personagem).exists())


class ProgressaoAventurasTests(_CriadorBase):
    """aplicar_aventuras + permissão staff-only + subir-nível travado pelo teto."""

    def setUp(self):
        self.dono = self._novo_usuario('jogador-dono')
        self.outro = self._novo_usuario('outro-jogador')
        self.staff = self._novo_usuario('mestre-staff', staff=True)
        self.p = TbPersonagem.objects.create(
            dono=self.dono, nome='Peão', nivel=1,
            forca=15, destreza=15, constituicao=15, inteligencia=15, sabedoria=15, carisma=15)
        TbPersonagemClasse.objects.create(
            id_personagem=self.p, id_classe=TbClasse.objects.get(slug='guerreiro'),
            nivel=1, principal=True)

    def test_aplicar_uma_aventura_credita_ouro_obsidiana(self):
        ouro, bras = views.aplicar_aventuras(self.p, 1)
        esperado = ouro_de_progressao(1) - ouro_de_progressao(0)
        self.assertEqual(ouro, esperado)
        self.assertEqual(ouro, 120)  # rank Obsidiana, 1ª aventura
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 1)
        self.assertEqual(self.p.carteira_pc, 120 * 100)

    def test_aplicar_n_aventuras_cruzando_limiar(self):
        # 0 -> 9 aventuras: teto de nível vai a 5 (rank Ametista), ouro = soma sequencial
        ouro, _ = views.aplicar_aventuras(self.p, 9)
        self.assertEqual(ouro, ouro_de_progressao(9) - ouro_de_progressao(0))
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 9)
        self.assertEqual(nivel_por_aventuras(self.p.aventuras), 5)
        self.assertEqual(rank_por_nivel(nivel_por_aventuras(self.p.aventuras)), 'Ametista')
        self.assertEqual(self.p.carteira_pc, ouro * 100)

    def test_evento_credita_braseiros(self):
        _, bras = views.aplicar_aventuras(self.p, 3, evento=True)
        self.assertGreater(bras, 0)
        self.p.refresh_from_db()
        self.assertEqual(self.p.braseiros, bras)

    def test_registrar_aventuras_e_staff_only(self):
        url = reverse('personagem_registrar_aventuras', args=[self.p.pk])
        # dono NÃO pode
        self.client.force_login(self.dono)
        self.assertEqual(self.client.post(url, {'aventuras': 5}).status_code, 404)
        # outro jogador NÃO pode
        self.client.force_login(self.outro)
        self.assertEqual(self.client.post(url, {'aventuras': 5}).status_code, 404)
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 0)
        # staff pode (agora exige NOME da aventura e o MESTRE — onda E)
        self.client.force_login(self.staff)
        resp = self.client.post(url, {'aventuras': 5, 'nome_aventura': 'Mesa de Teste',
                                      'mestre': self.staff.pk})
        self.assertEqual(resp.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 5)

    def test_subir_nivel_travado_pelo_teto(self):
        views.aplicar_aventuras(self.p, 9)  # teto = nível 5
        url = reverse('personagem_subir_nivel', args=[self.p.pk])
        self.client.force_login(self.dono)
        for _ in range(10):  # tenta subir muito além
            self.client.post(url, {'classe': self.p.classes.first().id_classe_id})
        self.p.refresh_from_db()
        self.assertEqual(self.p.nivel, 5)  # parou no teto


class LedgerAventuraRollbackTests(_CriadorBase):
    """Ledger nomeado de lançamentos (TbPersonagemAventura): o registro grava a linha, e o
    rollback por linha (staff) devolve aventuras/ouro com os 3 bloqueios + permissão."""

    def setUp(self):
        self.dono = self._novo_usuario('dono-ledger')
        self.outro = self._novo_usuario('outro-ledger')
        self.staff = self._novo_usuario('staff-ledger', staff=True)
        self.p = TbPersonagem.objects.create(
            dono=self.dono, nome='Ledgerino', nivel=1,
            forca=15, destreza=15, constituicao=15, inteligencia=15, sabedoria=15, carisma=15)
        TbPersonagemClasse.objects.create(
            id_personagem=self.p, id_classe=TbClasse.objects.get(slug='guerreiro'),
            nivel=1, principal=True)

    def _registrar(self, **data):
        # Onda E: o lançamento novo exige mestre do cadastro (o staff serve de mestre nos
        # testes de rollback, que não são sobre o mestre em si).
        data.setdefault('mestre', self.staff.pk)
        self.client.force_login(self.staff)
        return self.client.post(
            reverse('personagem_registrar_aventuras', args=[self.p.pk]), data)

    def _reverter_url(self, lanc):
        return reverse('personagem_reverter_aventura', args=[self.p.pk, lanc.id_lancamento])

    # ── REGISTRO grava a linha do ledger ──────────────────────────────────
    def test_registro_grava_ledger(self):
        resp = self._registrar(nome_aventura='A Cripta Gelada', aventuras=3)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('compra=aventuras', resp.url)
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 3)
        ledger = list(self.p.aventuras_ledger.all())
        self.assertEqual(len(ledger), 1)
        l = ledger[0]
        self.assertEqual(l.nome_aventura, 'A Cripta Gelada')
        self.assertEqual(l.qtd_aventuras, 3)
        # 1ª carga: todo o ouro da carteira veio deste lançamento
        self.assertEqual(l.ouro_pago_pc, self.p.carteira_pc)
        self.assertGreater(l.ouro_pago_pc, 0)
        self.assertEqual(l.criado_por, self.staff)
        self.assertFalse(l.revertido)

    def test_registro_fetch_atualiza_fragmento_sem_redirect(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            reverse('personagem_registrar_aventuras', args=[self.p.pk]),
            {'nome_aventura': 'Mesa via Fetch', 'aventuras': 2, 'mestre': self.staff.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        self.assertIn('Mesa via Fetch', body['staffbox_html'])
        self.assertEqual(body['progressao']['aventuras'], 2)
        self.assertIn('carteira_display', body)

    def test_registro_exige_nome(self):
        resp = self._registrar(aventuras=3)  # sem nome_aventura
        self.assertEqual(resp.status_code, 302)
        self.assertIn('aventuras_sem_nome', resp.url)
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 0)          # não creditou
        self.assertEqual(self.p.aventuras_ledger.count(), 0)  # nada no ledger

    # ── ROLLBACK feliz ────────────────────────────────────────────────────
    def test_rollback_feliz_reverte_contadores(self):
        self._registrar(nome_aventura='Mesa 1', aventuras=1)
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 1)
        carteira_antes = self.p.carteira_pc
        l = self.p.aventuras_ledger.first()
        self.client.force_login(self.staff)
        resp = self.client.post(self._reverter_url(l))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('rollback=ok', resp.url)
        self.p.refresh_from_db(); l.refresh_from_db()
        self.assertEqual(self.p.aventuras, 0)
        self.assertEqual(self.p.carteira_pc, carteira_antes - l.ouro_pago_pc)
        self.assertEqual(self.p.carteira_pc, 0)
        self.assertTrue(l.revertido)
        self.assertEqual(l.revertido_por, self.staff)
        self.assertIsNotNone(l.revertido_em)

    def test_rollback_fetch_atualiza_fragmento_sem_redirect(self):
        self._registrar(nome_aventura='Mesa Fetch Reversão', aventuras=1)
        lanc = self.p.aventuras_ledger.first()
        self.client.force_login(self.staff)
        resp = self.client.post(
            self._reverter_url(lanc),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'], body)
        self.assertIn('revertido', body['staffbox_html'])
        self.assertEqual(body['progressao']['aventuras'], 0)

    # ── BLOQUEIO (c): linha já revertida ──────────────────────────────────
    def test_rollback_bloqueia_ja_revertido(self):
        self._registrar(nome_aventura='Mesa dup', aventuras=1)
        l = self.p.aventuras_ledger.first()
        self.client.force_login(self.staff)
        self.client.post(self._reverter_url(l))  # 1ª: reverte
        self.p.refresh_from_db()
        aventuras_apos, carteira_apos = self.p.aventuras, self.p.carteira_pc
        resp = self.client.post(self._reverter_url(l))  # 2ª: recusa
        self.assertIn('rollback=ja_revertido', resp.url)
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, aventuras_apos)   # inalterado
        self.assertEqual(self.p.carteira_pc, carteira_apos)

    # ── BLOQUEIO (a): já subiu de nível com essas aventuras ───────────────
    def test_rollback_bloqueia_por_teto_de_nivel(self):
        self._registrar(nome_aventura='Grinding', aventuras=9)  # teto = nível 5
        self.assertEqual(aventuras_para_nivel(5), 9)
        self.p.nivel = 5  # efetivamente subiu de nível consumindo as aventuras
        self.p.save(update_fields=['nivel'])
        l = self.p.aventuras_ledger.first()
        self.client.force_login(self.staff)
        resp = self.client.post(self._reverter_url(l))
        self.assertIn('rollback=teto_nivel', resp.url)
        self.p.refresh_from_db(); l.refresh_from_db()
        self.assertEqual(self.p.aventuras, 9)   # nada revertido
        self.assertFalse(l.revertido)

    # ── BLOQUEIO (b): ouro insuficiente para estornar ─────────────────────
    def test_rollback_bloqueia_por_ouro_insuficiente(self):
        self._registrar(nome_aventura='Gastão', aventuras=1)
        self.p.refresh_from_db()
        l = self.p.aventuras_ledger.first()
        self.assertGreater(l.ouro_pago_pc, 0)
        self.p.carteira_pc = 0  # o jogador já gastou o ouro
        self.p.save(update_fields=['carteira_pc'])
        self.client.force_login(self.staff)
        resp = self.client.post(self._reverter_url(l))
        self.assertIn('rollback=ouro_insuf', resp.url)
        self.p.refresh_from_db(); l.refresh_from_db()
        self.assertEqual(self.p.aventuras, 1)   # nada revertido
        self.assertFalse(l.revertido)

    # ── UI: a ficha renderiza o campo nome + histórico + botão Reverter ───
    def test_editar_ficha_renderiza_ledger_para_staff(self):
        self._registrar(nome_aventura='Mesa Visível', aventuras=2)
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('editar_ficha', args=[self.p.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        l = self.p.aventuras_ledger.first()
        self.assertIn('name="nome_aventura"', html)   # campo obrigatório no form
        self.assertIn('Mesa Visível', html)           # linha do histórico
        self.assertIn('Reverter', html)               # botão de rollback por linha
        self.assertIn(reverse('personagem_reverter_aventura',
                              args=[self.p.pk, l.id_lancamento]), html)  # action do form

    # ── PERMISSÃO: rollback é staff-only ──────────────────────────────────
    def test_rollback_staff_only(self):
        self._registrar(nome_aventura='Segredo', aventuras=1)
        l = self.p.aventuras_ledger.first()
        url = self._reverter_url(l)
        for u in (self.dono, self.outro):
            self.client.force_login(u)
            self.assertEqual(self.client.post(url).status_code, 404)
        l.refresh_from_db(); self.p.refresh_from_db()
        self.assertFalse(l.revertido)     # não-staff não reverteu
        self.assertEqual(self.p.aventuras, 1)


class Bug1MulticlasseTetoTests(_CriadorBase):
    """BUG-1: multiclasse não pode furar o teto de aventuras do dono."""

    def setUp(self):
        self.dono = self._novo_usuario('dono-mc')
        self.p = TbPersonagem.objects.create(
            dono=self.dono, nome='Multi', nivel=1,
            forca=17, destreza=17, constituicao=17, inteligencia=17, sabedoria=17, carisma=17)
        TbPersonagemClasse.objects.create(
            id_personagem=self.p, id_classe=TbClasse.objects.get(slug='feiticeiro'),
            nivel=1, principal=True)

    def _classe_elegivel(self):
        from home.character_engine import derive
        elig = views._classes_multiclasse(self.p, derive(self.p))
        self.assertTrue(elig, 'personagem precisa ter ao menos 1 multiclasse elegível')
        return elig[0]['id']

    def test_bloqueado_sem_aventuras(self):
        # 0 aventuras -> teto = 1 -> multiclasse recusada, nível fica em 1
        self.assertEqual(self.p.aventuras, 0)
        cls_id = self._classe_elegivel()
        self.client.force_login(self.dono)
        resp = self.client.post(
            reverse('personagem_adicionar_classe', args=[self.p.pk]), {'classe': cls_id})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('mc=teto', resp.url)
        self.p.refresh_from_db()
        self.assertEqual(self.p.nivel, 1)
        self.assertEqual(self.p.classes.count(), 1)

    def test_permitido_com_aventuras_suficientes(self):
        # 1 aventura -> teto = 2 -> multiclasse permitida, nível vai a 2
        views.aplicar_aventuras(self.p, 1)
        cls_id = self._classe_elegivel()
        self.client.force_login(self.dono)
        resp = self.client.post(
            reverse('personagem_adicionar_classe', args=[self.p.pk]), {'classe': cls_id})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('mc=ok', resp.url)
        self.p.refresh_from_db()
        self.assertEqual(self.p.nivel, 2)
        self.assertEqual(self.p.classes.count(), 2)


class PreviewAoVivoTests(_CriadorBase):
    """U4 — o preview AO VIVO (endpoint que roda o derive numa transação revertida)
    BATE com o derive da ficha realmente criada, campo a campo (PV/CA/PB/atributos)."""

    def _preview(self, user, payload):
        self.client.force_login(user)
        resp = self.client.post(reverse('criar_personagem_preview'),
                                data=json.dumps(payload),
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def _bate(self, classe_slug, **kw):
        from home.character_engine import derive
        user = self._novo_usuario('prev-%s' % classe_slug, staff=True)
        payload = self._payload(classe_slug, **kw)

        prev = self._preview(user, payload)
        self.assertTrue(prev.get('ready'), prev)
        pv = prev['preview']

        # cria de verdade e deriva
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        ficha = derive(p)

        self.assertEqual(pv['pv'], ficha['pv']['maximo_calculado'], 'PV diverge')
        self.assertEqual(pv['ca'], ficha['ca'], 'CA diverge')
        self.assertEqual(pv['pb'], ficha['bonus_proficiencia'], 'PB diverge')
        # atributos (valor + mod) idênticos ao derive
        by_sig = {a['sig']: a for a in pv['atributos']}
        for sig, a in ficha['atributos'].items():
            self.assertEqual(by_sig[sig]['valor'], a['valor'], 'valor %s diverge' % sig)
            self.assertEqual(by_sig[sig]['mod'], a['mod'], 'mod %s diverge' % sig)
        # perícias proficientes do preview == as proficientes do derive
        prev_prof = sorted(x['nome'] for x in pv['pericias'])
        der_prof = sorted(x['nome'] for x in ficha['pericias'] if x['proficiente'] or x['expertise'])
        self.assertEqual(prev_prof, der_prof, 'perícias proficientes divergem')
        return pv, ficha

    def test_preview_guerreiro_bate(self):
        self._bate('guerreiro')

    def test_preview_mago_bate(self):
        self._bate('mago')

    def test_preview_feiticeiro_essencia_bate(self):
        # essência (sem linhagem: as duas são mutuamente exclusivas)
        self._bate('feiticeiro', raca_slug='anao',
                   essencia_slug='draconica', vertente='Vermelho',
                   escolhas_raca={'menus': [{'tipo': 'alento_elemental',
                       'fonte': 'Alento Elemental', 'valores': ['fogo']}]})

    def test_preview_reports_missing_racial_choice_without_saving(self):
        user = self._novo_usuario('prev-alento')
        payload = self._payload('feiticeiro', essencia_slug='draconica',
                                vertente='Vermelho')
        before = TbPersonagem.objects.count()
        for values in ([], ['invalid'], ['fogo', 'agua'], ['fogo', 'fogo']):
            with self.subTest(values=values):
                payload['escolhas_raca'] = {'menus': [{
                    'tipo': 'alento_elemental', 'fonte': 'Alento Elemental',
                    'valores': values}]}
                preview = self._preview(user, payload)
                self.assertTrue(preview['ready'], preview)
                self.assertIn('Alento Elemental', ' '.join(preview['erros']))
                response = self._post_criar(user, payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(preview['erros'], response.json()['erros'])
                self.assertEqual(TbPersonagem.objects.count(), before)
        payload['escolhas_raca']['menus'][0]['valores'] = ['fogo']
        preview = self._preview(user, payload)
        self.assertEqual(preview['erros'], [])
        self.assertEqual(TbPersonagem.objects.count(), before)
        response = self._post_criar(user, payload)
        self.assertEqual(response.status_code, 200, response.content)
        person = TbPersonagem.objects.get(pk=response.json()['id'])
        self.assertEqual(person.escolhas.get(tipo='alento_elemental').valor, 'fogo')

    def test_preview_incompleto_nao_pronto(self):
        # sem classe -> preview responde ready:false (mostra placeholder no front)
        user = self._novo_usuario('prev-incompleto')
        payload = self._payload('guerreiro')
        payload['classe'] = ''
        prev = self._preview(user, payload)
        self.assertFalse(prev.get('ready'), prev)


@override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='')
class PicksGenericoTests(_CriadorBase):
    """Sistema GENÉRICO de escolhas `pick:*` (home.picks): o criador passa a montar as
    escolhas de Maestria de Arma e Estilo de Luta pelo componente genérico (payload
    `picks:[{kind,tipo,valores}]`), com o MESMO resultado do caminho legado."""

    def _cria(self, apelido, payload):
        resp = self._post_criar(self._novo_usuario(apelido, staff=True), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        return TbPersonagem.objects.get(pk=resp.json()['id'])

    def _para_picks(self, payload):
        """Converte os campos legados (maestrias/estilo_luta) para o payload genérico
        `picks:[...]` — exatamente o que o JS do wizard passa a enviar."""
        pl = dict(payload)
        picks = list(pl.get('picks') or [])
        armas = pl.pop('maestrias', None)
        if armas:
            picks.append({'kind': 'arma', 'tipo': None, 'valores': list(armas)})
        estilo = pl.pop('estilo_luta', None)
        if estilo:
            picks.append({'kind': 'opcao', 'tipo': 'estilo_de_luta', 'valores': [estilo]})
        pl['picks'] = picks
        return pl

    def _prova_identico(self, classe_slug, **kw):
        """Cria o MESMO personagem por dois caminhos (campos legados vs picks[]) e prova
        que as escolhas persistidas e a ficha derivada são idênticas."""
        from home.character_engine import derive
        base = self._payload(classe_slug, **kw)
        leg = self._cria('leg-%s' % classe_slug, base)
        gen = self._cria('gen-%s' % classe_slug, self._para_picks(base))

        def escset(p):
            return sorted((e.tipo, e.slot, e.valor) for e in p.escolhas.all())
        self.assertEqual(escset(leg), escset(gen), 'escolhas persistidas divergem legado×genérico')
        dl, dg = derive(leg), derive(gen)
        self.assertEqual([m.get('slug') for m in dl['maestrias_armas']],
                         [m.get('slug') for m in dg['maestrias_armas']], 'maestrias divergem')
        self.assertEqual(sorted(f['nome'] for f in dl['features']),
                         sorted(f['nome'] for f in dg['features']), 'features divergem')
        return gen

    def test_guerreiro_via_picks(self):
        # Guerreiro exercita os DOIS kinds no N1: arma (Maestria x3) + opcao (Estilo de Luta)
        p = self._prova_identico('guerreiro')
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), 3)
        self.assertTrue(p.escolhas.filter(tipo='estilo_de_luta').exists())

    def test_cacador_via_picks(self):
        p = self._prova_identico('cacador')
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), 3)
        self.assertEqual(p.escolhas.filter(tipo='ferramenta').count(), 1)
        self.assertEqual(p.proficiencias.filter(tipo='ferramenta').count(), 1)

    def test_cacador_expoe_um_unico_grupo_de_ferramenta(self):
        from home import picks

        classe = TbClasse.objects.get(slug='cacador')
        grupos = [g for g in picks.resolve_builder(classe) if g['kind'] == 'ferramenta']
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]['n'], 1)

        catalogo = views._criador_catalogos()
        cacador = next(c for c in catalogo['classes'] if c['slug'] == 'cacador')
        grupos_catalogo = [g for g in cacador['pick_groups'] if g['kind'] == 'ferramenta']
        self.assertEqual(len(grupos_catalogo), 1)
        self.assertNotIn('classe_prof_picks', cacador)

    def test_payload_antigo_de_ferramenta_continua_compativel(self):
        """Uma aba antiga ainda aberta pode enviar o formato removido por NOME."""
        payload = self._payload('cacador')
        tool_group = next(g for g in payload['picks'] if g['kind'] == 'ferramenta')
        tool_slug = tool_group['valores'][0]
        tool = TbItemMundano.objects.get(slug=tool_slug)
        # O JS anterior já enviava o grupo genérico, porém vazio, ao mesmo tempo em
        # que enviava a escolha preenchida pelo componente duplicado legado.
        tool_group['valores'] = []
        payload['escolhas_classe_prof'] = [{'tipo': 'ferramenta', 'valores': [tool.nome]}]

        p = self._cria('cacador-legado-ferramenta', payload)
        self.assertEqual(p.escolhas.filter(tipo='ferramenta', valor=tool.slug).count(), 1)
        self.assertEqual(p.proficiencias.filter(tipo='ferramenta', nome=tool.nome).count(), 1)

    def test_ladino_via_picks(self):
        p = self._prova_identico('ladino')
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), 2)
        from home import picks
        expertise = next(
            group for group in picks.resolve_personagem(p)
            if group['kind'] == 'pericia_expertise'
        )
        self.assertEqual(expertise['pendentes'], 0)

    def test_maestria_obrigatoria_no_generico(self):
        # sem o pick de arma, a validação genérica (server-side) rejeita com a msg correta.
        pl = self._para_picks(self._payload('guerreiro'))
        pl['picks'] = [g for g in pl['picks'] if g['kind'] != 'arma']
        resp = self._post_criar(self._novo_usuario('sem-arma-gen', staff=True), pl)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertTrue(any('Maestria de Arma' in e for e in resp.json().get('erros', [])), resp.json())


class PickTipoSinteticoTests(_CriadorBase):
    """O TESTE-CHAVE do PO: um TIPO de opção NOVO, inventado só nos dados (uma feature de
    classe com `pick:opcao:tipo_sintetico:2` + 3 opções TbOpcaojogo desse tipo), é
    LISTADO, VALIDADO e PERSISTIDO pelo criador SEM UMA LINHA de código novo — prova de que
    as escolhas são dirigidas pelas tags, não por caminhos hardcoded por tipo."""

    def setUp(self):
        from home.models import TbClasse, TbClassehabilidade, TbOpcaojogo
        # Mago: sem pick:arma/estilo no N1 -> isola o grupo sintético como única escolha genérica.
        self.classe = TbClasse.objects.get(slug='mago')
        TbClassehabilidade.objects.create(
            id_classe=self.classe, id_subclasse=None, nome='Dom Sintético',
            descricao='Feature de teste.', niveladquirido=1,
            tags_json=['pick:opcao:tipo_sintetico:2'])
        self.slugs = []
        for i in range(3):
            o = TbOpcaojogo.objects.create(
                nome='Opção Sintética %d' % i, slug='op-sint-%d' % i,
                tipo='Tipo Sintético', descricao='efeito %d' % i, tags_json=[])
            self.slugs.append(o.slug)

    def test_resolvedor_lista_o_grupo(self):
        from home import picks as P
        grupos = [g for g in P.resolve_builder(self.classe, kinds={'opcao'})
                  if g['tipo'] == 'tipo_sintetico']
        self.assertEqual(len(grupos), 1, 'o resolvedor deve descobrir o grupo pelas tags')
        g = grupos[0]
        self.assertEqual(g['n'], 2)
        self.assertEqual(g['persist_tipo'], 'tipo_sintetico')
        self.assertEqual({u['slug'] for u in g['universo']}, set(self.slugs))

    def test_criador_persiste_o_tipo_sintetico(self):
        pl = self._payload('mago')
        synthetic_pick = next(g for g in pl['picks']
                              if g['kind'] == 'opcao' and g['tipo'] == 'tipo_sintetico')
        synthetic_pick['valores'] = [self.slugs[0], self.slugs[2]]
        resp = self._post_criar(self._novo_usuario('sintetico', staff=True), pl)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        escs = p.escolhas.filter(tipo='tipo_sintetico')
        self.assertEqual(escs.count(), 2)
        self.assertEqual(set(escs.values_list('valor', flat=True)), {self.slugs[0], self.slugs[2]})

    def test_validacao_generica_rejeita_contagem_errada(self):
        pl = self._payload('mago')
        synthetic_pick = next(g for g in pl['picks']
                              if g['kind'] == 'opcao' and g['tipo'] == 'tipo_sintetico')
        synthetic_pick['valores'] = [self.slugs[0]]
        resp = self._post_criar(self._novo_usuario('sintetico-bad', staff=True), pl)
        self.assertEqual(resp.status_code, 400, resp.content)


class PickPericiaTests(_CriadorBase):
    """kind 'pericia' no PICK_REGISTRY: o Bárbaro Conhecimento Primitivo (N5, +1 no N10)
    passa a CONCEDER a escolha de verdade — pendência no painel genérico do level-up,
    universo = lista de perícias do Bárbaro menos as já proficientes, contagem pela
    fórmula classlvl (cumulativa), persistência em TbPersonagemEscolha e readback como
    proficiência no derive. Ancora a sintaxe de restrição das outras tags pick:pericia."""

    def _barbaro(self, nivel, apelido='dono-per'):
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('%s-%d' % (apelido, nivel)), nome='Bárbaro N%d' % nivel,
            nivel=nivel, forca=15, destreza=14, constituicao=13,
            inteligencia=12, sabedoria=10, carisma=8)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='barbaro'),
            nivel=nivel, principal=True)
        return p

    def _grupo_pericia(self, p):
        from home import picks
        return next(g for g in picks.resolve_personagem(p, kinds={'pericia'}))

    def test_conhecimento_primitivo_universo_menos_proficientes(self):
        # Bárbaro N10: Conhecimento Primitivo abre 2 slots (classlvl=5:1 + classlvl=10:1
        # cumulativo = 2); universo = perícias de classe do Bárbaro MENOS as já proficientes.
        p = self._barbaro(10)
        TbPersonagemPericia.objects.create(
            id_personagem=p, nome='Atletismo', atributo='FOR', proficiente=True)
        g = self._grupo_pericia(p)
        self.assertEqual(g['origem'], 'Conhecimento Primitivo')
        self.assertEqual(g['n'], 2)
        slugs = {u['slug'] for u in g['universo']}
        self.assertEqual(slugs, {'adestrar-animais', 'intimidacao', 'natureza',
                                 'percepcao', 'sobrevivencia'})
        self.assertNotIn('atletismo', slugs, 'perícia já proficiente sai do universo')

    def test_conta_por_formula_classlvl(self):
        # N5 => 1 (só classlvl=5:1); N10 => 2 (cumulativo). Prova a fórmula sem if.
        self.assertEqual(self._grupo_pericia(self._barbaro(5, 'n5'))['n'], 1)
        self.assertEqual(self._grupo_pericia(self._barbaro(10, 'n10'))['n'], 2)

    def test_persist_e_readback_como_proficiencia_no_derive(self):
        from home import picks
        from home.character_engine import derive
        p = self._barbaro(10)
        antes = {x['nome']: x['proficiente'] for x in derive(p)['pericias']}
        self.assertFalse(antes['Natureza'])
        self.assertFalse(antes['Sobrevivência'])
        g = self._grupo_pericia(p)
        g['slot_base'] = g['prox_slot']
        picks.PICK_REGISTRY['pericia']['persist'](p, g, ['natureza', 'sobrevivencia'])
        self.assertEqual(p.escolhas.filter(tipo='pericia').count(), 2)
        depois = {x['nome']: x['proficiente'] for x in derive(p)['pericias']}
        self.assertTrue(depois['Natureza'])
        self.assertTrue(depois['Sobrevivência'])
        # idempotência do painel: pendência zera e as escolhidas saem do universo
        g2 = self._grupo_pericia(p)
        self.assertEqual((g2['usados'], g2['pendentes']), (2, 0))
        self.assertNotIn('natureza', {u['slug'] for u in g2['universo']})

    def test_validate_conta_e_pertinencia(self):
        from home import picks
        reg = picks.PICK_REGISTRY['pericia']
        g = self._grupo_pericia(self._barbaro(10))
        self.assertEqual(reg['validate'](g, ['natureza', 'sobrevivencia']), [])
        self.assertTrue(reg['validate'](g, ['natureza']), 'conta errada rejeitada')
        self.assertTrue(reg['validate'](g, ['natureza', 'arcanismo']),
                        'perícia fora do universo do Bárbaro rejeitada')

    def test_painel_generico_lista_e_submete_sem_if_por_tipo(self):
        # _opcao_grupos (painel genérico do level-up) LISTA a pendência de perícia e o
        # POST persiste pelo REGISTRY — mesmo caminho das opções, sem ramo por tipo.
        p = self._barbaro(10)
        pg = next(g for g in views._opcao_grupos(p) if g['kind'] == 'pericia')
        self.assertEqual(pg['tipo'], 'Perícia')
        self.assertEqual(pg['pendentes'], 2)
        self.assertTrue(all(o['val'] == o['slug'] for o in pg['disponiveis']))
        val = pg['disponiveis'][0]['val']
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_escolher_opcoes', args=[p.pk]),
                                {'classe': pg['classe_id'], 'slug': pg['slug'], 'opcao': val})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(p.escolhas.filter(tipo='pericia', valor=val).count(), 1)

    def test_sintaxes_de_restricao_de_universo(self):
        # As sintaxes de restrição presentes na base parseiam para o mesmo universo.
        from home import picks
        classe = TbClasse.objects.get(slug='mago')
        casos = {
            'pick:pericia:1(de:[atletismo, acrobacia])': {'atletismo', 'acrobacia'},
            'always_active{ pick:pericia:1 de [percepcao, sobrevivencia] }':
                {'percepcao', 'sobrevivencia'},
            'pick:pericia:1{ de:[historia, intuicao] }': {'historia', 'intuicao'},
            'pick:pericia:1(=skill:{persuasao | intimidacao})': {'persuasao', 'intimidacao'},
            'pick:pericia:{arcanismo|historia|religiao}:1': {'arcanismo', 'historia', 'religiao'},
            'pick:pericia:1(de:[adestrar_animais, natureza])': {'adestrar-animais', 'natureza'},
        }
        for tag, esperado in casos.items():
            hab = TbClassehabilidade(id_classe=classe, nome='Feature X',
                                     niveladquirido=1, tags_json=[tag])
            g = next(x for x in picks.resolve_groups(
                [hab], classe=classe, nivel=10, personagem=None) if x['kind'] == 'pericia')
            self.assertEqual({u['slug'] for u in g['universo']}, esperado, tag)


class PickMetamagiaProgressaoTests(_CriadorBase):
    """BUG do dedup de `pick:opcao`: a progressão de Metamagia do Feiticeiro ficava presa em
    2. A dedup `(kind,sub,classe)` mantinha o PRIMEIRO token visto (o literal
    `pick:opcao:metamagia:2` das features N2/N10/N17) e descartava a fórmula por nível que
    concede mais. O resolvedor passa a manter a MAIOR contagem aplicável ao nível
    (`count_for`) entre os tokens/features repetidos: 2 no N2, 4 no N10, 6 no N17 — exatamente
    a descrição da classe (escolhe 2; +2 no 10º; +2 no 17º, totalizando 6)."""

    def _feiticeiro(self, nivel):
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('feit-%d' % nivel), nome='Feiticeiro N%d' % nivel,
            nivel=nivel, forca=8, destreza=14, constituicao=13,
            inteligencia=12, sabedoria=10, carisma=15)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='feiticeiro'),
            nivel=nivel, principal=True)
        return p

    def _n_metamagia(self, p):
        from home import picks
        g = next(g for g in picks.resolve_personagem(p, kinds={'opcao'})
                 if g['tipo'] == 'metamagia')
        return g['n']

    def test_progressao_2_4_6(self):
        self.assertEqual(self._n_metamagia(self._feiticeiro(2)), 2)
        self.assertEqual(self._n_metamagia(self._feiticeiro(10)), 4)
        self.assertEqual(self._n_metamagia(self._feiticeiro(17)), 6)

    def test_maior_formula_vence_o_primeiro_literal(self):
        # A feature de Metamagia carrega DOIS tokens de contagem: o literal `:2` (primeiro) e
        # a fórmula cumulativa. Antes o literal (primeiro visto) travava em 2; agora a MAIOR
        # (=6 no N17) vence. Prova a regra da dedup sem depender do fim-a-fim do personagem.
        from home import picks
        classe = TbClasse.objects.get(slug='feiticeiro')
        habs = list(TbClassehabilidade.objects.filter(
            id_classe=classe, id_subclasse__isnull=True, niveladquirido__lte=17))
        tokens = [t for h in habs for t in (h.tags_json or []) if 'pick:opcao:metamagia' in str(t)]
        self.assertIn('pick:opcao:metamagia:2', tokens)  # o literal "travador" está presente
        g = next(g for g in picks.resolve_groups(habs, classe=classe, nivel=17, personagem=None)
                 if g['tipo'] == 'metamagia')
        self.assertEqual(g['n'], 6)


class PickTalentoDefineMenuTests(_CriadorBase):
    """Picks de talento só persistem quando representam estado fixo da ficha.

    Máscara de Guerra escolhe sua modalidade no descanso longo e, portanto, seu
    ``pick`` dentro de ``instant{}`` é runtime: não abre pendência e não relê escolhas
    antigas. O ``define{list}`` irmão também não pode vazar perícias estáticas.
    """

    def _orc_com_mascara(self, nivel=1):
        from home.models import TbRaca
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('orc-mascara-%d' % nivel), nome='Orc da Máscara',
            id_raca=TbRaca.objects.get(slug='orc'), nivel=nivel,
            forca=15, destreza=13, constituicao=14, inteligencia=8, sabedoria=12, carisma=10)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='barbaro'),
            nivel=nivel, principal=True)
        # Máscara de Guerra é um talento racial salvo só por NOME (id_talento=None) — como no
        # Scar de produção; `_talentos` resolve a TbTracoracial pela raça do personagem.
        TbPersonagemTalento.objects.create(
            id_personagem=p, id_talento=None, categoria='racial', nivel=1,
            nome='Máscara de Guerra')
        return p

    def test_pick_de_uso_nao_vira_pendencia(self):
        from home import picks
        grupos = picks.resolve_personagem(self._orc_com_mascara())
        self.assertNotIn('mascara_guerra', {g['kind'] for g in grupos})

    def test_talento_nao_concede_pericia_estatica(self):
        # o define é MENU (stripado dos verbos passivos), não concessão fixa: nenhuma das
        # perícias listadas nas 4 máscaras (religião/natureza/arcanismo/enganação) vira
        # proficiência estática — só a escolha, quando feita, aplicaria a do ramo.
        from home.character_engine import derive
        prof = {x['nome'] for x in derive(self._orc_com_mascara())['pericias']
                if x['proficiente'] or x['expertise']}
        self.assertFalse(prof & {'Religião', 'Natureza', 'Arcanismo', 'Enganação'}, prof)

    def test_escolha_antiga_e_ignorada_sem_apagar_dado(self):
        from home import picks
        p = self._orc_com_mascara()
        p.escolhas.create(
            origem='Máscara de Guerra', tipo='mascara_guerra', valor='a_magia', slot=0)
        self.assertEqual(p.escolhas.filter(tipo='mascara_guerra', valor='a_magia').count(), 1)
        self.assertNotIn('mascara_guerra',
                         {g['kind'] for g in picks.resolve_personagem(p)})
        # Compatibilidade: parar de ler não significa destruir escolhas existentes.
        self.assertTrue(p.escolhas.filter(
            tipo='mascara_guerra', valor='a_magia').exists())


class PerfilDeArmaTests(_CriadorBase):
    """Capacidade 1 — perfil de ataque de arma do inventário equipado.

    Cada arma EQUIPADA (mundana ou mágica com dado de arma) vira um perfil: dado/tipo,
    atributo (FOR; DES p/ acuidade/à distância), acerto = mod + PB(se proficiente na
    categoria) + weapon.atk, dano = dado + mod + weapon.dmg; escopos melee/ranged/
    off_hand. Reviva os Estilos de Luta (Arquearia/Duelo/Defesa/Combate com Duas
    Armas) hoje órfãos. Maestria da arma aparece no perfil. O desarmado NÃO muda.
    """

    def _cria(self, classe_slug='barbaro', forca=16, destreza=10, sufixo=''):
        user = self._novo_usuario('arma-%s-%d-%d%s' % (classe_slug, forca, destreza, sufixo), staff=True)
        resp = self._post_criar(user, self._payload(classe_slug))
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        # Atributos determinísticos: zera bônus de ASI/antecedente e fixa o SCORE base.
        p.atributo_bonus.all().delete()
        p.forca, p.destreza = forca, destreza
        p.save(update_fields=['forca', 'destreza'])
        return p

    def _equipa(self, p, slug, equipado=True):
        w = TbItemMundano.objects.get(slug=slug)
        return TbPersonagemItem.objects.create(
            id_personagem=p, qtd=1, nome=w.nome, equipado=equipado,
            tags_json=list(w.tags_json or []))

    def _estilo(self, p, tags):
        """Liga UMA opção 'Estilo de Luta' (com as tags dadas) ao personagem via escolha.
        Classes usadas aqui (barbaro) não têm Estilo no N1, então não há escolha duplicada."""
        from home.models import TbPersonagemEscolha
        op = TbOpcaojogo.objects.filter(tipo='Estilo de Luta').first()
        op.tags_json = tags
        op.save(update_fields=['tags_json'])
        TbPersonagemEscolha.objects.update_or_create(
            id_personagem=p, origem='Estilo de Luta', tipo='estilo', slot=0,
            defaults={'id_opcao': op})
        return op

    def _derive(self, p):
        from home.character_engine import derive
        d = derive(p)
        return d, d['atributos']['FOR']['mod'], d['atributos']['DES']['mod'], d['bonus_proficiencia']

    def _perfil(self, ficha, escopo=None, nome_contem=None):
        for pf in ficha['ataques']['perfis']:
            if escopo and pf['escopo'] != escopo:
                continue
            if nome_contem and nome_contem.lower() not in pf['nome'].lower():
                continue
            return pf
        return None

    # ── caso base: melee por Força, com/sem proficiência ──
    def test_espada_longa_melee_por_forca(self):
        p = self._cria(forca=16, destreza=10)          # FOR +3, DES +0
        self._equipa(p, 'arma-espada-longa')
        d, FOR, DES, pb = self._derive(p)
        pf = self._perfil(d, nome_contem='Espada Longa')
        self.assertIsNotNone(pf, d['ataques'])
        self.assertEqual(pf['escopo'], 'weapon-melee')
        self.assertEqual(pf['atributo'], 'FOR')
        self.assertTrue(pf['proficiente'])              # bárbaro é proficiente em marciais
        self.assertEqual(pf['bonus_ataque'], FOR + pb)
        self.assertEqual(pf['dano'], '1d8 %+d cortante' % FOR)
        # o aviso 'não derivados' sumiu (perfil derivado de verdade)
        self.assertEqual(d['ataques']['avisos'], [])

    def test_arma_nao_equipada_nao_gera_perfil(self):
        p = self._cria()
        self._equipa(p, 'arma-espada-longa', equipado=False)
        d, *_ = self._derive(p)
        self.assertIsNone(self._perfil(d, nome_contem='Espada Longa'))

    def test_desarmado_nao_muda_com_arma_equipada(self):
        # regressão do Scar: derivar armas não pode mexer no perfil desarmado.
        p = self._cria()
        base = self._perfil(self._derive(p)[0], escopo='unarmed-strike')
        self._equipa(p, 'arma-espada-longa')
        depois = self._perfil(self._derive(p)[0], escopo='unarmed-strike')
        self.assertEqual(base, depois)

    def test_firearm_sem_proficiencia_nao_soma_pb(self):
        p = self._cria(forca=10, destreza=18)           # DES +4
        self._equipa(p, 'arma-pistola-pederneira')       # à distância, 'Armas de Fogo'
        d, FOR, DES, pb = self._derive(p)
        pf = self._perfil(d, nome_contem='Pistola')
        self.assertIsNotNone(pf, d['ataques'])
        self.assertEqual(pf['atributo'], 'DES')          # arma à distância -> DES
        self.assertFalse(pf['proficiente'])              # bárbaro não tem Armas de Fogo
        self.assertEqual(pf['bonus_ataque'], DES)        # sem PB
        self.assertTrue(pf['nota'])

    # ── atributo: acuidade e à distância ──
    def test_rapieira_acuidade_usa_maior_mod(self):
        p = self._cria(forca=10, destreza=18)           # DES +4 > FOR +0
        self._equipa(p, 'arma-rapieira')                 # acuidade (finesse)
        d, FOR, DES, pb = self._derive(p)
        pf = self._perfil(d, nome_contem='Rapieira')
        self.assertEqual(pf['atributo'], 'DES')
        self.assertEqual(pf['bonus_ataque'], DES + pb)
        self.assertEqual(pf['dano'], '1d8 %+d perfurante' % DES)

    def test_arco_curto_a_distancia_usa_des(self):
        p = self._cria(forca=16, destreza=14)           # FOR +3, DES +2
        self._equipa(p, 'arma-arco-curto')
        d, FOR, DES, pb = self._derive(p)
        pf = self._perfil(d, escopo='weapon-ranged')
        self.assertIsNotNone(pf, d['ataques'])
        self.assertEqual(pf['atributo'], 'DES')
        self.assertEqual(pf['bonus_ataque'], DES + pb)

    # ── Estilos de Luta revividos ──
    def test_arquearia_soma_so_no_perfil_a_distancia(self):
        p = self._cria(forca=14, destreza=14)
        self._equipa(p, 'arma-arco-curto')               # à distância
        self._equipa(p, 'arma-espada-longa')             # corpo a corpo
        self._estilo(p, ['always_active{ ranged.atk:+2 }'])
        d, FOR, DES, pb = self._derive(p)
        arco = self._perfil(d, escopo='weapon-ranged')
        espada = self._perfil(d, escopo='weapon-melee')
        self.assertEqual(arco['bonus_ataque'], DES + pb + 2)     # +2 no ranged
        self.assertEqual(espada['bonus_ataque'], FOR + pb)       # melee intocado

    def test_duelo_soma_dano_so_no_corpo_a_corpo(self):
        p = self._cria(forca=16, destreza=16)
        self._equipa(p, 'arma-espada-longa')             # melee
        self._equipa(p, 'arma-arco-curto')               # ranged
        self._estilo(p, ['always_active{ requires:{ equiped{weapon{melee}} and one_handed and without{other_weapon} }, melee.dmg:+2 }'])
        d, FOR, DES, pb = self._derive(p)
        espada = self._perfil(d, escopo='weapon-melee')
        arco = self._perfil(d, escopo='weapon-ranged')
        self.assertEqual(espada['dano'], '1d8 %+d cortante' % (FOR + 2))
        self.assertEqual(arco['dano'], '1d6 %+d perfurante' % DES)   # ranged sem +2

    def test_defesa_soma_ca_so_com_armadura(self):
        p = self._cria()
        self._estilo(p, ['always_active{ requires:equiped{armor}, armor.ca:+1 }'])
        sem = self._derive(p)[0]['ca']
        # equipa uma armadura qualquer que dê CA base (ca= nas tags)
        arm = next((a for a in TbItemMundano.objects.filter(categoria='armadura')
                    if any(str(t).strip().startswith('ca=') for t in (a.tags_json or []))), None)
        if arm is None:
            self.skipTest('sem armadura no catálogo de teste')
        TbPersonagemItem.objects.create(id_personagem=p, qtd=1, nome=arm.nome,
                                        equipado=True, tags_json=list(arm.tags_json or []))
        com = self._derive(p)[0]
        self.assertEqual(com['ca'], self._ca_base_armadura(arm, p) + 1)
        self.assertIn('estilo', com['ca_fonte'])

    def _ca_base_armadura(self, arm, p):
        from home.item_mecanica import mecanica_de_tags
        from home.character_engine import _eval_formula, modificador
        mec = mecanica_de_tags(arm.tags_json, arm.subcategoria)
        dex = modificador(p.destreza)
        ca = _eval_formula(mec.get('ca_formula') or '', {'dex_mod': dex})
        return ca if ca is not None else (mec['ca_base'] or 10) + dex

    def test_duas_armas_leves_gera_offhand_sem_mod_positivo(self):
        p = self._cria(forca=10, destreza=18)            # mod +4
        self._equipa(p, 'arma-espada-curta')             # leve, acuidade
        self._equipa(p, 'arma-adaga')                    # leve, acuidade
        d, FOR, DES, pb = self._derive(p)
        off = self._perfil(d, escopo='off_hand')
        self.assertIsNotNone(off, d['ataques'])
        # mão secundária: sem modificador POSITIVO no dano (regra 5e)
        self.assertRegex(off['dano'], r'^1d[46] \+0')
        # mas o acerto mantém mod + PB
        self.assertEqual(off['bonus_ataque'], DES + pb)

    def test_combate_com_duas_armas_devolve_mod_ao_offhand(self):
        p = self._cria(forca=10, destreza=18)            # mod +4
        self._equipa(p, 'arma-espada-curta')
        self._equipa(p, 'arma-adaga')
        self._estilo(p, ['always_active{ requires:weapon{leve}, off_hand.dmg:+ability_mod }'])
        d, FOR, DES, pb = self._derive(p)
        off = self._perfil(d, escopo='off_hand')
        self.assertRegex(off['dano'], r'\+%d' % DES)     # mod positivo devolvido

    # ── item mágico de bônus plano + maestria no perfil ──
    def test_item_weapon_bonus_soma_no_perfil_de_arma(self):
        from home.models import TbItemMagico
        p = self._cria(forca=16, destreza=10)
        mag = TbItemMagico.objects.create(
            nome='Espada Longa +1 (teste)', slug='espada-longa-1-teste', raridade='incomum',
            slot='arma', tags_json=['item:magico', 'weapon.atk:+1', 'weapon.dmg:+1'])
        w = TbItemMundano.objects.get(slug='arma-espada-longa')
        TbPersonagemItem.objects.create(id_personagem=p, qtd=1, nome=w.nome, equipado=True,
                                        tags_json=list(w.tags_json or []), id_item_magico=mag)
        d, FOR, DES, pb = self._derive(p)
        pf = self._perfil(d, nome_contem='Espada Longa')
        self.assertEqual(pf['bonus_ataque'], FOR + pb + 1)
        self.assertEqual(pf['dano'], '1d8 %+d cortante' % (FOR + 1))

    def test_maestria_da_arma_aparece_no_perfil(self):
        # Maestria de Arma em DOIS NÍVEIS (desenho correto): a escolha é ARMA + UMA maestria
        # dela, no formato combinado `'<arma>|<maestria>'`. O perfil de ataque traz SÓ a
        # maestria escolhida (minar_sap), resolvida ao NOME legível do catálogo pela ponte de
        # slug '_'→'-' (a tag da arma usa 'minar_sap'; TbOpcaojogo usa 'minar-sap').
        from home.models import TbPersonagemEscolha, TbOpcaojogo
        p = self._cria()
        p.escolhas.filter(tipo='maestria').delete()
        TbPersonagemEscolha.objects.create(id_personagem=p, origem='Maestria em Armas',
                                           tipo='maestria', slot=0,
                                           valor='arma-espada-longa|minar_sap')
        self._equipa(p, 'arma-espada-longa')
        d, *_ = self._derive(p)
        pf = self._perfil(d, nome_contem='Espada Longa')
        nome_minar = TbOpcaojogo.objects.get(slug='minar-sap').nome
        # EXATAMENTE a escolhida: o perfil mostra o nome legível de minar_sap e nada mais.
        self.assertEqual(pf['maestria'], nome_minar, pf)
        self.assertNotIn('minar_sap', pf['maestria'])              # não vaza o slug cru
        for outra in ('raspar-graze', 'debilitar-weaken'):         # nem as outras da espada longa
            self.assertNotIn(TbOpcaojogo.objects.get(slug=outra).nome, pf['maestria'], pf)


class _ConcessaoBase(_CriadorBase):
    """Base p/ Capacidades 2 e 3: cria um bárbaro determinístico (sem expertise/grant
    próprios) e injeta features sintéticas via opção-fonte (lida por _features_de_opcoes)."""

    _seq = 0

    def _cria(self, forca=16):
        _ConcessaoBase._seq += 1
        user = self._novo_usuario('conc-%d' % _ConcessaoBase._seq, staff=True)
        resp = self._post_criar(user, self._payload('barbaro'))
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        p.atributo_bonus.all().delete()
        p.forca, p.destreza = forca, 10
        p.save(update_fields=['forca', 'destreza'])
        return p

    def _feature_opcao(self, p, tags, origem='Feature Teste', tipo='Estilo de Luta', slot=0):
        """Anexa uma opção-fonte (TbOpcaojogo própria) com as tags dadas como feature ativa
        do personagem (via TbPersonagemEscolha com id_opcao). É lida por _features_de_opcoes
        (efeitos passivos + grant:opcao/grant:talento no grants_fixos)."""
        from home.models import TbPersonagemEscolha
        _ConcessaoBase._seq += 1
        op = TbOpcaojogo.objects.create(
            tipo=tipo, slug='conc-carrier-%d' % _ConcessaoBase._seq, nome=origem,
            tags_json=list(tags))
        TbPersonagemEscolha.objects.create(
            id_personagem=p, origem=origem[:150], tipo='estilo', slot=slot, id_opcao=op)
        return op

    def _derive(self, p):
        from home.character_engine import derive
        d = derive(p)
        return d, d['atributos']['FOR']['mod'], d['bonus_proficiencia']

    def _per(self, d, nome):
        return next((x for x in d['pericias'] if x['nome'] == nome), None)


class ExpertisePorTagTests(_ConcessaoBase):
    """Capacidade 2 — Especialização (expertise) por tag: o dobro do PB numa perícia.

    (A) verbo direto `expertise:<pericia>` em segmento passivo (Campeão/Comandante/Cav.
        Arcano/Ronin/Veterano da Horda/Curandeiro). Expertise IMPLICA proficiência.
    (B) kind `pick:pericia_expertise` no PICK_REGISTRY (escolha entre as proficientes),
        persistido em TbPersonagemEscolha e relido no derive (Ladino/Batedor/Monge).
    """

    # ── (A) verbo direto ──
    def test_expertise_verbo_direto_dobra_o_pb(self):
        p = self._cria(forca=16)                       # FOR +3
        base = self._per(self._derive(p)[0], 'Atletismo')['bonus']
        self._feature_opcao(p, ['always_active{ expertise:atletismo }'])
        d, FOR, pb = self._derive(p)
        per = self._per(d, 'Atletismo')
        self.assertTrue(per['proficiente'])            # expertise implica proficiência
        self.assertTrue(per['expertise'])
        self.assertEqual(per['bonus'], FOR + 2 * pb)   # DOBRO do PB (prova absoluta)
        self.assertGreater(per['bonus'], base)         # subiu vs. antes da expertise

    def test_expertise_condicional_if_prof(self):
        # Cena é Corpo / Dom de Palco (slug PT corrigido): always_active{ prof:X, if(prof:X):expertise:X }
        p = self._cria()
        self._feature_opcao(p, ['always_active{ prof:atuacao, if(prof:atuacao):expertise:atuacao }'])
        per = self._per(self._derive(p)[0], 'Atuação')
        self.assertTrue(per['expertise'], per)

    def test_expertise_de_ferramenta_permanece_inerte(self):
        # expertise:tool{}/ferramentas não são perícias -> continuam mortas (sem surface).
        p = self._cria()
        d0 = self._derive(p)[0]
        self._feature_opcao(p, ['always_active{ expertise:ferramentas }',
                                'prof:tool{utensilios_de_cozinha}, expertise:tool{utensilios_de_cozinha}'])
        d1 = self._derive(p)[0]
        self.assertEqual([x['expertise'] for x in d0['pericias']],
                         [x['expertise'] for x in d1['pericias']])

    # ── (B) kind pick:pericia_expertise (universe/persist/readback + derive) ──
    def _proficiente(self, p, nome, attr):
        from home.models import TbPersonagemPericia
        TbPersonagemPericia.objects.update_or_create(
            id_personagem=p, nome=nome, defaults={'atributo': attr, 'proficiente': True})

    def test_pick_expertise_readback_dobra_o_pb(self):
        from home.models import TbPersonagemEscolha
        p = self._cria()
        self._proficiente(p, 'Intuição', 'SAB')
        antes = self._per(self._derive(p)[0], 'Intuição')
        self.assertTrue(antes['proficiente'] and not antes['expertise'])
        base = antes['bonus']
        TbPersonagemEscolha.objects.create(id_personagem=p, origem='Perícia Especializada',
                                           tipo='pericia_expertise', slot=0, valor='intuicao')
        d, FOR, pb = self._derive(p)
        depois = self._per(d, 'Intuição')
        self.assertTrue(depois['expertise'])
        self.assertEqual(depois['bonus'] - base, pb)   # +1 PB adicional (dobro)

    def test_pick_expertise_grupo_end_to_end(self):
        """Token -> grupo (registry) -> persist -> derive: prova a máquina do kind inteira."""
        import types
        from home import picks
        p = self._cria()
        self._proficiente(p, 'Furtividade', 'DES')
        src = types.SimpleNamespace(
            nome='Treinamento das Sombras',
            tags_json=['pick:pericia_expertise:1(from:{furtividade | acrobacia | prestidigitacao})'])
        grupos = picks.resolve_groups([src], classe=None, subclasse=None,
                                      nivel=int(p.nivel or 1), personagem=p)
        g = next((x for x in grupos if x['kind'] == 'pericia_expertise'), None)
        self.assertIsNotNone(g, grupos)
        self.assertEqual(g['n'], 1)
        # universo = só PROFICIENTES DENTRO da restrição from:{...}; Furtividade presente,
        # nada fora da lista permitida.
        univ = [u['slug'] for u in g['universo']]
        self.assertIn('furtividade', univ)
        self.assertTrue(set(univ) <= {'furtividade', 'acrobacia', 'prestidigitacao'}, univ)
        picks.PICK_REGISTRY['pericia_expertise']['persist'](p, g, ['furtividade'])
        per = self._per(self._derive(p)[0], 'Furtividade')
        self.assertTrue(per['expertise'], per)

    def test_pick_expertise_universo_exclui_ja_especializada(self):
        from home.models import TbPersonagemPericia
        from home import picks
        p = self._cria()
        TbPersonagemPericia.objects.create(id_personagem=p, nome='Intuição', atributo='SAB',
                                           proficiente=True, expertise=True)
        ctx = {'personagem': p, 'tipo': None, 'tag_text': 'pick:pericia_expertise:1'}
        universo = {u['slug'] for u in picks.PICK_REGISTRY['pericia_expertise']['universe'](ctx)}
        self.assertNotIn('intuicao', universo)          # já especializada -> fora do universo


class GrantsFixosTests(_ConcessaoBase):
    """Capacidade 3 — concessões FIXAS sem escolha (grant:opcao / grant:talento).

    grant:opcao:<tipo>:<slug> e grant:opcao{<tipo>: [<slugs>]} adicionam uma opção
    específica à ficha (via _features_de_opcoes) FORA do painel de pick. grant:talento{slug,
    without{asi}} concede os benefícios de um talento sem o incremento de atributo. Materialização
    idempotente e origem-rastreada (padrão de _sync_magias_concedidas).
    """

    def _mm_alvo(self):
        """Metamagia-alvo sintética (slug hifenado, como o catálogo real)."""
        return TbOpcaojogo.objects.create(tipo='Metamagia', slug='mm-teste-grant',
                                          nome='MM Teste', tags_json=['modify:spell{ without{verbal} }'])

    def test_grant_opcao_single_materializa_e_aparece(self):
        p = self._cria()
        self._mm_alvo()
        self._feature_opcao(p, ['grant:opcao:metamagia:mm_teste_grant(extra, always_prepared)'],
                            origem='Metamagia Concedida')
        # engine reporta a concessão
        from home.character_engine import grants_fixos
        gf = grants_fixos(p)
        self.assertIn('mm-teste-grant', [o['slug'] for o in gf['opcoes']])
        # sync materializa como escolha 'grant-opcao' (NÃO conta no pick)
        n_op, n_tal = views._sync_grants_fixos(p)
        self.assertEqual((n_op, n_tal), (1, 0))
        esc = p.escolhas.filter(tipo='grant-opcao')
        self.assertEqual(esc.count(), 1)
        self.assertEqual(esc.first().id_opcao.slug, 'mm-teste-grant')
        # aparece na ficha (state['features'] via _features_de_opcoes)
        d = self._derive(p)[0]
        self.assertIn('MM Teste', [f['nome'] for f in d['features']])

    def test_grant_opcao_lista_materializa_varias(self):
        p = self._cria()
        for slug in ('mm-a', 'mm-b'):
            TbOpcaojogo.objects.create(tipo='Metamagia', slug=slug, nome=slug.upper(),
                                       tags_json=['modify:spell{ without{verbal} }'])
        self._feature_opcao(p, ['grant:opcao{metamagia: [mm-a, mm-b], fora_do_limite}'],
                            origem='Lista Concedida')
        views._sync_grants_fixos(p)
        slugs = {e.id_opcao.slug for e in p.escolhas.filter(tipo='grant-opcao')}
        self.assertEqual(slugs, {'mm-a', 'mm-b'})

    def test_grant_opcao_idempotente(self):
        p = self._cria()
        self._mm_alvo()
        self._feature_opcao(p, ['grant:opcao:metamagia:mm_teste_grant(extra)'])
        views._sync_grants_fixos(p)
        views._sync_grants_fixos(p)          # 2ª chamada não duplica
        self.assertEqual(p.escolhas.filter(tipo='grant-opcao').count(), 1)

    def test_grant_opcao_removida_quando_deixa_de_valer(self):
        p = self._cria()
        self._mm_alvo()
        op = self._feature_opcao(p, ['grant:opcao:metamagia:mm_teste_grant(extra)'])
        views._sync_grants_fixos(p)
        self.assertEqual(p.escolhas.filter(tipo='grant-opcao').count(), 1)
        # remove a feature-fonte -> a concessão some (idempotência de remoção)
        p.escolhas.filter(id_opcao=op).delete()
        views._sync_grants_fixos(p)
        self.assertEqual(p.escolhas.filter(tipo='grant-opcao').count(), 0)

    def test_grant_talento_concede_beneficios_sem_asi(self):
        p = self._cria(forca=16)
        for_antes = self._derive(p)[0]['atributos']['FOR']['valor']
        t = TbTalento.objects.create(nome='Talento Teste Grant', slug='talento_teste_grant',
                                     tipo='geral', tags_json=['prof:historia'], atrib_forca=True)
        self._feature_opcao(p, ['grant:talento{talento_teste_grant, without{asi}}'], origem='Concede Talento')
        n_op, n_tal = views._sync_grants_fixos(p)
        self.assertEqual((n_op, n_tal), (0, 1))
        pt = p.talentos.filter(categoria='concedido')
        self.assertEqual(pt.count(), 1)
        self.assertEqual(pt.first().id_talento_id, t.id_talento)
        d = self._derive(p)[0]
        # benefício do talento aplicado (proficiência em História)
        self.assertTrue(self._per(d, 'História')['proficiente'])
        # without{asi}: NENHUM incremento de atributo (a Força não subiu)
        self.assertEqual(d['atributos']['FOR']['valor'], for_antes)

    def test_grant_nao_casa_verbos_de_runtime(self):
        # grant:reaction / grant:grapple / grant:move NÃO são concessões fixas.
        from home.character_engine import grants_fixos
        p = self._cria()
        self._feature_opcao(p, ['trigger=hit, instant{ grant:grapple(without{extra_action}) }',
                                'grant:move(without{opportunity})', 'grant:reaction{ attack:1 }'])
        gf = grants_fixos(p)
        self.assertEqual(gf['opcoes'], [])
        self.assertEqual(gf['talentos'], [])


class Cap56VerbosNovosTests(_CriadorBase):
    """Cap 5/6 — verbos novos, provados no DERIVE:
      A. modify:<X> cross-feature — registrado inerte (modo=combate) e RETIRADO da
         varredura estática (não vaza resist:/str_score:/immune: internos).
      B. verbos menores ESTÁTICOS: ability_check/all_checks/<attr>_check (Pau Pra Toda
         Obra), attr_max:sintonizacao (limite por nível), speed:+resource/+fórmula
         (gate de armadura), incremento relativo de sentido, move:liquid, check_bonus
         com vírgula (max(wis_mod,1)); e gate requires:lvl>=N em segmento passivo,
         resist:source{} nota, while:<cond>{} ativo, max_cr na biblioteca.
    """

    _seq = 0

    def _mk(self, feats, nivel=11, classe='mago'):
        Cap56VerbosNovosTests._seq += 1
        u = self._novo_usuario('cap56-%d' % Cap56VerbosNovosTests._seq)
        p = TbPersonagem.objects.create(
            dono=u, nome='Cap56 N%d #%d' % (nivel, Cap56VerbosNovosTests._seq), nivel=nivel,
            forca=12, destreza=12, constituicao=12, inteligencia=12, sabedoria=14, carisma=12)
        cl = TbClasse.objects.get(slug=classe)
        TbPersonagemClasse.objects.create(id_personagem=p, id_classe=cl, nivel=nivel, principal=True)
        for i, tags in enumerate(feats):
            TbClassehabilidade.objects.create(
                id_classe=cl, id_subclasse=None, nome='Cap56 F%d #%d' % (i, Cap56VerbosNovosTests._seq),
                descricao='.', niveladquirido=1, tags_json=list(tags))
        return p

    def _relevel(self, p, nivel):
        p.nivel = nivel
        p.save(update_fields=['nivel'])
        c = p.classes.first()
        c.nivel = nivel
        c.save(update_fields=['nivel'])

    def _d(self, p):
        from home.character_engine import derive
        return derive(p)

    def _per(self, d, nome):
        return next(x for x in d['pericias'] if x['nome'] == nome)

    # ── A. modify: cross-feature ──
    def test_modify_registrado_inerte_e_sem_vazamento(self):
        # modify:companion.resist:... NÃO vaza resistência-lixo no PC; verbo IRMÃO
        # (prof:atletismo) é preservado; o descritor fica registrado (modo=combate).
        p = self._mk([['always_active{ modify:companion.resist:match(pick:energia){ '
                       'lumen:radiante, umbra:necrotico }(target:companion), prof:atletismo }']])
        d = self._d(p)
        self.assertEqual(d['resistencias'], [])           # nenhum vazamento (radiante/necrotico/match)
        self.assertTrue(self._per(d, 'Atletismo')['proficiente'])  # irmão preservado
        mods = d.get('modificadores') or []
        self.assertTrue(any(m['alvo_tipo'] == 'companion' and m['modo'] == 'combate' for m in mods))

    def test_modify_ability_bloco_nao_vaza_immune_alento(self):
        # modify:ability{...}{ ignore:resist:alento, ... } não injeta imunidade/resist lixo.
        p = self._mk([['always_active{ modify:ability{sopro_draconico, essencia:draconica}{ '
                       'ignore:resist:alento, dmg_bonus:lvl } }']])
        d = self._d(p)
        self.assertEqual(d['resistencias'], [])
        self.assertEqual([x for x in d['imunidades'] if 'alento' in x.lower()], [])

    # ── B. ability_check / all_checks / <attr>_check (Pau Pra Toda Obra) ──
    def test_ability_check_meia_proficiencia_nas_nao_proficientes(self):
        p = self._mk([['always_active{ ability_check:+(rounddown(pb/2))(unless:proficient) }']])
        d = self._d(p)
        pb = d['bonus_proficiencia']
        half = pb // 2
        self.assertGreater(half, 0)
        nao_prof = [s for s in d['pericias'] if not s['proficiente'] and not s['expertise']]
        self.assertTrue(nao_prof)
        for s in nao_prof:
            amod = d['atributos'][s['atributo']]['mod']
            self.assertEqual(s['bonus'], amod + half, 'jack em %s' % s['nome'])
        for s in d['pericias']:
            if s['proficiente'] and not s['expertise']:
                amod = d['atributos'][s['atributo']]['mod']
                self.assertEqual(s['bonus'], amod + pb, 'proficiente NÃO leva jack: %s' % s['nome'])

    def test_attr_check_filtra_por_atributo(self):
        # str_check:+3 só nas perícias de Força.
        p = self._mk([['always_active{ str_check:+3 }']])
        d = self._d(p)
        atl = self._per(d, 'Atletismo')          # FOR
        acr = self._per(d, 'Acrobacia')          # DES
        self.assertEqual(atl['bonus'], d['atributos']['FOR']['mod'] + 3 + (d['bonus_proficiencia'] if atl['proficiente'] else 0))
        self.assertEqual(acr['bonus'], d['atributos']['DES']['mod'] + (d['bonus_proficiencia'] if acr['proficiente'] else 0))

    # ── B. attr_max:sintonizacao (limite por nível) ──
    def test_sintonizacao_maxima_escala_por_nivel(self):
        p = self._mk([['always_active{ attr_max:sintonizacao=match(classlvl){'
                       'classlvl>=18:6, classlvl>=14:5, default:4} }']], nivel=10)
        self.assertEqual(self._d(p)['sintonizacao_maxima'], 4)
        self._relevel(p, 14)
        self.assertEqual(self._d(p)['sintonizacao_maxima'], 5)
        self._relevel(p, 18)
        self.assertEqual(self._d(p)['sintonizacao_maxima'], 6)

    def test_sintonizacao_base_e_tres(self):
        self.assertEqual(self._d(self._mk([[]]))['sintonizacao_maxima'], 3)

    # ── B. speed:+resource / +fórmula + gate de armadura ──
    def test_speed_formula(self):
        p = self._mk([['always_active{ speed:+min(2*pb, 30) }']])   # pb=4 -> +8
        self.assertEqual(self._d(p)['velocidade_bonus'], 8)

    def test_speed_resource_no_nivel(self):
        from home.models import TbRecursoclasse, TbClasse
        cl = TbClasse.objects.get(slug='mago')
        TbRecursoclasse.objects.create(id_classe=cl, id_subclasse=None, nome='Passo Veloz',
                                       slug='passo_veloz', valores_json={'1': '15 ft'})
        p = self._mk([['always_active{ speed:+resource{passo_veloz} }']])
        self.assertEqual(self._d(p)['velocidade_bonus'], 15)

    def test_speed_gate_armadura_bloqueia(self):
        p = self._mk([['always_active{ restriction{equiped{armadura}, equiped{escudo}}, '
                       'speed:+min(2*pb, 30) }']])
        # descalço: bônus aplica
        self.assertEqual(self._d(p)['velocidade_bonus'], 8)
        # com escudo equipado (tag ca:+2 => is_escudo): gate bloqueia
        TbPersonagemItem.objects.create(id_personagem=p, nome='Escudo', qtd=1,
                                        equipado=True, tags_json=['ca:+2'])
        self.assertEqual(self._d(p)['velocidade_bonus'], 0)

    # ── B. incremento relativo de sentido ──
    def test_sentido_incremento_relativo_if_present(self):
        p = self._mk([['always_active{ sense:darkvision(range:60ft) }'],
                      ['always_active{ sense:darkvision(range:+60ft, if_present) }']])
        self.assertIn('darkvision 120ft', self._d(p)['sentidos'])

    def test_sentido_if_present_sem_base_e_descartado(self):
        p = self._mk([['always_active{ sense:tremorsense(range:+30ft, if_present) }']])
        self.assertNotIn('tremorsense', ' '.join(self._d(p)['sentidos']))

    def test_sentido_if_present_nao_usa_base_da_propria_feature(self):
        p = self._mk([[
            'always_active{ sense:darkvision(range:60ft), '
            'sense:darkvision(range:+30ft, if_present) }',
        ]])
        self.assertIn('darkvision 60ft', self._d(p)['sentidos'])
        self.assertNotIn('darkvision 90ft', self._d(p)['sentidos'])

    # ── B. move:liquid ──
    def test_move_liquid(self):
        p = self._mk([['always_active{ move:wall, move:liquid }']])
        modos = self._d(p).get('movimento_modos') or {}
        self.assertIn('liquid', modos)
        self.assertIn('wall', modos)

    # ── B. check_bonus com vírgula interna (max(wis_mod, 1)) ──
    def test_check_bonus_formula_com_virgula(self):
        p = self._mk([['always_active{ check_bonus:religiao=max(wis_mod, 1) }']])
        d = self._d(p)
        rel = self._per(d, 'Religião')
        base = d['atributos'][rel['atributo']]['mod'] + (d['bonus_proficiencia'] if rel['proficiente'] else 0)
        self.assertEqual(rel['bonus'], base + 2)          # wis_mod=+2 (SAB 14); regex antigo -> None

    # ── B. gate requires:lvl>=N em segmento passivo ──
    def test_requires_lvl_gate_passivo(self):
        feat = ['always_active{ sense:devilsight(requires:lvl>=5) }']
        p3 = self._mk([feat], nivel=3)
        self.assertNotIn('devilsight', ' '.join(self._d(p3)['sentidos']))
        p5 = self._mk([feat], nivel=5)
        self.assertIn('devilsight', ' '.join(self._d(p5)['sentidos']))

    # ── B. resist:source{} vira nota ──
    def test_resist_source_vira_nota(self):
        p = self._mk([['always_active{ adv:save{spell}, resist:source{magical_effect} }']])
        d = self._d(p)
        self.assertEqual(d['resistencias'], [])
        self.assertTrue(any('resistência a dano de magical effect' in n for n in d['notas_passivas']))

    # ── B. while:<cond>{} é ativo (não vaza estático) ──
    def test_while_cond_nao_vaza_desvantagem_permanente(self):
        p = self._mk([['while:in_sunlight{dadv:attack, dadv:check, dadv:save}']])
        d = self._d(p)
        self.assertEqual(d.get('desvantagens_impostas', []), [])

    # ── B. max_cr registrado na biblioteca (mata WARN 'cr') ──
    def test_max_cr_conhecido_e_sem_warn(self):
        from home.tag_engine import Library, validate_tags_json
        lib = Library()
        self.assertTrue(lib.head_known('max_cr'))
        diags = validate_tags_json(['restriction{ forma: creature_type:besta, max_cr:2 }'], lib)
        self.assertFalse([d for d in diags if d.code == 'verbo-desconhecido'],
                         'max_cr não deve gerar verbo-desconhecido')


# ─────────────────────────── R3 Blocos A/B/C ────────────────────────────
class BlocoCRecursoFormulaTests(_CriadorBase):
    """Bloco C (decisão 9): o TOTAL de um recurso pode ser uma FÓRMULA (descrição
    prevalece). Fúrias do Bárbaro = Bônus de Proficiência — não a tabela fixa
    2/3/4/5/6. O motor avalia a fórmula (multiclasse-safe pelo nível TOTAL)."""

    def setUp(self):
        from home.models import TbRecursoclasse
        # A descrição da Fúria diz "usos = Bônus de Proficiência". Reforça a fórmula no
        # DB de teste (a fixture pode estar defasada) p/ exercitar a CAPACIDADE do motor.
        n = TbRecursoclasse.objects.filter(
            id_classe__slug='barbaro', slug='furias'
        ).update(valores_json={'1': 'pb'}, tipo='consumable', reset='long-rest')
        self.assertEqual(n, 1, 'recurso Fúrias do Bárbaro não encontrado na fixture')
        self.dono = self._novo_usuario('dono-furia')

    def _barbaro(self, nivel, multiclasse=None):
        p = TbPersonagem.objects.create(
            dono=self.dono, nome='Fúria N%d' % nivel, nivel=nivel,
            forca=16, destreza=14, constituicao=15, inteligencia=8, sabedoria=10, carisma=12)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='barbaro'),
            nivel=(multiclasse['barbaro'] if multiclasse else nivel), principal=True)
        if multiclasse:
            TbPersonagemClasse.objects.create(
                id_personagem=p, id_classe=TbClasse.objects.get(slug=multiclasse['classe']),
                nivel=multiclasse['nivel2'], principal=False)
        return p

    def _furias_max(self, p):
        from home.character_engine import _recursos_consumiveis
        classes = list(p.classes.select_related('id_classe', 'id_subclasse'))
        for r in _recursos_consumiveis(p, classes):
            if (r.get('slug') or '') == 'furias' or r['nome'] == 'Fúrias':
                return r['maximo']
        return None

    def test_furias_igual_pb_por_nivel(self):
        from home.character_engine import _pb_from_nivel
        for nivel in (1, 3, 5, 6, 11, 12, 17, 20):
            p = self._barbaro(nivel)
            self.assertEqual(
                self._furias_max(p), _pb_from_nivel(nivel),
                'Fúrias N%d deve exibir PB=%d (descrição), não a tabela fixa'
                % (nivel, _pb_from_nivel(nivel)))

    def test_furias_discrimina_da_tabela_antiga(self):
        # nv3: PB=2 (a tabela hardcoded antiga dava 3) -> prova que a descrição prevaleceu.
        self.assertEqual(self._furias_max(self._barbaro(3)), 2)
        # nv6: PB=3 (tabela antiga dava 4).
        self.assertEqual(self._furias_max(self._barbaro(6)), 3)

    def test_furias_multiclasse_usa_pb_do_nivel_total(self):
        # Bárbaro 3 / Guerreiro 8 = nível TOTAL 11 -> PB=4 (não o PB do nível de classe 3).
        p = self._barbaro(11, multiclasse={'barbaro': 3, 'classe': 'guerreiro', 'nivel2': 8})
        self.assertEqual(self._furias_max(p), 4)

    def test_resource_value_at_avalia_pb(self):
        from home.models import TbRecursoclasse
        from home.character_engine import _resource_value_at
        r = TbRecursoclasse.objects.get(id_classe__slug='barbaro', slug='furias')
        self.assertEqual(_resource_value_at(r, 5, 5), '3')    # PB nv5
        self.assertEqual(_resource_value_at(r, 12, 12), '4')  # PB nv12 (tabela antiga daria 5)

    def test_resource_value_at_avalia_modificador_de_atributo(self):
        from home.models import TbRecursoclasse
        from home.character_engine import _resource_value_at
        chama = TbRecursoclasse.objects.get(slug='chama-angelical')
        disparo = TbRecursoclasse.objects.get(slug='usos-de-disparo-silvestre')
        self.assertEqual(_resource_value_at(chama, 3, 3, {'cha_mod': 4}), '5')
        self.assertEqual(_resource_value_at(disparo, 3, 3, {'wis_mod': -1}), '1')
        self.assertEqual(_resource_value_at(disparo, 3, 3, {'wis_mod': 3}), '3')

    def test_attr_max_de_recurso_e_generico(self):
        from types import SimpleNamespace
        from home.character_engine import _resource_max_overrides
        feature = SimpleNamespace(tags_json=[
            'attr_max:recurso_caseiro=roundup(classlvl/2)'])
        self.assertEqual(
            _resource_max_overrides([('classe', 'Teste', feature, 7)], {'lvl': 7}),
            {'recurso_caseiro': 4})

    def test_valores_numericos_e_dados_passam_intactos(self):
        # Regressao critica: formulas com variaveis conhecidas sao avaliadas; tabela
        # numerica, dado, distancia e +N continuam literais.
        from home.models import TbRecursoclasse
        from home.character_engine import _resource_value_at
        dados = TbRecursoclasse.objects.filter(
            id_classe__slug='ladino', slug='dados-de-furtividade').first()
        self.assertIsNotNone(dados)
        self.assertEqual(str(_resource_value_at(dados, 5, 5)), '3')      # tabela {1:1,3:2,5:3}
        d6 = TbRecursoclasse.objects.filter(slug='dado-de-furtividade').first()
        if d6:
            self.assertEqual(str(_resource_value_at(d6, 5, 5)), 'd6')    # dado passa intacto


class BlocoBMagiaRemapTests(_CriadorBase):
    """Bloco B (decisão 8): slugs de magia em hold existem no catálogo sob OUTRO
    nome. Confirma que os 4 alvos existem e que a ponte snake_case→hífen resolve."""

    def test_alvos_existem_no_catalogo(self):
        from home.models import TbMagia
        for hifen in ('mao-arcana', 'golpe-brilhante', 'aprimoramento-de-pericia',
                      'derivacao-temporal'):
            self.assertTrue(TbMagia.objects.filter(slug=hifen).exists(),
                            'catálogo deve conter %s (destino do remap)' % hifen)

    def test_ponte_snake_para_hifen(self):
        # o resolvedor casa a ponte '_'<->'-': o slug snake_case remapeado aponta
        # para o slug hifenado real do catálogo.
        from home.models import TbMagia
        from home.character_engine import _ref_slug
        for snake, hifen in (('mao_arcana', 'mao-arcana'),
                             ('golpe_brilhante', 'golpe-brilhante'),
                             ('aprimoramento_de_pericia', 'aprimoramento-de-pericia'),
                             ('derivacao_temporal', 'derivacao-temporal')):
            self.assertEqual(_ref_slug(snake), hifen)
            self.assertTrue(TbMagia.objects.filter(slug=_ref_slug(snake)).exists())


class BlocoANarrativoTests(_CriadorBase):
    """Bloco A (decisão 7): verbos de combate mantidos (inertes) validam limpo; e
    remover um token narrativo de um passivo misto não quebra o derive."""

    def test_verbos_de_combate_validam_limpo(self):
        from home.tag_engine import Library
        from home.tag_engine.validator import validate_tags_json
        lib = Library()
        tags = [
            'always_active{without{adv:attack{vs:self}}, unless:incapacitated}',
            'always_active{ resist:necrotico, immune_effect:max_hp_reduction }',
            'always_active{ immune_effect:elixir_proprio }',
            'always_active{ without{surprised} }',
            'always_active{ reduce_forced_movement:half(min:5ft) }',
        ]
        diags = validate_tags_json(tags, lib)
        ruins = [d for d in diags if d.code in ('verbo-desconhecido', 'nome-com-hifen')]
        self.assertEqual(ruins, [], 'verbos de combate inertes devem validar limpo: %r' % ruins)

    def test_remover_token_narrativo_preserva_mecanica_irma(self):
        # Visão Umbral: sense:darkvision (real) permanece após remover detect:darkness (RP).
        from home.tag_engine import Library
        from home.tag_engine.validator import validate_tags_json
        lib = Library()
        pos = 'always_active{ sense:darkvision(range:60ft) }'
        diags = validate_tags_json([pos], lib)
        self.assertEqual([d for d in diags if d.code in ('verbo-desconhecido', 'nome-com-hifen')], [])


class CondicionalEmValorEstaticoTests(TestCase):
    """Bug do print: um `if(...)` condicional em posição de VALOR ESTÁTICO
    (unarmed_strike.dmg) vazava a expressão CRUA para o painel Ataques — a ficha
    exibia `if(unarmed_strike.dmg >= 1d6):` como dano. Cobre as 3 defesas:
      1. GUARD do motor: a string de dano nunca renderiza expressão (só dado NdM +
         modificador numérico); o resíduo é descartado (com nota de debug).
      2. VALIDADOR: acusa ERROR `cond-em-valor-estatico` para essa classe de tag.
      3. Forma consumida (piso de dado) rende dano estático limpo."""

    LEAK = ("unarmed_strike.dmg:= if(unarmed_strike.dmg >= 1d6+str_mod): "
            "+1 else: 1d6+str_mod (concussao)")
    CANON = "always_active{ unarmed_strike.dmg:=1d6+str_mod(concussao) }"

    def _derive_unarmed(self, tag, nivel=4, forca=16):
        """Deriva só o perfil desarmado por um caminho fiel: apply_tags -> _ataques."""
        from home.character_engine import (apply_tags, _ataques, _build_ctx,
                                           bonus_proficiencia)
        fmod = (forca - 10) // 2
        attrs = {'FOR': {'valor': forca, 'mod': fmod},
                 'DES': {'valor': 14, 'mod': 2}, 'CON': {'valor': 14, 'mod': 2},
                 'INT': {'valor': 10, 'mod': 0}, 'SAB': {'valor': 10, 'mod': 0},
                 'CAR': {'valor': 10, 'mod': 0}}
        pb = bonus_proficiencia(nivel)
        feat = type('F', (), {'nome': 'X', 'tags_json': [tag], 'table_only': False})()
        state = {'_ctx': _build_ctx(nivel, pb, attrs), 'pv': {'maximo_calculado': 30},
                 'velocidade': '9 m / 30 ft', 'iniciativa': 0, 'recursos': {}, 'ca': 10}
        apply_tags(state, [('talento', 'X', feat, None)], personagem=None, escolhas={})
        res = _ataques(state['_tag'], attrs, pb)
        desarmado = next((p for p in res['perfis'] if p['escopo'] == 'unarmed-strike'), None)
        return desarmado, res, pb, fmod

    def test_guard_nao_vaza_expressao_na_string_de_dano(self):
        desarmado, res, pb, fmod = self._derive_unarmed(self.LEAK)
        self.assertIsNotNone(desarmado, 'perfil desarmado deve existir')
        # A defesa central: NENHUM resíduo de expressão pode aparecer na string.
        for proibido in ('if(', 'else', '>=', ':='):
            self.assertNotIn(proibido, desarmado['dano'],
                             'expressão vazou na string de dano: %r' % desarmado['dano'])
        self.assertNotIn('if(', desarmado['dado'])
        # o acerto continua numérico e correto (mod + PB)
        self.assertEqual(desarmado['bonus_ataque'], fmod + pb)
        # e há nota de debug do trecho descartado
        self.assertTrue(any('não-parseável' in a for a in res['avisos']),
                        'esperava nota de debug do descarte: %r' % res['avisos'])

    def test_sanitizer_isola_die_e_descarta_expressao(self):
        from home.character_engine import _sanitize_dano_dado
        # expressão -> descartada (sem dado que inicie a string) => '—'
        limpo, desc = _sanitize_dano_dado('if(unarmed_strike.dmg >= 1d6): +1 else: 1d6 (concussao)')
        self.assertEqual(limpo, '—')
        self.assertIsNotNone(desc)
        # forma estática legítima passa intacta (dado + tipo de dano)
        self.assertEqual(_sanitize_dano_dado('1d6(concussao)'), ('1d6(concussao)', None))
        # placeholder textual seguro é preservado (fallback de recurso)
        self.assertEqual(_sanitize_dano_dado('dado de artes marciais'),
                         ('dado de artes marciais', None))

    def test_forma_consumida_rende_dano_estatico_limpo(self):
        desarmado, _res, pb, fmod = self._derive_unarmed(self.CANON)
        self.assertIsNotNone(desarmado)
        self.assertEqual(desarmado['dado'], '1d6(concussao)')
        self.assertEqual(desarmado['dano'], '1d6(concussao) %+d' % fmod)

    def test_validador_acusa_condicional_em_dmg(self):
        from home.tag_engine import Library
        from home.tag_engine.validator import validate_tag_line
        lib = Library()
        diags = validate_tag_line(self.LEAK, lib, data=None)
        hits = [d for d in diags if d.code == 'cond-em-valor-estatico']
        self.assertEqual(len(hits), 1, 'validador deve acusar 1x: %r' % diags)
        self.assertEqual(hits[0].level, 'ERROR')

    def test_validador_pega_if_aninhado_em_instant_dentro_de_always_active(self):
        # always_active{ ... instant{ unarmed_strike.dmg:= if(...) } }: o corpo do
        # always_active é tomado inteiro (motor não subtrai o instant aninhado), então
        # o if( AINDA vaza — o validador precisa acusar.
        from home.tag_engine import Library
        from home.tag_engine.validator import validate_tag_line
        lib = Library()
        tag = ("always_active{ trigger=hit_melee, attack:unarmed_strike, instant{ "
               "unarmed_strike.dmg:= if(equiped{weapon} or equiped{shield}): "
               "1d6+str_mod else: 1d8+str_mod (concussao) } }")
        hits = [d for d in validate_tag_line(tag, lib, data=None)
                if d.code == 'cond-em-valor-estatico']
        self.assertEqual(len(hits), 1)

    def test_validador_nao_falsopositiva_condicional_legitimo(self):
        # if( em posição CONSUMIDA (expertise/sense/resist) ou dentro de instant+trigger
        # (inerte) NÃO é o bug — não pode acusar.
        from home.tag_engine import Library
        from home.tag_engine.validator import validate_tag_line
        lib = Library()
        ok = [
            'always_active{ prof:atuacao, if(prof:atuacao):expertise:atuacao }',
            'if(already:sense:darkvision): sense:darkvision(range:+30ft)',
            'match(vertente){ oread:{ if(already:resist{veneno}): resist:acido else: resist:veneno } }',
            'trigger=apply{amedrontado}, action=reaction, instant{ dmg:2d8(psiquico), if(crit_or_crit_fail): dmg:=4d8(psiquico) }',
            self.CANON,
            'while_active{ trigger=hit{unarmed}, if(unarmed_strike.dmg >= 1d6): unarmed_strike.dmg:+1 }',
        ]
        for tag in ok:
            hits = [d for d in validate_tag_line(tag, lib, data=None)
                    if d.code == 'cond-em-valor-estatico']
            self.assertEqual(hits, [], 'falso-positivo em %r' % tag)


# ======================================================================================
# Beta da staff (2a rodada) — 7 correcoes do criador/level-up
# ======================================================================================
class Item1FiltroLinhagemNasQueriesPorRacaTests(_CriadorBase):
    """Item 1: as queries POR RACA de _criador_catalogos (talentos_raca, racial_choices_raca,
    pericias_concedidas_raca) filtram id_linhagem/essencia NULL — tracos de linhagem (que
    carregam o id_raca do pai) NAO vazam mais para toda a raca-base ('Ameaca Latente' etc.)."""

    def test_humano_nao_vaza_tracos_de_linhagem(self):
        cat = views._criador_catalogos()
        fontes = {c['fonte'] for c in cat['racial_choices_raca'].get('humano', [])}
        self.assertIn('Habilidoso', fontes)              # traco-base legitimo (pick:pericia:2)
        self.assertNotIn('Ameaca Latente', fontes)
        self.assertNotIn('Ameaça Latente', fontes)       # traco da linhagem Goruun nao vaza
        for t in cat['talentos_raca'].get('humano', []):
            self.assertNotIn('Ameaca', t['nome'])
            self.assertNotIn('Ameaça', t['nome'])
        self.assertEqual({c['tipo'] for c in cat['racial_choices_raca'].get('humano', [])},
                         {'pericia', 'idioma', 'ferramenta'})

    def test_orc_nao_vaza_pericias_de_linhagem(self):
        cat = views._criador_catalogos()
        fontes = {g['fonte'] for g in cat['pericias_concedidas_raca'].get('orc', [])}
        self.assertNotIn('Experiencia do Cacador', fontes)
        self.assertNotIn('Experiência do Caçador', fontes)
        self.assertNotIn('Sombra Viva', fontes)


class Item2PicksRaciaisPericiaPersistemTests(_CriadorBase):
    """Item 2: as escolhas raciais de pericia gravam TbPersonagemEscolha(tipo='pericia',
    origem=<traco>) via o registry — o traco-base 'Habilidoso' (pick:pericia:2) deixa de
    reaparecer como pendencia nao-resolvida no level-up ('duas pericias extras')."""

    def test_habilidoso_persiste_como_escolha_e_nao_reabre(self):
        from home import picks
        payload = self._payload('guerreiro', raca_slug='humano')
        payload['escolhas_raca'] = {'pericias': ['intimidacao', 'religiao'],
                                    'idiomas': [], 'ferramentas': []}
        resp = self._post_criar(self._novo_usuario('hab', staff=True), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        self.assertEqual(p.escolhas.filter(tipo='pericia', origem='Habilidoso').count(), 2)
        grupos = [g for g in picks.resolve_personagem(p, kinds={'pericia'})
                  if g['origem'] == 'Habilidoso']
        self.assertEqual(len(grupos), 1)
        self.assertEqual((grupos[0]['usados'], grupos[0]['pendentes']), (2, 0))


class CrossLockIdiomaServerTests(_CriadorBase):
    """Cross-lock de IDIOMA no SERVIDOR (não só no criador.js): um idioma escolhido como
    pick racial (escolhas_raca.idiomas) NÃO pode ser re-escolhido na lista idioma/ferramenta
    do antecedente — o POST direto que furava o bloqueio do cliente agora é recusado com
    mensagem clara; um idioma NOVO no antecedente continua passando.

    (humano tem picks raciais de idioma: 'Poliglota' pick:idioma:2 e 'Prodígio Nato'
    pick:{ferramenta|idioma}:2 — o cenário real do bug reportado.)"""

    def _payload_humano_idioma(self, racial_idioma, antec_idiomas):
        # acolito concede 2 idiomas/ferramentas — antec_idiomas deve ter exatamente 2.
        payload = self._payload('guerreiro', raca_slug='humano', antec_slug='acolito')
        payload['idiomas_ferramentas'] = list(antec_idiomas)
        payload['escolhas_raca'] = {'pericias': ['intimidacao', 'religiao'],
                                    'idiomas': list(racial_idioma), 'ferramentas': []}
        return payload

    def test_idioma_duplicado_raca_x_antecedente_recusado(self):
        # 'Élfico' pego como pick racial E de novo na lista do antecedente → recusado (400).
        payload = self._payload_humano_idioma(['Élfico'], ['Élfico', 'Anão'])
        resp = self._post_criar(self._novo_usuario('xlock-dup', staff=True), payload)
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertFalse(body.get('ok'), body)
        self.assertTrue(any('já concedido' in e and 'Élfico' in e for e in body.get('erros', [])), body)

    def test_idioma_novo_no_antecedente_ok(self):
        # Mesmo pick racial ('Élfico'), mas o antecedente escolhe idiomas DIFERENTES → passa (200).
        payload = self._payload_humano_idioma(['Élfico'], ['Enânico', 'Órquico'])
        resp = self._post_criar(self._novo_usuario('xlock-ok', staff=True), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body.get('ok'), body)
        p = TbPersonagem.objects.get(pk=body['id'])
        # o idioma do antecedente e o pick racial coexistem, sem colisão
        idiomas = set(p.proficiencias.filter(tipo='idioma').values_list('nome', flat=True))
        self.assertTrue({'Enânico', 'Órquico'} <= idiomas, idiomas)

    def test_resolver_marca_erro_de_idioma_duplicado(self):
        # Unidade direta no _criador_resolver: o erro de idioma duplicado é acumulado.
        payload = self._payload_humano_idioma(['Élfico'], ['Élfico', 'Anão'])
        _R, erros = views._criador_resolver(payload)
        self.assertTrue(any('já concedido' in e for e in erros), erros)


class Item3PickTalentoTests(_CriadorBase):
    """Item 3: kind 'talento' no PICK_REGISTRY — 'Determinacao Comum' (linhagem Erthari,
    pick:talento:1(=talento_de_origem)) e 'Raizes Profundas' (pick:talento:1(tipo:origem,
    requires:prereqs)) passam a conceder a escolha (universo = TbTalento de origem)."""

    def _humano_erthari(self, nivel=1):
        from home.models import TbRaca, TbLinhagem
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('erth-%d' % nivel), nome='Erthari N%d' % nivel, nivel=nivel,
            id_raca=TbRaca.objects.get(slug='humano'), id_linhagem=TbLinhagem.objects.get(slug='erthari'),
            forca=15, destreza=14, constituicao=13, inteligencia=12, sabedoria=10, carisma=8)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='guerreiro'), nivel=nivel, principal=True)
        return p

    def _grupo_determinacao(self, p):
        from home import picks
        for x in picks.resolve_personagem(p, kinds={'talento'}):
            if x['origem'].startswith('Determina'):
                return x
        raise AssertionError('grupo Determinacao Comum nao encontrado')

    def test_determinacao_comum_abre_e_persiste(self):
        from home import picks
        p = self._humano_erthari()
        g = self._grupo_determinacao(p)
        self.assertEqual(g['n'], 1)
        self.assertTrue(g['universo'])
        for u in g['universo']:
            self.assertEqual(TbTalento.objects.get(id_talento=u['id']).tipo.lower(), 'origem')
        picks.PICK_REGISTRY['talento']['persist'](
            p, dict(g, slot_base=g['prox_slot']), [str(g['universo'][0]['id'])])
        self.assertEqual(p.escolhas.filter(tipo='talento').filter(origem__startswith='Determina').count(), 1)
        self.assertTrue(TbPersonagemTalento.objects.filter(
            id_personagem=p, id_talento__isnull=False).exists())
        g2 = self._grupo_determinacao(p)
        self.assertEqual(g2['pendentes'], 0)

    def test_raizes_profundas_via_asi_lista_no_painel(self):
        p = self._humano_erthari(nivel=4)
        rp = TbTalento.objects.get(slug='raizes-profundas')
        TbPersonagemTalento.objects.create(id_personagem=p, id_talento=rp, categoria='geral',
                                           nivel=4, nome=rp.nome)
        pg = [g for g in views._opcao_grupos(p) if g['kind'] == 'talento'
              and any(TbTalento.objects.filter(slug=o['slug'], tipo__iexact='origem').exists()
                      for o in g['disponiveis'])]
        self.assertTrue(pg, 'Raizes Profundas deve listar um grupo de talento de origem')
        self.assertTrue(any(g['pendentes'] == 1 for g in pg))


class Item4CountAsTalentoRacialTests(_CriadorBase):
    """Item 4: linhagens com trait count_as:<raca>(for:prereq{talento_racial}) herdam os
    talentos raciais GERAIS da outra raca — no criador e no level-up (Salarin -> Elfo)."""

    def test_criador_salarin_herda_gerais_do_elfo(self):
        cat = views._criador_catalogos()
        nomes = {t['nome'] for t in cat['talentos_linhagem'].get('sálarin', [])}
        self.assertIn('Mente Velada', nomes)
        self.assertIn('Condutor da Trama', nomes)
        self.assertNotIn('Passagem Umbral', nomes)  # exige linhagem elfa especifica: nao e geral

    def test_levelup_salarin_oferece_talento_do_elfo(self):
        from home.models import TbRaca, TbLinhagem
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('sal'), nome='Sal', nivel=5,
            id_raca=TbRaca.objects.get(slug='humano'), id_linhagem=TbLinhagem.objects.get(slug='sálarin'),
            forca=15, destreza=14, constituicao=13, inteligencia=12, sabedoria=10, carisma=8)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='guerreiro'), nivel=5, principal=True)
        nomes = {o['nome'] for b in views._pendencias_talento_racial(p) for o in b['opcoes']}
        self.assertIn('Mente Velada', nomes)


class Item6ConjuracaoSubclasseAwareTests(_CriadorBase):
    """Item 6: o pipeline de magia enxerga a spellcasting/recursos da SUBCLASSE (third-casters
    Cavaleiro Arcano e Trapaceiro Arcano): pendencia de truques + magias e slots na ficha."""

    def _third(self, classe_slug, sub_nome, nivel=3):
        from home.models import TbSubclasse
        cl = TbClasse.objects.get(slug=classe_slug)
        sub = TbSubclasse.objects.filter(id_classe=cl, nome__icontains=sub_nome).first()
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('third-%s' % sub_nome[:6]), nome='Third', nivel=nivel,
            forca=13, destreza=14, constituicao=13, inteligencia=15, sabedoria=12, carisma=10)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=cl, id_subclasse=sub, nivel=nivel, principal=True)
        return p, cl, sub

    def test_cavaleiro_arcano_pendencia_e_lista_mago(self):
        p, cl, sub = self._third('guerreiro', 'Cavaleiro Arcano')
        info = views._classe_spellcasting_info(cl, 3, sub)
        self.assertIsNotNone(info)
        self.assertEqual(info['slots'], 'third')
        self.assertIn('Mago', info['lista_nomes'])
        pend = views._pendencias_magias(p)
        self.assertEqual(pend['cantrips_pend'], 2)
        self.assertEqual(pend['known_pend'], 3)
        self.assertTrue(pend['lista_magias'])

    def test_trapaceiro_arcano_pendencia(self):
        # O Trapaceiro Arcano prepara magias por uma cota tabelada: o level-up exige os
        # truques novos, mas não transforma as preparadas em "magias conhecidas".
        p, cl, sub = self._third('ladino', 'Trapaceiro Arcano')
        info = views._classe_spellcasting_info(cl, 3, sub)
        self.assertIsNotNone(info)
        self.assertEqual(info['slots'], 'third')
        self.assertEqual(info['mode'], 'prepared')
        self.assertEqual(info['spell_limit']['value'], 'magias_preparadas')
        pend = views._pendencias_magias(p)
        self.assertGreaterEqual(pend['cantrips_pend'], 1)
        self.assertEqual(pend['known_pend'], 0)

    def test_sheet_mostra_conjuracao_e_slots(self):
        from home.character_engine import derive
        p, cl, sub = self._third('guerreiro', 'Cavaleiro Arcano')
        sheet = views._magias_sheet_info(p, derive(p), [])
        self.assertIsNotNone(sheet.get('spellcasting'))
        self.assertEqual(sheet['spellcasting']['slots_kind'], 'third')
        self.assertTrue(any(r['total'] > 0 for r in sheet['slots']))


class ConjuradorDeGuerraPrereqTests(_CriadorBase):
    """Pré-requisito 'Conjuração ou Magia de Pacto' (talento 'Conjurador de Guerra') deve
    aceitar QUALQUER fonte de conjuração — não só a classe base. Regressão do gate em
    _talento_prereq_ok, que consultava a CLASSE BASE e falhava para third-casters por
    subclasse (Cavaleiro/Trapaceiro Arcano) e para magia concedida por feature."""

    def _char(self, classe_slug, sub_needle=None, nivel=4, magia_origem=None):
        cl = TbClasse.objects.get(slug=classe_slug)
        sub = None
        if sub_needle:
            from home.models import TbSubclasse
            sub = TbSubclasse.objects.filter(id_classe=cl, nome__icontains=sub_needle).first()
            self.assertIsNotNone(sub, 'subclasse %r nao encontrada' % sub_needle)
        p = TbPersonagem.objects.create(
            dono=self._novo_usuario('cdg-%s-%s' % (classe_slug[:4], sub_needle or 'base')),
            nome='CdG', nivel=nivel, forca=13, destreza=14, constituicao=13,
            inteligencia=15, sabedoria=12, carisma=10)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=cl, id_subclasse=sub, nivel=nivel, principal=True)
        if magia_origem:
            from home.models import TbMagia
            mag = TbMagia.objects.first()
            TbPersonagemMagia.objects.create(
                id_personagem=p, id_magia=mag, nome=mag.nome, nivel=1, origem=magia_origem)
        return p

    def _ve_conjurador_de_guerra(self, p):
        from home.character_engine import derive
        nomes = {t['nome'] for t in views._talentos_asi_disponiveis(p, derive(p))}
        return 'Conjurador de Guerra' in nomes

    def test_cavaleiro_arcano_ve(self):
        # third-caster por SUBCLASSE: era o caso quebrado (base guerreiro nao conjura).
        p = self._char('guerreiro', 'Cavaleiro Arcano')
        self.assertTrue(views._personagem_conjura(p))
        self.assertTrue(self._ve_conjurador_de_guerra(p))

    def test_trapaceiro_arcano_ve(self):
        p = self._char('ladino', 'Trapaceiro Arcano')
        self.assertTrue(views._personagem_conjura(p))
        self.assertTrue(self._ve_conjurador_de_guerra(p))

    def test_guerreiro_campeao_nao_ve(self):
        # subclasse NÃO conjuradora: não pode enxergar a habilidade de outra subclasse.
        p = self._char('guerreiro', 'Campe')
        self.assertFalse(views._personagem_conjura(p))
        self.assertFalse(self._ve_conjurador_de_guerra(p))

    def test_mistico_ve(self):
        # magia de pacto (spellcasting{slots:pact} na classe base).
        p = self._char('mistico')
        self.assertTrue(views._personagem_conjura(p))
        self.assertTrue(self._ve_conjurador_de_guerra(p))

    def test_magia_concedida_por_feature_ve(self):
        # decisão do PO: quem tem magia persistida de QUALQUER origem (ex.: vertente de
        # essência) conjura — mesmo numa classe/subclasse sem spellcasting.
        # controle: a mesma classe/subclasse SEM magia não conjura (test_guerreiro_campeao_nao_ve);
        # aqui a única diferença é a magia persistida — que passa a habilitar o talento.
        p = self._char('guerreiro', 'Campe', magia_origem='essencia-vertente')
        self.assertTrue(views._personagem_conjura(p))
        self.assertTrue(self._ve_conjurador_de_guerra(p))

    def test_mago_full_continua_vendo(self):
        p = self._char('mago')
        self.assertTrue(views._personagem_conjura(p))
        self.assertTrue(self._ve_conjurador_de_guerra(p))

    def test_subclasse_conjuradora_travada_no_nivel_nao_ve(self):
        # Cavaleiro Arcano ganha conjuração no N3; abaixo disso a subclasse existe mas a
        # habilidade de spellcasting ainda não desbloqueou → não conjura.
        p = self._char('guerreiro', 'Cavaleiro Arcano', nivel=2)
        self.assertFalse(views._personagem_conjura(p))


class MarcasArcanasPipelineTests(_CriadorBase):
    """Pipeline das Marcas Arcanas/Anomalas ponta-a-ponta (laudo das Marcas). Consolida os
    achados:
      1. DETECTOR UNIVERSAL (character_engine._personagem_conjura, pre-requisito de talento):
         falso-positivo do Ladino morto (subclasse que ele NAO tem), conjurador por essencia
         reconhecido, delegacao de views intacta.
      2. GATE `requires:spellcasting` das LISTAS DE DECRETO = CONJURACAO REAL
         (character_engine._conjuracao_real): um NAO-conjurador que pega a Marca recebe SO as
         `cast{}` diretas — a lista expandida fica VAZIA (magia meramente concedida NAO abre o
         portao). Conjurador REAL abre o portao MAS respeita o TETO de nivel conjuravel
         (`_teto_nivel_conjuravel`): so materializa magia da lista ate o nivel que ele consegue
         conjurar; ao subir de nivel, as novas que passam a caber entram.
      3. PONTE DE SLUG _<->-: a magia multi-palavra `fogo-das-fadas` da lista de decreto
         (que vinha como `fogo_das_fadas`) deixa de sumir em silencio.
      4. GATES DE PRE-REQUISITO: 2a Marca recusada (exclusao mutua) e Superior sem/ com base.
    """
    _seq = 0

    def _usr(self):
        MarcasArcanasPipelineTests._seq += 1
        return self._novo_usuario('marca-%d' % MarcasArcanasPipelineTests._seq, staff=True)

    def _marcial(self, nivel=4, classe='barbaro', sub_needle=None):
        cl = TbClasse.objects.get(slug=classe)
        sub = None
        if sub_needle:
            from home.models import TbSubclasse
            sub = TbSubclasse.objects.filter(id_classe=cl, nome__icontains=sub_needle).first()
        p = TbPersonagem.objects.create(
            dono=self._usr(), nome='Marcial', nivel=nivel,
            forca=15, destreza=13, constituicao=14, inteligencia=10, sabedoria=12, carisma=8)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=cl, id_subclasse=sub, nivel=nivel, principal=True)
        return p

    def _pega_talento(self, p, nome):
        t = TbTalento.objects.get(nome=nome)
        TbPersonagemTalento.objects.create(id_personagem=p, id_talento=t, nome=t.nome)
        return t

    def _caster(self, nivel=3, classe='mago'):
        """Conjurador REAL single-class (classe base conjuradora), sem magia persistida ainda."""
        cl = TbClasse.objects.get(slug=classe)
        p = TbPersonagem.objects.create(
            dono=self._usr(), nome='Caster', nivel=nivel,
            forca=8, destreza=13, constituicao=14, inteligencia=15, sabedoria=12, carisma=10)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=cl, nivel=nivel, principal=True)
        return p

    # ── 2 + 3: NAO-conjurador com Marca → SO as cast{} diretas, lista expandida VAZIA ──
    def test_marca_nao_conjurador_so_casts_diretas(self):
        from home.character_engine import (magias_concedidas, _personagem_conjura,
                                            _conjuracao_real)
        p = self._marcial(nivel=4)                       # barbaro N4: NAO conjura
        self._pega_talento(p, 'Marca Arcana da Busca')   # via Raizes Profundas (origem)
        self.assertFalse(_conjuracao_real(p))            # sem conjuracao REAL
        self.assertFalse(_personagem_conjura(p))         # e sem magia persistida ainda
        info = magias_concedidas(p)
        slugs = {c['slug'] for c in info['concedidas']}
        # cast{} DIRETAS da Marca (nao-gateadas) — sempre concedidas
        self.assertIn('marca-do-cacador', slugs)         # cast always_prepared
        self.assertIn('localizar-objeto', slugs)         # cast requires:lvl{3}, N4 ok
        # LISTA EXPANDIDA (requires:spellcasting) VAZIA — nenhuma abriu o portao
        for gated in ('fogo-das-fadas', 'passos-longos', 'localizar-animais-ou-plantas',
                      'espinho-mental', 'clarividencia', 'falar-com-plantas', 'adivinhacao',
                      'localizar-criatura', 'comunhao-com-a-natureza'):
            self.assertNotIn(gated, slugs, gated)
        # end-to-end: o sync materializa SO as diretas
        views._sync_magias_concedidas(p)
        mat = {m.id_magia.slug for m in TbPersonagemMagia.objects.filter(
            id_personagem=p, sempre_preparada=True).select_related('id_magia')}
        self.assertEqual(mat, {'marca-do-cacador', 'localizar-objeto'})

    # A Marca expande a lista de classe. Ela não concede, prepara ou materializa
    # essas magias; o teto só é aplicado quando a classe escolhe/aprende uma delas.
    def test_marca_conjurador_real_expande_lista_sem_conceder(self):
        from home.character_engine import magias_concedidas, _conjuracao_real
        from home.spellcasting import character_spell_list_delta
        p = self._caster(nivel=3)
        self._pega_talento(p, 'Marca Arcana da Busca')
        self.assertTrue(_conjuracao_real(p))
        granted = {c['slug'] for c in magias_concedidas(p)['concedidas']}
        expanded = character_spell_list_delta(p)['add']
        mark_list = {
            'fogo-das-fadas', 'passos-longos',
            'localizar-animais-ou-plantas', 'espinho-mental',
            'clarividencia', 'falar-com-plantas', 'adivinhacao',
            'localizar-criatura', 'comunhao-com-a-natureza',
        }
        self.assertTrue(mark_list <= expanded)
        self.assertFalse(mark_list & granted)

    def test_marca_nao_materializa_lista_ao_subir_nivel(self):
        from home.spellcasting import character_spell_list_delta
        p = self._caster(nivel=3)
        self._pega_talento(p, 'Marca Arcana da Busca')
        before = set(character_spell_list_delta(p)['add'])
        pc = p.classes.first(); pc.nivel = 5; pc.save(update_fields=['nivel'])
        p.nivel = 5; p.save(update_fields=['nivel'])
        views._sync_magias_concedidas(p)
        after = set(character_spell_list_delta(p)['add'])
        mat = {m.id_magia.slug for m in TbPersonagemMagia.objects.filter(
            id_personagem=p, sempre_preparada=True).select_related('id_magia')}
        self.assertEqual(before, after)
        self.assertFalse(after & mat)

    def test_sem_marca_lista_fechada(self):
        # controle: barbaro puro (sem Marca) nao conjura e nao recebe magia nenhuma.
        from home.character_engine import magias_concedidas, _personagem_conjura
        p = self._marcial(nivel=4)
        self.assertFalse(_personagem_conjura(p))
        self.assertEqual(magias_concedidas(p)['concedidas'], [])

    # ── 1: detector unico ──
    def test_falso_positivo_ladino_morto(self):
        from home.character_engine import _personagem_conjura
        # Ladino N5 SEM subclasse: a 'Magia do Trapaceiro' fica sob id_classe=ladino,
        # id_subclasse=Trapaceiro Arcano — o detector NAO pode enxergar subclasse que ele
        # nao tem. Antes do fix o detector do engine dava True (falso-positivo).
        p = self._marcial(nivel=5, classe='ladino')       # sem subclasse
        self.assertFalse(_personagem_conjura(p))
        self.assertFalse(views._personagem_conjura(p))     # delegacao identica

    def test_conjurador_por_essencia_reconhecido(self):
        from home.character_engine import _personagem_conjura
        from home.models import TbMagia
        p = self._marcial(nivel=4)                         # barbaro: nao conjura
        self.assertFalse(_personagem_conjura(p))
        mag = TbMagia.objects.first()
        TbPersonagemMagia.objects.create(id_personagem=p, id_magia=mag, nome=mag.nome,
                                         nivel=1, origem='essencia-vertente')
        self.assertTrue(_personagem_conjura(p))            # magia de QUALQUER origem basta
        self.assertTrue(views._personagem_conjura(p))

    # ── 4: gates de pre-requisito ──
    def test_segunda_marca_recusada(self):
        from home.character_engine import derive
        p = self._marcial(nivel=4)
        self._pega_talento(p, 'Marca Arcana da Busca')
        criacao = TbTalento.objects.get(nome='Marca Arcana da Criação')
        self.assertFalse(views._talento_prereq_ok(criacao, p, derive(p)))   # exclusao mutua
        # controle: personagem SEM marca aceita a mesma base
        p2 = self._marcial(nivel=4)
        self.assertTrue(views._talento_prereq_ok(criacao, p2, derive(p2)))

    def test_marca_anomala_exclui_arcana(self):
        from home.character_engine import derive
        p = self._marcial(nivel=4)
        self._pega_talento(p, 'Marca Arcana da Busca')
        anomala = TbTalento.objects.get(nome='Marca Anômala')
        # 'Marca Anomala' exige 'nao possuir outra Marca Arcana' → recusada
        self.assertFalse(views._talento_prereq_ok(anomala, p, derive(p)))

    def test_superior_exige_base(self):
        from home.character_engine import derive
        p = self._marcial(nivel=4)
        superior = TbTalento.objects.get(nome='Marca Arcana Superior da Busca')
        self.assertFalse(views._talento_prereq_ok(superior, p, derive(p)))   # sem base
        self._pega_talento(p, 'Marca Arcana da Busca')
        self.assertTrue(views._talento_prereq_ok(superior, p, derive(p)))    # com base

    def test_superior_exige_a_base_certa(self):
        # a base ERRADA (Criacao) NAO habilita a Superior da Busca.
        from home.character_engine import derive
        p = self._marcial(nivel=4)
        self._pega_talento(p, 'Marca Arcana da Criação')
        superior = TbTalento.objects.get(nome='Marca Arcana Superior da Busca')
        self.assertFalse(views._talento_prereq_ok(superior, p, derive(p)))

    def test_marca_potente_exige_categoria_possuida(self):
        from home.character_engine import derive
        p = self._marcial(nivel=4)
        potente = TbTalento.objects.get(nome='Marca Potente')
        self.assertFalse(views._talento_prereq_ok(potente, p, derive(p)))
        self._pega_talento(p, 'Marca Arcana Superior da Busca')
        self.assertTrue(views._talento_prereq_ok(potente, p, derive(p)))


class Item7AsiFormaAlternativaTests(_CriadorBase):
    """Item 7: ASI do antecedente aceita a forma alternativa +1/+1/+1 (regra de sistema)
    alem do +2/+1 legado — validacao, resolucao e persistencia (2 ou 3 linhas de bonus)."""

    def test_forma_1_1_1_cria_tres_bonus(self):
        from home.models import TbPersonagemAtributoBonus
        from home.character_engine import derive
        payload = self._payload('guerreiro', raca_slug='humano')
        payload['asi'] = {'modo': '1/1/1', 'attrs': ['CON', 'DES', 'FOR']}
        resp = self._post_criar(self._novo_usuario('asi111', staff=True), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        bonus = TbPersonagemAtributoBonus.objects.filter(id_personagem=p)
        self.assertEqual(bonus.count(), 3)
        self.assertEqual(set(bonus.values_list('valor', flat=True)), {1})
        self.assertEqual(set(bonus.values_list('atributo', flat=True)), {'CON', 'DES', 'FOR'})
        at = derive(p)['atributos']
        self.assertEqual(at['FOR']['valor'], payload['scores']['FOR'] + 1)

    def test_forma_2_1_legada_continua(self):
        from home.models import TbPersonagemAtributoBonus
        payload = self._payload('guerreiro')  # asi legado {mais2, mais1}
        resp = self._post_criar(self._novo_usuario('asi21', staff=True), payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        self.assertEqual(TbPersonagemAtributoBonus.objects.filter(id_personagem=p).count(), 2)

    def test_forma_1_1_1_com_atributo_repetido_rejeitada(self):
        payload = self._payload('guerreiro')
        payload['asi'] = {'modo': '1/1/1', 'attrs': ['CON', 'CON', 'FOR']}
        resp = self._post_criar(self._novo_usuario('asibad', staff=True), payload)
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_forma_1_1_1_com_atributos_faltando_rejeitada(self):
        payload = self._payload('guerreiro')
        payload['asi'] = {'modo': '1/1/1', 'attrs': ['CON', 'DES']}
        resp = self._post_criar(self._novo_usuario('asifalta', staff=True), payload)
        self.assertEqual(resp.status_code, 400, resp.content)


class QualificadorOnLevelUpTests(TestCase):
    """QUIRK do Robusto: PV contado em dobro pelo qualificador `on:level_up`.

    O talento traz DUAS linhas de PV — `buff:max_hp:+(2*lvl)` (a fórmula, o total)
    e `buff:max_hp:+2(on:level_up)` (o texto "+2 ao subir de nível", que descreve
    COMO o bônus acumula). O adaptador estático somava as duas (N11 => +24 em vez
    de +22). A regra do motor: operando com qualificador `on:<evento>` é momento/
    acúmulo, nunca valor passivo do derive.
    """

    @classmethod
    def setUpTestData(cls):
        # A migration semeia a mesma regra que existe no fixture oficial.
        TbRegra.objects.filter(slug='aumento-de-atributo').delete()
        call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)

    def _hp_bonus(self, tags, nivel=11):
        """Roda apply_tags com uma feature sintética e devolve os bônus de PV."""
        from home.character_engine import apply_tags, _build_ctx, bonus_proficiencia
        attrs = {'FOR': {'valor': 10, 'mod': 0}, 'DES': {'valor': 14, 'mod': 2},
                 'CON': {'valor': 14, 'mod': 2}, 'INT': {'valor': 10, 'mod': 0},
                 'SAB': {'valor': 10, 'mod': 0}, 'CAR': {'valor': 10, 'mod': 0}}
        feat = type('F', (), {'nome': 'X', 'tags_json': list(tags),
                              'table_only': False})()
        state = {'_ctx': _build_ctx(nivel, bonus_proficiencia(nivel), attrs),
                 'pv': {'maximo_calculado': 100}, 'velocidade': '9 m / 30 ft',
                 'iniciativa': 0, 'recursos': {}, 'ca': 10}
        apply_tags(state, [('talento', 'X', feat, None)], personagem=None,
                   escolhas={})
        return state['pv']

    def test_robusto_real_conta_so_a_formula(self):
        # Tags REAIS do talento (fixture), não uma paráfrase.
        robusto = TbTalento.objects.get(pk=27)
        self.assertEqual(robusto.nome, 'Robusto')
        self.assertIn('buff:max_hp:+(2*lvl)', robusto.tags_json)
        self.assertIn('buff:max_hp:+2(on:level_up)', robusto.tags_json)

        pv = self._hp_bonus(robusto.tags_json, nivel=11)
        self.assertEqual([v for _, v in pv['bonus_tags']], [22],
                         'N11 deve somar só a fórmula 2*lvl: %r' % (pv['bonus_tags'],))
        self.assertEqual(pv['maximo_calculado'], 122)

    def test_on_level_up_sozinho_nao_e_valor_estatico(self):
        # Caso sintético: a nota de acúmulo SEM a fórmula irmã não concede PV.
        pv = self._hp_bonus(['buff:max_hp:+2(on:level_up)'], nivel=11)
        self.assertEqual(pv['bonus_tags'], [])
        self.assertEqual(pv['maximo_calculado'], 100)

    def test_buff_estatico_sem_qualificador_continua_somando(self):
        # Guarda contra skip cego: buff de PV sem `on:` não pode ser engolido.
        pv = self._hp_bonus(['buff:max_hp:+5'], nivel=11)
        self.assertEqual([v for _, v in pv['bonus_tags']], [5])
        self.assertEqual(pv['maximo_calculado'], 105)

    def test_fallback_textual_nao_ressuscita_a_formula(self):
        # A categoria max_hp precisa continuar CONSUMIDA quando a linha `on:` é
        # pulada — senão o varredor textual legado reaplicaria a fórmula (+22 x2).
        pv = self._hp_bonus(['buff:max_hp:+(2*lvl)',
                             'buff:max_hp:+2(on:level_up)'], nivel=11)
        self.assertEqual(len(pv['bonus_tags']), 1, repr(pv['bonus_tags']))
