# -*- coding: utf-8 -*-
"""Regressão da FICHA v2 — onda E (MISSÕES DA STAFF), briefing docs/agentes/briefing_ficha_v2.md.

O ledger `TbPersonagemAventura` deixa de ser "nome + quantidade" e vira o REGISTRO DA MISSÃO:

  1. MIGRAÇÃO segura sobre tabela de MEMÓRIA: `data_missao`, `id_mestre` (FK) e
     `detalhes_json` entram sem tocar nas linhas já lançadas em produção — a prova roda a
     0086 para trás, cria um lançamento LEGADO e migra de volta para frente.
  2. MESTRE obrigatório na CAMADA DE APLICAÇÃO (o schema segue nulo por causa do legado):
     lançamento novo sem mestre — ou com um `pk` fora do cadastro real — é recusado.
  3. EDIÇÃO de lançamento pela staff (corrigir nome/data/mestre/observações), com trilha
     APPEND-ONLY em `detalhes_json['trilha']` marcando quem editou. Não existe delete.
  4. CONSUMOS da missão registrados NA LINHA: item consumível gasto decrementa o inventário
     (mesma baixa da Mochila) e ouro de RP debita a carteira (pc interno, exibição em PO).
  5. Permissão: os endpoints novos são staff-only e exigem login.
  6. EXIBIÇÃO: staffbox e aba Histórico da ficha mostram data da missão e nome do mestre
     quando existem, e marcam `(legado)` quando a linha é anterior à onda E.

O "campo string de mestre legado" citado no briefing NÃO existe no schema: antes da onda E o
mestre só aparecia (quando aparecia) dentro do NOME da aventura digitado pela staff. Por isso
não há campo read-only a preservar — o que cobre o buraco é o rótulo `(legado)`.

Roda contra o conteúdo real (fixture `conteudo.json`), reusando `_CriadorBase`.
"""
from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.urls import reverse

from home import views
from home.models import (
    TbClasse, TbItemMagico, TbPersonagem, TbPersonagemAventura, TbPersonagemClasse,
    TbPersonagemItem, TbTransacao,
)
from home.test_criador import _CriadorBase


# ───────────────────────────────── base comum ──────────────────────────────────
class _OndaEBase(_CriadorBase):
    AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    def setUp(self):
        self.dono = self._novo_usuario('onda-e-dono')
        self.outro = self._novo_usuario('onda-e-outro')
        self.staff = self._novo_usuario('onda-e-staff', staff=True)
        self.p = TbPersonagem.objects.create(
            dono=self.dono, nome='Peregrino', nivel=1,
            forca=15, destreza=15, constituicao=15, inteligencia=15, sabedoria=15, carisma=15)
        TbPersonagemClasse.objects.create(
            id_personagem=self.p, id_classe=TbClasse.objects.get(slug='guerreiro'),
            nivel=1, principal=True)

    # ── mestres ──
    def _mestre_do_cadastro(self, username='mestre-mm'):
        """Mestre NÃO-staff que existe no cadastro real: tem carteira de Moedas de
        Mestragem (a pegada que o Mercado de Mestre deixa no `UserProfile`)."""
        u = self._novo_usuario(username)
        perfil = u.profile
        perfil.moedas_mestragem = 120
        perfil.save(update_fields=['moedas_mestragem'])
        return u

    # ── ações da staff ──
    def _registrar(self, ajax=False, **data):
        data.setdefault('nome_aventura', 'A Torre Submersa')
        data.setdefault('aventuras', 1)
        self.client.force_login(self.staff)
        return self.client.post(
            reverse('personagem_registrar_aventuras', args=[self.p.pk]), data,
            **(self.AJAX if ajax else {}))

    def _linha(self):
        return self.p.aventuras_ledger.first()

    def _editar(self, lanc, ajax=True, **data):
        self.client.force_login(self.staff)
        return self.client.post(
            reverse('personagem_editar_aventura', args=[self.p.pk, lanc.id_lancamento]),
            data, **(self.AJAX if ajax else {}))

    def _consumo(self, lanc, ajax=True, **data):
        self.client.force_login(self.staff)
        return self.client.post(
            reverse('personagem_aventura_consumo', args=[self.p.pk, lanc.id_lancamento]),
            data, **(self.AJAX if ajax else {}))

    def _pocao(self, qtd=3, nome='Poção de Prova'):
        item = TbItemMagico.objects.create(
            nome=nome, slug='pocao-de-prova', slot='pocao', tipo='poção')
        return TbPersonagemItem.objects.create(
            id_personagem=self.p, id_item_magico=item, nome=item.nome, qtd=qtd)


