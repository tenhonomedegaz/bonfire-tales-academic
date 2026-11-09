"""Regressions for the common creator and secondary-class level-five boundary."""
from django.test import override_settings
from django.urls import reverse
from unittest.mock import patch

from . import views
from .content_versions import create_revision, seal_ruleset
from .hunter_catalog import compose_order_revision
from .hunter_rework import catalog
from .models import (TbClasse, TbPersonagem,
                     TbPersonagemCacador, TbPersonagemClasse, TbSubclasse)
from .test_criador import _CriadorBase
from . import test_hunter_catalog as hunter_fixtures
from .versioned_classes import EVALUATOR, VOCABULARY, inventory_class


class HunterBugfixTests(_CriadorBase):
    setup_catalog = hunter_fixtures.HunterCatalogTests.setup_catalog

    def setUp(self):
        self.setup_catalog()
        orders = {}
        for order in catalog()['orders']:
            row = TbSubclasse.objects.create(
                id_classe=self.classe, nome=order['name'], slug=order['id'] + '-rework')
            orders[order['id']] = row.pk
        revised = compose_order_revision(self.new, class_id=self.classe.pk, order_ids=orders)
        self.fighter = TbClasse.objects.get(slug='guerreiro')
        self.ruleset = seal_ruleset(
            [row.revision for row in revised.entries.select_related('revision')] + [
                create_revision('class-catalog:%s' % self.fighter.pk, inventory_class(self.fighter.pk)),
            ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.orders = orders
        self.user = self._novo_usuario('hunter-bugfix')
        self.client.force_login(self.user)

    def test_configured_hunter_is_in_common_creator_with_frozen_features(self):
        with override_settings(CLASS_CATALOG_RULESETS={'cacador': self.ruleset.checksum}):
            page = self.client.get(reverse('criacao_ficha'))
            self.assertEqual(page.status_code, 200)
            row = next(c for c in page.context['catalogos']['classes'] if c['slug'] == 'cacador')
            self.assertTrue(row['hunter_rework'])

    def test_secondary_hunter_four_to_five_and_reopen(self):
        self._check_level_five(primary=False, revised=True)

    def test_primary_hunter_four_to_five_and_reopen(self):
        self._check_level_five(primary=True, revised=True)

    def test_legacy_secondary_hunter_four_to_five_and_reopen(self):
        self._check_level_five(primary=False, revised=False)

    def test_advancing_other_class_keeps_secondary_hunter_ruleset(self):
        person = TbPersonagem.objects.create(
            dono=self.user, nome='Secondary revision context', nivel=6, aventuras=130,
            forca=15, destreza=15, constituicao=14, inteligencia=15, sabedoria=15)
        fighter = TbPersonagemClasse.objects.create(
            id_personagem=person, id_classe=self.fighter, nivel=2, principal=True)
        hunter = TbPersonagemClasse.objects.create(
            id_personagem=person, id_classe=self.classe, nivel=4,
            id_subclasse_id=self.orders['ordem-dos-mutantes'], ruleset=self.ruleset)
        TbPersonagemCacador.objects.create(
            personagem_classe=hunter, ruleset=self.ruleset, ability='int')
        body = {'acoes': [{'tipo': 'subir_nivel', 'payload': {'classe': self.fighter.pk}}]}
        for endpoint in ('personagem_levelup_preview', 'personagem_levelup_aplicar'):
            with patch('home.views._sync_magias_concedidas', wraps=views._sync_magias_concedidas) as sync:
                response = self.client.post(reverse(endpoint, args=[person.pk]), body,
                                            content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content[:1000])
            self.assertEqual(sync.call_args.kwargs['ruleset'], self.ruleset)
        fighter.refresh_from_db()
        hunter.refresh_from_db()
        self.assertEqual((fighter.nivel, hunter.nivel), (3, 4))
        self.assertEqual(hunter.ruleset_id, self.ruleset.pk)

    def _check_level_five(self, *, primary, revised):
        person = TbPersonagem.objects.create(
            dono=self.user, nome='Hunter boundary', nivel=6, aventuras=130,
            forca=15, destreza=15, constituicao=14,
            inteligencia=15, sabedoria=15, carisma=10)
        fighter = TbPersonagemClasse.objects.create(
            id_personagem=person, id_classe=self.fighter, nivel=2, principal=not primary)
        if revised:
            subclass_id = self.orders['ordem-dos-mutantes']
        else:
            subclass_id = TbSubclasse.objects.filter(
                id_classe=self.classe, nome__icontains='mutante').exclude(
                    slug__endswith='-rework').get().pk
        hunter = TbPersonagemClasse.objects.create(
            id_personagem=person, id_classe=self.classe, nivel=4,
            principal=primary, id_subclasse_id=subclass_id)
        if revised:
            hunter.ruleset = self.ruleset
            hunter.save(update_fields=['ruleset'])
            TbPersonagemCacador.objects.create(
                personagem_classe=hunter, ruleset=self.ruleset, ability='int')
        body = {'acoes': [{'tipo': 'subir_nivel', 'payload': {'classe': self.classe.pk}}]}
        preview = self.client.post(reverse('personagem_levelup_preview', args=[person.pk]),
                                   body, content_type='application/json')
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json()['ready'], preview.content)
        hunter.refresh_from_db()
        self.assertEqual(hunter.nivel, 4)
        applied = self.client.post(reverse('personagem_levelup_aplicar', args=[person.pk]),
                                   body, content_type='application/json')
        self.assertEqual(applied.status_code, 200, applied.content[:1000])
        hunter.refresh_from_db()
        fighter.refresh_from_db()
        self.assertEqual((hunter.nivel, fighter.nivel), (5, 2))
        sheet = self.client.get(reverse('ficha_detail', args=[person.pk]))
        self.assertEqual(sheet.status_code, 200, sheet.content[:1000])
