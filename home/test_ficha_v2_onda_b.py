# -*- coding: utf-8 -*-
"""Regressão da FICHA v2 — onda B (ABA MOCHILA), briefing docs/agentes/briefing_ficha_v2.md.

  1. A ficha ganha a aba MOCHILA (par de Magias/Histórico), com GRADE DE SLOTS derivada
     dos slots REAIS do catálogo (`TbItemMagico.slot` distinct + armadura/escudo/arma dos
     mundanos) — nada de lista fixa no template.
  2. A grade reflete o que está equipado; consumível/objeto/item menor NÃO viram vaga.
  3. `acessorio` concede efeito SEM consumir vaga (regra do PO 27/07): vaga ilimitada.
  4. Equipar/desequipar/sintonizar por fetch devolvem os partials re-renderizados
     (mochila + grade + blocos da aba Ficha) — a página se atualiza sem reload.
  5. Slot corporal cheio RECUSA o equipar, com mensagem nomeando slot e ocupante.
  6. O inventário SAIU do editar_ficha (que caminha para ferramenta só-da-staff).

Roda contra o conteúdo real (fixture `conteudo.json`), reusando o `LevelUpLoteBase`.
"""
from django.urls import reverse

from home import slots as _slots
from home.models import TbItemMagico, TbPersonagemItem
from home.test_levelup import LevelUpLoteBase


class _MochilaBase(LevelUpLoteBase):
    AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    def _char(self, apelido='mochila'):
        return self._guerreiro_no_nivel(1, apelido=apelido)

    def _item_no_slot(self, slot, nome=None, sintonizacao=False):
        """Cria (ou reusa) um item mágico de catálogo no slot pedido."""
        slug = 'teste-slot-%s%s' % (slot, '-s' if sintonizacao else '')
        nome = nome or ('Item de %s' % slot)
        item, _ = TbItemMagico.objects.get_or_create(
            slug=slug, defaults={'nome': nome, 'slot': slot, 'tipo': 'item maravilhoso',
                                 'requer_sintonizacao': sintonizacao,
                                 'tags_json': ['always_active{ca:+0}']})
        return item

    def _linha(self, p, item, nome=None, equipado=False, sintonizado=False):
        return TbPersonagemItem.objects.create(
            id_personagem=p, id_item_magico=item, nome=nome or item.nome, qtd=1,
            equipado=equipado, sintonizado=sintonizado)

    def _html(self, p):
        self.client.force_login(p.dono)
        resp = self.client.get(reverse('ficha_detail', args=[p.pk]))
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode('utf-8')


