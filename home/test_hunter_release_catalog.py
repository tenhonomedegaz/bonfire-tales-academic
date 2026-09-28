"""Full catalog composition against the shipped fixture, without marker stubs."""
import json
from io import StringIO

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
from .models import (TbClasse, TbSubclasse, TbPersonagem, TbPersonagemClasse,
                     TbPersonagemCacador)
from .versioned_classes import EVALUATOR, VOCABULARY, inventory_class


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
        self.assertEqual(derive(person), before)
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=pc).exists())

        self.client.force_login(owner)
        url = reverse('hunter_regularization_preview', args=[person.pk])
        payload = {'ruleset_checksum': target.checksum, 'expected_level': '3',
            'expected_order_id': str(old_order.pk), 'ability': 'wis', 'confirm': '1',
            'order': str(old_order.pk)}
        with override_settings(HUNTER_CREATOR_RULESET_CHECKSUM=target.checksum):
            preview = self.client.get(url)
            comparison = preview.context['comparison']
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
        self.assertEqual(profile.ruleset_id, target.pk)
        person.refresh_from_db()
        self.assertEqual((person.carteira_pc, person.aventuras, person.braseiros), (321, 8, 4))
        self.assertEqual(self.client.get(reverse('hunter_sheet', args=[person.pk])).status_code, 200)
