from django.test import TestCase
from django.urls import reverse
from .models import TbItemMundano, TbOpcaojogo, TbClassehabilidade
from .hunter_masteries import save, state
from .character_engine import _maestrias_armas


class HunterMasteryTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind=HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.cl.tags_json=['prof{armas_simples}']; self.cl.save()
        self.mastery=TbOpcaojogo.objects.create(nome='Minar teste',slug='test-sap',tipo='Maestria de Arma',descricao='Efeito congelado')
        self.weapons=[TbItemMundano.objects.create(nome=f'Arma {i}',slug=f'weapon-{i}',categoria='arma',
            subcategoria='arma_simples',tags_json=['maestrias{test_sap}']) for i in range(5)]
        self.bind(self.data)
        self.values=[f'{w.slug}|test_sap' for w in self.weapons]

    def save(self, selected):
        self.profile.refresh_from_db()
        save(character_id=self.person.pk,owner_id=self.user.pk,selected=selected,expected_version=self.profile.version)

    def test_post_pinned_effects_and_single_long_rest_replacement(self):
        response=self.client.post(self.url,{'action':'masteries','mastery':self.values[:3],'version':0})
        self.assertEqual(response.status_code,302)
        result=_maestrias_armas(self.person,ruleset=self.ruleset)
        self.assertEqual(len(result),3)
        self.assertEqual(result[0]['maestria']['efeito'],'Efeito congelado')
        self.assertEqual(_maestrias_armas(self.person),[])
        replacement=self.values[1:4]
        with self.assertRaises(ValueError):self.save(replacement)
        rest=reverse('personagem_descansar',args=[self.person.pk])
        self.client.post(rest,{'tipo':'curto'})
        with self.assertRaises(ValueError):self.save(replacement)
        self.client.post(rest,{'tipo':'longo'})
        self.save(replacement)
        with self.assertRaises(ValueError):self.save(self.values[2:5])
        self.mastery.descricao='Mutated';self.mastery.save()
        self.assertEqual(_maestrias_armas(self.person,ruleset=self.ruleset)[0]['maestria']['efeito'],'Efeito congelado')
        self.assertContains(self.client.get(self.url),'Armas de Caçada')

    def test_invalid_duplicate_unproficient_stale_and_legacy(self):
        for values in (self.values[:2],[self.values[0]]*3,['unknown|test_sap']+self.values[:2]):
            with self.assertRaises(ValueError):self.save(values)
        self.save(self.values[:3])
        with self.assertRaises(ValueError):save(character_id=self.person.pk,owner_id=self.user.pk,
            selected=self.values[:3],expected_version=0)
        self.cl.tags_json=[];self.cl.save();self.bind(self.data)
        with self.assertRaises(ValueError):self.save(self.values[:3])
        self.data.pop('weapon_masteries');self.bind(self.data)
        self.assertIsNone(state(self.profile))
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url,{'action':'masteries'}).status_code,404)

    def test_specific_weapon_grant_is_frozen_and_no_proficiency_fails_closed(self):
        self.cl.tags_json=[]
        feature=TbClassehabilidade.objects.create(id_classe=self.cl,nome='Specific proficiency',
            niveladquirido=1,tags_json=[f'prof:weapon{{weapon-{i}}}' for i in range(3)])
        self.cl.save(); self.bind(self.data)
        self.assertEqual({o['value'] for o in state(self.profile)['options']},set(self.values[:3]))
        self.cl.tags_json=['prof{armas_simples}']; self.cl.save()
        self.assertEqual({o['value'] for o in state(self.profile)['options']},set(self.values[:3]))
        self.save(self.values[:3])
        self.cl.tags_json=[];self.cl.save();feature.tags_json=[];feature.save();self.bind(self.data)
        self.assertEqual(state(self.profile)['options'],[])

    def test_secondary_class_proficiency_uses_frozen_multiclass_tokens(self):
        from .models import TbClasse, TbPersonagemClasse
        from .content_versions import create_revision, seal_ruleset
        from .versioned_classes import inventory_class, EVALUATOR, VOCABULARY
        self.cl.tags_json=['multiclass_prof{armas_simples}']; self.cl.save()
        self.pc.principal=False;self.pc.save()
        primary=TbClasse.objects.create(nome='Primary',slug='primary')
        TbPersonagemClasse.objects.create(id_personagem=self.person,id_classe=primary,nivel=1,principal=True)
        self.bind(self.data)
        revisions=[e.revision for e in self.ruleset.entries.select_related('revision')]
        revisions.append(create_revision('class-catalog:%s'%primary.pk,inventory_class(primary.pk)))
        self.ruleset=seal_ruleset(revisions,evaluator_version=EVALUATOR,vocabulary_version=VOCABULARY)
        self.profile.ruleset=self.ruleset;self.profile.save()
        self.assertEqual(len(state(self.profile)['options']),5)
        self.save(self.values[:3])

    def test_compound_grant_keeps_frozen_weapon_property_exclusions(self):
        self.cl.tags_json=[]
        TbClassehabilidade.objects.create(id_classe=self.cl,nome='Compound proficiency',niveladquirido=1,
            tags_json=['prof:weapon{marcial, melee, not:{pesada, duas_maos}}'])
        self.cl.save()
        for index,weapon in enumerate(self.weapons):
            weapon.subcategoria='arma_marcial_dist' if index==4 else 'arma_marcial'
            weapon.tags_json=['maestrias{test_sap}'] + (['add_property:pesada'] if index==3 else [])
            weapon.save()
        self.bind(self.data)
        self.assertEqual({o['value'] for o in state(self.profile)['options']},set(self.values[:3]))
        self.weapons[3].tags_json=['maestrias{test_sap}'];self.weapons[3].save()
        self.assertEqual({o['value'] for o in state(self.profile)['options']},set(self.values[:3]))

    def test_specific_proficiency_reaches_attacks_and_off_hand_without_legacy_change(self):
        from .character_engine import derive
        self.cl.tags_json=[];self.cl.save()
        feature=TbClassehabilidade.objects.create(id_classe=self.cl,nome='Blade training',
            niveladquirido=1,tags_json=['prof:weapon{weapon-0}', 'prof:weapon{weapon-1}'])
        for weapon in self.weapons[:3]:
            self.person.inventario.create(nome=weapon.nome,id_item_mundano=weapon,
                equipado=True,tags_json=['dmg:1d6(cortante)', 'add_property:leve'])
        self.bind(self.data)
        def profiles(ruleset=None):
            return derive(self.person,ruleset=ruleset)['ataques']['perfis']
        legacy=profiles()
        frozen=profiles(self.ruleset)
        self.assertEqual([p['proficiente'] for p in frozen],[True,True,False,False])
        for index in (0,1):
            self.assertEqual(frozen[index]['bonus_ataque'],legacy[index]['bonus_ataque']+2)
        # Remove the untrained third weapon: off-hand must inherit the grant.
        self.person.inventario.filter(id_item_mundano=self.weapons[2]).update(equipado=False)
        trained=profiles(self.ruleset)
        self.assertEqual(trained[-1]['escopo'],'off_hand')
        self.assertTrue(trained[-1]['proficiente'])
        self.assertEqual(trained[-1]['bonus_ataque'],trained[1]['bonus_ataque'])
        feature.tags_json=[];feature.save()
        self.weapons[0].slug='changed-live';self.weapons[0].save()
        self.assertEqual(profiles(self.ruleset),trained)
        self.assertFalse(any(p['proficiente'] for p in profiles()))

    def test_compound_attack_grant_rejects_heavy_and_ranged_weapons(self):
        from .character_engine import derive
        self.cl.tags_json=[];self.cl.save()
        TbClassehabilidade.objects.create(id_classe=self.cl,nome='Light martial training',
            niveladquirido=1,tags_json=['prof:weapon{marcial, melee, not:{pesada, duas_maos}}'])
        for index,weapon in enumerate(self.weapons[:3]):
            weapon.subcategoria='arma_marcial_dist' if index==2 else 'arma_marcial'
            weapon.save()
            self.person.inventario.create(nome=weapon.nome,id_item_mundano=weapon,
                equipado=True,tags_json=['dmg:1d6(cortante)'] +
                (['add_property:pesada'] if index==1 else []))
        self.bind(self.data)
        attacks=derive(self.person,ruleset=self.ruleset)['ataques']['perfis']
        self.assertEqual([p['proficiente'] for p in attacks],[True,False,False])