class GradeDeSlotsDerivadaTests(_MochilaBase):
    def test_slots_vem_do_catalogo_e_nao_de_lista_fixa(self):
        catalogo = _slots.slots_do_catalogo()
        self.assertTrue(catalogo, 'catálogo real deveria ter slots vestíveis')
        # os slots do catálogo SÃO os valores realmente usados por TbItemMagico...
        usados = {s for s in TbItemMagico.objects.values_list('slot', flat=True).distinct()
                  if _slots.slot_e_vestivel(s)}
        self.assertTrue(usados.issubset(set(catalogo)))
        # ...e nenhum slot de consumo/uso entra na grade
        for proibido in ('pocao', 'pergaminho', 'objeto', 'item_menor', 'municao'):
            self.assertNotIn(proibido, catalogo, proibido)
        # slot novo no catálogo aparece na grade sozinho (sem tocar em template/CSS)
        self._item_no_slot('dedos', nome='Dedal Élfico')
        self.assertIn('dedos', _slots.slots_do_catalogo())

    def test_mundano_entra_pela_mecanica_das_tags(self):
        # armadura/escudo/arma mundanos não têm coluna `slot`: o slot vem das tags
        self.assertEqual(_slots.slot_de_mecanica({'is_escudo': True}), 'escudo')
        self.assertEqual(_slots.slot_de_mecanica({'is_armadura': True}), 'armadura')
        self.assertEqual(_slots.slot_de_mecanica({'dano_dado': '1d8'}), 'arma')
        self.assertIsNone(_slots.slot_de_mecanica({}))
        for esperado in ('armadura', 'escudo', 'arma'):
            self.assertIn(esperado, _slots.slots_do_catalogo(), esperado)

    def test_aba_mochila_renderiza_com_a_grade(self):
        p = self._char('aba')
        html = self._html(p)
        self.assertIn('data-tab="mochila"', html)
        self.assertIn('data-tabpanel="mochila"', html)
        self.assertIn('data-slots-grid', html)
        self.assertIn('Slots de Equipamento', html)
        # um cartão por slot do catálogo, com o rótulo PT do próprio modelo
        for slug in _slots.slots_do_catalogo():
            self.assertIn('data-slot="%s"' % slug, html, slug)
        self.assertIn('Cabeça', html)
        # mochila vazia: todas as vagas livres
        self.assertIn('livre', html)

    def test_grade_reflete_o_item_equipado(self):
        p = self._char('reflete')
        elmo = self._item_no_slot('cabeca', nome='Elmo de Prova')
        linha = self._linha(p, elmo, equipado=True)
        html = self._html(p)
        # o cartão de cabeça deixa de estar livre e passa a mostrar o item
        self.assertIn('Elmo de Prova', html)
        celula = html.split('data-slot="cabeca"')[1].split('</div>')[0]
        self.assertIn('is-filled', html.split('data-slot="cabeca"')[0][-60:] + celula)
        # desequipando, some da grade
        linha.equipado = False
        linha.save(update_fields=['equipado'])
        html = self._html(p)
        self.assertNotIn('Elmo de Prova</li>', html)

    def test_consumivel_nao_entra_na_grade_mas_aparece_na_mochila(self):
        p = self._char('consumivel')
        pocao = TbItemMagico.objects.create(
            nome='Poção de Prova', slug='pocao-de-prova', slot='pocao', tipo='poção')
        TbPersonagemItem.objects.create(id_personagem=p, id_item_magico=pocao,
                                        nome=pocao.nome, qtd=3)
        html = self._html(p)
        self.assertNotIn('data-slot="pocao"', html)     # não é vestível
        self.assertIn('Poção de Prova', html)           # mas está na mochila
        self.assertIn('3×', html)
        self.assertIn(reverse('personagem_usar_item_consumivel', args=[p.pk]), html)


class AcessorioNaoConsomeVagaTests(_MochilaBase):
    def test_vaga_ilimitada_no_modelo_de_slots(self):
        self.assertIsNone(_slots.vagas_do_slot('acessorio'))
        self.assertEqual(_slots.vagas_do_slot('cabeca'), 1)
        self.assertEqual(_slots.vagas_do_slot('aneis'), 2)   # decidido sobre o dado real

    def test_varios_acessorios_equipados_ao_mesmo_tempo(self):
        p = self._char('acessorio')
        a1 = self._item_no_slot('acessorio', nome='Membro Protético')
        a2 = TbItemMagico.objects.create(nome='Sela do Cavaleiro', slug='teste-sela',
                                         slot='acessorio', tipo='item maravilhoso')
        self._linha(p, a1, equipado=True)
        self.client.force_login(p.dono)
        linha2 = self._linha(p, a2)
        resp = self.client.post(reverse('personagem_equipar_item', args=[p.pk]),
                                data={'item': linha2.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['msg'], 'equipado')
        linha2.refresh_from_db()
        self.assertTrue(linha2.equipado)
        # a grade mostra os dois no mesmo cartão, marcado como ilimitado
        html = self._html(p)
        self.assertIn('Membro Protético', html)
        self.assertIn('Sela do Cavaleiro', html)
        self.assertIn('slot-cell is-open', html)

    def test_acessorio_nao_bloqueia_slot_anatomico(self):
        p = self._char('acessorio-livre')
        self._linha(p, self._item_no_slot('acessorio', nome='Implante'), equipado=True)
        torso = self._linha(p, self._item_no_slot('torso', nome='Manto de Prova'))
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_equipar_item', args=[p.pk]),
                                data={'item': torso.id}, **self.AJAX)
        self.assertEqual(resp.json()['msg'], 'equipado')


