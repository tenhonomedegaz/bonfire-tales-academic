"""Q13: identity and content-defined racial milestones, shared by the laboratory."""
from django.contrib.auth.models import User
from django.test import TestCase

from home.models import TbEssencia, TbLinhagem, TbPersonagem, TbRaca, TbTracoracial
from home.pathbuilder import _apply_racial_talents
from home.views import (
    _lvl_aplicar_talento_racial, _pendencias_talento_racial,
    _talentos_raciais_criador,
)


class RacialMilestoneTests(TestCase):
    def setUp(self):
        race = TbRaca.objects.create(nome='Race Q13', slug='race-q13')
        self.lineage = TbLinhagem.objects.create(id_raca=race, nome='A', slug='q13-a')
        other = TbLinhagem.objects.create(id_raca=race, nome='B', slug='q13-b')
        self.essence = TbEssencia.objects.create(nome='Essence', slug='q13-essence')
        foreign = TbEssencia.objects.create(nome='Foreign', slug='q13-foreign')
        self.character = TbPersonagem.objects.create(
            dono=User.objects.create_user('q13'), nome='Q13', nivel=20,
            id_raca=race, id_linhagem=self.lineage, id_essencia=self.essence)
        for level in (1, 5, 9, 13, 17):
            TbTracoracial.objects.create(id_raca=race, nome='Base %s' % level,
                descricao='', talento_racial=True, nivel_requisito=level)
        for name, level, identity in (
            ('Own lineage', 7, {'id_linhagem': self.lineage}),
            ('Other lineage', 8, {'id_linhagem': other}),
            ('Own essence', 11, {'id_essencia': self.essence}),
            ('Other essence', 12, {'id_essencia': foreign}),
            ('Other lineage initial', 1, {'id_linhagem': other}),
        ):
            TbTracoracial.objects.create(id_raca=race, nome=name, descricao='',
                talento_racial=True, nivel_requisito=level, **identity)

    def test_identity_filters_options_and_does_not_invent_foreign_milestones(self):
        groups = _pendencias_talento_racial(self.character)
        self.assertEqual([g['nivel'] for g in groups], [1, 5, 7, 9, 11, 13, 17])
        names = {o['nome'] for g in groups for o in g['opcoes']}
        self.assertIn('Own lineage', names)
        self.assertIn('Own essence', names)
        self.assertFalse(any(name.startswith('Other') for name in names))
        initial = _talentos_raciais_criador(self.character.id_raca, self.lineage, self.essence)
        self.assertEqual({o.nome for o in initial}, {o['nome'] for o in groups[0]['opcoes']})

    def test_levelup_persists_once_and_rejects_foreign_choice(self):
        self.assertTrue(_lvl_aplicar_talento_racial(self.character,
            {'nivel': 8, 'talento': 'Other lineage'}))
        choice = {'nivel': 7, 'talento': 'Own lineage'}
        self.assertEqual(_lvl_aplicar_talento_racial(self.character, choice), [])
        self.assertTrue(_lvl_aplicar_talento_racial(self.character, choice))
        self.character.refresh_from_db()
        self.assertEqual(self.character.talentos.count(), 1)
        self.assertNotIn(7, [g['nivel'] for g in _pendencias_talento_racial(self.character)])

    def test_laboratory_exposes_all_content_milestones_and_resolves_each_once(self):
        selections = [{'nivel': level, 'nome': 'Base %s' % level}
                      for level in (1, 5, 9, 13, 17)]
        selections += [{'nivel': 7, 'nome': 'Own lineage'},
                       {'nivel': 11, 'nome': 'Own essence'}]
        groups, issues = _apply_racial_talents(self.character, {'talentos_raciais': selections})
        self.assertEqual(issues, [])
        self.assertEqual(len(groups), 7)
        self.assertEqual(self.character.talentos.count(), 7)
        self.assertEqual(_pendencias_talento_racial(self.character), [])

    def test_level_and_absent_identity_remove_unavailable_milestones(self):
        self.character.nivel = 9
        self.character.id_linhagem = None
        self.character.id_essencia = None
        self.character.save()
        self.assertEqual([g['nivel'] for g in _pendencias_talento_racial(self.character)], [1, 5, 9])