# ─────────────────────────── 1. migração sobre legado ───────────────────────────
class MigracaoLedgerOndaETests(TransactionTestCase):
    """A migração é ADITIVA sobre uma tabela de MEMÓRIA (dados de usuário em produção):
    volta o banco para antes da 0086, grava um lançamento LEGADO (sem data, sem mestre,
    sem detalhes) e migra para frente — a linha tem de sobreviver íntegra, só com os
    campos novos em branco."""
    ANTES = ('home', '0085_alter_tbitemmagico_slot')
    DEPOIS = ('home', '0086_ledger_aventura_onda_e')

    def _migrar(self, alvo):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([alvo])
        executor.loader.build_graph()
        return executor.loader.project_state([alvo]).apps

    def tearDown(self):
        # Deixa o banco na cabeça das migrações para os testes seguintes.
        self._migrar(self.DEPOIS)

    def test_linha_legada_sobrevive_a_migracao_sem_perda(self):
        antigas = self._migrar(self.ANTES)
        User_ = antigas.get_model('auth', 'User')
        Personagem = antigas.get_model('home', 'TbPersonagem')
        Ledger = antigas.get_model('home', 'TbPersonagemAventura')
        # O modelo histórico NÃO tem os campos novos — é a prova de que a linha nasceu antes.
        campos_antigos = {f.name for f in Ledger._meta.get_fields()}
        for novo in ('data_missao', 'id_mestre', 'detalhes_json'):
            self.assertNotIn(novo, campos_antigos)

        u = User_.objects.create(username='staff-legado', is_staff=True)
        p = Personagem.objects.create(
            dono=u, nome='Veterano', nivel=3, aventuras=4, carteira_pc=12345,
            forca=15, destreza=15, constituicao=15, inteligencia=15, sabedoria=15, carisma=15)
        legado = Ledger.objects.create(
            id_personagem=p, nome_aventura='Mesa do Fulano (mestre na string)',
            qtd_aventuras=2, ouro_pago_pc=24000, braseiros_pago=1,
            nivel_no_lancamento=3, criado_por=u)

        self._migrar(self.DEPOIS)

        vivo = TbPersonagemAventura.objects.get(pk=legado.pk)
        # nada do lançamento antigo se perdeu…
        self.assertEqual(vivo.nome_aventura, 'Mesa do Fulano (mestre na string)')
        self.assertEqual(vivo.qtd_aventuras, 2)
        self.assertEqual(vivo.ouro_pago_pc, 24000)
        self.assertEqual(vivo.braseiros_pago, 1)
        self.assertEqual(vivo.nivel_no_lancamento, 3)
        self.assertEqual(vivo.criado_por.username, 'staff-legado')
        self.assertFalse(vivo.revertido)
        # …e os campos novos entraram vazios, sem exigir backfill.
        self.assertIsNone(vivo.data_missao)
        self.assertIsNone(vivo.id_mestre_id)
        self.assertEqual(vivo.detalhes_json, {})
        # o rótulo de legado é o que cobre o buraco do mestre que nunca existiu
        self.assertTrue(vivo.eh_legado)
        self.assertEqual(vivo.mestre_display, '(legado)')
        # o personagem (memória) segue intacto
        alvo = TbPersonagem.objects.get(pk=p.pk)
        self.assertEqual((alvo.aventuras, alvo.carteira_pc), (4, 12345))


