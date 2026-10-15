from django.test import TestCase
from home.models import TbClasse, TbSubclasse, TbOpcaojogo, TbAcessoopcao, TbRulesetContent
from home.content_versions import seal_ruleset, create_revision
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options, VersionedOptions
from home.picks import _opcao_universe


class VersionedOptionsTests(TestCase):
    def setUp(self):
        self.classe = TbClasse.objects.create(nome='Hunter', slug='hunter-options')
        self.other = TbClasse.objects.create(nome='Other', slug='other-options')
        self.sub = TbSubclasse.objects.create(id_classe=self.classe, nome='Order', slug='order-options')
        self.option = TbOpcaojogo.objects.create(nome='Style', slug='style-options', tipo='Style', tags_json=['ca:+1'])
        self.global_option = TbOpcaojogo.objects.create(nome='Maneuver', slug='global-options', tipo='Maneuver')
        self.access = TbAcessoopcao.objects.create(id_opcao=self.option, id_subclasse=self.sub, nivel_recebimento=3)
        self.ruleset = self.seal()

    def seal(self):
        return seal_ruleset([snapshot_options()], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)

    def ctx(self, tipo='style', **kw):
        return dict(tipo=tipo, classe=self.classe, subclasse=self.sub, nivel=3, **kw)

    def test_equivalence_and_level_gates(self):
        for tipo in ('style', 'maneuver', 'missing'):
            for level in (1, 3, 20):
                ctx = self.ctx(tipo)
                ctx['nivel'] = level
                self.assertEqual(_opcao_universe(ctx), _opcao_universe(dict(ctx, ruleset=self.ruleset)))

    def test_mutable_edits_and_deletion_leave_old_universe_unchanged(self):
        ctx = self.ctx(ruleset=self.ruleset)
        before = _opcao_universe(ctx)
        self.option.nome = 'Changed'
        self.option.save()
        self.access.nivel_recebimento = 20
        self.access.save()
        self.assertEqual(_opcao_universe(ctx), before)
        self.assertEqual(_opcao_universe(self.ctx()), [])
        self.access.delete()
        self.option.delete()
        self.assertEqual(_opcao_universe(ctx), before)

    def test_global_acl_presence_is_frozen_per_type(self):
        ctx = self.ctx('maneuver', ruleset=self.ruleset)
        before = _opcao_universe(ctx)
        TbAcessoopcao.objects.create(id_opcao=self.global_option, id_classe=self.other)
        self.assertEqual(_opcao_universe(ctx), before)
        self.assertEqual(_opcao_universe(self.ctx('maneuver')), [])
        self.assertEqual(_opcao_universe(self.ctx('maneuver', ruleset=self.seal())), [])

    def test_explicit_origin_uses_frozen_slugs_and_never_opens_unknown_source(self):
        constraints = {'from_kind': 'subclasse', 'from_slug': self.sub.slug}
        before = _opcao_universe(self.ctx(constraints=constraints))
        self.sub.slug = 'renamed-order'
        self.sub.save()
        self.assertEqual(_opcao_universe(self.ctx(constraints=constraints, ruleset=self.ruleset)), before)
        self.assertEqual(_opcao_universe(self.ctx(constraints=constraints)), [])
        missing = {'from_kind': 'classe', 'from_slug': 'unknown'}
        self.assertEqual(_opcao_universe(self.ctx('maneuver', constraints=missing, ruleset=self.ruleset)), [])

    def test_page_list_limits_options_in_live_and_frozen_catalog(self):
        listed_option = TbOpcaojogo.objects.create(
            nome='Listed Style', slug='listed-style', tipo='Style')
        ruleset = self.seal()
        ctx = self.ctx(constraints={'listed_slugs': ['listed-style']})
        self.assertEqual([o['slug'] for o in _opcao_universe(ctx)], ['listed-style'])
        frozen = dict(ctx, ruleset=ruleset)
        self.assertEqual(_opcao_universe(frozen), _opcao_universe(ctx))
        listed_option.delete()
        self.assertEqual(_opcao_universe(ctx), [])
        self.assertEqual([o['slug'] for o in _opcao_universe(frozen)], ['listed-style'])

    def test_pinned_class_feature_resolves_its_listed_style(self):
        from home.picks import resolve_versioned_class_options
        from home.versioned_classes import inventory_class

        TbOpcaojogo.objects.create(nome='Listed Style', slug='listed-style', tipo='Style')
        self.classe.tags_json = ['pick:opcao:style:1(de:[listed-style],swap:level_up)']
        self.classe.save(update_fields=['tags_json'])
        revision = create_revision('class-catalog:%s' % self.classe.pk,
                                   inventory_class(self.classe.pk))
        ruleset = seal_ruleset([revision, snapshot_options()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        groups = resolve_versioned_class_options(
            ruleset, self.classe.pk, nivel=3, subclass_id=self.sub.pk)
        self.assertEqual(len(groups), 1)
        self.assertEqual([o['slug'] for o in groups[0]['universo']], ['listed-style'])
        self.assertEqual(groups[0]['swap'], 'level_up')

    def test_frozen_reads_issue_no_catalog_queries(self):
        catalog = VersionedOptions(self.ruleset)
        with self.assertNumQueries(0):
            self.assertEqual(len(catalog.universe(self.ctx())), 1)
            self.assertEqual(len(catalog.universe(self.ctx('maneuver'))), 1)

    def test_missing_revision_fails_closed(self):
        incomplete = seal_ruleset([create_revision('unrelated-options', {})],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        with self.assertRaises(TbRulesetContent.DoesNotExist):
            _opcao_universe(self.ctx(ruleset=incomplete))

    def test_class_option_groups_preserve_tags_counts_labels_and_selection(self):
        from home.models import TbRecursoclasse
        from home.versioned_classes import inventory_class
        from home.picks import resolve_versioned_class_options
        self.classe.tags_json = ['pick:opcao:style:1']
        self.classe.save()
        revision = create_revision('class-catalog:%s' % self.classe.pk, inventory_class(self.classe.pk))
        ruleset = seal_ruleset([revision, snapshot_options()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        selected = {'style': [{'valor': self.option.slug, 'slot': 0}]}
        before = resolve_versioned_class_options(ruleset, self.classe.pk,
            nivel=3, subclass_id=self.sub.pk, escolhas_map=selected)
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0]['n'], 1)
        self.assertEqual(before[0]['pendentes'], 0)
        self.classe.tags_json = []
        self.classe.save()
        self.option.tipo = 'Renamed'
        self.option.save()
        after = resolve_versioned_class_options(ruleset, self.classe.pk,
            nivel=3, subclass_id=self.sub.pk, escolhas_map=selected)
        self.assertEqual(after, before)

    def test_selected_effects_preserve_linked_identity_and_legacy_slug(self):
        from types import SimpleNamespace
        from home.character_engine import _features_de_opcoes
        # A poisoned FK property proves the versioned reader uses the ID only.
        class Choice:
            def __init__(self, pk, value):
                self.id_opcao_id, self.valor = pk, value
            @property
            def id_opcao(self):
                raise AssertionError('Mutable option FK was read')
        choices = [Choice(self.option.pk, 'obsolete-slug'),
                   Choice(None, self.option.slug), Choice(None, 'non-option-menu')]
        person = SimpleNamespace(escolhas=SimpleNamespace(all=lambda: choices))
        def effects():
            return [(kind, name, obj.slug, obj.tags_json, level)
                    for kind, name, obj, level in _features_de_opcoes(person, ruleset=self.ruleset)]
        before = effects()
        self.assertEqual(len(before), 2)
        self.assertEqual(before[0][3], ['ca:+1'])
        self.option.tags_json = ['ca:+9']
        self.option.nome = 'Changed style'
        self.option.save()
        self.assertEqual(effects(), before)
        self.access.delete()
        self.option.delete()
        self.assertEqual(effects(), before)

    def test_missing_linked_option_refuses_slug_substitution(self):
        from types import SimpleNamespace
        catalog = VersionedOptions(self.ruleset)
        with self.assertRaisesMessage(ValueError, 'absent from the pinned ruleset'):
            catalog.selected_features([SimpleNamespace(id_opcao_id=999999999, valor=self.option.slug)])

    def test_selected_effects_are_isolated_between_reads(self):
        from types import SimpleNamespace
        catalog = VersionedOptions(self.ruleset)
        choice = SimpleNamespace(id_opcao_id=self.option.pk, valor='')
        first = catalog.selected_features([choice])
        first[0][2].tags_json.append('ca:+99')
        self.assertEqual(catalog.selected_features([choice])[0][2].tags_json, ['ca:+1'])

    def test_frozen_option_effect_reaches_numeric_character_calculation(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from home.character_engine import apply_tags
        choice = SimpleNamespace(id_opcao_id=self.option.pk, valor='')
        self.option.tags_json = ['ca:+9']
        self.option.save()
        features = VersionedOptions(self.ruleset).selected_features([choice])
        state = {'_ctx': {'lvl': 3, 'classlvl': 3, 'pb': 2, 'dex_mod': 0},
                 'pv': {'maximo_calculado': 20}, 'ca': 10,
                 'velocidade': '9 m / 30 ft', 'recursos': {}}
        with patch('home.character_engine._cond_nomes', return_value={}):
            result = apply_tags(state, features, escolhas={})
        self.assertEqual(result['ca'], 11)
