# -*- coding: utf-8 -*-
"""Regressão da 4a leva de bugs da staff.

1. CA COM ESCUDO MÁGICO: `_armadura_equipada` varria só o snapshot da linha de
   inventário (itens mundanos); um item MÁGICO equipado cuja mecânica de escudo
   (`ca:+N`) vive no catálogo TbItemMagico sumia da conta da CA. Prova: Bárbaro
   DES20/CON16 (defesa sem armadura = 18) + '+1 Escudo' (ca:+3) equipado -> CA 21.
   Escudos NÃO empilham (5e): mundano + mágico -> conta só o melhor.
2. BLOQUEIO UNIVERSAL DE PERÍCIA:
   (a) criador: guard server-side em `_criador_resolver` recusa perícia do antecedente
       duplicada com a da classe;
   (b) level-up: o universo de `pick:pericia` exclui TODAS as perícias já proficientes,
       de QUALQUER origem — inclusive as concedidas por TAG (raça/essência/feature), que
       não vivem em TbPersonagemPericia.
4. DESCRIÇÃO DAS MAGIAS na aba Magias: cada magia com descrição vira card expansível.

Roda contra o conteúdo real (fixture `conteudo.json`).
"""
import os

from django.test import TestCase
from django.urls import reverse

from home import picks, views
from home.character_engine import derive, proficient_skill_slugs
from home.models import (
    TbClasse, TbRaca, TbMagia, TbItemMagico,
    TbPersonagem, TbPersonagemClasse, TbPersonagemItem, TbPersonagemMagia,
    TbPersonagemEscolha,
)
from home.test_criador import _CriadorBase


# ======================================================================================
# FIX 1 — CA ciente do escudo MÁGICO equipado
# ======================================================================================
class CAEscudoMagicoTests(_CriadorBase):
    def _barbaro(self, dex=20, con=16, sufixo=''):
        user = self._novo_usuario('ca-esc-%d-%d%s' % (dex, con, sufixo), staff=True)
        resp = self._post_criar(user, self._payload('barbaro'))
        self.assertEqual(resp.status_code, 200, resp.content)
        p = TbPersonagem.objects.get(pk=resp.json()['id'])
        p.atributo_bonus.all().delete()          # zera ASI p/ SCORE determinístico
        p.destreza, p.constituicao = dex, con
        p.save(update_fields=['destreza', 'constituicao'])
        return p

    def _ca(self, p):
        return derive(p)['ca']

    def _escudo_magico(self, p, ca_bonus=3, equipado=True):
        item = TbItemMagico.objects.create(
            nome='+1 Escudo (teste %d)' % ca_bonus, slug='escudo-mais-teste-%d' % ca_bonus,
            raridade='incomum', slot='escudo', tags_json=['ca:+%d' % ca_bonus])
        return TbPersonagemItem.objects.create(
            id_personagem=p, qtd=1, nome=item.nome, equipado=equipado, id_item_magico=item)

    def test_defesa_sem_armadura_barbaro_e_18(self):
        # Guerreiro Desprotegido: ca=10+dex_mod+con_mod -> 10 + DES5 + CON3 = 18.
        self.assertEqual(self._ca(self._barbaro()), 18)

    def test_escudo_magico_equipado_soma_na_ca(self):
        p = self._barbaro(sufixo='-mag')
        self.assertEqual(self._ca(p), 18)
        self._escudo_magico(p, 3)
        self.assertEqual(self._ca(p), 21)        # 18 + 3 (o escudo mágico agora conta)

    def test_escudo_magico_guardado_nao_soma(self):
        p = self._barbaro(sufixo='-guardado')
        self._escudo_magico(p, 3, equipado=False)
        self.assertEqual(self._ca(p), 18)        # não equipado = sem benefício

    def test_escudos_nao_empilham_conta_o_melhor(self):
        p = self._barbaro(sufixo='-nostack')
        # escudo MUNDANO +2 (snapshot da própria linha) equipado
        TbPersonagemItem.objects.create(id_personagem=p, qtd=1, nome='Escudo',
                                        equipado=True, tags_json=['ca:+2'])
        self.assertEqual(self._ca(p), 20)        # 18 + 2
        # + escudo MÁGICO +3 equipado: NÃO soma os dois (18+2+3=23); usa só o melhor (+3)
        self._escudo_magico(p, 3)
        self.assertEqual(self._ca(p), 21)        # 18 + 3


# ======================================================================================
# FIX 2a — guard server-side do criador: perícia de antecedente x classe
# ======================================================================================
class CriadorPericiaDuplicadaGuardTests(_CriadorBase):
    def test_resolver_recusa_pericia_antecedente_igual_a_escolhida_da_classe(self):
        payload = self._payload('barbaro')
        self.assertTrue(payload['pericias_classe'], payload)
        self.assertTrue(payload['pericias_antecedente'], 'antecedente do teste precisa dar perícia')
        dup = payload['pericias_classe'][0]
        # troca a 1ª perícia do antecedente pela MESMA escolhida na classe (mantém a contagem)
        pa = list(payload['pericias_antecedente'])
        pa[0] = dup
        payload['pericias_antecedente'] = pa
        _R, erros = views._criador_resolver(payload)
        self.assertTrue(any('duplicada com uma perícia da classe' in e for e in erros), erros)

    def test_resolver_recusa_pericia_antecedente_ganha_pela_classe(self):
        # Arcanismo é GANHO pelo Mago (feature 'Estudo Arcano'), não escolhido. Pegá-lo no
        # antecedente ainda é duplicação e deve ser recusado (bloqueio universal).
        payload = self._payload('mago')
        pa = list(payload['pericias_antecedente'])
        pa[0] = 'arcanismo'
        payload['pericias_antecedente'] = pa
        _R, erros = views._criador_resolver(payload)
        self.assertTrue(any('duplicada com uma perícia da classe' in e for e in erros), erros)

    def test_catalogo_expoe_pericia_ganha_pela_classe(self):
        cat = views._criador_catalogos()
        mago = next(c for c in cat['classes'] if c['slug'] == 'mago')
        slugs = {g['slug'] for g in mago.get('pericias_concedidas', [])}
        self.assertIn('arcanismo', slugs)   # o front bloqueia Arcanismo em todas as listas

    def test_resolver_aceita_pericias_disjuntas(self):
        _R, erros = views._criador_resolver(self._payload('barbaro'))
        self.assertFalse(any('duplicada' in e for e in erros), erros)


