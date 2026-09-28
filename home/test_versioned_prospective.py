from django.test import TestCase
from home.test_versioned_derive import VersionedDeriveTests as Fixtures
from home.models import TbSubclasse, TbClassehabilidade, TbMagia
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items
from home.versioned_spells import snapshot_spells
from home.views import _pendencias_magias_levelup


class VersionedProspectiveTests(TestCase):
    def test_frozen_subclass_preview_is_read_only_and_level_gated(self):
        Fixtures.setUp(self)
        self.cl.tags_json = ['subclass-choices{2}']
        self.cl.save()
        sub = TbSubclasse.objects.create(id_classe=self.cl, nome='Old school', slug='old-school')
        feature = TbClassehabilidade.objects.create(id_classe=self.cl, id_subclasse=sub,
            nome='School casting', descricao='', niveladquirido=2,
            tags_json=['spellcasting{ability:int, list:pinned-derive, slots:third, mode:known, cantrip_limit{fixed:1}}'])
        spell = TbMagia.objects.create(nome='Old cantrip', slug='old-cantrip', nivel=0, classes=self.cl.nome)
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        pending = {'subclasse': True, 'subclasses': [{'id': sub.pk}]}
        before = _pendencias_magias_levelup(self.person, pending, ruleset=ruleset)
        self.assertTrue(before['prospectiva'])
        self.assertEqual(before['subclasses_prospectivas'], ['old-school'])
        self.assertEqual(before['lista_truques'][0]['slug'], 'old-cantrip')
        sub.slug = 'changed-school'
        sub.save()
        feature.tags_json = []
        feature.save()
        spell.slug = 'changed-cantrip'
        spell.classes = ''
        spell.save()
        self.assertEqual(_pendencias_magias_levelup(self.person, pending, ruleset=ruleset), before)
        self.pc.refresh_from_db()
        self.assertIsNone(self.pc.id_subclasse_id)
        self.pc.nivel = 1
        self.pc.save()
        self.assertIsNone(_pendencias_magias_levelup(self.person, pending, ruleset=ruleset))
        with self.assertRaisesMessage(ValueError, 'Subclass is not part'):
            _pendencias_magias_levelup(self.person,
                {'subclasse': True, 'subclasses': [{'id': -1}]}, ruleset=ruleset)
