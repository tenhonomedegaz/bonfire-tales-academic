import json
from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from .models import TbClassehabilidade, TbRecursoclasse, TbRuleset
from .hunter_catalog import compose_choice_revision
from .versioned_classes import VersionedClassCatalog, resolved_classes
from .spellcasting import class_spellcasting_contract, resource_limit_at
from .character_engine import derive


class HunterSpellCatalogTests(TestCase):
    def setUp(self):
        from .test_hunter_spell_progression import HunterSpellProgressionTests
        HunterSpellProgressionTests.setUp(self)
        self.choices = {key: TbClassehabilidade.objects.create(id_classe=self.cl,
            nome=key, niveladquirido=1).pk for key in ('preparation', 'expertise')}
        self.feature = TbClassehabilidade.objects.create(id_classe=self.cl,
            nome='Renamed old spellcasting', niveladquirido=1,
            tags_json=['ca:+99', 'spellcasting{ability:int, list:cacador, slots:full, mode:prepared}'])
        self.slots = [TbRecursoclasse.objects.create(id_classe=self.cl,
            nome='Old slots %s' % circle, slug='%so' % circle, tipo='table-only',
            valores_json={'1': '99'}) for circle in range(1, 6)]
        self.bind(self.data)
        self.old = self.ruleset
        self.ids = {'feature': self.feature.pk, 'slots': [r.pk for r in self.slots]}

    def compose(self, ruleset=None, ids=None):
        return compose_choice_revision(ruleset or self.old, class_id=self.cl.pk,
            feature_ids=self.choices, spellcasting_ids=self.ids if ids is None else ids)

    def test_composed_creator_sheet_spend_and_rest(self):
        from .test_hunter_spell_progression import HunterSpellProgressionTests
        before = derive(self.person, ruleset=self.old)
        self.assertGreater(before['ca'], 90)
        new = self.compose()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ruleset_id, self.old.pk)
        self.assertEqual(derive(self.person, ruleset=self.old), before)
        self.ruleset = new
        self.profile.ruleset = new
        self.profile.save()
        self.assertLess(derive(self.person, ruleset=new)['ca'], 20)
        HunterSpellProgressionTests.test_creator_offers_two_choices_in_addition_to_fixed_mark(self)
        HunterSpellProgressionTests.test_first_level_sheet_spend_rest_and_preparation_use_table(self)
        self.assertEqual(TbRecursoclasse.objects.get(pk=self.slots[0].pk).valores_json, {'1': '99'})
        self.assertTrue(TbClassehabilidade.objects.get(pk=self.feature.pk).tags_json)

    def test_both_abilities_and_all_frozen_resource_tables_agree(self):
        new = self.compose()
        self.profile.ruleset = new
        self.profile.save()
        for ability in ('int', 'wis'):
            self.profile.ability = ability
            self.profile.save()
            cl = resolved_classes(new, [self.pc])[0].id_classe
            for row in self.data['progression']:
                contract = class_spellcasting_contract(cl, level=row['level'], ruleset=new)
                self.assertEqual(contract['ability'], ability)
                self.assertEqual(contract['spell_limit']['value'], str(row['prepared_spells']))
                for circle, count in enumerate(row['slots'], 1):
                    self.assertEqual(resource_limit_at({'kind': 'resource', 'value': '%so' % circle},
                        cl, level=row['level'], ruleset=new), count)
        feature = next(h for h in VersionedClassCatalog(new, self.cl.pk).collections[TbClassehabilidade]
                       if h.pk == self.feature.pk)
        self.assertEqual(feature.tags_json, [])
        self.assertTrue(feature.descricao)

    def test_invalid_mapping_old_revision_and_command_idempotence(self):
        output = StringIO()
        count = TbRuleset.objects.count()
        call_command('compose_hunter_choices', ruleset=self.old.pk, class_id=self.cl.pk,
            preparation_id=self.choices['preparation'], expertise_id=self.choices['expertise'],
            spellcasting_ids=json.dumps(self.ids), stdout=output)
        self.assertEqual(TbRuleset.objects.count(), count)
        result = json.loads(output.getvalue())
        self.assertFalse(result['persisted'])
        self.assertTrue(result['spellcasting_replaced'])
        new = self.compose()
        self.assertEqual(new.checksum, result['checksum'])
        self.assertEqual(self.compose(new).pk, new.pk)
        count = TbRuleset.objects.count()
        for ids in ({}, dict(self.ids, feature=True), dict(self.ids, slots=self.ids['slots'][::-1]),
                    dict(self.ids, slots=[self.slots[0].pk] * 5)):
            with self.assertRaises(ValueError):
                self.compose(ids=ids)
        self.assertEqual(TbRuleset.objects.count(), count)
        self.data.pop('spellcasting_progression')
        self.bind(self.data)
        with self.assertRaises(ValueError):
            self.compose(self.ruleset)
