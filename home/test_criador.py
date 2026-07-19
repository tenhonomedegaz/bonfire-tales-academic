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
