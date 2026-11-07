from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import TbBestiario, TbMagia


class BestiaryDeleteReferencesTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('bestiary_delete_staff', password='test', is_staff=True)
        self.client.force_login(self.staff)
        self.creature = TbBestiario.objects.create(nome='Espírito', slug='espirito-elemental', comunidade=False)
        self.url = reverse('bestiario_excluir', args=[self.creature.pk])

    def test_spell_reference_through_slug_alias_blocks_delete_and_shows_reason(self):
        TbMagia.objects.create(nome='Invocar', slug='invocar-espirito',
                               tags_json=['summon:bestiary{espirito_elemental}'])
        response = self.client.post(self.url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Remova a referência antes de excluí-la')
        self.assertTrue(TbBestiario.objects.filter(pk=self.creature.pk).exists())

    def test_statblock_feature_reference_blocks_delete(self):
        TbBestiario.objects.create(nome='Invocador', slug='invocador', statblock_json={
            'trait': [{'name': 'Invocar', 'tags_json': ['summon:bestiary{espirito-elemental}']}],
        })
        self.assertIn('m=referenciada', self.client.post(self.url)['Location'])
        self.assertTrue(TbBestiario.objects.filter(pk=self.creature.pk).exists())

    def test_unreferenced_creature_can_be_deleted(self):
        TbMagia.objects.create(nome='Escolha dinâmica', slug='escolha-dinamica',
                               tags_json=[
                                   'summon:bestiary{familiar(creature_type:pick:tipo)}',
                                   'summon:bestiary{familiar(creature_type:match(pick:polo)'
                                   '{ celestial:celestial, infero:corruptor })}',
                               ])
        self.assertIn('m=excluida', self.client.post(self.url)['Location'])
        self.assertFalse(TbBestiario.objects.filter(pk=self.creature.pk).exists())

    def test_unauthorized_user_cannot_delete(self):
        other = User.objects.create_user('bestiary_delete_other', password='test')
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url)['Location'], reverse('bestiario'))
        self.assertTrue(TbBestiario.objects.filter(pk=self.creature.pk).exists())

    def test_community_author_can_delete_unreferenced_creature(self):
        author = User.objects.create_user('bestiary_delete_author', password='test')
        self.creature.comunidade = True
        self.creature.autor = author
        self.creature.save(update_fields=['comunidade', 'autor'])
        self.client.force_login(author)
        self.assertIn('m=excluida', self.client.post(self.url)['Location'])
        self.assertFalse(TbBestiario.objects.filter(pk=self.creature.pk).exists())
