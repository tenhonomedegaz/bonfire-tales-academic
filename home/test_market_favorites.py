from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import serializers
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from home.models import MarketItemFavorite, TbItemMagico, TbItemMundano
from home import deploy_sync


class MarketFavoriteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('favorite-owner', password='test-only')
        cls.other = get_user_model().objects.create_user('favorite-other', password='test-only')
        cls.mundane = TbItemMundano.objects.create(nome='Corda favorita', slug='corda-favorita', preco='2 PO')
        cls.magic = TbItemMagico.objects.create(nome='Anel favorito', slug='anel-favorito', preco=Decimal('4.00'))

    def endpoint(self, kind, item):
        return reverse('market_item_favorite', args=[kind, item.pk])

    def post_state(self, kind, item, state):
        return self.client.post(self.endpoint(kind, item), {'favorite': state},
                                HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_login_method_and_invalid_state_guard(self):
        url = self.endpoint('mundano', self.mundane)
        self.assertEqual(self.client.post(url, {'favorite': 'true'}).status_code, 302)
        self.assertEqual(MarketItemFavorite.objects.count(), 0)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.post_state('mundano', self.mundane, 'toggle').status_code, 400)
        self.assertEqual(self.client.post(reverse('market_item_favorite', args=['other', self.mundane.pk]),
                                          {'favorite': 'true'}).status_code, 404)
        self.assertEqual(MarketItemFavorite.objects.count(), 0)

    def test_desired_state_retries_and_account_isolation_in_both_markets(self):
        self.client.force_login(self.owner)
        for kind, item in [('mundano', self.mundane), ('magico', self.magic)]:
            for _ in range(2):
                response = self.post_state(kind, item, 'true')
                self.assertEqual((response.status_code, response.json()['favorite'], response.json()['count']),
                                 (200, True, 1))
        self.assertEqual(MarketItemFavorite.objects.filter(user=self.owner).count(), 2)
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse('mercado_itens_mundanos')), 'data-favorite="true"')
        self.assertEqual(self.post_state('mundano', self.mundane, 'true').json()['count'], 2)
        self.client.force_login(self.owner)
        for _ in range(2):
            response = self.post_state('mundano', self.mundane, 'false')
            self.assertEqual((response.json()['favorite'], response.json()['count']), (False, 1))
        self.assertEqual(MarketItemFavorite.objects.filter(user=self.owner).count(), 1)
        self.assertTrue(MarketItemFavorite.objects.filter(user=self.other, mundane_item=self.mundane).exists())

    def test_catalog_renders_saved_state_without_changing_item_or_stock(self):
        self.client.force_login(self.owner)
        self.post_state('mundano', self.mundane, 'true')
        self.post_state('magico', self.magic, 'true')
        for kind, item, page in [
            ('mundano', self.mundane, 'mercado_itens_mundanos'),
            ('magico', self.magic, 'mercado_itens_magicos'),
        ]:
            html = self.client.get(reverse(page)).content.decode()
            self.assertIn('data-shop-favorites', html)
            self.assertIn('data-favorite="true"', html)
            self.assertIn(self.endpoint(kind, item), html)
            self.assertIn('★ Favorito', html)
        self.mundane.refresh_from_db()
        self.magic.refresh_from_db()
        self.assertEqual(self.mundane.preco, '2 PO')
        self.assertEqual(self.magic.preco, Decimal('4.00'))
        self.client.logout()
        self.assertNotContains(self.client.get(reverse('mercado_itens_mundanos')), 'data-shop-favorites')

    def test_database_prevents_duplicate_or_ambiguous_favorites(self):
        MarketItemFavorite.objects.create(user=self.owner, mundane_item=self.mundane)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MarketItemFavorite.objects.create(user=self.owner, mundane_item=self.mundane)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MarketItemFavorite.objects.create(user=self.owner, mundane_item=self.mundane,
                                              magic_item=self.magic)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MarketItemFavorite.objects.create(user=self.owner)

    def test_catalog_rename_keeps_both_favorites_and_tombstone_is_blocked(self):
        mundane_pk, magic_pk = self.mundane.pk, self.magic.pk
        MarketItemFavorite.objects.create(user=self.owner, mundane_item=self.mundane)
        MarketItemFavorite.objects.create(user=self.owner, magic_item=self.magic)
        incoming_mundane = TbItemMundano.objects.create(
            nome='Corda renomeada', slug='corda-renomeada', preco='2 PO')
        incoming_magic = TbItemMagico.objects.create(
            nome='Anel renomeado', slug='anel-renomeado', preco=Decimal('4.00'))
        fixture = serializers.serialize('json', [incoming_mundane, incoming_magic])
        incoming_mundane.delete()
        incoming_magic.delete()
        renames = {
            'TbItemMundano': {'corda-favorita': 'corda-renomeada'},
            'TbItemMagico': {'anel-favorito': 'anel-renomeado'},
        }
        with patch.object(deploy_sync, '_load_content_renames', return_value=renames), \
             patch.object(deploy_sync, '_load_content_deletions', return_value={}):
            report = deploy_sync.sincronizar_conteudo(fixture)
        self.assertTrue(report['mem_ok'])
        self.assertEqual(TbItemMundano.objects.get(slug='corda-renomeada').pk, mundane_pk)
        self.assertEqual(TbItemMagico.objects.get(slug='anel-renomeado').pk, magic_pk)
        self.assertTrue(MarketItemFavorite.objects.filter(user=self.owner,
                        mundane_item_id=mundane_pk).exists())
        self.assertTrue(MarketItemFavorite.objects.filter(user=self.owner,
                        magic_item_id=magic_pk).exists())
        with patch.object(deploy_sync, '_load_content_deletions', return_value={
            'TbItemMundano': ['corda-renomeada'],
            'TbItemMagico': ['anel-renomeado'],
        }):
            rows = deploy_sync.inspect_content_deletions()
            deletion_report = deploy_sync.sincronizar_conteudo('[]', allow_content_deletions=True)
        self.assertEqual([row[2] for row in rows], ['blocked', 'blocked'])
        self.assertEqual([row[3][0][0] for row in rows], ['MarketItemFavorite', 'MarketItemFavorite'])
        self.assertEqual([row[2] for row in deletion_report['deletions']], [1, 1])
        self.assertTrue(TbItemMundano.objects.filter(pk=mundane_pk).exists())
        self.assertTrue(TbItemMagico.objects.filter(pk=magic_pk).exists())
        self.client.force_login(self.owner)
        for kind, page, item in (
            ('mundano', 'mercado_itens_mundanos', self.mundane),
            ('magico', 'mercado_itens_magicos', self.magic),
        ):
            response = self.client.get(reverse(page))
            self.assertContains(response, 'data-favorite="true"')
            self.assertContains(response, self.endpoint(kind, item))
            removed = self.post_state(kind, item, 'false')
            self.assertEqual((removed.status_code, removed.json()['favorite']), (200, False))
        self.assertFalse(MarketItemFavorite.objects.filter(user=self.owner).exists())
