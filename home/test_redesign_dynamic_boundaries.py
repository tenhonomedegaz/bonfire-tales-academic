"""S09: legacy parameterized actions keep their method and ownership boundaries."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from .models import TbPersonagem, UserProfile


class LegacyDynamicBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user('s09-dynamic-owner')
        cls.other = users.objects.create_user('s09-dynamic-other')
        cls.staff = users.objects.create_superuser('s09-dynamic-staff', 's09@example.test', 'unused')
        cls.character = TbPersonagem.objects.create(dono=cls.owner, nome='Ficha sintética S09')

    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))

    def test_character_mutations_are_post_only_and_private(self):
        routes = (
            ('personagem_usar_magia_inata', (self.character.pk, 999999)),
            ('personagem_escolher_subclasse', (self.character.pk,)),
            ('personagem_aplicar_asi', (self.character.pk,)),
            ('personagem_aprender_magias', (self.character.pk,)),
            ('personagem_anunciar_magico', (self.character.pk,)),
        )
        for name, args in routes:
            with self.subTest(route=name):
                url = reverse(name, args=args)
                self.client.logout()
                self.assertEqual(self.client.get(url).status_code, 302)
                self.client.force_login(self.owner)
                self.assertEqual(self.client.get(url).status_code, 405)
                self.client.force_login(self.other)
                self.assertEqual(self.client.post(url, {}).status_code, 404)
        self.character.refresh_from_db()
        self.assertEqual(self.character.nome, 'Ficha sintética S09')

    def test_map_layer_mutations_require_superuser_and_protect_surface(self):
        edit = reverse('wiki_edit_layer', args=[999999])
        delete = reverse('wiki_delete_layer', args=[999999])
        self.assertEqual(self.client.post(edit, {}).status_code, 302)
        self.assertEqual(self.client.post(delete, {}).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(edit, {}).status_code, 403)
        self.assertEqual(self.client.post(delete, {}).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(delete).status_code, 405)
        self.assertEqual(self.client.post(reverse('wiki_delete_layer', args=[0]), {}).status_code, 400)

    def test_market_mutations_reject_get(self):
        names = (
            ('mercado_responder_emprestimo', 999999),
            ('mercado_cancelar_emprestimo', 999999),
            ('mercado_pagar_emprestimo', 999999),
            ('cancelar_anuncio', 999999),
        )
        for name, pk in names:
            with self.subTest(route=name):
                url = reverse(name, args=[pk])
                self.assertEqual(self.client.get(url).status_code, 302)
                self.client.force_login(self.owner)
                self.assertEqual(self.client.get(url).status_code, 405)
                self.client.logout()

    def test_editorial_edit_routes_reject_missing_objects(self):
        cases = (
            ('armadilha_editar', 404), ('armadilha_excluir', 405),
            ('condicao_editar', 404), ('condicao_excluir', 405),
        )
        for name, expected in cases:
            with self.subTest(route=name):
                url = reverse(name, args=[999999])
                self.assertEqual(self.client.get(url).status_code, 302)
                self.client.force_login(self.staff)
                self.assertEqual(self.client.get(url).status_code, expected)
                self.client.logout()

    def test_invalid_public_tokens_do_not_verify_or_reset_account(self):
        verify = self.client.get(reverse('verify_email', args=['invalid-signature']))
        self.assertEqual(verify.status_code, 200)
        self.assertContains(verify, 'inválido')
        self.assertFalse(UserProfile.objects.filter(user=self.owner, email_verified=True).exists())

        reset = self.client.get(reverse('password_reset_confirm', args=['invalid-uid', 'invalid-token']))
        self.assertEqual(reset.status_code, 200)
        self.assertNotContains(reset, 'name="new_password1"')
