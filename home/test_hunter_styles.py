from django.test import TestCase
from .models import TbOpcaojogo, TbAcessoopcao, TbPersonagemEscolha
from .hunter_styles import save_style, features
from .character_engine import derive


class HunterStyleTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.styles = []
        for i in range(3):
            option = TbOpcaojogo.objects.create(nome='Style %s' % i, slug='style-%s' % i,
                tipo='Estilo de Luta', tags_json=['ca:+%s' % (i+1)],
                pre_requisito='Força 30+' if i == 2 else '')
            TbAcessoopcao.objects.create(id_opcao=option, id_classe=self.cl, nivel_recebimento=2)
            self.styles.append(option)
        self.bind(self.data)

    def save(self, index, version=0):
        return save_style(character_id=self.person.pk, owner_id=self.user.pk,
                          selected=self.styles[index].pk, expected_version=version)

    def test_persist_frozen_effect_and_replace_once_per_hunter_level(self):
        before = derive(self.person, ruleset=self.ruleset)
        self.assertEqual(self.client.post(self.url, {'action':'style',
            'style':self.styles[0].pk, 'version':0}).status_code,302)
        self.assertEqual(len(features(self.person,self.ruleset)),1)
        after = derive(self.person, ruleset=self.ruleset)
        self.assertNotEqual(before['ca'],after['ca'])
        self.assertEqual(features(self.person,None),[])
        self.styles[0].tags_json=['ca:+99']
        self.styles[0].save()
        self.assertEqual(derive(self.person,ruleset=self.ruleset)['ca'],after['ca'])
        self.save(0,1)
        with self.assertRaises(ValueError):self.save(1,1)
        self.pc.nivel=4
        self.pc.save()
        self.save(1,1)
        self.assertEqual(TbPersonagemEscolha.objects.filter(tipo='hunter-style').count(),1)
        with self.assertRaises(ValueError):self.save(0,2)
        self.assertContains(self.client.get(self.url),'Style 1')

    def test_prerequisites_duplicates_level_and_stale_write(self):
        with self.assertRaises(ValueError):self.save(2)
        TbPersonagemEscolha.objects.create(id_personagem=self.person,origem='other',
            tipo='estilo-de-luta',id_opcao=self.styles[0],valor=self.styles[0].slug)
        with self.assertRaises(ValueError):self.save(0)
        self.pc.nivel=1
        self.pc.id_subclasse=None
        self.pc.save()
        with self.assertRaises(ValueError):self.save(1)
        self.pc.nivel=2
        self.pc.save()
        self.save(1)
        with self.assertRaises(ValueError):self.save(1)

    def test_owner_and_archive_protection(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,{'action':'style','style':self.styles[0].pk,'version':0}).status_code,404)
        self.client.force_login(self.user)
        self.person.arquivado=True
        self.person.save()
        self.assertEqual(self.client.post(self.url,{'action':'style','style':self.styles[0].pk,'version':0}).status_code,404)
