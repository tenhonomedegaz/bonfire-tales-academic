"""Full catalog composition against the shipped fixture, without marker stubs."""
import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from .test_criador import _CriadorBase
from . import test_creator_pinned_catalog as snapshots
from .content_versions import create_revision, seal_ruleset
from .hunter_catalog import compose_choice_revision, compose_order_revision
from .hunter_rework import catalog
from .hunter_regularization import _reviewed_target
from .character_engine import derive
from .class_revision_editor import create_class_revision
from .class_publication import publish_class
from .models import (TbClassPublication, TbClassPublicationLog, TbClasse, TbClassehabilidade, TbRecursoclasse, TbSubclasse, TbPersonagem, TbPersonagemClasse,
                     TbPersonagemCacador)
from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog, inventory_class
from .views import _normalize_key


class HunterReleaseCatalogTests(_CriadorBase):
    def test_complete_composition_preserves_legacy_and_only_regularizes_to_reviewed_orders(self):
        hunter = TbClasse.objects.get(pk=4, slug='cacador')
        old_order = TbSubclasse.objects.get(id_classe=hunter, nome='Ordem da Aliança Selvagem')
        owner = self._novo_usuario('release-catalog')
        person = TbPersonagem.objects.create(dono=owner, nome='Legado preservado',
            nivel=3, carteira_pc=321, aventuras=8, braseiros=4)
        pc = TbPersonagemClasse.objects.create(id_personagem=person, id_classe=hunter,
            id_subclasse=old_order, nivel=3, principal=True)
        before = derive(person)
        live_catalog = inventory_class(hunter.pk)
        base = snapshots.CreatorPinnedCatalogTests.seal(self, hunter)
        base = seal_ruleset([entry.revision for entry in base.entries.select_related('revision')]
            + [create_revision('hunter-rework', catalog())],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        mapping = dict(class_id=4, feature_ids={'preparation': 881, 'expertise': 1021},
            passive_ids={'extra_attack': 1036, 'relentless': 1045, 'sharp_instinct': 1047,
                         'unshakable_will': 1066, 'predatory_instinct': 1068},
            secrets_ids={'feature': 1020, 'points': 3775, 'known': 2736},
            conditional_ids={'favored': 884, 'territory': 1037, 'predator': 1055,
                             'hide': 1057, 'domination': 1077, 'favored_resource': 2737},
            spellcasting_ids={'feature': 1019, 'slots': [2733, 2754, 2779, 2808, 2841]},
            mark_feature_id=880)
        composed = compose_choice_revision(base, **mapping)
        self.assertEqual(inventory_class(hunter.pk), live_catalog)
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        orders = json.loads(output.getvalue())['order_ids']
        target = compose_order_revision(composed, class_id=hunter.pk, order_ids=orders)
        self.assertTrue(_reviewed_target(target, hunter.pk, catalog()))
        self.assertEqual(compose_order_revision(compose_choice_revision(target, **mapping),
            class_id=hunter.pk, order_ids=orders).pk, target.pk)
        person.refresh_from_db()
        after = derive(person)
        # Legacy resource rows have no database ordering guarantee. The new
        # Order identities must preserve every resource and its value, while
        # PostgreSQL may return the same rows in a different sequence.
        for kind, rows in before['recursos_por_tipo'].items():
            self.assertCountEqual(after['recursos_por_tipo'][kind], rows)
        for snapshot in (before, after):
            snapshot.pop('recursos_por_tipo')
        self.assertEqual(after, before)
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())

        detail_url = reverse('classe_detail', args=['cacador'])
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=target.checksum):
            detail = self.client.get(detail_url)
            self.assertEqual(detail.status_code, 200)
            from .hunter_publication_diagnostic import publication_status
            self.assertEqual(publication_status()['code'], 'ok')
            self.assertEqual(publication_status()['orders'], 8)
            self.assertEqual([row['nivel'] for row in detail.context['progression_table']],
                             list(range(1, 21)))
            self.assertEqual({sub.pk for sub in detail.context['subclasses']},
                             set(orders.values()))
            self.assertNotIn(old_order.pk, {sub.pk for sub in detail.context['subclasses']})
            self.assertFalse(detail.context['can_edit_wiki'])
            die_index = next(index for index, column in enumerate(detail.context['colunas'])
                             if _normalize_key(column['name']).startswith('dado_de_ca'))
            for level, die in ((1, 'd6'), (5, 'd8'), (11, 'd10'), (17, 'd12')):
                cell = detail.context['progression_table'][level - 1]['cells'][die_index]
                self.assertIn(die, str(cell['valor']))
            self.assertIn('Ordem do Ca', str(detail.context['progression_table'][2]['cells']))
            ajax = self.client.get(detail_url + '?ajax=1&subclasse=' + old_order.slug,
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            self.assertEqual(ajax.status_code, 200)
            self.assertEqual({sub.pk for sub in ajax.context['subclasses']}, set(orders.values()))
        # A new publication reads the same class rows as every other class.
        # The older publication above remains usable while the new revision is
        # reviewed and activated separately.
        marker = TbClassehabilidade.objects.create(id_classe=hunter,
            nome='Ordem do Caçador', niveladquirido=3,
            descricao='## Ordem do Caçador\n\n**Escolha** sua Ordem.')
        frozen = VersionedClassCatalog(target, hunter.pk)
        die = next(row for row in frozen.collections[TbRecursoclasse]
                   if row.id_subclasse_id is None and row.nome.startswith('Dado de'))
        v2 = create_class_revision(target.checksum, hunter.pk, [
            {'model': 'home.tbclassehabilidade', 'action': 'add', 'pk': marker.pk},
            {'model': 'home.tbrecursoclasse', 'action': 'update', 'pk': die.pk,
             'fields': {'valores_json': {'1': 'd6', '5': 'd8', '11': 'd10', '17': 'd12'}}},
        ], presentation_source='catalog')
        with patch('home.content_maintenance._local_postgres', return_value=True), \
                patch('home.content_maintenance._protected_directory', return_value='safe'), \
                patch('home.content_maintenance._fresh_backup', return_value='backup') as backup:
            result = publish_class(hunter.pk, v2.checksum, 'unpublished')
            replay = publish_class(hunter.pk, v2.checksum, v2.checksum)
        self.assertTrue(result['published'])
        self.assertTrue(replay['already_published'])
        backup.assert_called_once()
        self.assertEqual(TbClassPublication.objects.get(id_classe=hunter).ruleset_id, v2.pk)
        self.assertEqual(TbClassPublicationLog.objects.filter(id_classe=hunter).count(), 1)
        from .views import _criador_hunter_catalog_args
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=target.checksum):
            self.assertEqual(_criador_hunter_catalog_args()['hunter_ruleset'].pk, v2.pk)
            revised = self.client.get(detail_url)
            self.assertEqual(revised.status_code, 200)
            cells = revised.context['progression_table'][2]['cells']
            feature_cell = next(cell for cell in cells if cell['col']['is_feature'])
            self.assertIn('Ordem do Caçador', str(feature_cell['valor']))
            self.assertIn('Companheiro Primordial', str(feature_cell['valor']))
            self.assertEqual(revised.context['progression_table'][0]['cells'][die_index]['valor'],
                             '<span class="block">d6</span>')
            self.assertEqual(self.client.get(reverse('classe_detail', args=['guerreiro'])).status_code,
                             200)
        pc.refresh_from_db()
        self.assertEqual((pc.id_subclasse_id, pc.nivel), (old_order.pk, 3))
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())

        self.client.force_login(owner)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': v2.checksum, 'expected_level': '3',
            'expected_order_id': str(old_order.pk), 'ability': 'wis', 'confirm': '1',
            'order': str(old_order.pk)}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=target.checksum):
            preview = self.client.get(url)
            comparison = preview.context['comparison']
            self.assertEqual(comparison['ruleset_checksum'], v2.checksum)
            self.assertEqual({o.pk for o in comparison['available_orders']}, set(orders.values()))
            self.assertIsNone(comparison['candidate_order_id'])
            rejected = self.client.post(url, payload)
            self.assertContains(rejected, 'Escolha uma Ordem da revisão.')
            pc.refresh_from_db()
            self.assertEqual(pc.id_subclasse_id, old_order.pk)
            self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())
            payload['order'] = str(orders['ordem-da-alianca-selvagem'])
            applied = self.client.post(url, payload)
            self.assertEqual(applied.status_code, 302, applied.content[:1000])
        profile = TbPersonagemCacador.objects.get(personagem_classe=pc)
        self.assertEqual(profile.regularization['old_order_id'], old_order.pk)
        self.assertEqual(profile.ruleset_id, v2.pk)
        person.refresh_from_db()
        self.assertEqual((person.carteira_pc, person.aventuras, person.braseiros), (321, 8, 4))
        self.assertEqual(self.client.get(reverse('hunter_sheet', args=[person.pk])).status_code, 200)

        # The protected status and real public route reject the same failed
        # frozen resolver without bypassing the immutable-revision DB trigger.
        from .hunter_publication_diagnostic import publication_status
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=target.checksum), \
                patch('home.class_publication.VersionedClassCatalog',
                      side_effect=ValueError('Frozen class unavailable')):
            self.assertEqual(publication_status()['code'], 'class_snapshot_invalid')
            self.assertEqual(self.client.get(detail_url).status_code, 503)

    def test_public_hunter_page_fails_closed_without_valid_publication(self):
        url = reverse('classe_detail', args=['cacador'])
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=''):
            self.assertEqual(self.client.get(url).status_code, 503)
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM='0' * 64):
            self.assertEqual(self.client.get(url).status_code, 503)
        self.assertEqual(self.client.get(reverse('classe_detail', args=['guerreiro'])).status_code, 200)
