from copy import deepcopy
from django.test import TestCase

from .hunter_rework import catalog
from .hunter_spells import granted_spells
from .models import TbMagia, TbPersonagemMagia, TbSubclasse
from .content_versions import create_revision, seal_ruleset
from .versioned_classes import inventory_class, EVALUATOR, VOCABULARY
from .versioned_spells import snapshot_spells


class HunterSpellGrantTests(TestCase):
    def setUp(self):
        from .test_hunter_preparation import HunterPersistentPreparationTests
        HunterPersistentPreparationTests.setUp(self)
        self.data = catalog()
        # These regression fixtures exercise revisions published before the
        # dedicated spell progression. New progression has its own integration tests.
        self.data.pop('spellcasting_progression', None)
        identities = {g['english']: g['catalog_identity'] for g in self.data['spell_grants']
                      if g.get('catalog_identity')}
        for i, english in enumerate(sorted({g['english'] for g in self.data['spell_grants']})):
            identity = identities.get(english, {})
            TbMagia.objects.create(nome='Frozen %s' % i, nome_ingles=english,
                                   slug=identity.get('slug', 'hunter-spell-%s' % i),
                                   nivel=identity.get('level', 1))
        self.subs = {o['id']: TbSubclasse.objects.create(id_classe=self.cl, nome=o['name'],
                     slug=o['id']) for o in self.data['orders']}
        self.bind(self.data)

    def bind(self, data):
        from .versioned_options import snapshot_options
        from .versioned_origins import snapshot_origins
        from .versioned_items import snapshot_magic_items, snapshot_mundane_items
        from .versioned_conditions import snapshot_conditions
        from .versioned_library import snapshot_library
        from .tag_engine.library import Library
        self.ruleset = seal_ruleset([
            create_revision('class-catalog:%s' % self.cl.pk, inventory_class(self.cl.pk)),
            create_revision('hunter-rework', data), snapshot_spells(), snapshot_options(),
            snapshot_origins(), snapshot_magic_items(), snapshot_mundane_items(),
            snapshot_conditions(), snapshot_library(raw=Library(prefer_db=False).raw),
        ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.profile.ruleset = self.ruleset
        self.profile.save()

    def test_every_order_and_level_grants_only_unlocked_spells(self):
        self.assertEqual(len(self.data['spell_grants']), 83)
        for order in self.data['orders']:
            for level in (3, 4, 5, 8, 9, 12, 13, 16, 17, 20):
                self.pc.id_subclasse = self.subs[order['id']]
                self.pc.nivel = level
                self.pc.save()
                grants = granted_spells(self.person, self.ruleset)
                self.assertEqual(len(grants), 1 + 2 * sum(level >= n for n in (3, 5, 9, 13, 17))
                                 + int(order['id'] in ('ordem-do-enxame', 'ordem-da-alianca-selvagem')))
                expected = {g['english'] for g in self.data['spell_grants']
                    if g['order'] in ('', order['id']) and g['level'] <= level}
                actual = set(TbMagia.objects.filter(slug__in=[g['slug'] for g in grants])
                             .values_list('nome_ingles', flat=True))
                self.assertEqual(actual, expected)

    def test_explicit_identity_handles_bad_english_metadata_without_guessing(self):
        TbMagia.objects.create(nome='Other spell', nome_ingles='Alter Self', slug='other', nivel=9)
        correct = TbMagia.objects.get(slug='confusao')
        correct.nome_ingles = 'Befuddlement'
        correct.save()
        self.bind(self.data)
        self.pc.nivel = 13
        self.pc.id_subclasse = self.subs['ordem-do-enxame']
        self.pc.save()
        self.assertIn('confusao', [g['slug'] for g in granted_spells(self.person, self.ruleset)])
        self.pc.id_subclasse = self.subs['ordem-dos-mutantes']
        self.pc.save()
        slugs = [g['slug'] for g in granted_spells(self.person, self.ruleset)]
        self.assertIn('alterar-se', slugs)
        self.assertNotIn('other', slugs)
        TbMagia.objects.filter(slug='alterar-se').update(nivel=9)
        self.bind(self.data)
        with self.assertRaisesMessage(ValueError, 'absent or ambiguous'):
            granted_spells(self.person, self.ruleset)

    def test_spell_tables_match_source_and_preparation_does_not_block_grants(self):
        import json
        import re
        from pathlib import Path
        source = json.loads((Path(__file__).parent / 'rules/hunter_content.json').read_text(encoding='utf-8'))
        for order in self.data['orders']:
            feature = next(f for f in source['features'] if f['order'] == order['name']
                           and f['name'].startswith('Magias'))
            blocks = re.split(r'(3|5|9|13|17)º ', feature['text'].split('Nível de Caçador Magias ', 1)[1])
            for i in range(1, len(blocks), 2):
                expected = re.findall(r'\[([^\]]+)\]', blocks[i + 1])
                self.assertEqual([g['english'] for g in self.data['spell_grants']
                    if g['order'] == order['id'] and g['level'] == int(blocks[i])
                    and not g.get('feature_grant')], expected)
        self.profile.selected = ['unknown-old-choice']
        self.profile.save()
        self.assertEqual(len(granted_spells(self.person, self.ruleset)), 3)

    def test_level_change_removes_only_managed_grants(self):
        from .views import _sync_magias_concedidas
        self.pc.nivel = 5
        self.pc.save()
        _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        self.assertEqual(self.person.magias.filter(sempre_preparada=True).count(), 5)
        acquired = TbPersonagemMagia.objects.create(id_personagem=self.person,
            id_magia=TbMagia.objects.get(nome_ingles='Alter Self'),
            nome='Acquired separately', nivel=2, sempre_preparada=False)
        self.pc.nivel = 3
        self.pc.save()
        _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        self.assertEqual(self.person.magias.filter(sempre_preparada=True).count(), 3)
        self.assertTrue(self.person.magias.filter(pk=acquired.pk).exists())

    def test_sync_persists_once_and_preserves_acquired_magic_and_frozen_names(self):
        from .views import _sync_magias_concedidas
        manual = TbPersonagemMagia.objects.create(id_personagem=self.person,
            nome='Purchased spell', nivel=1, preparada=True, sempre_preparada=False)
        _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        rows = list(self.person.magias.filter(sempre_preparada=True).values_list('pk', 'nome'))
        self.assertEqual(len(rows), 3)
        TbMagia.objects.update(nome='Changed', nome_ingles='Changed')
        _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        self.assertEqual(list(self.person.magias.filter(sempre_preparada=True)
                             .values_list('pk', 'nome')), rows)
        self.assertTrue(TbPersonagemMagia.objects.filter(pk=manual.pk).exists())

    def test_missing_reference_fails_atomically_and_old_revision_stays_unchanged(self):
        from .views import _sync_magias_concedidas
        data = deepcopy(self.data)
        next(g for g in data['spell_grants'] if not g['order'])['english'] = 'Absent spell'
        self.bind(data)
        with self.assertRaisesMessage(ValueError, 'absent or ambiguous'):
            _sync_magias_concedidas(self.person, ruleset=self.ruleset)
        self.assertFalse(TbPersonagemMagia.objects.filter(id_personagem=self.person).exists())
        data.pop('spell_grants')
        self.bind(data)
        self.assertEqual(granted_spells(self.person, self.ruleset), [])

    def test_legacy_has_no_grants_and_mismatched_revision_is_rejected(self):
        wrong = seal_ruleset([create_revision('unrelated', {'schema': 1})],
                             evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        with self.assertRaisesMessage(ValueError, 'differ'):
            granted_spells(self.person, wrong)
        self.profile.delete()
        self.assertEqual(granted_spells(self.person, wrong), [])