class EquiparPorFetchTests(_MochilaBase):
    def test_fetch_devolve_grade_mochila_e_blocos_da_aba_ficha(self):
        p = self._char('fetch')
        linha = self._linha(p, self._item_no_slot('pescoco', nome='Amuleto de Prova'))
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_equipar_item', args=[p.pk]),
                                data={'item': linha.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['msg'], 'equipado')
        for chave in ('inventario_html', 'slots_html', 'sintonizados_html',
                      'equipados_html', 'total_display', 'sintonizacao_maxima'):
            self.assertIn(chave, body, chave)
        # a grade já volta com o item na vaga e o bloco Equipados atualizado
        self.assertIn('data-slot="pescoco"', body['slots_html'])
        self.assertIn('Amuleto de Prova', body['slots_html'])
        self.assertIn('Amuleto de Prova', body['equipados_html'])
        linha.refresh_from_db()
        self.assertTrue(linha.equipado)
        # desequipar pelo mesmo endpoint volta ao estado anterior
        resp = self.client.post(reverse('personagem_equipar_item', args=[p.pk]),
                                data={'item': linha.id}, **self.AJAX)
        self.assertEqual(resp.json()['msg'], 'desequipado')
        self.assertNotIn('Amuleto de Prova', resp.json()['slots_html'])

    def test_sintonizar_por_fetch_atualiza_o_bloco_da_aba_ficha(self):
        p = self._char('fetch-sint')
        item = self._item_no_slot('aneis', nome='Anel de Prova', sintonizacao=True)
        linha = self._linha(p, item)
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_sintonizar_item', args=[p.pk]),
                                data={'item': linha.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body['msg'], 'sintonizado')
        self.assertEqual(body['sintonizados_usados'], 1)
        self.assertIn('Itens Sintonizados', body['sintonizados_html'])
        self.assertIn('Anel de Prova', body['sintonizados_html'])
        linha.refresh_from_db()
        self.assertTrue(linha.sintonizado)
        self.assertTrue(linha.equipado)     # sintonizar implica portar

    def test_ficha_do_dono_tem_os_forms_da_mochila_e_visitante_nao(self):
        p = self._char('perm')
        self._linha(p, self._item_no_slot('maos', nome='Luvas de Prova'))
        html = self._html(p)
        self.assertIn('data-mochila-form', html)
        self.assertIn(reverse('personagem_equipar_item', args=[p.pk]), html)
        p.publico = True
        p.save(update_fields=['publico'])
        outro = self._novo_usuario('mochila-visitante', staff=False)
        self.client.force_login(outro)
        html = self.client.get(reverse('ficha_detail', args=[p.pk])).content.decode('utf-8')
        self.assertIn('Luvas de Prova', html)        # vê o inventário
        self.assertNotIn('data-mochila-form', html)  # mas não mexe
        self.assertNotIn(reverse('personagem_equipar_item', args=[p.pk]), html)


