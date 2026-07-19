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

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from home import views, point_buy
from home.character_engine import (
    background_grants, background_asi_values, _SKILL_INFO,
    nivel_por_aventuras, ouro_de_progressao, rank_por_nivel,
)
from home.models import (
    TbClasse, TbAntecedente, TbTalento, TbItemMundano, TbOpcaojogo,
    TbPersonagem, TbPersonagemClasse, TbPersonagemMagia, TbPersonagemItem,
    TbPersonagemTalento, TbPersonagemPericia, TbClassehabilidade,
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

        mn = views._classe_maestria_n(classe, 1)
        if mn:
            payload['maestrias'] = list(
                TbItemMundano.objects.filter(categoria='arma').values_list('slug', flat=True))[:mn]

        esc1 = views._classe_escolhas_nv1(classe)
        if esc1['estilo_n']:
            payload['estilo_luta'] = TbOpcaojogo.objects.filter(tipo='Estilo de Luta').first().slug
        if esc1['expertise_n']:
            payload['expertise'] = (pericias_classe + pericias_antec)[:esc1['expertise_n']]

        picks = views._classe_prof_picks_nv1(classe)
        if picks:
            sel = []
            for pick in picks:
                allowed = list(views._classe_prof_pick_options(pick['tipo']))
                sel.append({'valores': allowed[:int(pick.get('n') or 0)]})
            payload['escolhas_classe_prof'] = sel

        conj = views._classe_conjuracao(classe)
        if conj:
            base = {s: int(_SCORES[s]) for s in point_buy.SIGLAS}
            n_mag = views._spell_count_nv1(conj, base, 'CON', 'DES', (asi_major, asi_minor))
            payload['truques'] = [t['slug'] for t in conj['truques']][:conj['truques_n']]
            payload['magias'] = [m['slug'] for m in conj['magias_nv1']][:n_mag]

        payload.update(overrides)
        return payload

    def _post_criar(self, user, payload):
        self.client.force_login(user)
        return self.client.post(reverse('criar_personagem'),
                                data=json.dumps(payload),
                                content_type='application/json')


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
        p, ficha = self._cria_ok(self._payload('mago'))
        # 3 truques materializados a partir das escolhas
        self.assertEqual(p.magias.filter(nivel=0).count(), 3)

    def test_feiticeiro_hibrido(self):
        # raça + linhagem + essência + vertente (o caminho híbrido da auditoria)
        p, ficha = self._cria_ok(self._payload(
            'feiticeiro', raca_slug='anao', linhagem_slug='montanha',
            essencia_slug='draconica', vertente='Vermelho'))
        self.assertEqual(p.id_essencia.slug, 'draconica')
        self.assertEqual(p.id_linhagem.slug, 'montanha')
        self.assertTrue(p.escolhas.filter(tipo='vertente').exists())

    def test_talento_de_origem_materializado(self):
        p, _ = self._cria_ok(self._payload('guerreiro'))
        self.assertTrue(TbPersonagemTalento.objects.filter(
            id_personagem=p, categoria='origem').exists())


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
        payload = self._payload('feiticeiro', raca_slug='anao', linhagem_slug='montanha',
                                essencia_slug='draconica', vertente='Vermelho')
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])

        concedidas = {c['slug'] for c in magias_concedidas(p)['concedidas']}
        materializadas = {m.id_magia.slug for m in TbPersonagemMagia.objects.filter(
            id_personagem=p, sempre_preparada=True).select_related('id_magia')}
        # o path é consistente: sync materializa exatamente o que o motor concede
        self.assertEqual(materializadas, concedidas)
        # e as magias escolhidas no criador estão lá (não-sempre-preparadas)
        escolhidas = TbPersonagemMagia.objects.filter(id_personagem=p, sempre_preparada=False)
        self.assertEqual(escolhidas.count(), len(payload['truques']) + len(payload['magias']))


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

    def test_point_buy_incompleto_rejeitado(self):
        payload = self._payload('guerreiro')
        payload['scores'].pop('INT')  # atributo faltando
        resp = self._post_criar(self._staff(), payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('seis atributos', ' '.join(resp.json()['erros']))

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


class Bug2EquipamentoInicialTests(_CriadorBase):
    """BUG-2: 'equipamento inicial' em classe sem kit vira ouro — mas agora explícito."""

    def test_inicial_sem_kit_credita_ouro_transparente(self):
        classe = TbClasse.objects.get(slug='guerreiro')
        self.assertFalse((classe.equipamento or '').strip(),
                         'pré-condição do teste: guerreiro sem kit cadastrado')
        user = self._novo_usuario('dono-equip', staff=True)
        payload = self._payload('guerreiro', equip_classe='inicial')
        resp = self._post_criar(user, payload)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        # ouro alternativo creditado (po_inicial 100 + equip_gold_alt 150 = 250 PO)
        self.assertEqual(p.carteira_pc, 250 * 100)
        # e há um item transparente explicando que virou ouro (não fica em silêncio)
        self.assertTrue(TbPersonagemItem.objects.filter(
            id_personagem=p, nome__icontains='sem kit de equipamento').exists())


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
        # staff pode
        self.client.force_login(self.staff)
        resp = self.client.post(url, {'aventuras': 5})
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

    def test_preview_feiticeiro_hibrido_bate(self):
        self._bate('feiticeiro', raca_slug='anao', linhagem_slug='montanha',
                   essencia_slug='draconica', vertente='Vermelho')

    def test_preview_incompleto_nao_pronto(self):
        # sem classe -> preview responde ready:false (mostra placeholder no front)
        user = self._novo_usuario('prev-incompleto')
        payload = self._payload('guerreiro')
        payload['classe'] = ''
        prev = self._preview(user, payload)
        self.assertFalse(prev.get('ready'), prev)


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
        picks = []
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

    def test_ladino_via_picks(self):
        p = self._prova_identico('ladino')
        self.assertEqual(p.escolhas.filter(tipo='maestria').count(), 2)

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
        pl['picks'] = [{'kind': 'opcao', 'tipo': 'tipo_sintetico',
                        'valores': [self.slugs[0], self.slugs[2]]}]
        resp = self._post_criar(self._novo_usuario('sintetico', staff=True), pl)
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        escs = p.escolhas.filter(tipo='tipo_sintetico')
        self.assertEqual(escs.count(), 2)
        self.assertEqual(set(escs.values_list('valor', flat=True)), {self.slugs[0], self.slugs[2]})

    def test_validacao_generica_rejeita_contagem_errada(self):
        pl = self._payload('mago')
        pl['picks'] = [{'kind': 'opcao', 'tipo': 'tipo_sintetico', 'valores': [self.slugs[0]]}]
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
    """PICKS DENTRO DE TALENTOS: `resolve_personagem` passa a varrer os TALENTOS do
    personagem (antes só classe/subclasse). Prova com a Máscara de Guerra (talento racial de
    Orc): seu `pick:mascara_guerra:1` tem o universo num `define{mascara_guerra: list{...}}`
    IRMÃO — kind resolvido genericamente pelo handler de menu inline (zero if-por-tipo). A
    escolha vira pendência (1 de 4) SEM que as perícias do menu vazem como estáticas."""

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

    def test_pick_de_talento_vira_pendencia(self):
        from home import picks
        g = next(g for g in picks.resolve_personagem(self._orc_com_mascara())
                 if g['kind'] == 'mascara_guerra')
        self.assertEqual(g['n'], 1)
        self.assertEqual(g['pendentes'], 1)
        self.assertEqual(g['origem'], 'Máscara de Guerra')
        self.assertEqual(g['persist_tipo'], 'mascara_guerra')
        # universo = as 4 opções do define{mascara_guerra: list{...}}, na ordem do menu
        self.assertEqual({u['slug'] for u in g['universo']},
                         {'o_divino', 'a_terra', 'a_magia', 'a_umbra'})

    def test_talento_nao_concede_pericia_estatica(self):
        # o define é MENU (stripado dos verbos passivos), não concessão fixa: nenhuma das
        # perícias listadas nas 4 máscaras (religião/natureza/arcanismo/enganação) vira
        # proficiência estática — só a escolha, quando feita, aplicaria a do ramo.
        from home.character_engine import derive
        prof = {x['nome'] for x in derive(self._orc_com_mascara())['pericias']
                if x['proficiente'] or x['expertise']}
        self.assertFalse(prof & {'Religião', 'Natureza', 'Arcanismo', 'Enganação'}, prof)

    def test_persist_e_readback_da_escolha_de_menu(self):
        from home import picks
        p = self._orc_com_mascara()
        g = next(g for g in picks.resolve_personagem(p) if g['kind'] == 'mascara_guerra')
        g['slot_base'] = g['prox_slot']
        picks._MENU_ENTRY['persist'](p, g, ['a_magia'])
        self.assertEqual(p.escolhas.filter(tipo='mascara_guerra', valor='a_magia').count(), 1)
        # idempotência do painel: a pendência zera e a escolha é relida
        g2 = next(g for g in picks.resolve_personagem(p) if g['kind'] == 'mascara_guerra')
        self.assertEqual((g2['usados'], g2['pendentes']), (1, 0))
        self.assertEqual([e['valor'] for e in g2['escolhidas']], ['a_magia'])
        self.assertEqual([e['nome'] for e in g2['escolhidas']], ['A Magia'])


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
        self._estilo(p, ['always_active{ requires:{ equiped{weapon{melee}} and one_handed and no_other_weapon }, melee.dmg:+2 }'])
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
        p = self._cria()
        # escolhe a maestria da Espada Longa (substitui as escolhas de maestria do bárbaro)
        p.escolhas.filter(tipo='maestria').delete()
        from home.models import TbPersonagemEscolha
        TbPersonagemEscolha.objects.create(id_personagem=p, origem='Maestria em Armas',
                                           tipo='maestria', slot=0, valor='arma-espada-longa')
        self._equipa(p, 'arma-espada-longa')
        d, *_ = self._derive(p)
        pf = self._perfil(d, nome_contem='Espada Longa')
        self.assertTrue(pf['maestria'], pf)


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
    no_asi} concede os benefícios de um talento sem o incremento de atributo. Materialização
    idempotente e origem-rastreada (padrão de _sync_magias_concedidas).
    """

    def _mm_alvo(self):
        """Metamagia-alvo sintética (slug hifenado, como o catálogo real)."""
        return TbOpcaojogo.objects.create(tipo='Metamagia', slug='mm-teste-grant',
                                          nome='MM Teste', tags_json=['modify:spell{ no_verbal }'])

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
                                       tags_json=['modify:spell{ no_verbal }'])
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
        self._feature_opcao(p, ['grant:talento{talento_teste_grant, no_asi}'], origem='Concede Talento')
        n_op, n_tal = views._sync_grants_fixos(p)
        self.assertEqual((n_op, n_tal), (0, 1))
        pt = p.talentos.filter(categoria='concedido')
        self.assertEqual(pt.count(), 1)
        self.assertEqual(pt.first().id_talento_id, t.id_talento)
        d = self._derive(p)[0]
        # benefício do talento aplicado (proficiência em História)
        self.assertTrue(self._per(d, 'História')['proficiente'])
        # no_asi: NENHUM incremento de atributo (a Força não subiu)
        self.assertEqual(d['atributos']['FOR']['valor'], for_antes)

    def test_grant_nao_casa_verbos_de_runtime(self):
        # grant:reaction / grant:grapple / grant:move NÃO são concessões fixas.
        from home.character_engine import grants_fixos
        p = self._cria()
        self._feature_opcao(p, ['trigger=hit, instant{ grant:grapple(no_extra_action) }',
                                'grant:move(no_opportunity)', 'grant:reaction{ attack:1 }'])
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

    def test_valores_numericos_e_dados_passam_intactos(self):
        # Regressão crítica: só fórmulas (pb/lvl/classlvl) são avaliadas; tabela
        # numérica / dado / distância / +N continuam literais.
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
            'always_active{no_adv:attack{vs:self}, unless:incapacitated}',
            'always_active{ resist:necrotico, immune_effect:max_hp_reduction }',
            'always_active{ immune_effect:elixir_proprio }',
            'always_active{ no_surprised }',
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
