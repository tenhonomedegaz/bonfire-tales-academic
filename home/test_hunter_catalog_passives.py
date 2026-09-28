from django.test import TestCase
from django.core.management import call_command, CommandError
from io import StringIO
import json
from .models import TbClassehabilidade, TbRuleset
from .hunter_catalog import compose_choice_revision, PASSIVE_SOURCES
from .versioned_classes import VersionedClassCatalog
from .character_engine import derive


class HunterCatalogPassiveTests(TestCase):
    def setUp(self):
        from .test_hunter_passives import HunterPassiveTests
        HunterPassiveTests.setUp(self)
        self.choice_ids = {}
        for key in ('preparation', 'expertise'):
            self.choice_ids[key] = TbClassehabilidade.objects.create(
                id_classe=self.cl, nome=key, niveladquirido=1, tags_json=[]).pk
        self.passive_ids = {}
        effects = ['attacks:=9', 'speed:+100ft', 'always_active{con_save:+99}',
                   'ca:+20', 'speed:+50ft']
        for key, tag in zip(PASSIVE_SOURCES, effects):
            self.passive_ids[key] = TbClassehabilidade.objects.create(
                id_classe=self.cl, nome='Renamed legacy ' + key,
                niveladquirido=1, tags_json=[tag]).pk
        self.bind(self.data)
        self.old = self.ruleset

    def compose(self):
        return compose_choice_revision(self.old, class_id=self.cl.pk,
            feature_ids=self.choice_ids, passive_ids=self.passive_ids)

    def test_real_sheet_replaces_by_identity_without_legacy_bonuses(self):
        self.pc.nivel = 17
        self.pc.save()
        old_sheet = derive(self.person, ruleset=self.old)
        self.assertEqual(old_sheet['ataques']['quantidade'], 9)
        new = self.compose()
        # Composition itself must not migrate the bound character.
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ruleset_id, self.old.pk)
        self.assertEqual(derive(self.person, ruleset=self.old), old_sheet)
        self.profile.ruleset = new
        self.profile.save()
        for level in (1, 4, 5, 6, 7, 8, 9, 14, 15, 16, 17, 20):
            with self.subTest(level=level):
                self.pc.nivel = level
                self.pc.id_subclasse = self.sub if level >= 3 else None
                self.pc.save()
                sheet = derive(self.person, ruleset=new)
                self.assertEqual(sheet['ataques']['quantidade'], 2 if level >= 5 else 1)
                self.assertEqual(sheet['velocidade'], '12 m / 40 ft' if level >= 7 else '9 m / 30 ft')
                self.assertLess(sheet['ca'], 20)
                self.assertLess(sheet['saves']['CON']['bonus'], 20)
                self.assertEqual('blindsight 30ft' in sheet['sentidos'], level >= 17)
                self.assertEqual('Possessão' in sheet['imunidades'], level >= 15)
        frozen = VersionedClassCatalog(new, self.cl.pk)
        features = {row[2].pk: row[2] for row in frozen.features(20)}
        for key, pk in self.passive_ids.items():
            self.assertEqual(features[pk].tags_json, [])
            self.assertTrue(features[pk].descricao)
            self.assertTrue(TbClassehabilidade.objects.get(pk=pk).tags_json)

    def test_command_idempotence_and_rejection_do_not_mutate_bindings(self):
        new = self.compose()
        self.assertEqual(compose_choice_revision(new, class_id=self.cl.pk,
            feature_ids=self.choice_ids, passive_ids=self.passive_ids).pk, new.pk)
        output = StringIO()
        call_command('compose_hunter_choices', ruleset=self.old.pk, class_id=self.cl.pk,
            preparation_id=self.choice_ids['preparation'], expertise_id=self.choice_ids['expertise'],
            passive_ids=json.dumps(self.passive_ids), stdout=output)
        self.assertEqual(json.loads(output.getvalue())['checksum'], new.checksum)
        count = TbRuleset.objects.count()
        for bad in ([], {}, {'extra_attack': True}, dict(self.passive_ids, relentless=999999)):
            with self.assertRaises(ValueError):
                compose_choice_revision(self.old, class_id=self.cl.pk,
                    feature_ids=self.choice_ids, passive_ids=bad)
        with self.assertRaises(CommandError):
            call_command('compose_hunter_choices', ruleset=self.old.pk, class_id=self.cl.pk,
                preparation_id=self.choice_ids['preparation'], expertise_id=self.choice_ids['expertise'],
                passive_ids='[]', stdout=StringIO())
        self.assertEqual(TbRuleset.objects.count(), count)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ruleset_id, self.old.pk)
