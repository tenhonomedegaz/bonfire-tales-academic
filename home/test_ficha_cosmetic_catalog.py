"""Ficha: o seletor mostra apenas escolhas permitidas e sua origem comprovada."""

from decimal import Decimal
import os
from pathlib import Path
import subprocess
import unittest
from uuid import uuid4

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from home.models import (AsaasCheckoutOrder, CosmeticCheckoutPurchase,
                         EventCosmeticOffer, EventCosmeticRedemption,
                         TbCosmetico, TbRegra)
from home.test_criador import _CriadorBase
from home.test_levelup import LevelUpLoteBase


class FichaCosmeticCatalogTests(LevelUpLoteBase):
    def test_owner_selects_event_theme_and_paid_frame_after_offer_ends(self):
        character = self._guerreiro_no_nivel(1, apelido='cosmetico-ficha')
        owner = character.dono
        theme = TbCosmetico.objects.create(
            slug='tema-evento-ficha', tipo='tema', nome='Tema de Evento',
            origem='evento_manual', escopo='ficha')
        offer = EventCosmeticOffer.objects.create(
            event_key='evento-ficha-teste', cosmetico=theme,
            cost_braseiros=0, active=False)
        EventCosmeticRedemption.objects.create(
            request_id=uuid4(), offer=offer, user=owner,
            cosmetico=theme, cost_braseiros=0)
        frame = TbCosmetico.objects.create(
            slug='moldura-paga-ficha', tipo='moldura', nome='Moldura Paga',
            origem='evento_manual', escopo='ficha')
        order = AsaasCheckoutOrder.objects.create(
            user=owner, email='owner-ficha@example.test',
            product_code='cosmetic:' + frame.slug,
            mode='single', amount=Decimal('12.34'))
        CosmeticCheckoutPurchase.objects.create(
            order=order, beneficiary=owner, cosmetico=frame,
            slug=frame.slug, name=frame.nome, granted_at=timezone.now())
        effect = TbCosmetico.objects.create(
            slug='efeito-bloqueado-ficha', tipo='efeito', nome='Efeito Bloqueado',
            origem='evento_manual', escopo='ficha')
        TbCosmetico.objects.create(
            slug='moldura-so-perfil', tipo='moldura', nome='Só Perfil',
            origem='livre', escopo='perfil')

        self.client.force_login(owner)
        url = reverse('ficha_detail', args=[character.pk])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Resgate de evento')
        self.assertContains(page, 'Moldura Paga (Compra confirmada)')
        self.assertContains(page, 'Efeito Bloqueado (bloqueado)')
        self.assertNotContains(page, 'Só Perfil')
        self.assertEqual(next(item['posse_origem'] for item in
                              page.context['appearance_themes']
                              if item['key'] == 'evento-ficha'), 'Resgate de evento')
        self.assertTrue(next(item['locked'] for item in
                             page.context['appearance_effects']
                             if item['key'] == 'bloqueado-ficha'))
        self.assertNotIn('so-perfil', [item['key'] for item in
                                     page.context['appearance_frames']])

        saved = self.client.post(reverse('personagem_info_salvar', args=[character.pk]), {
            'ficha_theme': 'evento-ficha', 'foto_frame': 'paga-ficha',
            'ficha_effect': 'bloqueado-ficha',
        })
        self.assertEqual(saved.status_code, 302)
        character.refresh_from_db()
        self.assertEqual(character.ficha_theme, 'evento-ficha')
        self.assertEqual(character.foto_frame, 'paga-ficha')
        self.assertIsNone(character.ficha_effect)
        reopened = self.client.get(url)
        self.assertEqual(reopened.context['appearance']['theme_key'], 'evento-ficha')
        self.assertEqual(reopened.context['appearance']['frame_key'], 'paga-ficha')
        self.assertEqual(reopened.context['appearance']['effect_key'], 'none')

        character.publico = True
        character.save(update_fields=['publico'])
        viewer = self._novo_usuario('cosmetico-ficha-viewer')
        self.client.force_login(viewer)
        public = self.client.get(url)
        self.assertEqual(public.status_code, 200)
        self.assertNotContains(public, 'Resgate de evento')
        self.assertNotContains(public, 'Compra confirmada')


@unittest.skipUnless(os.environ.get('BONFIRE_PLAYWRIGHT_MODULE'), 'Configure Playwright.')
class FichaCosmeticCatalogBrowserTests(StaticLiveServerTestCase):
    _novo_usuario = _CriadorBase._novo_usuario
    _payload = _CriadorBase._payload
    _post_criar = _CriadorBase._post_criar
    _guerreiro_no_nivel = LevelUpLoteBase._guerreiro_no_nivel

    def test_mobile_and_desktop_ficha_selectors_show_owned_and_locked(self):
        TbRegra.objects.filter(slug='aumento-de-atributo').delete()
        call_command('loaddata', 'home/fixtures/conteudo.json', verbosity=0)
        character = self._guerreiro_no_nivel(1, apelido='cosmetico-ficha-visual')
        theme = TbCosmetico.objects.create(
            slug='tema-evento-ficha-visual', tipo='tema', nome='Tema Evento',
            origem='evento_manual', escopo='ficha')
        offer = EventCosmeticOffer.objects.create(
            event_key='ficha-visual', cosmetico=theme, cost_braseiros=0,
            active=False)
        EventCosmeticRedemption.objects.create(
            request_id=uuid4(), offer=offer, user=character.dono,
            cosmetico=theme, cost_braseiros=0)
        TbCosmetico.objects.create(
            slug='tema-bloqueado-ficha-visual', tipo='tema', nome='Tema Bloqueado',
            origem='evento_manual', escopo='ficha')
        self.client.force_login(character.dono)
        env = dict(os.environ, FICHA_COSMETIC_ORIGIN=self.live_server_url,
                   FICHA_COSMETIC_PATH=reverse('ficha_detail', args=[character.pk]),
                   FICHA_COSMETIC_SESSION=self.client.cookies['sessionid'].value)
        result = subprocess.run(
            ['node', str(Path(__file__).parent / 'js_tests/ficha_cosmetic_catalog.e2e.cjs')],
            env=env, capture_output=True, encoding='utf-8', timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
