from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse

from .models import TbMapLayer, TbRegiao, TbTerritorio
from .views import _parse_lore_topics


class WorldLorePresentationTests(TestCase):
    def test_explicit_overview_does_not_create_empty_duplicate(self):
        topics = _parse_lore_topics(
            'Introducao editorial.\n## Visão Geral\nCorpo.\n## História\nPrimeira.\n'
            '## História\nSegunda.'
        )
        self.assertEqual([topic['title'] for topic in topics],
                         ['Visão Geral', 'História', 'História'])
        self.assertEqual([topic['slug'] for topic in topics],
                         ['base', 'historia', 'historia-2'])
        self.assertIn('Introducao editorial.', topics[0]['content'][0])
        self.assertIn('Corpo.', topics[0]['content'][0])
        self.assertEqual(_parse_lore_topics('   '), [])

    def test_region_and_territory_use_explicit_covers_or_shared_placeholder(self):
        TbMapLayer.objects.update_or_create(
            id_layer=0, defaults={'nome': 'Superficie', 'ordem': 0, 'publica': True},
        )
        territory = TbTerritorio.objects.create(
            nome='Vale Azul', slug='vale-azul', camada=0,
            lore_markdown='## Visão Geral\nTerritório.',
        )
        region = TbRegiao.objects.create(
            nome='Cidade A', slug='cidade-a', territorio=territory.nome,
            camada=0, brasao_url='https://example.invalid/a.png',
            lore_markdown='## Visão Geral\nCidade.',
        )
        TbRegiao.objects.create(
            nome='Cidade B', slug='cidade-b', territorio=territory.nome,
            camada=0, brasao_url='https://example.invalid/b.png',
        )
        placeholder = static('assets/fire_background.png')
        listing = self.client.get(reverse('mundo_regioes'))
        self.assertEqual(listing.status_code, 200)
        card = next(card for card in listing.context['territorios_cards']
                    if card['slug'] == territory.slug)
        self.assertEqual(card['imagem_url'], placeholder)

        detail = self.client.get(reverse('territorio_detail', args=[territory.slug]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.context['imagem_url'], placeholder)
        self.assertEqual(detail.context['client_territories'][territory.nome]['imagem_url'],
                         placeholder)
        self.assertEqual([topic['title'] for topic in detail.context['lore_topics']],
                         ['Visão Geral'])
        self.assertContains(detail, 'data-topic-slug="base"', count=1)
        region_detail = self.client.get(reverse('regiao_detail', args=[region.slug]))
        self.assertEqual(region_detail.context['imagem_url'],
                         'https://example.invalid/a.png')

        territory.imagem_url = 'https://example.invalid/vale.png'
        territory.save(update_fields=['imagem_url'])
        listing = self.client.get(reverse('mundo_regioes'))
        card = next(card for card in listing.context['territorios_cards']
                    if card['slug'] == territory.slug)
        self.assertEqual(card['imagem_url'], territory.imagem_url)
        detail = self.client.get(reverse('territorio_detail', args=[territory.slug]))
        self.assertEqual(detail.context['imagem_url'], territory.imagem_url)