# ────────────────────── 2. lançamento novo exige mestre/data ────────────────────
class LancamentoExigeMestreTests(_OndaEBase):
    def test_sem_mestre_recusa_com_400_e_nao_credita(self):
        resp = self._registrar(ajax=True)          # sem `mestre`
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertFalse(body['ok'])
        self.assertEqual(body['msg'], 'aventuras_sem_mestre')
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 0)                  # nada creditado
        self.assertEqual(self.p.carteira_pc, 0)
        self.assertEqual(self.p.aventuras_ledger.count(), 0)   # nada no ledger

    def test_post_classico_sem_mestre_volta_com_a_mensagem(self):
        resp = self._registrar(ajax=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('compra=aventuras_sem_mestre', resp.url)
        self.assertEqual(self.p.aventuras_ledger.count(), 0)

    def test_mestre_fora_do_cadastro_e_recusado(self):
        forasteiro = self._novo_usuario('nao-mestre')
        resp = self._registrar(ajax=True, mestre=forasteiro.pk)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['msg'], 'aventuras_sem_mestre')
        self.assertEqual(self.p.aventuras_ledger.count(), 0)

    def test_com_mestre_do_cadastro_grava_mestre_e_data(self):
        mestre = self._mestre_do_cadastro()
        resp = self._registrar(ajax=True, mestre=mestre.pk,
                               data_missao='2026-07-11', aventuras=2)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['ok'])
        l = self._linha()
        self.assertEqual(l.id_mestre_id, mestre.pk)
        self.assertEqual(str(l.data_missao), '2026-07-11')
        self.assertFalse(l.eh_legado)
        self.assertEqual(l.mestre_display, mestre.username)
        self.assertEqual(l.detalhes_json, {})
        self.p.refresh_from_db()
        self.assertEqual(self.p.aventuras, 2)          # a matemática de sempre segue valendo
        self.assertGreater(self.p.carteira_pc, 0)

    def test_data_da_missao_e_diferente_da_data_do_lancamento(self):
        mestre = self._mestre_do_cadastro('mestre-data')
        self._registrar(ajax=True, mestre=mestre.pk, data_missao='2026-01-05')
        l = self._linha()
        self.assertEqual(str(l.data_missao), '2026-01-05')
        self.assertNotEqual(l.criado_em.date(), l.data_missao)

    def test_data_invalida_recusa(self):
        mestre = self._mestre_do_cadastro('mestre-data-ruim')
        resp = self._registrar(ajax=True, mestre=mestre.pk, data_missao='11/07/2026')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['msg'], 'aventuras_data_invalida')
        self.assertEqual(self.p.aventuras_ledger.count(), 0)

    def test_select_de_mestre_vem_do_cadastro_real(self):
        mestre = self._mestre_do_cadastro('mestre-vitrine')
        forasteiro = self._novo_usuario('jogador-qualquer')
        cadastro = list(views.mestres_cadastrados())
        self.assertIn(mestre, cadastro)      # carteira de MM = está no Mercado de Mestre
        self.assertIn(self.staff, cadastro)  # staff é sempre mestre
        self.assertNotIn(forasteiro, cadastro)
        self.client.force_login(self.staff)
        html = self.client.get(reverse('editar_ficha', args=[self.p.pk])).content.decode()
        self.assertIn('name="mestre"', html)
        self.assertIn('name="data_missao"', html)
        self.assertIn('type="date"', html)
        self.assertIn('<option value="%d">%s</option>' % (mestre.pk, mestre.username), html)
        self.assertNotIn('>%s</option>' % forasteiro.username, html)


