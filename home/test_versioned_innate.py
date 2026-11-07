from django.test import TestCase
from home.test_versioned_derive import VersionedDeriveTests as Fixtures
from home.content_versions import create_revision, seal_ruleset
from home.versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from home.versioned_options import snapshot_options
from home.versioned_origins import snapshot_origins
from home.versioned_items import snapshot_magic_items
from home.versioned_spells import snapshot_spells
from home.views import _innate_spell_uses, _innate_spell_labels


class VersionedInnateTests(TestCase):
    def setUp(self):
        Fixtures.setUp(self)
        self.feature.tags_json = ['cast{spell:pinned-spell, without{slot}, uses{2, reset:long_rest}}']
        self.feature.save()

    def seal(self):
        return seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            snapshot_options(), snapshot_origins(), snapshot_magic_items(), snapshot_spells()],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)

    def test_uses_and_labels_remain_frozen_and_follow_live_level(self):
        ruleset = self.seal()
        before = _innate_spell_uses(self.person, ruleset=ruleset)
        self.assertEqual(before[('Old feature', 'pinned-spell')]['maximo'], 2)
        labels = _innate_spell_labels(self.person, ruleset=ruleset)
        self.feature.nome = 'New feature'
        self.feature.tags_json = []
        self.feature.save()
        self.spell.slug = 'new-spell'
        self.spell.save()
        self.assertEqual(_innate_spell_uses(self.person, ruleset=ruleset), before)
        self.assertEqual(_innate_spell_labels(self.person, ruleset=ruleset), labels)
        self.assertEqual(_innate_spell_uses(self.person), {})
        self.pc.nivel = 0
        self.pc.save()
        self.assertEqual(_innate_spell_uses(self.person, ruleset=ruleset), {})

    def test_missing_frozen_target_is_rejected(self):
        self.feature.tags_json = ['cast{spell:missing-spell, without{slot}, uses{1, reset:long_rest}}']
        self.feature.save()
        with self.assertRaisesMessage(ValueError, 'Innate spell absent'):
            _innate_spell_uses(self.person, ruleset=self.seal())
