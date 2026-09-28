from types import SimpleNamespace as NS
from django.test import TestCase
from home.models import TbAntecedente, TbTalento, TbTracoracial
from home.content_versions import seal_ruleset
from home.versioned_classes import EVALUATOR, VOCABULARY
from home.versioned_origins import snapshot_origins, VersionedOrigins
from home.character_engine import _antecedente, _talentos


class VersionedOriginsTests(TestCase):
    def setUp(self):
        self.background = TbAntecedente.objects.create(nome='Scholar', slug='frozen-scholar', descricao='', tags_json=['ca:+1'])
        self.talent = TbTalento.objects.create(nome='Gift', slug='frozen-gift', descricao='', tags_json=['ca:+2'], atrib_forca=True)
        self.trait = TbTracoracial.objects.create(nome='Racial gift', descricao='', talento_racial=True, tags_json=['ca:+3'])
        self.ruleset = seal_ruleset([snapshot_origins()], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.selected = [NS(id_talento_id=self.talent.pk, categoria='geral', nome='Gift'),
                         NS(id_talento_id=None, categoria='', nome=self.trait.nome)]
        self.person = NS(id_antecedente_id=self.background.pk, id_raca_id=None,
                         id_linhagem_id=None, id_essencia_id=None,
                         talentos=NS(all=lambda: self.selected))

    def values(self):
        features = _antecedente(self.person, ruleset=self.ruleset) + _talentos(self.person, ruleset=self.ruleset)
        return [(kind, name, obj.tags_json) for kind, name, obj, _ in features]

    def test_frozen_sources_survive_catalog_changes_and_deletion(self):
        before = self.values()
        self.assertEqual([v[2] for v in before], [['ca:+1'], ['ca:+2'], ['ca:+3']])
        for obj in (self.background, self.talent, self.trait):
            obj.tags_json = ['ca:+9']
            obj.save()
        self.assertEqual(self.values(), before)
        self.background.delete()
        self.talent.delete()
        self.trait.delete()
        self.assertEqual(self.values(), before)

    def test_missing_identity_fails_closed(self):
        self.person.id_antecedente_id = 999999
        with self.assertRaisesMessage(ValueError, 'Background absent'):
            self.values()
        self.person.id_antecedente_id = None
        self.selected[0].id_talento_id = 999999
        with self.assertRaisesMessage(ValueError, 'Talent absent'):
            self.values()

    def test_current_selection_is_preserved_and_empty_background_is_valid(self):
        self.selected.clear()
        self.person.id_antecedente_id = None
        self.assertEqual(self.values(), [])

    def test_objects_are_isolated_and_asi_metadata_is_frozen(self):
        catalog = VersionedOrigins(self.ruleset)
        self.talent.atrib_forca = False
        self.talent.save()
        with self.assertNumQueries(0):
            obj = catalog.talents(self.person)[0][2]
            self.assertTrue(obj.atrib_forca)
            obj.tags_json.append('ca:+99')
            self.assertEqual(catalog.talents(self.person)[0][2].tags_json, ['ca:+2'])

    def test_snapshot_replay_is_stable(self):
        self.assertEqual(snapshot_origins().pk, snapshot_origins().pk)