# ─────────────────────────── 3. edição + trilha (staff) ─────────────────────────
class EdicaoLancamentoTests(_OndaEBase):
    def setUp(self):
        super().setUp()
        self.mestre = self._mestre_do_cadastro('mestre-edicao')
        self.mestre2 = self._mestre_do_cadastro('mestre-corrigido')
        self._registrar(ajax=True, mestre=self.mestre.pk,
                        data_missao='2026-05-02', aventuras=2)
        self.lanc = self._linha()

    def test_edicao_corrige_campos_e_apenda_trilha_com_usuario(self):
        resp = self._editar(self.lanc, nome_aventura='A Torre Submersa (revisada)',
                            mestre=self.mestre2.pk, data_missao='2026-05-03',
                            observacoes='mesa dividida em duas sessões')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['msg'], 'ok')
        self.lanc.refresh_from_db()
        self.assertEqual(self.lanc.nome_aventura, 'A Torre Submersa (revisada)')
        self.assertEqual(self.lanc.id_mestre_id, self.mestre2.pk)
        self.assertEqual(str(self.lanc.data_missao), '2026-05-03')
        self.assertEqual(self.lanc.observacoes, 'mesa dividida em duas sessões')
        # trilha: 1 entrada, com QUEM editou e O QUE mudou
        self.assertEqual(len(self.lanc.trilha), 1)
        entrada = self.lanc.trilha[0]
        self.assertEqual(entrada['quem'], self.staff.username)
        self.assertTrue(entrada['quando'])
        self.assertIn('nome:', entrada['o_que_mudou'])
        self.assertIn('mestre:', entrada['o_que_mudou'])
        self.assertIn('data da missão:', entrada['o_que_mudou'])

    def test_trilha_e_append_only_a_cada_edicao(self):
        self._editar(self.lanc, nome_aventura='Passo 1', mestre=self.mestre.pk,
                     data_missao='2026-05-02')
        outro_staff = self._novo_usuario('staff-revisor', staff=True)
        self.client.force_login(outro_staff)
        self.client.post(
            reverse('personagem_editar_aventura', args=[self.p.pk, self.lanc.id_lancamento]),
            {'nome_aventura': 'Passo 2', 'mestre': self.mestre.pk,
             'data_missao': '2026-05-02'}, **self.AJAX)
        self.lanc.refresh_from_db()
        self.assertEqual(len(self.lanc.trilha), 2)                  # apendou, não sobrescreveu
        self.assertEqual([t['quem'] for t in self.lanc.trilha],
                         [self.staff.username, outro_staff.username])
        self.assertEqual(self.lanc.nome_aventura, 'Passo 2')

    def test_edicao_sem_mestre_ou_sem_nome_e_recusada_sem_gravar(self):
        for payload, msg in (
            ({'nome_aventura': 'Sem mestre'}, 'sem_mestre'),
            ({'mestre': self.mestre.pk}, 'sem_nome'),
            ({'nome_aventura': 'Data ruim', 'mestre': self.mestre.pk,
              'data_missao': '02/05/2026'}, 'data_invalida'),
        ):
            resp = self._editar(self.lanc, **payload)
            self.assertEqual(resp.status_code, 400, payload)
            self.assertEqual(resp.json()['msg'], msg)
        self.lanc.refresh_from_db()
        self.assertEqual(self.lanc.nome_aventura, 'A Torre Submersa')
        self.assertEqual(self.lanc.trilha, [])

    def test_edicao_nao_mexe_nos_contadores_do_lancamento(self):
        antes = (self.lanc.qtd_aventuras, self.lanc.ouro_pago_pc, self.lanc.braseiros_pago)
        self.p.refresh_from_db()
        carteira, aventuras = self.p.carteira_pc, self.p.aventuras
        self._editar(self.lanc, nome_aventura='Só o nome muda', mestre=self.mestre.pk,
                     data_missao='2026-05-02')
        self.lanc.refresh_from_db(); self.p.refresh_from_db()
        self.assertEqual(
            (self.lanc.qtd_aventuras, self.lanc.ouro_pago_pc, self.lanc.braseiros_pago), antes)
        self.assertEqual((self.p.carteira_pc, self.p.aventuras), (carteira, aventuras))

    def test_nao_existe_endpoint_de_delete_de_linha(self):
        """Correção é edição, não apagamento: só existem registrar/reverter/editar/consumo."""
        from django.urls import NoReverseMatch
        for nome in ('personagem_excluir_aventura', 'personagem_deletar_aventura'):
            with self.assertRaises(NoReverseMatch):
                reverse(nome, args=[self.p.pk, self.lanc.id_lancamento])