class SlotOcupadoRecusaTests(_MochilaBase):
    def test_segundo_item_no_mesmo_slot_e_recusado_com_mensagem(self):
        p = self._char('ocupado')
        elmo1 = self._linha(p, self._item_no_slot('cabeca', nome='Elmo Antigo'), equipado=True)
        elmo2 = self._linha(p, TbItemMagico.objects.create(
            nome='Elmo Novo', slug='teste-elmo-novo', slot='cabeca', tipo='item maravilhoso'))
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_equipar_item', args=[p.pk]),
                                data={'item': elmo2.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertFalse(body['ok'])
        self.assertEqual(body['msg'], 'slot_ocupado')
        self.assertIn('Cabeça', body['detalhe'])
        self.assertIn('Elmo Antigo', body['detalhe'])
        # nada mudou no banco: o que estava vestido continua vestido
        elmo2.refresh_from_db()
        elmo1.refresh_from_db()
        self.assertFalse(elmo2.equipado)
        self.assertTrue(elmo1.equipado)

    def test_slot_de_duas_vagas_aceita_dois_e_recusa_o_terceiro(self):
        p = self._char('aneis')
        for i in range(2):
            item = TbItemMagico.objects.create(
                nome='Anel %d' % i, slug='teste-anel-%d' % i, slot='aneis',
                tipo='item maravilhoso')
            self._linha(p, item, equipado=True)
        terceiro = self._linha(p, TbItemMagico.objects.create(
            nome='Anel Extra', slug='teste-anel-extra', slot='aneis', tipo='item maravilhoso'))
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_equipar_item', args=[p.pk]),
                                data={'item': terceiro.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['msg'], 'slot_ocupado')
        terceiro.refresh_from_db()
        self.assertFalse(terceiro.equipado)

    def test_sintonizar_respeita_a_guarda_de_slot(self):
        # sintonizar implica PORTAR — não pode furar a fila do slot
        p = self._char('sint-slot')
        self._linha(p, self._item_no_slot('costas', nome='Capa Velha'), equipado=True)
        nova = self._linha(p, TbItemMagico.objects.create(
            nome='Capa Mágica', slug='teste-capa-magica', slot='costas',
            tipo='item maravilhoso', requer_sintonizacao=True))
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_sintonizar_item', args=[p.pk]),
                                data={'item': nova.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()['msg'], 'slot_ocupado')
        nova.refresh_from_db()
        self.assertFalse(nova.sintonizado)
        self.assertFalse(nova.equipado)

    def test_limite_de_sintonizacao_usa_o_maximo_derivado(self):
        p = self._char('sint-limite')
        for i in range(3):
            item = TbItemMagico.objects.create(
                nome='Sint %d' % i, slug='teste-sint-%d' % i, slot='acessorio',
                tipo='item maravilhoso', requer_sintonizacao=True)
            self._linha(p, item, equipado=True, sintonizado=True)
        extra = self._linha(p, TbItemMagico.objects.create(
            nome='Sint Extra', slug='teste-sint-extra', slot='acessorio',
            tipo='item maravilhoso', requer_sintonizacao=True))
        self.client.force_login(p.dono)
        resp = self.client.post(reverse('personagem_sintonizar_item', args=[p.pk]),
                                data={'item': extra.id}, **self.AJAX)
        self.assertEqual(resp.status_code, 400, resp.content)
        body = resp.json()
        self.assertEqual(body['msg'], 'limite_sintonizacao')
        self.assertIn('3', body['detalhe'])      # o teto derivado, não um 3 cravado na view
        self.assertEqual(body['sintonizacao_maxima'], 3)


class TotaisDaMochilaTests(_MochilaBase):
    def test_valor_total_em_po_e_contagem_de_sintonizados(self):
        p = self._char('totais')
        TbPersonagemItem.objects.create(id_personagem=p, nome='Corda de teste',
                                        qtd=2, custo='5 PO')
        TbPersonagemItem.objects.create(id_personagem=p, nome='Vela de teste',
                                        qtd=1, custo='2 PP')
        html = self._html(p)
        self.assertIn('data-mochila-total', html)
        self.assertIn('10,2 PO', html)            # 2×5 PO + 0,2 PO, exibido em PO
        self.assertIn('data-sintonizados-count', html)
        self.assertIn('0/3', html)


class EditarFichaSemInventarioTests(_MochilaBase):
    def test_inventario_e_equipar_sairam_do_editar_ficha(self):
        p = self._char('editor')
        self._linha(p, self._item_no_slot('cintura', nome='Cinto de Prova'))
        self.client.force_login(p.dono)   # `_guerreiro_no_nivel` cria o dono já staff
        html = self.client.get(reverse('editar_ficha', args=[p.pk])).content.decode('utf-8')
        self.assertNotIn('id="lvl-inventario"', html)
        self.assertNotIn('data-inventory-form', html)
        self.assertNotIn('bag-list', html)
        self.assertNotIn(reverse('personagem_equipar_item', args=[p.pk]), html)
        self.assertNotIn(reverse('personagem_sintonizar_item', args=[p.pk]), html)
        self.assertNotIn(reverse('personagem_usar_item_consumivel', args=[p.pk]), html)
        # (o nome do item ainda aparece na página: o <select> de CONCEDER lista o
        # catálogo mágico inteiro — o que sumiu é a LINHA DE INVENTÁRIO do personagem)
        # e aponta o jogador para a Mochila
        self.assertIn('?aba=mochila', html)
        # o que fica: staffbox de aventuras e conceder item. A LOJA saiu na onda C —
        # compra/venda vivem nas páginas do Mercado (ver test_ficha_v2_onda_c.py).
        self.assertIn('lvl-aventuras-staffbox', html)
        self.assertIn(reverse('personagem_conceder_item', args=[p.pk]), html)
        self.assertNotIn('id="loja-shell"', html)

    def test_js_do_editor_sem_seletor_morto(self):
        # gate da onda A: o seletor form[data-rest-form] não tinha mais nenhum form
        import io
        import os
        from django.conf import settings
        caminho = os.path.join(settings.BASE_DIR, 'home', 'static', 'js', 'editar_ficha.js')
        codigo = io.open(caminho, encoding='utf-8').read()
        self.assertNotIn('data-rest-form', codigo)
        self.assertNotIn('data-inventory-form', codigo)
