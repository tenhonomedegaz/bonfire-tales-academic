import json
from unittest.mock import patch

from django.urls import reverse

from .class_revision_editor import create_class_revision
from .class_publication import ClassPublicationConflict, publication_preview, publish_class
from .db_access_models import ManagedApiKey
from .models import TbClassPublication, TbClassPublicationLog, TbClasse, TbClassehabilidade
from .test_criador import _CriadorBase
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
