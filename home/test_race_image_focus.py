import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import TbEssencia, TbLinhagem, TbRaca


class RaceImageFocusTests(TestCase):
    def setUp(self):
        self.race = TbRaca.objects.create(nome='Teste', slug='teste', imagem_url='https://example.com/race.png', imagem_foco_x=22, imagem_foco_y=76)
        self.lineage = TbLinhagem.objects.create(id_raca=self.race, nome='Linhagem', slug='linhagem-teste')
        self.essence = TbEssencia.objects.create(nome='Essencia', slug='essencia-teste', imagem_url='https://example.com/essence.png', imagem_foco_x=81, imagem_foco_y=14)

    def test_public_page_uses_own_and_inherited_image_focus(self):
        response = self.client.get(reverse('raca_detail', args=[self.race.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-base-focus-x="22"')
        self.assertContains(response, 'data-focus-x="22" data-focus-y="76" data-name="Linhagem"')
        self.assertContains(response, 'data-focus-x="81" data-focus-y="14" data-name="Essencia"')
        self.assertContains(response, 'background-position: 22% 76%')
        ajax = self.client.get(reverse('raca_detail', args=[self.race.slug]), {'ajax': '1'})
        self.assertEqual(ajax.status_code, 200)
        self.assertContains(ajax, 'data-base-focus-y="76"')

    def test_essence_without_own_image_inherits_race_focus(self):
        self.essence.imagem_url = None
        self.essence.save(update_fields=['imagem_url'])
        response = self.client.get(reverse('raca_detail', args=[self.race.slug]))
        self.assertContains(response, 'data-focus-x="22" data-focus-y="76" data-name="Essencia"')

    def test_staff_can_edit_focus_but_invalid_focus_is_atomic(self):
        user = get_user_model().objects.create_user(username='race-editor', password='test-password', is_staff=True)
        self.client.force_login(user)
        url = reverse('wiki_update_race', args=[self.race.pk])
        original = self.race.nome
        response = self.client.post(url, data=json.dumps({'nome': 'Alterado', 'imagem_foco_x': 101, 'imagem_foco_y': 20}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.race.refresh_from_db()
        self.assertEqual((self.race.nome, self.race.imagem_foco_x), (original, 22))
        response = self.client.post(url, data=json.dumps({'nome': 'Alterado', 'imagem_foco_x': 38, 'imagem_foco_y': 61}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.race.refresh_from_db()
        self.assertEqual((self.race.nome, self.race.imagem_foco_x, self.race.imagem_foco_y), ('Alterado', 38, 61))

    def test_non_staff_cannot_edit_focus(self):
        user = get_user_model().objects.create_user(username='race-reader', password='test-password')
        self.client.force_login(user)
        response = self.client.post(reverse('wiki_update_race', args=[self.race.pk]), data=json.dumps({'imagem_foco_x': 5}), content_type='application/json')
        self.assertNotEqual(response.status_code, 200)
        self.race.refresh_from_db()
        self.assertEqual(self.race.imagem_foco_x, 22)

    def test_admin_exposes_validated_focus_for_race_lineage_and_essence(self):
        user = get_user_model().objects.create_superuser(username='race-admin', password='test-password', email='admin@example.com')
        self.client.force_login(user)
        for model_name, pk in (('tbraca', self.race.pk), ('tblinhagem', self.lineage.pk), ('tbessencia', self.essence.pk)):
            response = self.client.get(reverse(f'admin:home_{model_name}_change', args=[pk]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'name="imagem_foco_x"')
            self.assertContains(response, 'name="imagem_foco_y"')

    def test_admin_model_validation_rejects_out_of_range_focus(self):
        for image_owner in (self.race, self.lineage, self.essence):
            image_owner.imagem_foco_x = 101
            with self.assertRaises(ValidationError):
                image_owner.full_clean()
