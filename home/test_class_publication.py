import json
from unittest.mock import patch

from django.urls import reverse

from . import views
from .class_revision_editor import create_class_revision
from .class_publication import ClassPublicationConflict, publication_preview, publish_class
from .db_access_models import ManagedApiKey
from .models import TbClassPublication, TbClassPublicationLog, TbClasse, TbClassehabilidade, TbPersonagem
from .test_criador import _CriadorBase
from .test_creator_pinned_catalog import CreatorPinnedCatalogTests
from .versioned_classes import seal_class_snapshot


class ClassPublicationTests(_CriadorBase):
    def _target(self, slug='guerreiro'):
        classe = TbClasse.objects.get(slug=slug)
        base = seal_class_snapshot(classe.pk)
        feature = TbClassehabilidade.objects.filter(id_classe=classe, id_subclasse__isnull=True).first()
        target = create_class_revision(base.checksum, classe.pk, [
            {'model': 'home.tbclassehabilidade', 'action': 'update', 'pk': feature.pk,
             'fields': {'descricao': '## Revisão publicada\n\n**Texto** revisado.'}},
        ], presentation_source='catalog')
        return classe, base, target

    def test_publish_and_replay_use_generic_class_binding(self):
        classe, base, target = self._target()
        before = self.client.get(reverse('classe_detail', args=[classe.slug]))
        self.assertEqual(before.status_code, 200)
        self.assertNotIn('Revisão publicada', before.content.decode())
        preflight = publication_preview(classe.pk, target.checksum, 'unpublished')
        self.assertEqual(preflight['target_checksum'], target.checksum)
        with patch('home.content_maintenance._local_postgres', return_value=True), \
                patch('home.content_maintenance._protected_directory', return_value='safe'), \
                patch('home.content_maintenance._fresh_backup', return_value='backup') as backup:
            first = publish_class(classe.pk, target.checksum, 'unpublished')
            again = publish_class(classe.pk, target.checksum, target.checksum)
        self.assertTrue(first['published'])
        self.assertTrue(again['already_published'])
        self.assertEqual(backup.call_count, 1)
        self.assertEqual(TbClassPublicationLog.objects.filter(id_classe=classe).count(), 1)
        self.assertEqual(TbClassPublication.objects.get(id_classe=classe).ruleset, target)
        after = self.client.get(reverse('classe_detail', args=[classe.slug]))
        self.assertContains(after, 'Revisão publicada')
        with self.assertRaises(ClassPublicationConflict):
            publication_preview(classe.pk, target.checksum, 'unpublished')

    def test_backup_failure_rolls_back_publication(self):
        classe, _, target = self._target()
        with patch('home.content_maintenance._local_postgres', return_value=True), \
                patch('home.content_maintenance._protected_directory', return_value='safe'), \
                patch('home.content_maintenance._fresh_backup', side_effect=ValueError('backup failed')):
            with self.assertRaises(ValueError):
                publish_class(classe.pk, target.checksum, 'unpublished')
        self.assertFalse(TbClassPublication.objects.filter(id_classe=classe).exists())
        self.assertFalse(TbClassPublicationLog.objects.filter(id_classe=classe).exists())

    def test_other_published_class_drives_creator_preview_and_creation(self):
        classe = TbClasse.objects.get(slug='guerreiro')
        legacy_payload = self._payload('guerreiro')
        legacy_user = self._novo_usuario('legacy-warrior')
        legacy = self._post_criar(legacy_user, legacy_payload)
        self.assertEqual(legacy.status_code, 200, legacy.content[:300])
        legacy_person = TbPersonagem.objects.get(pk=legacy.json()['id'])
        self.assertIsNone(legacy_person.classes.get().ruleset_id)
        base = CreatorPinnedCatalogTests.seal(self, classe)
        feature = TbClassehabilidade.objects.filter(
            id_classe=classe, id_subclasse__isnull=True).first()
        target = create_class_revision(base.checksum, classe.pk, [
            {'model': 'home.tbclassehabilidade', 'action': 'update', 'pk': feature.pk,
             'fields': {'descricao': '## Guerreiro publicado\n\n**Texto** revisado.'}},
        ], presentation_source='catalog')
        payload = self._payload('guerreiro')
        before, errors = views._criador_public_resolution(payload)
        self.assertEqual(errors, [])
        self.assertIsNone(before['ruleset'])
        with patch('home.content_maintenance._local_postgres', return_value=True), \
                patch('home.content_maintenance._protected_directory', return_value='safe'), \
                patch('home.content_maintenance._fresh_backup', return_value='backup'):
            publish_class(classe.pk, target.checksum, 'unpublished')
        resolved, errors = views._criador_public_resolution(payload)
        self.assertEqual(errors, [])
        self.assertEqual(resolved['ruleset'], target)
        self.assertEqual(resolved['classe'].pk, classe.pk)
        user = self._novo_usuario('published-warrior')
        self.client.force_login(user)
        preview = self.client.post(reverse('criar_personagem_preview'),
            data=json.dumps(payload), content_type='application/json')
        self.assertEqual(preview.status_code, 200, preview.content[:300])
        self.assertTrue(preview.json()['ready'], preview.content[:300])
        created = self._post_criar(user, payload)
        self.assertEqual(created.status_code, 200, created.content[:300])
        person = TbPersonagem.objects.get(pk=created.json()['id'])
        self.assertEqual(person.classes.get().ruleset_id, target.pk)
        TbClassehabilidade.objects.filter(pk=feature.pk).update(descricao='Texto vivo alterado.')
        sheet = self.client.get(reverse('ficha_detail', args=[person.pk]))
        self.assertEqual(sheet.status_code, 200, sheet.content[:300])
        descriptions = [row['descricao'] for row in sheet.context['ficha']['features']]
        self.assertIn('## Guerreiro publicado\n\n**Texto** revisado.', descriptions)
        self.assertNotIn('Texto vivo alterado.', descriptions)
        self.client.force_login(legacy_user)
        legacy_sheet = self.client.get(reverse('ficha_detail', args=[legacy_person.pk]))
        self.assertEqual(legacy_sheet.status_code, 200, legacy_sheet.content[:300])
        self.assertIsNone(legacy_person.classes.get().ruleset_id)

    def test_incomplete_published_class_fails_closed_in_creator(self):
        classe, _, target = self._target()
        payload = self._payload('guerreiro')
        with patch('home.content_maintenance._local_postgres', return_value=True), \
                patch('home.content_maintenance._protected_directory', return_value='safe'), \
                patch('home.content_maintenance._fresh_backup', return_value='backup'):
            publish_class(classe.pk, target.checksum, 'unpublished')
        user = self._novo_usuario('incomplete-warrior')
        self.client.force_login(user)
        preview = self.client.post(reverse('criar_personagem_preview'),
            data=json.dumps(payload), content_type='application/json')
        created = self._post_criar(user, payload)
        self.assertEqual(preview.status_code, 503)
        self.assertEqual(created.status_code, 503)

    def test_api_requires_separate_publish_scope_and_previews_read_only(self):
        classe, _, target = self._target()
        secret = ManagedApiKey.new_secret()
        key = ManagedApiKey.objects.create(name='editor', prefix=secret[:16],
            secret_hash=ManagedApiKey.digest(secret), scopes=['read', 'write'])
        body = {'base_version': 'unpublished', 'class_id': classe.pk,
                'target_checksum': target.checksum}
        headers = {'HTTP_AUTHORIZATION': 'Bearer ' + secret,
                   'HTTP_IDEMPOTENCY_KEY': 'publish-one', 'secure': True}
        preview = self.client.post(reverse('db_access_operation', args=['class-publication-preview']),
            data=json.dumps(body), content_type='application/json',
            **{**headers, 'HTTP_IDEMPOTENCY_KEY': 'publish-preview-one'})
        self.assertEqual(preview.status_code, 200, preview.content)
        denied = self.client.post(reverse('db_access_operation', args=['class-publication']),
            data=json.dumps(body), content_type='application/json', **headers)
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(TbClassPublication.objects.filter(id_classe=classe).exists())
        key.scopes.append('publish')
        key.save(update_fields=['scopes'])
        with patch('home.content_maintenance._local_postgres', return_value=True), \
                patch('home.content_maintenance._protected_directory', return_value='safe'), \
                patch('home.content_maintenance._fresh_backup', return_value='backup'):
            applied = self.client.post(reverse('db_access_operation', args=['class-publication']),
                data=json.dumps(body), content_type='application/json', **headers)
            replay = self.client.post(reverse('db_access_operation', args=['class-publication']),
                data=json.dumps(body), content_type='application/json', **headers)
        self.assertEqual(applied.status_code, 200, applied.content)
        self.assertEqual(applied.json(), replay.json())
        self.assertEqual(TbClassPublicationLog.objects.filter(id_classe=classe).count(), 1)
