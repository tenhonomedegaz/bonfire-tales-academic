from unittest.mock import patch
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase
from . import views
from .content_versions import create_revision, seal_ruleset
from .models import TbClasse, TbMagia, TbPersonagem, TbRecursoclasse
from .versioned_classes import EVALUATOR, VOCABULARY, inventory_class
from .versioned_spells import snapshot_spells
from .test_criador import _CriadorBase


class FrozenCreatorSpellsTests(TestCase):
    def setUp(self):
        self.classe = TbClasse.objects.create(nome='Caçador', slug='cacador', tags_json=[
            'spellcasting{ability:wis,list:cacador,slots:half,mode:prepared,spell_limit{resource:prepared},cantrip_limit{resource:cantrips}}'])
        self.limit = TbRecursoclasse.objects.create(id_classe=self.classe, nome='Prepared',
            slug='prepared', tipo='table-only', valores_json={'1':'2'})
        self.cantrips = TbRecursoclasse.objects.create(id_classe=self.classe, nome='Cantrips',
            slug='cantrips', tipo='table-only', valores_json={'1':'1'})
        self.spell = TbMagia.objects.create(nome='Frozen spell',slug='frozen-spell',nivel=1,
            classes_slugs=['cacador'])
        TbMagia.objects.create(nome='Legacy cantrip',slug='legacy-cantrip',nivel=0,classes='Caçador')
        TbMagia.objects.create(nome='Outsider',slug='outsider',nivel=1,classes='Other')
        self.revision = create_revision('class-catalog:%s' % self.classe.pk, inventory_class(self.classe.pk))
        self.ruleset = seal_ruleset([self.revision,snapshot_spells()],
            evaluator_version=EVALUATOR,vocabulary_version=VOCABULARY)

    def test_builder_catalog_and_limits_are_frozen(self):
        expected = views._classe_conjuracao(self.classe, ruleset=self.ruleset)
        self.assertEqual(expected['magias_n'], 2)
        self.assertEqual(expected['truques_n'], 1)
        self.assertEqual([s['slug'] for s in expected['magias_nv1']], ['frozen-spell'])
        self.assertEqual([s['slug'] for s in expected['truques']], ['legacy-cantrip'])
        self.classe.nome='Changed class'; self.classe.tags_json=[]; self.classe.save()
        self.spell.nome='Changed spell'; self.spell.nivel=9; self.spell.classes_slugs=[]; self.spell.save()
        self.limit.valores_json={'1':'99'}; self.limit.save()
        TbMagia.objects.create(nome='New live spell',slug='new-live',nivel=1,classes_slugs=['cacador'])
        self.assertEqual(views._classe_conjuracao(self.classe,ruleset=self.ruleset), expected)
        self.assertIsNone(views._classe_conjuracao(self.classe))

    def test_missing_spell_snapshot_fails_without_live_fallback(self):
        incomplete = seal_ruleset([self.revision],evaluator_version=EVALUATOR,vocabulary_version=VOCABULARY)
        with self.assertRaises(ObjectDoesNotExist):
            views._classe_conjuracao(self.classe,ruleset=incomplete)


class CreatorSpellPersistenceTests(_CriadorBase):
    def test_create_keeps_validated_spell_identity_name_and_preparation(self):
        user=self._novo_usuario('spell-snapshot',staff=True)
        payload=self._payload('mago')
        expected,errors=views._criador_resolver(payload)
        self.assertEqual(errors,[])
        conj=expected['conj']
        self.assertEqual(conj['pool'],'spellbook')
        original=views._criador_resolver
        def change_after_validation(data):
            result,errors=original(data)
            for row in result['conj']['truques']+result['conj']['magias_nv1']:
                TbMagia.objects.filter(pk=row['id']).update(nome='Changed live spell',slug='changed-%s'%row['id'])
            return result,errors
        with patch('home.views._criador_resolver',side_effect=change_after_validation):
            response=self._post_criar(user,payload)
        self.assertEqual(response.status_code,200,response.content)
        person=TbPersonagem.objects.get(pk=response.json()['id'])
        for level,selected,catalog in ((0,expected['truques_sel'],conj['truques']),
                                       (1,expected['magias_sel'],conj['magias_nv1'])):
            for row in catalog:
                if row['slug'] not in selected:
                    continue
                spell=person.magias.get(id_magia_id=row['id'],origem=conj['origem'])
                self.assertEqual((spell.nome,spell.nivel),(row['nome'],level))
                self.assertEqual(spell.preparada,level==0 or row['slug'] in expected['magias_preparadas_sel'])
        self.assertEqual(person.magias.filter(origem=conj['origem']).count(),
                         len(expected['truques_sel'])+len(expected['magias_sel']))

    def test_missing_spell_identity_rejects_and_rolls_back_creation(self):
        user=self._novo_usuario('spell-missing',staff=True)
        payload=self._payload('mago')
        original=views._criador_resolver
        def missing_identity(data):
            result,errors=original(data)
            slug=result['magias_sel'][0]
            next(row for row in result['conj']['magias_nv1'] if row['slug']==slug)['id']=2147483647
            return result,errors
        with patch('home.views._criador_resolver',side_effect=missing_identity):
            response=self._post_criar(user,payload)
        self.assertEqual(response.status_code,400,response.content)
        self.assertFalse(TbPersonagem.objects.filter(dono=user).exists())
