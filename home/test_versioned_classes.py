from types import SimpleNamespace

from django.test import TestCase

from home.character_engine import _features_de_classe
from home.content_versions import create_revision, seal_ruleset
from home.models import TbClasse, TbClassehabilidade, TbSubclasse
from home.versioned_classes import (
    EVALUATOR, VOCABULARY, VersionedClassCatalog, inventory_class, seal_class_snapshot,
)


class VersionedClassTests(TestCase):
    def setUp(self):
        self.classe = TbClasse.objects.create(nome='Old Hunter', slug='version-hunter',
                                             tags_json=['subclass-choices{3}'])
        self.sub = TbSubclasse.objects.create(id_classe=self.classe, nome='Old Order', slug='old-order')
        self.feature = TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Fighting style', niveladquirido=2, descricao='Old effect', tags_json=['ca:+1'])
        self.order_feature = TbClassehabilidade.objects.create(id_classe=self.classe,
            id_subclasse=self.sub, nome='Order effect', niveladquirido=3, descricao='', tags_json=['ca:+2'])
        self.pc = SimpleNamespace(id_classe=self.classe, id_classe_id=self.classe.pk,
                                  id_subclasse=self.sub, id_subclasse_id=self.sub.pk, nivel=3)
        self.ruleset = seal_class_snapshot(self.classe.pk)

    def values(self, ruleset=None):
        return [(kind, name, h.nome, h.tags_json, level)
                for kind, name, h, level in _features_de_classe([self.pc], ruleset=ruleset)]

    def test_engine_sources_preserve_names_levels_and_effects_after_catalog_edit(self):
        old = self.values()
        self.assertEqual(self.values(self.ruleset), old)
        self.feature.tags_json = ['ca:+9']
        self.feature.save()
        self.classe.nome = 'New Hunter'
        self.classe.save()
        self.sub.nome = 'New Order'
        self.sub.save()
        self.assertNotEqual(self.values(), old)
        self.assertEqual(self.values(self.ruleset), old)
        new_ruleset = seal_class_snapshot(self.classe.pk)
        self.assertNotEqual(self.values(new_ruleset), old)

    def test_added_and_deleted_features_do_not_change_old_collection(self):
        old = self.values(self.ruleset)
        self.feature.delete()
        TbClassehabilidade.objects.create(id_classe=self.classe, nome='New feature',
                                         niveladquirido=1, descricao='')
        self.assertEqual(self.values(self.ruleset), old)
        self.assertNotEqual(self.values(), old)

    def test_level_gating_and_parent_reads_use_only_frozen_content(self):
        catalog = VersionedClassCatalog(self.ruleset, self.classe.pk)
        self.classe.tags_json = ['subclass-choices{1}']
        self.classe.save()
        with self.assertNumQueries(0):
            self.assertEqual(catalog.features(1, self.sub.pk), [])
            self.assertEqual(len(catalog.features(2, self.sub.pk)), 1)
            sources = catalog.features(3, self.sub.pk)
            self.assertEqual(len(sources), 2)
            self.assertEqual(sources[1][2].id_subclasse.nome, 'Old Order')
            self.assertEqual(sources[0][2].id_classe.nome, 'Old Hunter')
        with self.assertRaises(ValueError):
            catalog.features(20, self.sub.pk + 1000)

    def test_empty_collection_remains_empty_and_inventory_does_not_write(self):
        self.feature.delete()
        self.order_feature.delete()
        before = TbClassehabilidade.objects.count()
        payload = inventory_class(self.classe.pk)
        self.assertEqual(TbClassehabilidade.objects.count(), before)
        revision = create_revision('class-catalog:%s' % self.classe.pk, payload)
        frozen = seal_ruleset([revision], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        TbClassehabilidade.objects.create(id_classe=self.classe, nome='Later', niveladquirido=1, descricao='')
        self.assertEqual(self.values(frozen), [])

    def test_incomplete_ruleset_never_falls_back_to_current_class(self):
        from home.models import TbRulesetContent
        revision = create_revision('unrelated', {})
        incomplete = seal_ruleset([revision], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        with self.assertRaises(TbRulesetContent.DoesNotExist):
            self.values(incomplete)

    def test_feature_evaluation_order_matches_legacy_class_then_subclass(self):
        TbClassehabilidade.objects.create(id_classe=self.classe, nome='Late class feature',
                                         niveladquirido=10, descricao='')
        self.pc.nivel = 20
        frozen = seal_class_snapshot(self.classe.pk)
        self.assertEqual(self.values(frozen), self.values())


class VersionedResourceTests(VersionedClassTests):
    def setUp(self):
        super().setUp()
        from home.models import TbRecursoclasse
        self.resource = TbRecursoclasse.objects.create(id_classe=self.classe,
            nome='Secrets', slug='secrets', tipo='choice', valores_json={'1': '2', '5': '4'})
        self.pool = TbRecursoclasse.objects.create(id_classe=self.classe,
            id_subclasse=self.sub, nome='Order points', slug='order-points',
            tipo='consumable', reset='long-rest', valores_json={'1': '3', '5': '6'})
        self.ruleset = seal_class_snapshot(self.classe.pk)
        self.person = SimpleNamespace(recursos=SimpleNamespace(all=lambda: [
            SimpleNamespace(nome='Order points', chave='', atual=1)]))

    def outputs(self, ruleset=None):
        from home.character_engine import _recursos, _recursos_por_tipo, _recursos_consumiveis
        from home.picks import resource_limit, count_for
        return (
            _recursos([self.pc], ruleset=ruleset),
            _recursos_por_tipo([self.pc], ruleset=ruleset),
            _recursos_consumiveis(self.person, [self.pc], {}, {}, ruleset=ruleset),
            resource_limit(self.classe, self.pc.nivel, 'secrets', ruleset=ruleset),
            count_for('N', self.pc.nivel, self.classe, 'secrets', ruleset=ruleset),
        )

    def test_resources_and_choice_limits_preserve_old_results_and_current_usage(self):
        before = self.outputs()
        self.assertEqual(self.outputs(self.ruleset), before)
        self.assertEqual(before[2][0]['atual'], 1)
        self.assertEqual(before[3:], (2, 2))
        self.resource.valores_json = {'1': '9'}
        self.resource.save()
        self.pool.reset = 'short-rest'
        self.pool.valores_json = {'1': '12'}
        self.pool.save()
        self.classe.nome = 'New class'
        self.classe.save()
        self.sub.nome = 'New order'
        self.sub.save()
        self.assertNotEqual(self.outputs(), before)
        self.assertEqual(self.outputs(self.ruleset), before)
        self.assertNotEqual(self.outputs(seal_class_snapshot(self.classe.pk)), before)

    def test_resource_unlock_and_progression_are_frozen(self):
        self.classe.tags_json = ['subclass-choices{1}']
        self.classe.save()
        self.pc.nivel = 2
        self.assertEqual(self.outputs(self.ruleset)[2], [])
        self.pc.nivel = 5
        result = self.outputs(self.ruleset)
        self.assertEqual(result[2][0]['maximo'], 6)
        self.assertEqual(result[3:], (4, 4))
        catalog = VersionedClassCatalog(self.ruleset, self.classe.pk)
        with self.assertNumQueries(0):
            self.assertEqual(len(catalog.resources(5, self.sub.pk)), 2)
        with self.assertRaises(ValueError):
            catalog.resources(5, self.sub.pk + 999)

    def test_deletion_does_not_remove_frozen_resources(self):
        before = self.outputs(self.ruleset)
        self.pool.delete()
        self.resource.delete()
        self.assertEqual(self.outputs(self.ruleset), before)
        self.assertEqual(self.outputs()[2], [])

    def test_versioned_consumables_refuse_implicit_mutable_formula_context(self):
        from home.character_engine import _recursos_consumiveis
        with self.assertRaisesMessage(ValueError, 'explicit resolved formula context'):
            _recursos_consumiveis(self.person, [self.pc], ruleset=self.ruleset)

    def test_missing_class_revision_refuses_all_resource_consumers(self):
        from home.models import TbRulesetContent
        revision = create_revision('unrelated-resource', {})
        incomplete = seal_ruleset([revision], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        with self.assertRaises(TbRulesetContent.DoesNotExist):
            self.outputs(incomplete)


class VersionedNumericClassesTests(TestCase):
    def test_copied_class_preserves_hit_points_saves_and_proficiencies(self):
        from home.versioned_classes import resolved_classes
        from home.character_engine import _calcular_pv, _saves, _proficiencias_classe, ATRIBUTOS
        cl = TbClasse.objects.create(nome='Numeric class', slug='numeric-class', dado_vida='d8',
            tags_json=['saves_prof{str,con}', 'prof{armas_simples}'])
        row = SimpleNamespace(id_classe=cl, id_classe_id=cl.pk, id_subclasse=None,
            id_subclasse_id=None, nivel=2, principal=True)
        ruleset = seal_class_snapshot(cl.pk)
        attrs = {sig: {'mod': 1} for _, sig, _ in ATRIBUTOS}
        def read(rows):
            return (_calcular_pv(None, rows, 1, []), _saves(rows, attrs, 2), _proficiencias_classe(rows))
        before = read([row])
        self.assertEqual(before[0]['valor'], 15)
        self.assertTrue(before[1]['FOR']['proficiente'])
        self.assertEqual(before[2]['classe_armas'], ['Armas Simples'])
        self.assertEqual(read(resolved_classes(ruleset, [row])), before)
        cl.dado_vida = 'd12'
        cl.tags_json = ['saves_prof{int,wis}']
        cl.save()
        self.assertNotEqual(read([row]), before)
        frozen = resolved_classes(ruleset, [row])
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(read(frozen), before)
        self.assertFalse(any('TB_Classe' in q['sql'] for q in queries))
        self.assertIs(row.id_classe, cl)
        row.nivel = 3
        self.assertEqual(read(resolved_classes(ruleset, [row]))[0]['valor'], 21)
        row.id_subclasse_id = 999999
        with self.assertRaisesMessage(ValueError, 'Subclass is not part'):
            resolved_classes(ruleset, [row])
