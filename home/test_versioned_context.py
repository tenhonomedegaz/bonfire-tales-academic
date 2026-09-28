from types import SimpleNamespace as NS
from django.test import TestCase
from home.models import TbClasse, TbClassehabilidade, TbOpcaojogo, TbTalento
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items
from home.character_engine import _features_do_personagem, grants_fixos


class Rows:
    def __init__(self, rows): self.rows = rows
    def select_related(self, *args): return self
    def order_by(self, *args): return self.rows
    def all(self): return self.rows


class VersionedContextTests(TestCase):
    def setUp(self):
        self.classe = TbClasse.objects.create(nome='Source class', slug='context-class')
        self.feature = TbClassehabilidade.objects.create(id_classe=self.classe,
            nome='Gift source', niveladquirido=2, descricao='', tags_json=[
            'grant:opcao:style:context-style', 'grant:opcao:style:context-style',
            'grant:talento{context-talent, without{asi}}'])
        self.option = TbOpcaojogo.objects.create(nome='Old style', slug='context-style', tipo='Style', tags_json=['ca:+1'])
        self.talent = TbTalento.objects.create(nome='Old talent', slug='context-talent', descricao='', tags_json=['ca:+2'])
        self.pc = NS(id_classe_id=self.classe.pk, id_classe=self.classe,
                     id_subclasse_id=None, id_subclasse=None, nivel=2)
        self.person = NS(classes=Rows([self.pc]), nivel=2, id_raca_id=None,
            id_antecedente_id=None, talentos=Rows([]), inventario=Rows([]),
            escolhas=Rows([NS(id_opcao_id=self.option.pk, valor=self.option.slug)]))
        self.ruleset = self.seal()

    def seal(self):
        revision = create_revision('class-catalog:%s' % self.classe.pk, inventory_class(self.classe.pk))
        return seal_ruleset([revision, snapshot_options(), snapshot_origins(), snapshot_magic_items()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)

    def test_composed_context_and_grants_survive_catalog_mutation(self):
        before = grants_fixos(self.person, ruleset=self.ruleset)
        self.assertEqual(len(before['opcoes']), 1)
        self.assertEqual(before['opcoes'][0]['nome'], 'Old style')
        self.assertTrue(before['talentos'][0]['no_asi'])
        features = _features_do_personagem(self.person, ruleset=self.ruleset)
        self.assertEqual([kind for kind, _, _, _ in features], ['classe', 'opcao'])
        self.feature.tags_json = []
        self.feature.save()
        self.option.nome = 'New style'
        self.option.tags_json = ['ca:+9']
        self.option.save()
        self.talent.nome = 'New talent'
        self.talent.save()
        self.assertEqual(grants_fixos(self.person, ruleset=self.ruleset), before)
        self.assertEqual(_features_do_personagem(self.person, ruleset=self.ruleset)[-1][2].tags_json, ['ca:+1'])
        self.assertEqual(grants_fixos(self.person, ruleset=self.seal()), {'opcoes': [], 'talentos': []})

    def test_current_level_controls_frozen_source_availability(self):
        self.pc.nivel = 1
        self.assertEqual(grants_fixos(self.person, ruleset=self.ruleset), {'opcoes': [], 'talentos': []})
        self.pc.nivel = 2
        self.assertEqual(len(grants_fixos(self.person, ruleset=self.ruleset)['opcoes']), 1)

    def test_missing_grant_target_fails_closed(self):
        self.feature.tags_json = ['grant:opcao:style:missing-target']
        self.feature.save()
        ruleset = self.seal()
        with self.assertRaisesMessage(ValueError, 'Granted option absent'):
            grants_fixos(self.person, ruleset=ruleset)
        self.feature.tags_json = ['grant:talento{missing-talent}']
        self.feature.save()
        ruleset = self.seal()
        with self.assertRaisesMessage(ValueError, 'Granted talent absent'):
            grants_fixos(self.person, ruleset=ruleset)

    def test_formula_context_preserves_spell_ability_and_reads_live_scores(self):
        from home.character_engine import _resource_formula_context, ATRIBUTOS
        self.feature.tags_json = ['spellcasting{ability:wis, list:context-class}', 'attr_max:focus=spell_mod+2']
        self.feature.save()
        self.ruleset = self.seal()
        class Choices(list):
            def all(inner): return inner
            def order_by(inner, *args): return inner
        self.person.escolhas = Choices()
        self.person.atributo_bonus = Rows([])
        for field, _, _ in ATRIBUTOS:
            setattr(self.person, field, 10)
        self.person.sabedoria = 16
        before, features = _resource_formula_context(self.person, [self.pc], ruleset=self.ruleset)
        self.assertEqual(before['spell_mod'], 3)
        from home.character_engine import _resource_max_overrides
        self.assertEqual(_resource_max_overrides(features, before)['focus'], 5)
        self.feature.tags_json = ['spellcasting{ability:int, list:context-class}']
        self.feature.save()
        from home.character_engine import _spell_mod
        self.assertEqual(_spell_mod([self.pc], {'INT': {'mod': 0}, 'SAB': {'mod': 3}}), 0)
        self.assertEqual(_resource_formula_context(self.person, [self.pc], ruleset=self.ruleset)[0], before)
        self.person.sabedoria = 18
        self.assertEqual(_resource_formula_context(self.person, [self.pc], ruleset=self.ruleset)[0]['spell_mod'], 4)
        self.pc.nivel = 1
        self.assertEqual(_resource_formula_context(self.person, [self.pc], ruleset=self.ruleset)[0]['spell_mod'], 0)
