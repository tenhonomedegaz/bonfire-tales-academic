from django.test import TestCase
from .character_engine import derive
from .hunter_expertise import save_expertise
from .models import TbPersonagemPericia, TbPersonagemEscolha


class HunterExpertiseTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.skill = TbPersonagemPericia.objects.create(id_personagem=self.person,
            nome='Natureza', atributo='INT', proficiente=True)
        TbPersonagemPericia.objects.create(id_personagem=self.person,
            nome='Sobrevivência', atributo='SAB', proficiente=True)
        TbPersonagemPericia.objects.create(id_personagem=self.person,
            nome='Atletismo', atributo='FOR', proficiente=True)

    def save(self, values, version=0):
        return save_expertise(character_id=self.person.pk, owner_id=self.user.pk,
                              selected=values, expected_version=version)

    def nature(self, ruleset):
        return next(s for s in derive(self.person, ruleset=ruleset)['pericias'] if s['nome']=='Natureza')

    def test_save_reload_real_bonus_and_no_stacking(self):
        before = self.nature(self.ruleset)['bonus']
        response = self.client.post(self.url, {'action':'expertise','expertise':['natureza'],'version':0})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.nature(self.ruleset)['bonus'],before+2)
        self.assertFalse(self.nature(None)['expertise'])
        self.save(['natureza'],1)
        self.assertEqual(TbPersonagemEscolha.objects.filter(tipo='hunter-expertise').count(),1)
        self.skill.expertise=True
        self.skill.save()
        self.assertEqual(self.nature(self.ruleset)['bonus'],before+2)
        self.assertContains(self.client.get(self.url),'checked disabled')

    def test_level_nine_addition_and_invalid_choices(self):
        for values in (['atletismo'],['arcanismo'],['natureza','natureza'],[]):
            with self.assertRaises(ValueError):self.save(values)
        self.save(['natureza'])
        with self.assertRaises(ValueError):self.save(['sobrevivencia'],1)
        self.pc.nivel=9
        self.pc.save()
        self.save(['natureza','sobrevivencia'],1)
        self.assertEqual(self.nature(self.ruleset)['bonus'],8)
        with self.assertRaises(ValueError):self.save(['natureza','sobrevivencia'],1)

    def test_lost_proficiency_preserves_choice_but_stops_bonus(self):
        self.save(['natureza'])
        self.skill.proficiente=False
        self.skill.save()
        self.assertFalse(self.nature(self.ruleset)['expertise'])
        self.assertTrue(TbPersonagemEscolha.objects.filter(tipo='hunter-expertise').exists())
        self.assertContains(self.client.get(self.url),'perícias escolhidas precisam de regularização')

    def test_other_owner_and_archive_cannot_write(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,{'action':'expertise','expertise':['natureza'],'version':0}).status_code,404)
        self.client.force_login(self.user)
        self.person.arquivado=True
        self.person.save()
        self.assertEqual(self.client.post(self.url,{'action':'expertise','expertise':['natureza'],'version':0}).status_code,404)