# ──────────────────────── 4. consumos da missão, NA LINHA ───────────────────────
class ConsumoDeMissaoTests(_OndaEBase):
    def setUp(self):
        super().setUp()
        self.mestre = self._mestre_do_cadastro('mestre-consumo')
        self._registrar(ajax=True, mestre=self.mestre.pk, data_missao='2026-06-20')
        self.lanc = self._linha()

    # ── (a) item consumível ──
    def test_item_consumivel_decrementa_inventario_e_registra_na_linha(self):
        linha_item = self._pocao(qtd=3)
        resp = self._consumo(self.lanc, tipo='item', item=linha_item.id, qtd=2)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['msg'], 'consumo_ok')
        linha_item.refresh_from_db()
        self.assertEqual(linha_item.qtd, 1)                    # decrementou o inventário
        self.lanc.refresh_from_db()
        self.assertEqual(len(self.lanc.consumos), 1)
        c = self.lanc.consumos[0]
        self.assertEqual(c['tipo'], 'item')
        self.assertEqual(c['nome'], 'Poção de Prova')
        self.assertEqual((c['qtd'], c['antes'], c['depois']), (2, 3, 1))
        self.assertEqual(c['quem'], self.staff.username)
        # o consumo também deixa rastro na trilha da linha
        self.assertEqual(len(self.lanc.trilha), 1)
        self.assertIn('consumo item', self.lanc.trilha[0]['o_que_mudou'])

    def test_item_zera_e_some_do_inventario(self):
        linha_item = self._pocao(qtd=1)
        self._consumo(self.lanc, tipo='item', item=linha_item.id, qtd=1)
        self.assertFalse(TbPersonagemItem.objects.filter(pk=linha_item.pk).exists())
        self.lanc.refresh_from_db()
        self.assertEqual(self.lanc.consumos[0]['depois'], 0)

    def test_quantidade_maior_que_o_inventario_e_recusada(self):
        linha_item = self._pocao(qtd=2)
        resp = self._consumo(self.lanc, tipo='item', item=linha_item.id, qtd=5)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['msg'], 'qtd_insuficiente')
        linha_item.refresh_from_db()
        self.assertEqual(linha_item.qtd, 2)                    # nada tocado
        self.lanc.refresh_from_db()
        self.assertEqual(self.lanc.consumos, [])

    def test_item_nao_consumivel_e_recusado(self):
        anel = TbItemMagico.objects.create(
            nome='Anel Sólido', slug='anel-solido', slot='anel', tipo='anel')
        linha_item = TbPersonagemItem.objects.create(
            id_personagem=self.p, id_item_magico=anel, nome=anel.nome, qtd=1)
        resp = self._consumo(self.lanc, tipo='item', item=linha_item.id, qtd=1)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['msg'], 'item_invalido')
        linha_item.refresh_from_db()
        self.assertEqual(linha_item.qtd, 1)

    # ── (b) ouro de RP ──
    def test_ouro_de_rp_debita_carteira_e_registra_na_linha(self):
        self.p.refresh_from_db()
        self.p.carteira_pc = 500 * 100
        self.p.save(update_fields=['carteira_pc'])
        resp = self._consumo(self.lanc, tipo='ouro', ouro_po=75, motivo='suborno ao doqueiro')
        self.assertEqual(resp.status_code, 200, resp.content)
        payload = resp.json()
        self.assertEqual(payload['msg'], 'consumo_ok')
        self.p.refresh_from_db()
        self.assertEqual(self.p.carteira_pc, (500 - 75) * 100)   # débito interno em PC
        self.assertIn('425', payload['carteira_display'])        # exibição em PO
        self.lanc.refresh_from_db()
        c = self.lanc.consumos[0]
        self.assertEqual((c['tipo'], c['valor_po'], c['valor_pc']), ('ouro', 75, 7500))
        self.assertEqual(c['motivo'], 'suborno ao doqueiro')
        self.assertEqual(c['quem'], self.staff.username)
        self.assertEqual(self.lanc.ouro_rp_po, 75)
        # e vira extrato rastreável na carteira
        t = TbTransacao.objects.filter(id_personagem=self.p).order_by('-pk').first()
        self.assertEqual(t.valor_pc, -7500)
        self.assertIn('A Torre Submersa', t.descricao)

    def test_ouro_de_rp_sem_carteira_e_recusado(self):
        self.p.refresh_from_db()
        self.p.carteira_pc = 10 * 100
        self.p.save(update_fields=['carteira_pc'])
        resp = self._consumo(self.lanc, tipo='ouro', ouro_po=99)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['msg'], 'ouro_insuf')
        self.p.refresh_from_db()
        self.assertEqual(self.p.carteira_pc, 10 * 100)         # não debitou
        self.lanc.refresh_from_db()
        self.assertEqual(self.lanc.consumos, [])

    def test_valor_de_ouro_invalido_e_recusado(self):
        resp = self._consumo(self.lanc, tipo='ouro', ouro_po=0)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['msg'], 'valor_invalido')

    def test_tipo_de_consumo_desconhecido_e_recusado(self):
        resp = self._consumo(self.lanc, tipo='alma', qtd=1)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['msg'], 'consumo_tipo')

    def test_consumos_acumulam_na_mesma_linha(self):
        linha_item = self._pocao(qtd=2)
        self.p.refresh_from_db()
        self.p.carteira_pc = 300 * 100
        self.p.save(update_fields=['carteira_pc'])
        self._consumo(self.lanc, tipo='item', item=linha_item.id, qtd=1)
        self._consumo(self.lanc, tipo='ouro', ouro_po=30)
        self.lanc.refresh_from_db()
        self.assertEqual([c['tipo'] for c in self.lanc.consumos], ['item', 'ouro'])
        self.assertEqual(len(self.lanc.trilha), 2)


