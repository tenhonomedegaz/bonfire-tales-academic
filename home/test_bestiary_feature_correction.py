from copy import deepcopy
from types import SimpleNamespace

from django.test import SimpleTestCase

from home.bestiary_audit import statblock_hash
from home.bestiary_feature_retag import (
    FeatureRetagConflict, reviewed_statblock, source_entries_hash,
)
from home.management.commands.importar_bestiario_csv import _split_secao


class ReviewedFeatureCorrectionTests(SimpleTestCase):
    def setUp(self):
        self.source = {
            'Name': 'Test Dragon',
            'Actions': 'Rend. Melee Attack Roll: +8, reach 10 ft. '
                       'Hit: 14 (2d8 + 5) Thunder damage.',
        }
        action = _split_secao(self.source['Actions'], {})[0]
        self.old_tags = ['instant{attack:melee, dmg:2d8+5(trovao)}']
        self.new_tags = ['instant{attack:melee, dmg:2d8+5(trovejante)}']
        self.creature = SimpleNamespace(
            pk=41, slug='test-dragon', comunidade=False, autor_id=None,
            statblock_json={
                'name_en': self.source['Name'],
                'actions': [{**action, 'tags_json': self.old_tags}],
                'traits': [{'name': 'Intocado', 'entries': ['Regra.']}],
            },
        )
        revised = deepcopy(self.creature.statblock_json)
        revised['actions'][0]['tags_json'] = self.new_tags
        self.proposal = {
            'pk': 41, 'slug': 'test-dragon',
            'before_sha256': statblock_hash(self.creature.statblock_json),
            'after_sha256': statblock_hash(revised),
            'features': [{
                'index': 0, 'name_en': action['name_en'],
                'source_entries_sha256': source_entries_hash(action['entries']),
                'expected_tags': self.old_tags, 'tags': self.new_tags,
            }],
        }

    def test_replaces_only_reviewed_tags_and_replay_is_noop(self):
        revised, changed = reviewed_statblock(self.creature, self.source, self.proposal)
        self.assertTrue(changed)
        self.assertEqual(revised['actions'][0]['tags_json'], self.new_tags)
        self.assertEqual(revised['traits'], self.creature.statblock_json['traits'])
        self.assertEqual(self.creature.statblock_json['actions'][0]['tags_json'], self.old_tags)
        self.creature.statblock_json = revised
        replay, changed = reviewed_statblock(self.creature, self.source, self.proposal)
        self.assertFalse(changed)
        self.assertEqual(replay, revised)

    def test_rejects_stale_tags_source_and_hash(self):
        stale = deepcopy(self.creature)
        stale.statblock_json['actions'][0]['tags_json'] = ['instant{dmg:9d9(fogo)}']
        with self.assertRaises(FeatureRetagConflict):
            reviewed_statblock(stale, self.source, self.proposal)

        changed_source = dict(self.source, Actions=self.source['Actions'].replace('Thunder', 'Fire'))
        with self.assertRaises(FeatureRetagConflict):
            reviewed_statblock(self.creature, changed_source, self.proposal)

        altered = deepcopy(self.proposal)
        altered['after_sha256'] = '0' * 64
        with self.assertRaises(FeatureRetagConflict):
            reviewed_statblock(self.creature, self.source, altered)

    def test_new_tag_manifest_without_expected_tags_still_works(self):
        creature = deepcopy(self.creature)
        creature.statblock_json['actions'][0]['tags_json'] = []
        proposal = deepcopy(self.proposal)
        proposal['before_sha256'] = statblock_hash(creature.statblock_json)
        proposal['features'][0].pop('expected_tags')
        proposal['features'][0]['tags'] = self.new_tags
        revised = deepcopy(creature.statblock_json)
        revised['actions'][0]['tags_json'] = self.new_tags
        proposal['after_sha256'] = statblock_hash(revised)
        result, changed = reviewed_statblock(creature, self.source, proposal)
        self.assertTrue(changed)
        self.assertEqual(result, revised)
