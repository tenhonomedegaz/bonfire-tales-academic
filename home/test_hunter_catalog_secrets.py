import json
from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from django.urls import reverse
from .models import TbClassehabilidade, TbRecursoclasse, TbRuleset
from .hunter_catalog import compose_choice_revision
from .versioned_classes import VersionedClassCatalog


class HunterSecretCatalogTests(TestCase):
    def setUp(self):
        from .test_hunter_spells import HunterSpellGrantTests
        self.bind = HunterSpellGrantTests.bind.__get__(self)
        HunterSpellGrantTests.setUp(self)
        self.mapping = {}
        for key in ('preparation', 'expertise', 'secrets'):
            self.mapping[key] = TbClassehabilidade.objects.create(id_classe=self.cl,
                nome='Renamed ' + key, niveladquirido=1,
                tags_json=['pick:opcao:2']).pk
        self.points = TbRecursoclasse.objects.create(id_classe=self.cl,
            nome='Old points', slug='old-points', tipo='consumable',
            nivel=2, valor='99', reset='long_rest')
        self.known = TbRecursoclasse.objects.create(id_classe=self.cl,
            nome='Old known', slug='old-known', tipo='choice', nivel=2, valor='9')
        self.bind(self.data)
        self.old = self.ruleset
        self.ids = {'feature': self.mapping.pop('secrets'),
                    'points': self.points.pk, 'known': self.known.pk}

    def compose(self, ruleset=None, ids=None):
        return compose_choice_revision(ruleset or self.old, class_id=self.cl.pk,
            feature_ids=self.mapping, secrets_ids=self.ids if ids is None else ids)

    def test_use_replay_and_rest_have_one_reserve_preserving_old_revision(self):
        from .test_hunter_resources import HunterResourceFlowTests
        new = self.compose()
        # Composition alone must not migrate a character.
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.ruleset_id, self.old.pk)
        self.assertEqual(len(VersionedClassCatalog(self.old, self.cl.pk).collections[TbRecursoclasse]), 2)
        self.assertEqual(VersionedClassCatalog(new, self.cl.pk).collections[TbRecursoclasse], [])
        self.assertEqual(TbRecursoclasse.objects.get(pk=self.points.pk).valor, '99')
        self.assertTrue(TbClassehabilidade.objects.get(pk=self.ids['feature']).tags_json)
        # Explicit activation only in this test fixture.
        self.profile.ruleset = new
        self.profile.save()
        command = HunterResourceFlowTests.command(self, enhanced=True)
        self.assertEqual(self.client.post(self.url, command).status_code, 302)
        resource = self.person.recursos.get()
        self.assertEqual((resource.atual, resource.maximo), (1, 3))
        rest = reverse('personagem_descansar', args=[self.person.pk])
        for event, expected in (('curto', 1), ('longo', 3), ('longo', 3)):
            self.assertEqual(self.client.post(rest, {'tipo': event}).status_code, 302)
            resource.refresh_from_db()
            self.assertEqual(resource.atual, expected)
            self.assertFalse(self.person.recursos.filter(nome='Old points').exists())
            self.assertEqual(self.person.recursos.filter(chave__startswith='hunter:').count(), 1)
        self.assertEqual(self.client.post(self.url, command).status_code, 302)
        resource.refresh_from_db()
        self.assertEqual(resource.atual, 3)

    def test_mapping_validation_idempotence_and_command_dry_run(self):
        count = TbRuleset.objects.count()
        output = StringIO()
        call_command('compose_hunter_choices', ruleset=self.old.pk, class_id=self.cl.pk,
            preparation_id=self.mapping['preparation'], expertise_id=self.mapping['expertise'],
            secrets_ids=json.dumps(self.ids), stdout=output)
        result = json.loads(output.getvalue())
        self.assertTrue(result['secrets_replaced'])
        self.assertFalse(result['persisted'])
        self.assertEqual(TbRuleset.objects.count(), count)
        new = self.compose()
        self.assertEqual(new.checksum, result['checksum'])
        self.assertEqual(self.compose(new).pk, new.pk)
        count = TbRuleset.objects.count()
        for ids in ({}, dict(self.ids, points=True), dict(self.ids, points=999999),
                    dict(self.ids, points=self.known.pk),
                    dict(self.ids, feature=self.mapping['expertise'])):
            with self.assertRaises(ValueError):
                self.compose(ids=ids)
        self.assertEqual(TbRuleset.objects.count(), count)