# ======================================================================================
# FIX 2b — universo de pick:pericia no level-up exclui perícia concedida por TAG
# ======================================================================================
class LevelUpPericiaBloqueioUniversalTests(_CriadorBase):
    def _barbaro_elfo(self, nivel=4):
        u = self._novo_usuario('lvl-pericia-elfo')
        p = TbPersonagem.objects.create(
            dono=u, nome='Elfo Bárbaro', nivel=nivel,
            forca=15, destreza=14, constituicao=14, inteligencia=10, sabedoria=12, carisma=8,
            id_raca=TbRaca.objects.get(slug='elfo'))
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='barbaro'), nivel=nivel, principal=True)
        return p

    def test_pericia_concedida_por_tag_fica_fora_do_universo(self):
        p = self._barbaro_elfo()
        # Percepção é concedida pelo traço élfico 'Olhos da Convergência' (prof:percepcao),
        # que NÃO é persistido em TbPersonagemPericia.
        self.assertFalse(p.pericias.filter(nome__iexact='Percepção').exists())
        self.assertIn('percepcao', proficient_skill_slugs(p))
        self.assertIn('percepcao', picks._pericia_owned_slugs(p))
        # o pool do Bárbaro inclui Percepção, mas o universo NÃO deve oferecê-la (já proficiente)
        universo = {o['slug'] for o in picks._pericia_universe(
            {'personagem': p, 'classe': TbClasse.objects.get(slug='barbaro')})}
        self.assertNotIn('percepcao', universo)
        # regressão: uma perícia do pool NÃO concedida continua disponível
        self.assertIn('atletismo', universo)


# ======================================================================================
# FIX 4 — descrição das magias na aba Magias (card expansível)
# ======================================================================================
class MagiaDescricaoFichaTests(_CriadorBase):
    def test_aba_magias_traz_toggle_e_descricao(self):
        u = self._novo_usuario('magia-desc')
        p = TbPersonagem.objects.create(
            dono=u, nome='Portador de Magia', nivel=1,
            forca=10, destreza=12, constituicao=12, inteligencia=14, sabedoria=10, carisma=10)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=TbClasse.objects.get(slug='barbaro'), nivel=1, principal=True)
        magia = TbMagia.objects.filter(nivel=0).first()
        self.assertIsNotNone(magia, 'fixture precisa de ao menos um truque')
        magia.descricao = 'Um raio de energia atinge o alvo escolhido.'
        magia.save(update_fields=['descricao'])
        TbPersonagemMagia.objects.create(
            id_personagem=p, id_magia=magia, nivel=magia.nivel, nome=magia.nome)

        self.client.force_login(u)
        html = self.client.get(reverse('ficha_detail', args=[p.pk]) + '?aba=magias').content.decode('utf-8')
        self.assertIn('data-spell-toggle="%d"' % p.magias.first().id, html)  # nome vira toggle
        self.assertIn('id="ficha-magia-desc"', html)                          # blob de descrições
        self.assertIn('data-spell-body="%d"' % p.magias.first().id, html)     # painel do card
        self.assertIn('Um raio de energia', html)                             # descrição no blob


# ======================================================================================
# FIX 3 — CSS dos botões de descanso (só presença das regras de alinhamento)
# ======================================================================================
class DescansoBotaoCSSTests(TestCase):
    def test_css_alinha_botoes_de_descanso(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'static', 'css', 'pages', 'ficha.css')
        with open(path, encoding='utf-8') as f:
            css = f.read()
        # os <form> viram flex items (os dois botões dividem a linha do painel)
        self.assertIn('.resource-rest-actions form', css)
        # e os botões ganham min-height consistente com o design system
        self.assertRegex(css, r'\.resource-rest-actions button\s*\{[^}]*min-height')


# ======================================================================================
# FIX 6 — troca de maestria lê swap/reset:long_rest do catálogo real
# ======================================================================================
class TrocaMaestriaDescansoTests(_CriadorBase):
    def _personagem_com_maestria(self):
        u = self._novo_usuario('troca-maestria-descanso')
        classe = TbClasse.objects.get(pk=13)
        p = TbPersonagem.objects.create(
            dono=u, nome='Mestre de Armas', nivel=1,
            forca=15, destreza=14, constituicao=14,
            inteligencia=10, sabedoria=12, carisma=8)
        TbPersonagemClasse.objects.create(
            id_personagem=p, id_classe=classe, nivel=1, principal=True)
        arma = picks._arma_universe({})[0]
        maestria = (arma.get('maestrias') or [{}])[0].get('slug')
        valor = arma['slug'] + (('|%s' % maestria) if maestria else '')
        TbPersonagemEscolha.objects.create(
            id_personagem=p, tipo='maestria', valor=valor, slot=0)
        return p

    def test_derive_reconhece_swap_long_rest_como_trocavel(self):
        p = self._personagem_com_maestria()
        self.assertTrue(derive(p)['maestria_trocavel'])

    def test_fluxo_de_troca_volta_a_abrir(self):
        p = self._personagem_com_maestria()
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('personagem_trocar_maestria', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Maestrias de Arma')
