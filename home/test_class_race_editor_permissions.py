import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import TbClasse, TbClassehabilidade, TbRaca, TbTracoracial


class ClassRaceEditorPermissionTests(TestCase):
    def setUp(self):
        self.classe = TbClasse.objects.create(nome='Classe editorial', slug='classe-editorial')
        self.feature = TbClassehabilidade.objects.create(
            id_classe=self.classe, nome='Recurso original', niveladquirido=1,
            descricao='Descricao original',
        )
        self.race = TbRaca.objects.create(nome='Raca editorial', slug='raca-editorial')
        self.trait = TbTracoracial.objects.create(
            id_raca=self.race, nome='Traco original', descricao='Descricao original',
        )
        self.feature_url = reverse('wiki_update_class_feature', args=[self.feature.pk])
        self.race_url = reverse('wiki_update_race', args=[self.race.pk])
        self.trait_url = reverse('wiki_update_racial_trait', args=[self.trait.pk])
        self.class_page = reverse('classe_detail', args=[self.classe.slug])
        self.race_page = reverse('raca_detail', args=[self.race.slug])

    def editor(self, name, permission=None):
        user = get_user_model().objects.create_user(username=name, is_staff=True)
        if permission:
            user.user_permissions.add(Permission.objects.get(
                content_type__app_label='home', codename=permission,
            ))
        self.client.force_login(user)
        return user

    def post(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_generic_staff_cannot_edit_or_see_controls(self):
        self.editor('generic')
        for url, payload in (
            (self.feature_url, {'nome': 'Invasao'}),
            (self.race_url, {'nome': 'Invasao'}),
            (self.trait_url, {'nome': 'Invasao'}),
        ):
            self.assertEqual(self.post(url, payload).status_code, 403)
        self.feature.refresh_from_db()
        self.race.refresh_from_db()
        self.trait.refresh_from_db()
        self.assertEqual((self.feature.nome, self.race.nome, self.trait.nome),
                         ('Recurso original', 'Raca editorial', 'Traco original'))
        self.assertFalse(LogEntry.objects.exists())
        for page in (self.class_page, self.race_page):
            response = self.client.get(page)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'data-feature-edit>Editar')
            self.assertNotContains(response, 'data-race-edit aria-controls')
            self.assertNotContains(response, 'data-trait-edit>Editar')

    def test_editor_roles_are_independent_and_audited(self):
        roles = (
            ('class-editor', 'change_tbclassehabilidade', self.feature_url,
             {'nome': 'Recurso revisado', 'descricao': 'Conteudo revisado'}),
            ('race-editor', 'change_tbraca', self.race_url,
             {'nome': 'Raca revisada', 'lore_presentation': 'Historia revisada'}),
            ('trait-editor', 'change_tbtracoracial', self.trait_url,
             {'nome': 'Traco revisado', 'descricao': 'Traco publicado'}),
        )
        for name, permission, allowed_url, payload in roles:
            with self.subTest(role=name):
                self.editor(name, permission)
                for denied_url in (self.feature_url, self.race_url, self.trait_url):
                    if denied_url != allowed_url:
                        self.assertEqual(self.post(denied_url, {'nome': 'Invasao'}).status_code, 403)
                self.assertEqual(self.post(allowed_url, payload).status_code, 200)
                self.assertEqual(LogEntry.objects.filter(user__username=name).count(), 1)

        self.client.logout()
        self.feature.refresh_from_db()
        self.race.refresh_from_db()
        self.trait.refresh_from_db()
        self.assertEqual((self.feature.nome, self.race.nome, self.trait.nome),
                         ('Recurso revisado', 'Raca revisada', 'Traco revisado'))
        for page, published in ((self.class_page, 'Recurso revisado'),
                                (self.race_page, 'Traco revisado')):
            response = self.client.get(page)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, published)
            self.assertNotContains(response, 'data-feature-edit>Editar')
            self.assertNotContains(response, 'data-race-edit aria-controls')
            self.assertNotContains(response, 'data-trait-edit>Editar')

    def test_race_and_trait_controls_follow_their_own_permission(self):
        for name, permission, race_button, trait_button in (
            ('race-only', 'change_tbraca', True, False),
            ('trait-only', 'change_tbtracoracial', False, True),
        ):
            with self.subTest(role=name):
                self.editor(name, permission)
                for ajax in (False, True):
                    response = self.client.get(self.race_page, {'ajax': '1'} if ajax else {})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(b'data-race-edit aria-controls' in response.content, race_button)
                    self.assertEqual(b'data-trait-edit>Editar' in response.content, trait_button)

    def test_class_controls_follow_feature_permission_on_page_and_ajax(self):
        for name, permission, expected in (
            ('class-generic', None, False),
            ('class-authorized', 'change_tbclassehabilidade', True),
        ):
            with self.subTest(role=name):
                self.editor(name, permission)
                for ajax in (False, True):
                    response = self.client.get(self.class_page, {'ajax': '1'} if ajax else {})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(b'data-feature-edit>Editar' in response.content, expected)
