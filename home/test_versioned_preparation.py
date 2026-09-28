from django.test import TestCase
from home.test_versioned_derive import VersionedDeriveTests as Fixtures
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items
from home.versioned_spells import snapshot_spells
from home.views import _magias_preparadas_info


class VersionedPreparationTests(TestCase):
    def test_panel_preserves_catalog_limits_and_live_preparation(self):
        Fixtures.setUp(self)
        self.cl.tags_json = ['spellcasting{ability:int, list:pinned-derive, slots:full, mode:prepared, spell_limit{formula:classlvl+int_mod}, pool:class_list}']
        self.cl.save()
        self.spell.classes = self.cl.nome
        self.spell.save()
        self.choice.origem = self.cl.nome
        self.choice.save()
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        ficha = {'atributos': {a: {'mod': 2} for a in ['FOR','DES','CON','INT','SAB','CAR']},
                 'nivel_total': 2, 'bonus_proficiencia': 2}
        before = _magias_preparadas_info(self.person, ficha, ruleset=ruleset)
        self.assertIsNotNone(before)
        self.assertEqual(before['limite'], 4)
        self.assertEqual(before['grupos'][0]['magias'][0]['slug'], 'pinned-spell')
        self.assertTrue(before['grupos'][0]['magias'][0]['marcada'])
        self.cl.nome = 'Changed name'
        self.cl.tags_json = []
        self.cl.save()
        self.spell.nome = 'Changed spell'
        self.spell.slug = 'changed-slug'
        self.spell.classes = ''
        self.spell.nivel = 9
        self.spell.save()
        self.assertEqual(_magias_preparadas_info(self.person, ficha, ruleset=ruleset), before)
        self.choice.preparada = False
        self.choice.save()
        after = _magias_preparadas_info(self.person, ficha, ruleset=ruleset)
        self.assertFalse(after['grupos'][0]['magias'][0]['marcada'])
        self.assertEqual(after['preparadas_count'], 0)

    def test_list_changes_and_missing_owned_spell_use_pinned_catalog(self):
        Fixtures.setUp(self)
        from home.models import TbMagia
        from home.spellcasting import character_spell_list_delta
        self.cl.tags_json = ['spellcasting{ability:int, list:pinned-derive, slots:full, mode:prepared}']
        self.cl.save()
        self.feature.tags_json = ['requires:spellcasting, modify:spellcasting{list}.add{spell:pinned_spell}']
        self.feature.save()
        ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        ficha = {'atributos': {a: {'mod': 2} for a in ['FOR','DES','CON','INT','SAB','CAR']},
                 'nivel_total': 2, 'bonus_proficiencia': 2}
        self.assertEqual(character_spell_list_delta(self.person, ruleset=ruleset)['add'], {'pinned-spell'})
        self.feature.tags_json = []
        self.feature.save()
        self.spell.slug = 'new-slug'
        self.spell.save()
        panel = _magias_preparadas_info(self.person, ficha, ruleset=ruleset)
        self.assertEqual(panel['grupos'][0]['magias'][0]['slug'], 'pinned-spell')
        new = TbMagia.objects.create(nome='Outside', slug='outside', nivel=1)
        self.choice.id_magia = new
        self.choice.save()
        with self.assertRaisesMessage(ValueError, 'Spell absent from pinned ruleset'):
            _magias_preparadas_info(self.person, ficha, ruleset=ruleset)
