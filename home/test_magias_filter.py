from django.test import TestCase
from django.urls import reverse

from .models import TbMagia


class MagiasClassFilterTests(TestCase):
    def test_catalog_exposes_exact_spell_class_membership(self):
        TbMagia.objects.create(
            nome='Luz de Teste',
            slug='luz-de-teste',
            nivel=0,
            escola='Evocação',
            classes='Bardo, Mago',
        )

        response = self.client.get(reverse('magias_listas'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['classes_magia'], ['Bardo', 'Mago'])
        self.assertEqual(response.context['magias'][0]['classes_lista'], ['Bardo', 'Mago'])
        self.assertContains(response, 'id="mg-classe"')
        self.assertContains(response, '<option value="Bardo">Bardo</option>', html=True)
        self.assertContains(response, "(m.classes_lista||[]).indexOf(classe)===-1")
