"""Bounded regressions for the common catalog selection in main views."""
from django.db import transaction
from django.test import override_settings
from django.urls import reverse

from home import views, test_creator_hunter_binding as hunter_fixture, test_creator_pinned_catalog as pinned_fixture
from home.class_revision_editor import create_class_revision
from home.models import TbClasse, TbPersonagem, TbPersonagemCacador, TbPersonagemClasse
from home.test_criador import _CriadorBase


@override_settings(CLASS_CATALOG_RULESETS={}, HUNTER_CREATOR_RULESET_CHECKSUM='')
class ClassSelectionViewTests(_CriadorBase):
    def test_unavailable_hunter_does_not_block_other_class_listing_preview_or_creation(self):
        from home.versioned_classes import seal_class_snapshot
        hunter = TbClasse.objects.get(slug='cacador')
        incomplete = seal_class_snapshot(hunter.pk)
        owner = self._novo_usuario('isolated-hunter-guard', staff=True)
        old = TbPersonagem.objects.create(dono=owner, nome='Preserved Hunter link')
        old_pc = TbPersonagemClasse.objects.create(
            id_personagem=old, id_classe=hunter, nivel=1, principal=True)
        payload = self._payload('guerreiro')
        hunter_payload = dict(payload, classe='cacador', hunter_ability='int')
        self.client.force_login(owner)
        # Both selection failure and a valid class snapshot lacking Hunter content.
        for checksum in ('f' * 64, incomplete.checksum):
            with self.subTest(checksum=checksum), override_settings(
                    CLASS_CATALOG_RULESETS={'cacador': checksum}):
                count = TbPersonagem.objects.count()
                for route in ('criacao_ficha', 'pathbuilder'):
                    page = self.client.get(reverse(route))
                    self.assertEqual(page.status_code, 200, page.content[:300])
                    available = {row['slug'] for row in page.context['catalogos']['classes']}
                    self.assertIn('guerreiro', available)
                    self.assertNotIn('cacador', available)
                    self.assertFalse(page.context['hunter_creator_available'])
                    self.assertEqual(self.client.get(reverse(route) + '?hunter=1').status_code, 503)
                preview = self.client.post(reverse('criar_personagem_preview'),
                    data=payload, content_type='application/json')
                self.assertEqual(preview.status_code, 200, preview.content)
                self.assertTrue(preview.json()['ready'], preview.content)
                self.assertEqual(TbPersonagem.objects.count(), count)
                for route in ('criar_personagem_preview', 'criar_personagem'):
                    response = self.client.post(reverse(route), data=hunter_payload,
                                                content_type='application/json')
                    self.assertEqual(response.status_code, 503, response.content)
                    self.assertFalse(response.json()['ok'])
                self.assertEqual(TbPersonagem.objects.count(), count)
                created = self._post_criar(owner, payload)
                self.assertEqual(created.status_code, 200, created.content)
                new = TbPersonagem.objects.get(pk=created.json()['id'])
                self.assertEqual(new.classes.get().id_classe.slug, 'guerreiro')
                self.assertIsNone(new.classes.get().ruleset_id)
                old_pc.refresh_from_db()
                self.assertIsNone(old_pc.ruleset_id)
                self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=old_pc).exists())

    def test_configured_class_drives_detail_list_preview_create_and_multiclass_without_repinning(self):
        classe = TbClasse.objects.get(slug='guerreiro')
        payload = self._payload('guerreiro')
        owner = self._novo_usuario('class-selection', staff=True)
        old = TbPersonagem.objects.create(dono=owner, nome='Unbound build')
        old_pc = TbPersonagemClasse.objects.create(
            id_personagem=old, id_classe=classe, nivel=1, principal=True)
        base = pinned_fixture.CreatorPinnedCatalogTests.seal(self, classe)
        selected = create_class_revision(base.checksum, classe.pk, [
            {'model': 'home.tbclasse', 'action': 'update', 'pk': classe.pk,
             'fields': {'nome': 'Frozen selected class'}},
        ], presentation_source='catalog')
        TbClasse.objects.filter(pk=classe.pk).update(nome='Mutable source name')
        self.client.force_login(owner)
        with override_settings(CLASS_CATALOG_RULESETS={classe.slug: selected.checksum}):
            page = self.client.get(reverse('classe_detail', args=[classe.slug]))
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page.context['classe'].nome, 'Frozen selected class')
            self.assertFalse(page.context['can_edit_wiki'])
            creator = self.client.get(reverse('criacao_ficha'))
            self.assertEqual(creator.status_code, 200)
            row = next(row for row in creator.context['catalogos']['classes'] if row['slug'] == classe.slug)
            self.assertEqual(row['nome'], 'Frozen selected class')
            self.assertFalse(row['hunter_rework'])
            mastery_count = views._classe_maestria_n(classe, 1)
            self.assertGreater(mastery_count, 0)
            self.assertEqual(row['maestria_n'], mastery_count)
            before = TbPersonagem.objects.count()
            preview = self.client.post(reverse('criar_personagem_preview'),
                data=payload, content_type='application/json')
            self.assertTrue(preview.json()['ready'], preview.content)
            self.assertEqual(TbPersonagem.objects.count(), before)
            created = self._post_criar(owner, payload)
            self.assertEqual(created.status_code, 200, created.content)
            person = TbPersonagem.objects.get(pk=created.json()['id'])
            self.assertEqual(person.classes.get().ruleset_id, selected.pk)
            ruleset, effective = views._multiclass_publication(classe)
            self.assertEqual((ruleset.pk, effective.nome), (selected.pk, 'Frozen selected class'))
            old_pc.refresh_from_db()
            self.assertIsNone(old_pc.ruleset_id)
            self.assertIsNone(views._hunter_ruleset_for_class(old_pc))
            from home.models import TbClassehabilidade
            TbClasse.objects.filter(pk=classe.pk).update(tags_json=[])
            TbClassehabilidade.objects.filter(id_classe=classe).update(tags_json=[])
            frozen_row = next(row for row in views._criador_catalogos()['classes']
                              if row['slug'] == classe.slug)
            self.assertEqual(frozen_row['maestria_n'], mastery_count)

    def test_invalid_configured_selection_fails_closed_across_views_without_writes(self):
        from home.content_versions import create_revision, seal_ruleset
        from home.versioned_classes import EVALUATOR, VOCABULARY, inventory_class
        classe = TbClasse.objects.get(slug='guerreiro')
        payload = self._payload('guerreiro')
        owner = self._novo_usuario('invalid-class-selection', staff=True)
        person = TbPersonagem.objects.create(dono=owner, nome='Existing build', aventuras=500)
        TbPersonagemClasse.objects.create(id_personagem=person,
            id_classe=TbClasse.objects.get(slug='paladino'), nivel=1, principal=True)
        snapshot = inventory_class(classe.pk)
        snapshot['collections']['home.tbclasse'][0].pop('tagline')
        invalid = seal_ruleset([create_revision('class-catalog:%s' % classe.pk, snapshot)],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.client.force_login(owner)
        with override_settings(CLASS_CATALOG_RULESETS={classe.slug: invalid.checksum}):
            self.assertEqual(self.client.get(reverse('classe_detail', args=[classe.slug])).status_code, 503)
            for route in ('criacao_ficha', 'pathbuilder'):
                page = self.client.get(reverse(route))
                self.assertEqual(page.status_code, 200, page.content[:300])
                available = {row['slug'] for row in page.context['catalogos']['classes']}
                self.assertNotIn('guerreiro', available)
                self.assertIn('paladino', available)
            for route in ('criar_personagem_preview', 'criar_personagem'):
                response = self.client.post(reverse(route), data=payload, content_type='application/json')
                self.assertEqual(response.status_code, 503, response.content)
                self.assertFalse(response.json()['ok'])
            self.assertTrue(views._lvl_aplicar_adicionar_classe(person, {'classe': classe.pk}))
        self.assertEqual(TbPersonagem.objects.count(), 1)
        self.assertEqual(person.classes.count(), 1)
        person.refresh_from_db()
        self.assertEqual(person.nivel, 1)
        self.assertIsNone(person.classes.get().ruleset_id)

    def test_common_hunter_selection_keeps_permanent_ability_and_legacy_links(self):
        hunter_fixture.CreatorHunterBindingTests.setup_creation(self)
        self.resolve = lambda data: views._criador_resolver(
            data, ruleset=self.ruleset, class_id=self.classe.pk)
        old = TbPersonagem.objects.create(dono=self.user, nome='Legacy preserved')
        old_pc = TbPersonagemClasse.objects.create(
            id_personagem=old, id_classe=self.classe, nivel=1, principal=True)
        self.client.force_login(self.user)
        with override_settings(CLASS_CATALOG_RULESETS={'cacador': self.ruleset.checksum},
                               HUNTER_CREATOR_RULESET_CHECKSUM='not-a-selection'):
            self.assertEqual(views._criador_hunter_catalog_args()['hunter_ruleset'], self.ruleset)
            legacy_option = next(row for row in views._criador_catalogos()['classes']
                                 if row['slug'] == 'cacador')
            self.assertFalse(legacy_option['hunter_rework'])
            for route in ('criacao_ficha', 'pathbuilder'):
                page = self.client.get(reverse(route) + '?hunter=1')
                self.assertEqual(page.status_code, 200, page.content[:300])
                self.assertEqual([row['slug'] for row in page.context['catalogos']['classes']], ['cacador'])
                self.assertContains(page, 'cf-hunter-ability')
            for ability in ('int', 'wis'):
                with self.subTest(ability=ability), transaction.atomic():
                    _, errors = hunter_fixture.CreatorHunterBindingTests.valid_payload(self, ability)
                    self.assertEqual(errors, [])
                    count = TbPersonagem.objects.count()
                    preview = self.client.post(reverse('criar_personagem_preview'),
                        data=self.payload, content_type='application/json')
                    self.assertTrue(preview.json()['ready'], preview.content)
                    self.assertEqual(TbPersonagem.objects.count(), count)
                    created = self._post_criar(self.user, self.payload)
                    self.assertEqual(created.status_code, 200, created.content)
                    profile = TbPersonagemCacador.objects.get(
                        personagem_classe__id_personagem_id=created.json()['id'])
                    self.assertEqual((profile.ruleset_id, profile.ability), (self.ruleset.pk, ability))
                    transaction.set_rollback(True)
            old_pc.refresh_from_db()
            self.assertIsNone(old_pc.ruleset_id)
            self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=old_pc).exists())
