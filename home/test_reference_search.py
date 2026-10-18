import re
from html import unescape
from urllib.parse import quote

from django.test import TestCase
from django.urls import reverse

from .models import (TbAntecedente, TbArmadilha, TbBestiario, TbCondicao,
                     TbItemMagico, TbItemMundano, TbRegra)


class ReferenceSearchRoutesTests(TestCase):
    def test_global_search_opens_filtered_background_trap_and_glossary_catalogs(self):
        background = TbAntecedente.objects.create(
            slug='vigia-das-brumas', nome='Vigia das Brumas', descricao='Vigia as passagens.')
        trap = TbArmadilha.objects.create(
            slug='sino-das-brumas', nome='Sino das Brumas', efeito='O sino soa.')
        rule = TbRegra.objects.create(slug='chamado-das-brumas', nome='Chamado das Brumas')
        for entry, route in (
            (background, 'jogador_antecedentes'),
            (trap, 'mestre_armadilhas'),
            (rule, 'sistemas_glossario'),
        ):
            url = reverse(route)
            response = self.client.get(reverse('busca'), {'q': entry.nome})
            self.assertContains(response, f'href="{url}?q={quote(entry.nome)}"')
            self.assertEqual(self.client.get(url, {'q': entry.nome}).status_code, 200)

    def test_global_search_opens_filtered_market_and_bestiary_catalogs(self):
        mundane = TbItemMundano.objects.create(
            slug='corda-trinta-pes', nome='Corda 30 pés', preco='1 PO')
        magic = TbItemMagico.objects.create(
            slug='anel-de-cinzas', nome='Anel de Cinzas', preco=0)
        creature = TbBestiario.objects.create(
            slug='corcel-de-cinzas', nome='Corcel de Cinzas', tipo='Besta',
            statblock_json={'hp': 20})
        TbBestiario.objects.create(
            slug='corcel-de-vento', nome='Corcel de Vento', tipo='Besta')

        search = reverse('busca')
        mundane_url = reverse('mercado_itens_mundanos')
        mundane_results = self.client.get(search, {'q': mundane.nome})
        self.assertContains(mundane_results, f'href="{mundane_url}?busca={quote(mundane.nome)}"')
        mundane_page = self.client.get(mundane_url, {'busca': mundane.nome})
        row = re.search(
            rf'data-target="mu-{mundane.pk}"[^>]*data-search="([^"]*)"',
            mundane_page.content.decode())
        self.assertIsNotNone(row)
        self.assertIn(mundane.nome.lower(), unescape(row.group(1)).lower())

        magic_url = reverse('mercado_itens_magicos')
        magic_results = self.client.get(search, {'q': magic.nome})
        self.assertContains(
            magic_results,
            f'href="{magic_url}?busca={quote(magic.nome)}&amp;estoque=catalogo"')
        magic_page = self.client.get(magic_url, {
            'busca': magic.nome, 'estoque': 'catalogo'})
        self.assertContains(magic_page, f'data-magic-slug="{magic.slug}"')

        bestiary_url = reverse('bestiario')
        creature_results = self.client.get(search, {'q': creature.nome})
        self.assertContains(
            creature_results, f'href="{bestiary_url}?q={quote(creature.nome)}"')
        creature_page = self.client.get(bestiary_url, {'q': creature.nome})
        self.assertEqual(creature_page.context['total_criaturas'], 1)
        self.assertEqual(creature_page.context['active_creature_id'], creature.pk)

    def test_conditions_and_glossary_share_search_and_detail_link(self):
        condition = TbCondicao.objects.create(
            slug='q311-agarrado', nome='Agarrado', nome_en='Grappled',
            resumo='Movimento limitado',
            efeitos_json=[{'titulo': 'Deslocamento', 'texto': 'Fica em zero.'}],
        )
        TbRegra.objects.create(slug='q311-acao', nome='Ação', nome_en='Action')

        conditions = self.client.get(reverse('mestre_condicoes'))
        glossary = self.client.get(reverse('sistemas_glossario'))

        self.assertEqual(conditions.status_code, 200)
        self.assertEqual(glossary.status_code, 200)
        self.assertContains(conditions, 'id="co-search"')
        self.assertContains(glossary, 'data-reference-query')
        self.assertContains(conditions, 'id="co-count">1</strong> de 1 condições')
        self.assertContains(glossary, 'data-reference-count')
        self.assertContains(
            conditions, reverse('mestre_condicoes') + '#cond-' + condition.slug
        )
        self.assertContains(conditions, 'data-target="cond-q311-agarrado"')
        self.assertContains(conditions, 'id="cond-q311-agarrado"')
        self.assertContains(
            glossary, reverse('mestre_condicoes') + '#cond-' + condition.slug
        )
        self.assertContains(conditions, 'Fica em zero.')
        self.assertContains(glossary, 'Fica em zero.')
        self.assertContains(conditions, 'conditions.js')
        self.assertContains(glossary, 'reference-search.js')
