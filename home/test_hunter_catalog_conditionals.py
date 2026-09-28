import json
from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from .models import TbClassehabilidade, TbRecursoclasse, TbRuleset
from .hunter_catalog import compose_choice_revision, CONDITIONAL_SOURCES
from .hunter_choices import favored_state
from .hunter_preparation import preparation
from .hunter_combat import evaluate
from .character_engine import derive
from .versioned_classes import VersionedClassCatalog


class HunterConditionalCatalogTests(TestCase):
    def setUp(self):
        from .test_hunter_catalog_passives import HunterCatalogPassiveTests
        HunterCatalogPassiveTests.setUp(self)
        self.conditional_ids = {key: TbClassehabilidade.objects.create(
            id_classe=self.cl, nome='Renamed legacy ' + key, niveladquirido=1,
            tags_json=['ca:+20']).pk for key in CONDITIONAL_SOURCES}
        self.resource = TbRecursoclasse.objects.create(id_classe=self.cl,
            nome='Old favored', slug='inimigo-favorito', tipo='choice',
            valores_json={'2': '1', '6': '2', '14': '3'})
        self.conditional_ids['favored_resource'] = self.resource.pk
        self.bind(self.data)
        self.old = self.ruleset

    def compose(self, ruleset=None, ids=None):
        return compose_choice_revision(ruleset or self.old, class_id=self.cl.pk,
            feature_ids=self.choice_ids, passive_ids=self.passive_ids,
            conditional_ids=self.conditional_ids if ids is None else ids)

    def test_composed_sheet_and_target_conditions_at_every_level(self):
        old_sheet = derive(self.person, ruleset=self.old)
        new = self.compose()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ruleset_id, self.old.pk)
        self.assertEqual(derive(self.person, ruleset=self.old), old_sheet)
        self.profile.ruleset = new
        self.profile.save()
        for level in range(1, 21):
            self.pc.nivel = level
            self.pc.id_subclasse = self.sub if level >= 3 else None
            self.pc.save()
            self.profile.refresh_from_db()
            sheet = derive(self.person, ruleset=new)
            self.assertLess(sheet['ca'], 20)
            self.assertEqual(sheet['ataques']['quantidade'], 2 if level >= 5 else 1)
            prepared = preparation(self.profile)
            normal = evaluate(prepared)
            first = evaluate(prepared, marked=True, first_attack=True)
            later = evaluate(prepared, marked=True)
            secret = evaluate(prepared, secret_affected=True, third_attack_available=False)
            self.assertFalse(normal['attack_advantage'])
            self.assertEqual(first['attack_advantage'], level >= 11)
            self.assertEqual(later['attack_advantage'], level == 20)
            self.assertEqual(secret['attack_advantage'], level == 20)
            self.assertEqual(secret['attacks'], 2 if level >= 5 else 1)
            self.assertEqual(normal['bonus_hide'], level >= 13)
        self.assertTrue(TbClassehabilidade.objects.get(pk=self.conditional_ids['predator']).tags_json)
        self.assertEqual(self.resource.valores_json, {'2': '1', '6': '2', '14': '3'})

    def test_favored_selection_follows_new_unlocks_without_duplicate_picks(self):
        self.profile.ruleset = self.compose()
        self.profile.save()
        selected = []
        for level, count in ((2, 1), (6, 1), (8, 2), (14, 3)):
            self.pc.nivel = level
            self.pc.id_subclasse = self.sub if level >= 3 else None
            self.pc.save()
            self.profile.refresh_from_db()
            self.assertEqual(favored_state(self.profile)['limit'], count)
            selected = ['bestas', 'fadas', 'gigantes'][:count]
            response = self.client.post(self.url, {'action': 'favored',
                'favored': selected, 'version': self.profile.version})
            self.assertEqual(response.status_code, 302)
            self.profile.refresh_from_db()
            self.assertEqual(favored_state(self.profile)['selected'], selected)
            self.assertEqual(self.person.escolhas.filter(tipo='hunter-favored').count(), count)
        response = self.client.post(self.url, {'action': 'favored', 'favored': ['bestas'] * 3,
            'version': self.profile.version})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(favored_state(self.profile)['selected'], selected)

    def test_command_dry_run_idempotence_and_invalid_mapping(self):
        count = TbRuleset.objects.count()
        output = StringIO()
        call_command('compose_hunter_choices', ruleset=self.old.pk, class_id=self.cl.pk,
            preparation_id=self.choice_ids['preparation'], expertise_id=self.choice_ids['expertise'],
            passive_ids=json.dumps(self.passive_ids), conditional_ids=json.dumps(self.conditional_ids),
            stdout=output)
        result = json.loads(output.getvalue())
        self.assertTrue(result['conditionals_replaced'])
        self.assertFalse(result['persisted'])
        self.assertEqual(TbRuleset.objects.count(), count)
        new = self.compose()
        self.assertEqual(new.checksum, result['checksum'])
        self.assertEqual(self.compose(new).pk, new.pk)
        count = TbRuleset.objects.count()
        for bad in ({}, dict(self.conditional_ids, favored=True),
                    dict(self.conditional_ids, hide=self.passive_ids['relentless']),
                    dict(self.conditional_ids, favored_resource=999999)):
            with self.assertRaises(ValueError):
                self.compose(ids=bad)
        self.assertEqual(TbRuleset.objects.count(), count)
