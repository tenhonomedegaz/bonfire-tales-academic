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
    TbPersonagemTalento,
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
        # estilo de luta gravado
        self.assertTrue(p.escolhas.filter(tipo='estilo-de-luta').exists())

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
