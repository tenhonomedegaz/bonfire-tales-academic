from django.test import TestCase
from django.urls import reverse

from .models import TbAntecedente


class BackgroundCatalogTests(TestCase):
    def test_rule_summary_is_collapsed_and_repeated_quote_is_shown_once(self):
        quote = 'Uma longa citação que acompanha a história deste antecedente.'
        TbAntecedente.objects.create(
            nome='Viajante', slug='viajante', resumo=quote,
            descricao=f'*"{quote}"*\n\nUma habilidade própria para viajar.',
        )

        response = self.client.get(reverse('jogador_antecedente'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<details class="catalog-intro-box">')
        self.assertNotContains(response, '<details class="catalog-intro-box" open')
        markup = response.content.decode('utf-8')
        self.assertLess(markup.index('</details>'), markup.index('</header>'))
        self.assertLess(markup.index('</details>'), markup.index('class="catalog-grid"'))
        self.assertContains(response, 'Regras básicas dos antecedentes')
        self.assertContains(response, 'catalog-title--backgrounds')
        self.assertEqual(response.context['items'][0]['resumo'], '')
        self.assertContains(response, 'Uma habilidade própria para viajar.')

    def test_distinct_summary_is_preserved(self):
        TbAntecedente.objects.create(
            nome='Artesão', slug='artesao',
            resumo='Conhece as tradições de sua guilda.',
            descricao='Seu ofício abre portas na cidade.',
        )

        response = self.client.get(reverse('jogador_antecedente'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['items'][0]['resumo'], 'Conhece as tradições de sua guilda.')
        self.assertContains(response, 'Conhece as tradições de sua guilda.')
