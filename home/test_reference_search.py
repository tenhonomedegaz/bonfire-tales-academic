from django.test import TestCase
from django.urls import reverse

from .models import TbCondicao, TbRegra


class ReferenceSearchRoutesTests(TestCase):
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
        self.assertContains(conditions, 'data-reference-query')
        self.assertContains(glossary, 'data-reference-query')
        self.assertContains(conditions, 'data-reference-count')
        self.assertContains(glossary, 'data-reference-count')
        self.assertContains(conditions, 'href="#cond-q311-agarrado"')
        self.assertContains(
            glossary, reverse('mestre_condicoes') + '#cond-' + condition.slug
        )
        self.assertContains(conditions, 'Fica em zero.')
        self.assertContains(glossary, 'Fica em zero.')
        self.assertContains(conditions, 'reference-search.js')
        self.assertContains(glossary, 'reference-search.js')
