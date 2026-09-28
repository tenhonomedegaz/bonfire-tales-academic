from django.test import TestCase
from .character_engine import derive
from .models import TbClassehabilidade


class HunterPassiveTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.person.inteligencia = 18
        self.person.sabedoria = 8
        self.person.velocidade = '9 m / 30 ft'
        self.person.save()
        self.profile.ability = 'int'
        self.profile.save()

    def test_level_thresholds_apply_to_real_sheet_without_conditional_bonuses(self):
        for level in (1, 2, 3, 5, 7, 9, 13, 15, 17, 20):
            self.pc.nivel = level
            self.pc.id_subclasse = self.subs['ordem-dos-mutantes'] if level >= 3 else None
            self.pc.save()
            sheet = derive(self.person, ruleset=self.ruleset)
            legacy = derive(self.person)
            self.assertNotIn('cacador', legacy)
            self.assertEqual(sheet['ataques']['quantidade'], 2 if level >= 5 else 1)
            for sig in ('FOR','DES','CON'):
                self.assertEqual(sheet['saves'][sig]['bonus'],legacy['saves'][sig]['bonus']+(4 if level>=9 else 0))
            self.assertEqual(sheet['velocidade'],'12 m / 40 ft' if level>=7 else '9 m / 30 ft')
            self.assertEqual(sheet['cacador']['favored_damage'],0)
            self.assertEqual(sheet['cacador']['mark_damage'],'')
            self.assertEqual('blindsight 30ft' in sheet['sentidos'],level>=17)
            self.assertEqual('Possessão' in sheet['imunidades'],level>=15)
            self.assertEqual(any(c['slug']=='enfeiticado' for c in sheet['imunidades_condicao']),level>=15)
        self.assertContains(self.client.get(self.url),'Ataques por ação 2')
        self.assertContains(self.client.get(self.url),'Vantagem nas salvaguardas contra Amedrontado')

    def test_replaces_same_feature_once_and_preserves_other_source(self):
        TbClassehabilidade.objects.create(id_classe=self.cl,nome='Caçador Implacável',
            niveladquirido=7,tags_json=['speed:+10ft'])
        TbClassehabilidade.objects.create(id_classe=self.cl,nome='Other speed',
            niveladquirido=7,tags_json=['speed:+5ft'])
        self.bind(self.data)
        self.pc.nivel=9
        self.pc.save()
        sheet=derive(self.person,ruleset=self.ruleset)
        self.assertEqual(sheet['velocidade'],'13.5 m / 45 ft')
        self.assertTrue(any(f['nome']=='Caçador Implacável' for f in sheet['features']))
        self.profile.ability='wis'
        self.profile.save()
        negative=derive(self.person,ruleset=self.ruleset)
        self.assertEqual(negative['saves']['CON']['bonus'],sheet['saves']['CON']['bonus']-5)

    def test_old_sealed_contract_and_unknown_speed_are_preserved(self):
        self.data.pop('base_passives')
        self.bind(self.data)
        self.pc.nivel=9
        self.pc.save()
        self.assertNotIn('cacador',derive(self.person,ruleset=self.ruleset))
        from .hunter_rework import catalog
        self.bind(catalog())
        self.person.velocidade='unknown'
        self.person.save()
        sheet=derive(self.person,ruleset=self.ruleset)
        self.assertEqual(sheet['velocidade'],'unknown')
        self.assertIsNone(sheet['cacador']['walking_speed'])
        self.assertTrue(any('deslocamento base' in w for w in sheet['avisos']))
