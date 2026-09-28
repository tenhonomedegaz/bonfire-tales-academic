from django.test import TestCase
from django.contrib.auth import get_user_model
from home.models import TbClasse, TbClassehabilidade, TbPersonagem, TbPersonagemClasse, TbMagia, TbPersonagemMagia
from home.character_engine import derive
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items, snapshot_mundane_items
from home.versioned_conditions import snapshot_conditions
from home.versioned_library import snapshot_library
from home.versioned_spells import snapshot_spells
from home.tag_engine.library import Library


class VersionedDeriveTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='pinned-derive')
        self.cl = TbClasse.objects.create(nome='Old class', slug='pinned-derive', dado_vida='d8',
            tags_json=['saves_prof{str,con}', 'prof{armas_simples}'])
        self.feature = TbClassehabilidade.objects.create(id_classe=self.cl, nome='Old feature',
            descricao='', niveladquirido=1, tags_json=['ca:+1'])
        self.person = TbPersonagem.objects.create(dono=user, nome='Pinned hero', nivel=2)
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person, id_classe=self.cl,
                                                   nivel=2, principal=True)
        self.spell = TbMagia.objects.create(nome='Old spell', slug='pinned-spell', nivel=1,
                                           nome_ingles='Old English', escola='Old school')
        self.choice = TbPersonagemMagia.objects.create(id_personagem=self.person, id_magia=self.spell,
            nome='My spell', nivel=1, preparada=True)
        revision = create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk))
        self.ruleset = seal_ruleset([revision, snapshot_options(), snapshot_origins(),
            snapshot_magic_items(), snapshot_mundane_items(), snapshot_conditions(), snapshot_spells(),
            snapshot_library(raw=Library(prefer_db=False).raw)], evaluator_version=EVALUATOR,
            vocabulary_version=VOCABULARY)

    def test_complete_state_survives_catalog_changes_and_tracks_live_state(self):
        before = derive(self.person)
        self.assertEqual(derive(self.person, ruleset=self.ruleset), before)
        self.cl.nome = 'Changed class'
        self.cl.dado_vida = 'd12'
        self.cl.save()
        self.feature.tags_json = ['ca:+9']
        self.feature.save()
        self.spell.nome_ingles = 'Changed English'
        self.spell.escola = 'Changed school'
        self.spell.save()
        self.assertNotEqual(derive(self.person), before)
        self.assertEqual(derive(self.person, ruleset=self.ruleset), before)
        self.choice.preparada = False
        self.choice.save()
        self.pc.nivel = 3
        self.pc.save()
        after = derive(self.person, ruleset=self.ruleset)
        self.assertEqual(after['nivel_total'], 3)
        self.assertFalse(after['magias'][0]['preparada'])
        self.assertEqual(after['magias'][0]['nome_ingles'], 'Old English')

    def test_spell_added_after_snapshot_is_preserved_but_suspended(self):
        new = TbMagia.objects.create(nome='New spell', slug='new-pinned-spell', nivel=1)
        self.choice.id_magia = new
        self.choice.save()
        spell = derive(self.person, ruleset=self.ruleset)['magias'][0]
        self.assertEqual(spell['nome'], 'My spell')
        self.assertFalse(spell['preparada'])
        self.assertTrue(spell['preparada_legada'])
        self.assertTrue(spell['suspensa_na_revisao'])
        self.choice.refresh_from_db()
        self.assertEqual(self.choice.id_magia_id, new.pk)
        self.assertTrue(self.choice.preparada)

    def test_multiclass_equipment_resources_and_subclass_remain_frozen(self):
        from home.models import TbSubclasse, TbRecursoclasse, TbItemMagico, TbItemMundano, TbPersonagemItem
        second = TbClasse.objects.create(nome='Second class', slug='second-pinned', dado_vida='d6',
            tags_json=['subclass-choices{2}', 'multiclass-prof{armas_marciais}'])
        sub = TbSubclasse.objects.create(id_classe=second, nome='Old subclass', slug='old-sub')
        secondary = TbPersonagemClasse.objects.create(id_personagem=self.person, id_classe=second,
            id_subclasse=sub, nivel=2, principal=False)
        feature = TbClassehabilidade.objects.create(id_classe=second, id_subclasse=sub,
            nome='Subclass shield', niveladquirido=2, descricao='', tags_json=['initiative:+2'])
        resource = TbRecursoclasse.objects.create(id_classe=second, nome='Old resource', slug='old-resource',
            tipo='consumable', valores_json={'1': '2', '2': '3'})
        weapon = TbItemMundano.objects.create(nome='Frozen sword', slug='frozen-sword',
            categoria='arma', subcategoria='arma_simples')
        magic = TbItemMagico.objects.create(nome='Frozen magic', slug='frozen-magic', slot='arma',
            requer_sintonizacao=True, tags_json=['dmg:1d8(cortante)', 'ca:+1'])
        item = TbPersonagemItem.objects.create(id_personagem=self.person, nome=weapon.nome,
            id_item_mundano=weapon, id_item_magico=magic, equipado=True, sintonizado=True,
            peso='2', qtd=1)
        revisions = [create_revision('class-catalog:%s' % cl.pk, inventory_class(cl.pk))
                     for cl in (self.cl, second)]
        ruleset = seal_ruleset(revisions + [snapshot_options(), snapshot_origins(),
            snapshot_magic_items(), snapshot_mundane_items(), snapshot_conditions(), snapshot_spells(),
            snapshot_library(raw=Library(prefer_db=False).raw)], evaluator_version=EVALUATOR,
            vocabulary_version=VOCABULARY)
        before = derive(self.person)
        self.assertEqual(before['nivel_total'], 4)
        self.assertEqual(before['ataques']['perfis'][0]['dado'], '1d8')
        self.assertEqual(derive(self.person, ruleset=ruleset), before)
        second.dado_vida = 'd12'
        second.tags_json = []
        second.save()
        sub.nome = 'Changed subclass'
        sub.save()
        feature.tags_json = ['initiative:+9']
        feature.save()
        resource.valores_json = {'1': '99'}
        resource.save()
        weapon.subcategoria = 'arma_marcial_dist'
        weapon.save()
        magic.tags_json = ['dmg:2d12(fogo)', 'ca:+9']
        magic.save()
        self.assertNotEqual(derive(self.person), before)
        self.assertEqual(derive(self.person, ruleset=ruleset), before)
        item.equipado = False
        item.qtd = 2
        item.save()
        secondary.nivel = 1
        secondary.save()
        after = derive(self.person, ruleset=ruleset)
        self.assertEqual(after['nivel_total'], 3)
        self.assertEqual(after['ataques']['perfis'], [])
        self.assertEqual(after['peso_total'], 4)
        self.assertFalse(any(f['nome'] == 'Subclass shield' for f in after['features']))
        item.refresh_from_db()
        self.assertEqual(item.id_item_magico_id, magic.pk)

    def test_spell_grant_pool_preserves_class_names_and_catalog(self):
        from home.character_engine import magias_concedidas
        from home.models import TbPersonagemEscolha
        self.feature.tags_json = ['spell_selection:pinned-derive{nivel:1, qtd:1}']
        self.feature.save()
        self.spell.classes = self.cl.nome
        self.spell.save()
        revision = create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk))
        ruleset = seal_ruleset([revision, snapshot_options(), snapshot_origins(),
            snapshot_magic_items(), snapshot_spells()], evaluator_version=EVALUATOR,
            vocabulary_version=VOCABULARY)
        before = magias_concedidas(self.person)
        self.assertEqual(before['pendentes'][0]['opcoes'], [self.spell.slug])
        self.assertEqual(magias_concedidas(self.person, ruleset=ruleset), before)
        self.cl.nome = 'Changed class name'
        self.cl.save()
        self.spell.classes = 'Different list'
        self.spell.save()
        self.assertNotEqual(magias_concedidas(self.person), before)
        self.assertEqual(magias_concedidas(self.person, ruleset=ruleset), before)
        TbPersonagemEscolha.objects.create(id_personagem=self.person, tipo='magia-concedida',
            origem=self.feature.nome, slot=0, valor=self.spell.slug)
        selected = magias_concedidas(self.person, ruleset=ruleset)
        self.assertEqual(selected['pendentes'], [])
        self.assertEqual(selected['concedidas'][0]['slug'], self.spell.slug)
