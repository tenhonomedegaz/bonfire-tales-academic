from types import SimpleNamespace as NS
from unittest.mock import patch
from django.test import TestCase
from home.models import TbRaca, TbLinhagem, TbEssencia, TbTracoracial
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_origins import snapshot_origins, VersionedOrigins
from home.character_engine import _tracos_raciais


class VersionedRacialTests(TestCase):
    def setUp(self):
        self.race = TbRaca.objects.create(nome='Old race', slug='frozen-race')
        self.line = TbLinhagem.objects.create(id_raca=self.race, nome='Old lineage', slug='frozen-line')
        self.ess = TbEssencia.objects.create(nome='Old essence', slug='frozen-essence')
        for name, extra in [('Base', {'id_raca': self.race}),
                            ('Lineage', {'id_raca': self.race, 'id_linhagem': self.line}),
                            ('Shared', {'id_essencia': self.ess}),
                            ('Red', {'id_essencia': self.ess, 'pre_requisito': 'Cla Rubedo'}),
                            ('Dark', {'id_essencia': self.ess, 'pre_requisito': 'Cla Tenebrus'}),
                            ('Optional', {'id_raca': self.race, 'talento_racial': True})]:
            TbTracoracial.objects.create(nome=name, descricao='', tags_json=['ca:+1'], **extra)
        self.ruleset = seal_ruleset([snapshot_origins()], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.person = NS(id_raca_id=self.race.pk, id_raca=self.race,
                         id_linhagem_id=self.line.pk, id_linhagem=self.line,
                         id_essencia_id=self.ess.pk, id_essencia=self.ess)

    def values(self, ruleset=None):
        return [(kind, name, obj.nome, obj.tags_json) for kind, name, obj, _
                in _tracos_raciais(self.person, ruleset=ruleset)]

    @patch('home.character_engine.cla_escolhido', return_value='rubedo')
    def test_equivalence_and_frozen_clan_filter_after_catalog_edits(self, _chosen):
        before = self.values()
        self.assertEqual([v[2] for v in before], ['Base', 'Lineage', 'Shared', 'Red'])
        self.assertEqual(self.values(self.ruleset), before)
        TbTracoracial.objects.update(tags_json=['ca:+9'], pre_requisito='')
        self.race.nome = 'Changed race'
        self.race.save()
        self.assertNotEqual(self.values(), before)
        self.assertEqual(self.values(self.ruleset), before)
        TbTracoracial.objects.all().delete()
        self.assertEqual(self.values(self.ruleset), before)

    @patch('home.character_engine.cla_escolhido', return_value='tenebrus')
    def test_current_clan_choice_and_missing_identity(self, _chosen):
        self.assertEqual([v[2] for v in self.values(self.ruleset)], ['Base', 'Lineage', 'Shared', 'Dark'])
        self.person.id_linhagem_id = 999999
        with self.assertRaisesMessage(ValueError, 'Racial identity absent'):
            self.values(self.ruleset)

    @patch('home.character_engine.cla_escolhido', return_value='')
    def test_unselected_clan_gets_only_shared_traits_without_catalog_queries(self, _chosen):
        catalog = VersionedOrigins(self.ruleset)
        with self.assertNumQueries(0):
            self.assertEqual([v[2].nome for v in catalog.racial(self.person)], ['Base', 'Lineage', 'Shared'])

    def test_legacy_revision_keeps_existing_readers_but_refuses_new_racial_reader(self):
        from home.versioned_origins import IDENTITY, MODELS
        from home.versioned_classes import _fields
        payload = {'schema': 1, 'collections': {m._meta.label_lower:
                   [_fields(o) for o in m.objects.order_by('pk')] for m in MODELS}}
        ruleset = seal_ruleset([create_revision(IDENTITY, payload)],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        catalog = VersionedOrigins(ruleset)
        self.assertEqual(catalog.background(NS(id_antecedente_id=None)), [])
        with self.assertRaisesMessage(ValueError, 'lacks racial identities'):
            catalog.racial(self.person)
