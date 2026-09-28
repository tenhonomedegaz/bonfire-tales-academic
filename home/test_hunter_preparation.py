from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .content_versions import create_revision, seal_ruleset
from .hunter_rework import catalog
from .models import TbClasse, TbSubclasse, TbPersonagem, TbPersonagemClasse, TbPersonagemCacador
from .versioned_classes import inventory_class, EVALUATOR, VOCABULARY


class HunterPersistentPreparationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='hunter-owner')
        self.other = get_user_model().objects.create_user(username='hunter-other')
        self.cl = TbClasse.objects.create(nome='Caçador', slug='cacador')
        self.sub = TbSubclasse.objects.create(id_classe=self.cl, nome='Ordem dos Mutantes', slug='mutantes')
        self.person = TbPersonagem.objects.create(dono=self.user, nome='Hunter', nivel=3)
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person, id_classe=self.cl,
                                                    id_subclasse=self.sub, nivel=3, principal=True)
        rules = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            create_revision('hunter-rework', catalog()),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.profile = TbPersonagemCacador.objects.create(personagem_classe=self.pc, ruleset=rules, ability='int')
        self.url = reverse('hunter_preparation', args=[self.person.pk])
        self.client.force_login(self.user)

    def test_save_reload_reject_stale_and_preserve_catalog(self):
        response = self.client.post(self.url, {'secret': ['sinal-veritas'], 'version': 0,
                                              'ability': 'wis', 'level': 20})
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.selected, ['sinal-veritas'])
        self.assertEqual(self.profile.ability, 'int')
        self.assertEqual(self.profile.version, 1)
        response = self.client.get(self.url)
        self.assertContains(response, 'sinal-veritas')
        before = response.context['result']
        self.assertEqual(before['level'], 3)
        self.sub.nome = 'Changed order'
        self.sub.save()
        self.cl.nome = 'Changed class'
        self.cl.save()
        with patch('home.hunter_rework.catalog', side_effect=AssertionError('live catalog')):
            self.assertEqual(self.client.get(self.url).context['result'], before)
        self.assertEqual(self.client.post(self.url, {'secret': [], 'version': 0}).status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.selected, ['sinal-veritas'])
        self.assertEqual(self.client.post(self.url, {'secret': ['sinal-veritas'], 'version': 1}).status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.version, 1)

    def test_invalid_selections_never_write(self):
        for choices in (['granada-de-luz'], ['sinal-veritas'] * 2, ['sinal-eclipse'],
                        ['sinal-veritas', 'sinal-exitium', 'sinal-vorago']):
            self.assertEqual(self.client.post(self.url, {'secret': choices, 'version': 0}).status_code, 400)
            self.profile.refresh_from_db()
            self.assertEqual(self.profile.selected, [])
            self.assertEqual(self.profile.version, 0)

    def test_permissions_legacy_and_archive(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, {'version': 0}).status_code, 404)
        self.client.force_login(self.user)
        legacy = TbPersonagem.objects.create(dono=self.user, nome='Legacy hunter')
        TbPersonagemClasse.objects.create(id_personagem=legacy, id_classe=self.cl, nivel=1)
        self.assertEqual(self.client.get(reverse('hunter_preparation', args=[legacy.pk])).status_code, 404)
        self.assertEqual(TbPersonagemCacador.objects.count(), 1)
        self.person.arquivado = True
        self.person.save()
        self.assertEqual(self.client.post(self.url, {'version': 0}).status_code, 404)

    def test_csrf_and_current_level(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {'version': 0}).status_code, 403)
        self.pc.nivel = 5
        self.pc.save()
        response = self.client.get(self.url)
        self.assertEqual(response.context['result']['points'], 5)
        self.assertEqual(max(s['degree'] for s in response.context['result']['options']), 2)

    def test_missing_order_requires_resolution_without_destroying_selection(self):
        self.profile.selected = ['sinal-veritas']
        self.profile.save()
        self.pc.id_subclasse = None
        self.pc.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, 'Salvar preparação', status_code=400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.selected, ['sinal-veritas'])
