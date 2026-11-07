from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .models import TbPersonagem
from .test_criador import _CriadorBase


class CharacterVisibilityTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('visibility-owner')

    def test_new_character_is_public_without_exposing_optional_details(self):
        character = TbPersonagem.objects.create(dono=self.owner, nome='New public hero')
        character.refresh_from_db()
        self.assertTrue(character.publico)
        self.assertFalse(character.mostrar_atributos_publicos)
        self.assertFalse(character.mostrar_pericias_publicas)
        self.assertFalse(character.mostrar_resumo_mecanico_publico)
        self.assertEqual(self.client.get(reverse(
            'ficha_publica', args=[character.pk])).status_code, 200)

    def test_explicit_visibility_survives_edits_and_owner_can_privatize(self):
        private = TbPersonagem.objects.create(
            dono=self.owner, nome='Private hero', publico=False,
            mostrar_atributos_publicos=True)
        public = TbPersonagem.objects.create(
            dono=self.owner, nome='Public hero', publico=True,
            mostrar_pericias_publicas=True)
        private.nome = 'Renamed private hero'
        private.save()
        private.refresh_from_db()
        self.assertFalse(private.publico)
        self.assertTrue(private.mostrar_atributos_publicos)

        self.client.force_login(self.owner)
        response = self.client.post(reverse(
            'personagem_publicacao', args=[public.pk]), {'action': 'unpublish'})
        self.assertEqual(response.status_code, 302)
        public.refresh_from_db()
        private.refresh_from_db()
        self.assertFalse(public.publico)
        self.assertTrue(public.mostrar_pericias_publicas)
        self.assertFalse(private.publico)
        self.client.logout()
        for character in (private, public):
            self.assertEqual(self.client.get(reverse(
                'ficha_publica', args=[character.pk])).status_code, 404)

    def test_restoring_archived_private_character_does_not_publish_it(self):
        character = TbPersonagem.objects.create(
            dono=self.owner, nome='Archived hero', publico=False, arquivado=True)
        self.client.force_login(self.owner)
        response = self.client.post(reverse('personagem_restaurar', args=[character.pk]))
        self.assertEqual(response.status_code, 302)
        character.refresh_from_db()
        self.assertFalse(character.arquivado)
        self.assertFalse(character.publico)


class CreatorVisibilityTests(_CriadorBase):
    def test_creator_publishes_new_character_without_changing_private_ones(self):
        owner = self._novo_usuario('visibility-creator', staff=True)
        private = TbPersonagem.objects.create(
            dono=owner, nome='Existing private hero', publico=False,
            mostrar_resumo_mecanico_publico=True)
        response = self._post_criar(owner, self._payload('guerreiro'))
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['ok'])
        created = TbPersonagem.objects.get(pk=response.json()['id'])
        self.assertTrue(created.publico)
        private.refresh_from_db()
        self.assertFalse(private.publico)
        self.assertTrue(private.mostrar_resumo_mecanico_publico)


class CharacterVisibilityMigrationTests(TransactionTestCase):
    def test_migration_changes_default_without_backfilling_existing_choices(self):
        before = [('home', '0162_progression_milestone_choice')]
        after = [('home', '0163_tbpersonagem_public_default')]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            old_apps = executor.loader.project_state(before).apps
            owner = old_apps.get_model('auth', 'User').objects.create(username='visibility-migration')
            Character = old_apps.get_model('home', 'TbPersonagem')
            private = Character.objects.create(
                dono_id=owner.pk, nome='Legacy private', mostrar_atributos_publicos=True)
            public = Character.objects.create(
                dono_id=owner.pk, nome='Legacy public', publico=True,
                mostrar_pericias_publicas=True)
            self.assertFalse(private.publico)

            executor = MigrationExecutor(connection)
            executor.migrate(after)
            new_apps = executor.loader.project_state(after).apps
            Character = new_apps.get_model('home', 'TbPersonagem')
            private = Character.objects.get(pk=private.pk)
            public = Character.objects.get(pk=public.pk)
            self.assertFalse(private.publico)
            self.assertTrue(private.mostrar_atributos_publicos)
            self.assertTrue(public.publico)
            self.assertTrue(public.mostrar_pericias_publicas)
            self.assertTrue(Character.objects.create(
                dono_id=owner.pk, nome='New public default').publico)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