# ───────────────────────────── 5. permissão (staff) ─────────────────────────────
class PermissaoEndpointsOndaETests(_OndaEBase):
    def setUp(self):
        super().setUp()
        self.mestre = self._mestre_do_cadastro('mestre-perm')
        self._registrar(ajax=True, mestre=self.mestre.pk)
        self.lanc = self._linha()

    def _urls(self):
        return (
            reverse('personagem_editar_aventura', args=[self.p.pk, self.lanc.id_lancamento]),
            reverse('personagem_aventura_consumo', args=[self.p.pk, self.lanc.id_lancamento]),
        )

    def test_anonimo_e_mandado_para_o_login(self):
        self.client.logout()
        for url in self._urls():
            resp = self.client.post(url, {})
            self.assertEqual(resp.status_code, 302, url)
            self.assertIn('/login/', resp.url)

    def test_logado_nao_staff_nao_passa(self):
        """Gate `is_staff_user` idêntico ao de registrar/reverter/conceder: 404 (não vaza
        existência), inclusive para o DONO da ficha."""
        for user in (self.dono, self.outro):
            self.client.force_login(user)
            for url in self._urls():
                self.assertEqual(self.client.post(url, {}).status_code, 404, (user, url))
        self.lanc.refresh_from_db()
        self.assertEqual(self.lanc.nome_aventura, 'A Torre Submersa')
        self.assertEqual(self.lanc.detalhes_json, {})

    def test_get_nao_e_aceito(self):
        self.client.force_login(self.staff)
        for url in self._urls():
            self.assertEqual(self.client.get(url).status_code, 405, url)


