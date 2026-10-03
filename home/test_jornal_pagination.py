"""Public Jornal archives remain reachable after the first page fills up."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.models import TbJornal


class JornalPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        date = timezone.now()
        for number in range(23):
            TbJornal.objects.create(
                titulo=f'Artigo {number:02d}', slug=f'artigo-{number:02d}',
                conteudo_markdown=f'Texto público {number:02d}',
                data_publicacao=date - timedelta(days=number),
            )

    def test_newest_articles_are_first_and_older_articles_remain_reachable(self):
        listing = reverse('mundo_jornal')
        first = self.client.get(listing)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.context['artigos']), 20)
        self.assertEqual(first.context['artigos'][0].slug, 'artigo-00')
        self.assertEqual(first.context['artigos'][-1].slug, 'artigo-19')
        self.assertContains(first, '?page=2')
        self.assertNotContains(first, 'href="/mundo/jornal/artigo-20/"')

        older = self.client.get(listing, {'page': 2})
        self.assertEqual(older.status_code, 200)
        self.assertEqual([item.slug for item in older.context['artigos']],
                         ['artigo-20', 'artigo-21', 'artigo-22'])
        self.assertContains(older, '?page=1')
        self.assertContains(older, 'href="/mundo/jornal/artigo-22/"')
        self.assertContains(self.client.get(reverse('jornal_detail', args=['artigo-22'])),
                            'Texto público 22')

    def test_invalid_or_out_of_range_page_remains_usable(self):
        listing = reverse('mundo_jornal')
        self.assertEqual(self.client.get(listing, {'page': 'invalid'}).context['page_obj'].number, 1)
        self.assertEqual(self.client.get(listing, {'page': '999'}).context['page_obj'].number, 2)
