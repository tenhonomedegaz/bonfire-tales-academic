from django.test import TestCase
from .character_engine import derive
from .hunter_spells import granted_spells
from .models import TbMagia, TbClassehabilidade
from .views import _sync_magias_concedidas


class HunterSwarmTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save()
        self.person.velocidade = '9 m / 30 ft'
        self.person.save()

    def test_symbiosis_grant_and_evolution_are_visible_and_level_gated(self):
        for level in (3, 7, 9, 10, 11, 17, 20):
            self.pc.nivel = level
            self.pc.save()
            sheet = derive(self.person, ruleset=self.ruleset)
            self.assertEqual(sheet['movimento_modos']['climb'], 'walk')
            self.assertTrue(sheet['enxame']['feather_fall'])
            self.assertEqual(sheet['enxame']['hover'], level >= 10)
            self.assertEqual('fly' in sheet['movimento_modos'], level >= 10)
            self.assertIn('mao-arcana', [g['slug'] for g in granted_spells(self.person,self.ruleset)])
        self.assertEqual(sheet['enxame']['athletics_die'], '1d12')
        self.assertContains(self.client.get(self.url), 'com capacidade de pairar')
        self.assertNotIn('enxame', derive(self.person))

    def test_cantrip_sync_is_idempotent_and_frozen(self):
        hand = TbMagia.objects.get(slug='mao-arcana')
        hand.nome = 'Changed live spell'
        hand.save()
        _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        row = self.person.magias.get(id_magia=hand)
        self.assertEqual(row.nivel, 0)
        self.assertTrue(row.sempre_preparada)
        self.assertNotEqual(row.nome, hand.nome)
        _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        self.assertEqual(self.person.magias.filter(id_magia=hand).count(), 1)

    def test_other_order_and_old_revision_do_not_gain_swarm_effects(self):
        self.pc.id_subclasse=self.subs['ordem-dos-mutantes']
        self.pc.save()
        self.assertNotIn('enxame', derive(self.person,ruleset=self.ruleset))
        self.pc.id_subclasse=self.subs['ordem-do-enxame']
        self.pc.save()
        self.data.pop('swarm_passives')
        self.data['spell_grants']=[g for g in self.data['spell_grants'] if not g.get('feature_grant')]
        self.bind(self.data)
        self.assertNotIn('enxame', derive(self.person,ruleset=self.ruleset))
        self.assertNotIn('mao-arcana',[g['slug'] for g in granted_spells(self.person,self.ruleset)])

    def test_faster_movement_from_other_source_is_preserved(self):
        TbClassehabilidade.objects.create(id_classe=self.cl, nome='Other movement',
            niveladquirido=1,tags_json=['move:climb(60ft)', 'move:fly(90ft)'])
        self.bind(self.data)
        self.pc.nivel=10
        self.pc.save()
        sheet=derive(self.person,ruleset=self.ruleset)
        self.assertEqual(sheet['movimento_modos']['climb'],'60ft')
        self.assertEqual(sheet['movimento_modos']['fly'],'90ft')
