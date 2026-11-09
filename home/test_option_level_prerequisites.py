"""Option level prerequisites use the named class, not the multiclass total."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from . import picks
from .content_versions import seal_ruleset
from .models import TbClasse, TbClassehabilidade, TbOpcaojogo, TbPersonagem, TbPersonagemClasse
from .versioned_classes import EVALUATOR, VOCABULARY
from .versioned_options import snapshot_options


class OptionLevelPrerequisiteTests(TestCase):
    def setUp(self):
        self.fighter = TbClasse.objects.create(nome='Guerreiro', slug='guerreiro')
        self.hunter = TbClasse.objects.create(nome='Caçador', slug='cacador')
        self.person = TbPersonagem.objects.create(dono=get_user_model().objects.create_user('options-level'),
                                                  nome='Multiclass', nivel=19)
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=self.fighter, nivel=3, principal=False)
        TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=self.hunter, nivel=16, principal=True)
        for level in (0, 5, 9, 13):
            TbOpcaojogo.objects.create(nome='Choice %s' % level, slug='choice-%s' % level,
                tipo='Test options', pre_requisito='%sº nível de Guerreiro' % level if level else '')
        self.ruleset = seal_ruleset([snapshot_options()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)

    def add_choice_feature(self):
        TbClassehabilidade.objects.create(id_classe=self.fighter, nome='Choices',
            niveladquirido=1, tags_json=['pick:opcao:test_options:2'])

    def context(self, level=3, **kwargs):
        return dict(tipo='test_options', classe=self.fighter, nivel=level,
                    personagem=self.person, **kwargs)

    def test_multiclass_total_does_not_unlock_class_level_options(self):
        for ruleset in (None, self.ruleset):
            with self.subTest(ruleset=ruleset):
                rows = picks._opcao_universe(self.context(ruleset=ruleset))
                self.assertEqual([r['slug'] for r in rows], ['choice-0'])
        for level, expected in ((5, {'choice-0', 'choice-5'}),
                                (9, {'choice-0', 'choice-5', 'choice-9'})):
            self.pc.nivel = level
            self.pc.save(update_fields=['nivel'])
            self.assertEqual({r['slug'] for r in picks._opcao_universe(self.context(level))}, expected)

    def test_builder_and_explicit_list_do_not_bypass_the_requirement(self):
        ctx = self.context(constraints={'listed_slugs': ['choice-13']})
        self.assertEqual(picks._opcao_universe(ctx), [])
        self.assertEqual(picks._opcao_universe(dict(ctx, ruleset=self.ruleset)), [])
        ctx = self.context()
        ctx['personagem'] = None
        self.assertEqual([r['slug'] for r in picks._opcao_universe(ctx)], ['choice-0'])

    def test_validator_rejects_locked_identity_and_frozen_text_survives_live_edit(self):
        rows = picks._opcao_universe(self.context(ruleset=self.ruleset))
        group = {'n': 1, 'universo': rows}
        self.assertTrue(picks.registry_entry('opcao')['validate'](group, ['choice-13']))
        self.assertFalse(picks.registry_entry('opcao')['validate'](group, ['choice-0']))
        TbOpcaojogo.objects.filter(slug='choice-13').update(pre_requisito='')
        self.assertNotIn('choice-13', {r['slug'] for r in picks._opcao_universe(
            self.context(ruleset=self.ruleset))})
        self.assertIn('choice-13', {r['slug'] for r in picks._opcao_universe(self.context())})

    def test_actual_progression_rejects_locked_pick_and_reopens_valid_choices(self):
        from .views import _lvl_aplicar_opcao
        self.add_choice_feature()
        group = picks.resolve_personagem(self.person)[0]
        payload = {'slug': group['persist_tipo'], 'classe': self.fighter.pk, 'val': 'choice-13'}
        self.assertTrue(_lvl_aplicar_opcao(self.person, payload))
        self.assertFalse(self.person.escolhas.exists())
        payload['val'] = 'choice-0'
        self.assertEqual(_lvl_aplicar_opcao(self.person, payload), [])
        self.pc.nivel = 5
        self.pc.save(update_fields=['nivel'])
        payload['val'] = 'choice-5'
        self.assertEqual(_lvl_aplicar_opcao(self.person, payload), [])
        reopened = picks.resolve_personagem(self.person)[0]
        self.assertEqual(reopened['pendentes'], 0)
        self.assertEqual({r['valor'] for r in reopened['escolhidas']}, {'choice-0', 'choice-5'})
        self.assertTrue(_lvl_aplicar_opcao(self.person, payload))
        self.assertEqual(self.person.escolhas.count(), 2)

    def test_laboratory_uses_the_same_restricted_group(self):
        from .pathbuilder import PathbuilderError, _apply_choices, _groups_with_keys
        self.add_choice_feature()
        group = _groups_with_keys(self.person)[0]
        with self.assertRaises(PathbuilderError):
            _apply_choices(self.person, {'escolhas': {group['pathbuilder_key']: ['choice-13']}})
        self.assertFalse(self.person.escolhas.exists())

    def test_class_name_is_data_not_a_specific_fighter_branch(self):
        self.fighter.nome = 'Classe Customizada'
        self.fighter.slug = 'classe-customizada'
        self.fighter.save(update_fields=['nome', 'slug'])
        TbOpcaojogo.objects.filter(slug='choice-5').update(pre_requisito='5º nível de Classe Customizada')
        self.assertNotIn('choice-5', {r['slug'] for r in picks._opcao_universe(self.context())})
        self.pc.nivel = 5
        self.pc.save(update_fields=['nivel'])
        self.assertIn('choice-5', {r['slug'] for r in picks._opcao_universe(self.context(5))})
