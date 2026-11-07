"""A reviewed class edit creates a new catalog, never an in-place rewrite."""
import json

from django.urls import reverse

from .class_revision_editor import create_class_revision
from .content_versions import resolve_content
from .db_access_models import ManagedApiKey
from .models import TbClasse, TbClassehabilidade, TbContentRevision
from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog, seal_class_snapshot
from .test_criador import _CriadorBase


class ClassRevisionEditorTests(_CriadorBase):
    def test_add_update_remove_are_versioned_and_reusable_for_another_class(self):
        for slug in ('cacador', 'guerreiro'):
            classe = TbClasse.objects.get(slug=slug)
            base = seal_class_snapshot(classe.pk)
            original = VersionedClassCatalog(base, classe.pk)
            feature = next(row for row in original.collections[TbClassehabilidade]
                           if row.id_subclasse_id is None)
            added = TbClassehabilidade.objects.create(
                id_classe=classe, nome='Exemplo de apresentação', niveladquirido=20,
                descricao='**Conteúdo** revisado.')
            updated = create_class_revision(base.checksum, classe.pk, [
                {'model': 'home.tbclassehabilidade', 'action': 'update',
                 'pk': feature.pk, 'fields': {'descricao': '## Título\n\nTexto revisado.'}},
                {'model': 'home.tbclassehabilidade', 'action': 'add', 'pk': added.pk},
            ], presentation_source='catalog')
            self.assertNotEqual(updated.pk, base.pk)
            self.assertIsNone(original.presentation_source)
            self.assertEqual(VersionedClassCatalog(updated, classe.pk).presentation_source,
                             'catalog')
            before = resolve_content(base, 'class-catalog:%s' % classe.pk,
                                     evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
            after = resolve_content(updated, 'class-catalog:%s' % classe.pk,
                                    evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
            self.assertEqual(before['collections']['home.tbclassehabilidade'][0]['descricao'],
                             feature.descricao)
            self.assertIn('## Título', next(row['descricao'] for row in
                after['collections']['home.tbclassehabilidade']
                if row['id_habilidade'] == feature.pk))
            self.assertEqual(create_class_revision(base.checksum, classe.pk, [
                {'model': 'home.tbclassehabilidade', 'action': 'update',
                 'pk': feature.pk, 'fields': {'descricao': '## Título\n\nTexto revisado.'}},
                {'model': 'home.tbclassehabilidade', 'action': 'add', 'pk': added.pk},
            ], presentation_source='catalog').pk, updated.pk)

            removed = create_class_revision(updated.checksum, classe.pk, [
                {'model': 'home.tbclassehabilidade', 'action': 'remove', 'pk': added.pk},
            ], presentation_source='catalog')
            self.assertNotIn(added.pk, {row.pk for row in
                VersionedClassCatalog(removed, classe.pk).collections[TbClassehabilidade]})
            self.assertTrue(TbClassehabilidade.objects.filter(pk=added.pk).exists())

    def test_rejects_identity_change_and_rolls_back(self):
        classe = TbClasse.objects.get(slug='guerreiro')
        base = seal_class_snapshot(classe.pk)
        old_count = base.__class__.objects.count()
        revision_count = TbContentRevision.objects.count()
        with self.assertRaises(ValueError):
            create_class_revision(base.checksum, classe.pk, [
                {'model': 'home.tbclasse', 'action': 'update', 'pk': classe.pk,
                 'fields': {'slug': 'outra-classe'}},
            ])
        self.assertEqual(base.__class__.objects.count(), old_count)
        feature = TbClassehabilidade.objects.filter(id_classe=classe).first()
        with self.assertRaises(ValueError):
            create_class_revision(base.checksum, classe.pk, [
                {'model': 'home.tbclassehabilidade', 'action': 'update',
                 'pk': feature.pk, 'fields': {'descricao': 'Alteração válida'}},
                {'model': 'home.tbclassehabilidade', 'action': 'update',
                 'pk': feature.pk, 'fields': {'id_classe_id': 999}},
            ])
        self.assertEqual(TbContentRevision.objects.count(), revision_count)
        self.assertEqual(TbClassehabilidade.objects.get(pk=feature.pk).descricao,
                         feature.descricao)

    def test_structured_api_requires_scope_and_replays_without_new_revision(self):
        classe = TbClasse.objects.get(slug='guerreiro')
        base = seal_class_snapshot(classe.pk)
        feature = TbClassehabilidade.objects.filter(id_classe=classe).first()
        secret = ManagedApiKey.new_secret()
        key = ManagedApiKey.objects.create(name='class-editor', prefix=secret[:16],
            secret_hash=ManagedApiKey.digest(secret), scopes=['read'])
        url = reverse('db_access_operation', args=['class-revision'])
        body = {'base_version': base.checksum, 'class_id': classe.pk,
                'presentation_source': 'catalog', 'changes': [
                    {'model': 'home.tbclassehabilidade', 'action': 'update',
                     'pk': feature.pk, 'fields': {'descricao': '## Texto revisado'}}]}
        headers = {'HTTP_AUTHORIZATION': 'Bearer ' + secret,
                   'HTTP_IDEMPOTENCY_KEY': 'class-revision-1', 'secure': True}
        preview = self.client.post(reverse('db_access_operation', args=['class-revision-preview']),
            data=json.dumps(body), content_type='application/json',
            **{**headers, 'HTTP_IDEMPOTENCY_KEY': 'class-revision-preview-1'})
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertEqual(TbContentRevision.objects.filter(identity='class-catalog:%s' % classe.pk).count(), 1)
        denied = self.client.post(url, data=json.dumps(body),
                                  content_type='application/json', **headers)
        self.assertEqual(denied.status_code, 403)
        key.scopes = ['read', 'write']
        key.save(update_fields=['scopes'])
        first = self.client.post(url, data=json.dumps(body),
                                 content_type='application/json', **headers)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()['ruleset_checksum'], preview.json()['ruleset_checksum'])
        self.assertFalse(first.json()['activated'])
        again = self.client.post(url, data=json.dumps(body),
                                 content_type='application/json', **headers)
        self.assertEqual(again.json(), first.json())
        self.assertEqual(TbContentRevision.objects.filter(identity='class-catalog:%s' % classe.pk).count(), 2)
        body['changes'][0]['fields']['id_classe_id'] = 999
        invalid = self.client.post(url, data=json.dumps(body),
                                   content_type='application/json',
                                   **{**headers, 'HTTP_IDEMPOTENCY_KEY': 'class-revision-2'})
        self.assertEqual(invalid.status_code, 400)