# ──────────────────────── 6. exibição: data, mestre e legado ────────────────────
class ExibicaoDataMestreELegadoTests(_OndaEBase):
    def _legado(self, nome='Mesa Antiga (pré-onda-E)'):
        """Linha como o banco de produção tem hoje: sem data e sem mestre."""
        return TbPersonagemAventura.objects.create(
            id_personagem=self.p, nome_aventura=nome, qtd_aventuras=1,
            ouro_pago_pc=12000, braseiros_pago=0, nivel_no_lancamento=1,
            criado_por=self.staff)

    def test_staffbox_mostra_data_mestre_e_marca_legado(self):
        legado = self._legado()
        mestre = self._mestre_do_cadastro('mestre-exibe')
        self._registrar(ajax=True, mestre=mestre.pk, data_missao='2026-03-09',
                        nome_aventura='Mesa Nova')
        self.client.force_login(self.staff)
        html = self.client.get(reverse('editar_ficha', args=[self.p.pk])).content.decode()
        self.assertIn('Data da missão', html)          # coluna nova
        self.assertIn('09/03/2026', html)              # data da missão nova
        self.assertIn(mestre.username, html)           # nome do mestre
        self.assertIn('(legado)', html)                # linha antiga marcada
        self.assertIn(legado.nome_aventura, html)
        # e os controles de correção/consumo por linha existem
        self.assertIn(reverse('personagem_editar_aventura',
                              args=[self.p.pk, legado.id_lancamento]), html)
        self.assertIn(reverse('personagem_aventura_consumo',
                              args=[self.p.pk, legado.id_lancamento]), html)

    def test_aba_historico_da_ficha_lista_missoes_com_data_mestre_e_legado(self):
        self._legado()
        mestre = self._mestre_do_cadastro('mestre-ficha')
        self._registrar(ajax=True, mestre=mestre.pk, data_missao='2026-04-17',
                        nome_aventura='Mesa Publicada')
        lanc = self.p.aventuras_ledger.filter(nome_aventura='Mesa Publicada').first()
        linha_item = self._pocao(qtd=2)
        self._consumo(lanc, tipo='item', item=linha_item.id, qtd=1)

        self.client.force_login(self.dono)
        html = self.client.get(reverse('ficha_detail', args=[self.p.pk])).content.decode()
        self.assertIn('data-hist-missoes', html)
        self.assertIn('Mesa Publicada', html)
        self.assertIn('17/04/2026', html)
        self.assertIn(mestre.username, html)
        self.assertIn('(legado)', html)                       # a linha antiga se identifica
        self.assertIn('Poção de Prova ×1', html)              # consumo aparece na missão

    def test_mestre_display_e_legado_sao_a_regra_unica_de_rotulo(self):
        legado = self._legado()
        self.assertTrue(legado.eh_legado)
        self.assertEqual(legado.mestre_display, '(legado)')
        mestre = self._mestre_do_cadastro('mestre-rotulo')
        mestre.first_name, mestre.last_name = 'Ana', 'Chama'
        mestre.save(update_fields=['first_name', 'last_name'])
        self._registrar(ajax=True, mestre=mestre.pk)
        nova = self.p.aventuras_ledger.exclude(pk=legado.pk).first()
        self.assertFalse(nova.eh_legado)
        self.assertEqual(nova.mestre_display, 'Ana Chama')     # nome completo quando existe

    def test_mestre_com_lancamento_nao_pode_ser_apagado(self):
        """PROTECT no schema: quem conduziu missão registrada não some do histórico."""
        from django.db.models import ProtectedError
        mestre = self._mestre_do_cadastro('mestre-protegido')
        self._registrar(ajax=True, mestre=mestre.pk)
        with self.assertRaises(ProtectedError):
            User.objects.filter(pk=mestre.pk).delete()
