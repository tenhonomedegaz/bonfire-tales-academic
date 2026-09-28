from django.test import TestCase
from .character_engine import derive, _spell_mod
from .hunter_spell_preparation import save_spells, panel
from .magic_workshop import character_casters
from .models import TbMagia, TbPersonagemMagia, TbPersonagem, TbPersonagemClasse, TbPersonagemCacador
from .versioned_classes import resolved_classes
from .views import _magias_sheet_info


class HunterSpellPreparationTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.cl.tags_json = ['spellcasting{ability:wis, list:cacador, slots:full, mode:prepared, spell_limit{formula:classlvl+spell_mod}}']
        self.cl.save()
        self.person.inteligencia=18
        self.person.sabedoria=8
        self.person.save()
        self.spells=[TbMagia.objects.create(nome='Choice %s'%i,slug='choice-%s'%i,
            nivel=1,classes=self.cl.nome) for i in range(9)]
        self.bind(self.data)

    def save(self, selected, version=0):
        return save_spells(character_id=self.person.pk,owner_id=self.user.pk,
                           selected=selected,expected_version=version)

    def test_chosen_ability_reaches_sheet_preparation_formula_and_shared_cache(self):
        sheet=derive(self.person,ruleset=self.ruleset)
        self.assertEqual(panel(self.profile,sheet)['limite'],7)
        magic=_magias_sheet_info(self.person,sheet,[],ruleset=self.ruleset)['spellcasting']
        self.assertEqual((magic['ability'],magic['cd'],magic['ataque']),('INT',14,6))
        self.assertEqual(_spell_mod(resolved_classes(self.ruleset,[self.pc]),sheet['atributos'],ruleset=self.ruleset),4)
        cache={}
        self.assertEqual(character_casters(self.person,ruleset=self.ruleset,contract_cache=cache)[0]['contract']['ability'],'int')
        other=TbPersonagem.objects.create(dono=self.user,nome='Other',nivel=3)
        pc=TbPersonagemClasse.objects.create(id_personagem=other,id_classe=self.cl,
            id_subclasse=self.sub,nivel=3,principal=True)
        TbPersonagemCacador.objects.create(personagem_classe=pc,ruleset=self.ruleset,ability='wis')
        self.assertEqual(character_casters(other,ruleset=self.ruleset,contract_cache=cache)[0]['contract']['ability'],'wis')
        self.assertEqual(character_casters(self.person,contract_cache={})[0]['contract']['ability'],'wis')

    def test_save_reload_frozen_identity_preserves_acquired_and_fixed_spells(self):
        acquired=TbPersonagemMagia.objects.create(id_personagem=self.person,id_magia=self.spells[0],
            nome='Acquired',nivel=1,preparada=True,origem='')
        fixed=TbPersonagemMagia.objects.create(id_personagem=self.person,id_magia=self.spells[2],
            nome='Fixed',nivel=1,preparada=True,sempre_preparada=True,origem=self.cl.nome)
        self.cl.nome='Changed'
        self.cl.tags_json=[]
        self.cl.save()
        self.spells[1].slug='changed-slug'
        self.spells[1].nome='Changed spell'
        self.spells[1].save()
        response=self.client.post(self.url,{'action':'spells','spell':['choice-1'],'version':0})
        self.assertEqual(response.status_code,302)
        acquired.refresh_from_db();fixed.refresh_from_db()
        self.assertFalse(acquired.preparada)
        self.assertTrue(fixed.preparada)
        row=self.person.magias.get(id_magia=self.spells[1])
        self.assertEqual(row.nome,'Choice 1')
        self.assertEqual(row.origem,'Caçador')
        self.save(['choice-1'],1)
        self.assertEqual(self.person.magias.count(),3)
        self.assertContains(self.client.get(self.url),'Confirmar magias preparadas')
        self.save([],1)
        self.assertEqual(self.person.magias.count(),3)

    def test_invalid_stale_and_unauthorized_writes_are_atomic(self):
        for selected in (['unknown'],['choice-0','choice-0'],['choice-%s'%i for i in range(8)]):
            with self.assertRaises(ValueError):self.save(selected)
        self.assertFalse(self.person.magias.exists())
        self.save(['choice-0'])
        with self.assertRaises(ValueError):self.save([],0)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,{'action':'spells','version':1}).status_code,404)
        self.client.force_login(self.user)
        self.person.arquivado=True;self.person.save()
        self.assertEqual(self.client.post(self.url,{'action':'spells','version':1}).status_code,404)

    def test_old_revision_does_not_gain_new_choice_contract(self):
        self.data.pop('spellcasting_ability_choices')
        self.bind(self.data)
        self.assertEqual(character_casters(self.person,ruleset=self.ruleset)[0]['contract']['ability'],'wis')

    def test_fixed_grant_cannot_be_duplicated_before_materialization(self):
        mark=TbMagia.objects.get(nome_ingles="Hunter's Mark")
        mark.classes=self.cl.nome
        mark.save()
        self.bind(self.data)
        info=panel(self.profile,derive(self.person,ruleset=self.ruleset))
        self.assertNotIn(mark.slug,{m['slug'] for g in info['grupos'] for m in g['magias']})
        with self.assertRaises(ValueError):self.save([mark.slug])
        self.assertFalse(self.person.magias.exists())

    def test_main_sheet_endpoint_preserves_acquisitions_and_rejects_stale(self):
        from django.urls import reverse
        endpoint=reverse('personagem_preparar_magias',args=[self.person.pk])
        acquired=TbPersonagemMagia.objects.create(id_personagem=self.person,id_magia=self.spells[0],
            nome='Acquired',nivel=1,preparada=True,origem=self.cl.nome)
        old=self.client.post(endpoint,{'classe':self.cl.pk,'magia':['choice-1']})
        self.assertRedirects(old,self.url,fetch_redirect_response=False)
        acquired.refresh_from_db();self.assertTrue(acquired.preparada)
        self.cl.tags_json=[];self.cl.save()
        result=self.client.post(endpoint,{'classe':self.cl.pk,'version':0,'magia':['choice-1'],
            'next':self.url})
        self.assertRedirects(result,self.url,fetch_redirect_response=False)
        acquired.refresh_from_db();self.assertFalse(acquired.preparada)
        self.assertTrue(self.person.magias.get(id_magia=self.spells[1]).preparada)
        self.assertEqual(self.person.magias.count(),2)
        stale=self.client.post(endpoint,{'classe':self.cl.pk,'version':0,'magia':[]})
        self.assertEqual(stale.status_code,409)
        self.assertTrue(self.person.magias.get(id_magia=self.spells[1]).preparada)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(endpoint,{'version':1}).status_code,404)
        self.client.force_login(self.user)
        self.person.arquivado=True;self.person.save()
        self.assertEqual(self.client.post(endpoint,{'version':1}).status_code,404)

    def test_preparation_form_uses_main_endpoint_with_pinned_version(self):
        from django.urls import reverse
        response=self.client.get(self.url)
        self.assertContains(response,'action="%s"'%reverse('personagem_preparar_magias',args=[self.person.pk]))
        self.assertContains(response,'name="magia"')
        self.assertContains(response,'name="version" value="0"')
