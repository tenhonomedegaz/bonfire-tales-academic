import json
from io import StringIO
from django.core.management import call_command
from django.db import transaction
from .test_criador import _CriadorBase
from .test_creator_pinned_catalog import CreatorPinnedCatalogTests
from .models import TbClasse, TbClassehabilidade, TbMagia, TbPersonagemCacador, TbRuleset
from .content_versions import create_revision, seal_ruleset
from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog
from .hunter_rework import catalog
from .hunter_catalog import compose_choice_revision
from . import views, picks


class HunterCatalogTests(_CriadorBase):
    def test_imported_spellcasting_feature_and_slot_identities(self):
        from .models import TbRecursoclasse
        self.setup_catalog()
        ids = {'feature': 1019, 'slots': [2733, 2754, 2779, 2808, 2841]}
        new = compose_choice_revision(self.new, class_id=self.classe.pk,
            feature_ids=self.mapping, spellcasting_ids=ids)
        frozen = VersionedClassCatalog(new, self.classe.pk)
        feature = next(h for h in frozen.collections[TbClassehabilidade] if h.pk == 1019)
        self.assertEqual(feature.tags_json, [])
        self.assertEqual(feature.niveladquirido, 1)
        self.assertTrue(TbClassehabilidade.objects.get(pk=1019).tags_json)
        for circle, pk in enumerate(ids['slots']):
            resource = next(r for r in frozen.collections[TbRecursoclasse] if r.pk == pk)
            self.assertEqual(resource.valores_json,
                {str(row['level']): str(row['slots'][circle]) for row in catalog()['progression']})

    def test_imported_conditional_mapping_preserves_unmapped_rows(self):
        from .models import TbRecursoclasse
        from .versioned_classes import _fields
        self.setup_catalog()
        mapping = dict(favored=884, territory=1037, predator=1055, hide=1057,
                       domination=1077, favored_resource=2737)
        new = compose_choice_revision(self.new, class_id=self.classe.pk,
            feature_ids=self.mapping, conditional_ids=mapping)
        before = VersionedClassCatalog(self.new, self.classe.pk)
        after = VersionedClassCatalog(new, self.classe.pk)
        for model in (TbClassehabilidade, TbRecursoclasse):
            original = {r.pk: _fields(r) for r in before.collections[model]}
            changed = {r.pk: _fields(r) for r in after.collections[model]}
            self.assertEqual(set(original), set(changed))
            for pk in original:
                if pk not in mapping.values():
                    self.assertEqual(original[pk], changed[pk])
        features = {r.pk: r for r in after.collections[TbClassehabilidade]}
        for pk in (884, 1037, 1055, 1057, 1077):
            self.assertEqual(features[pk].tags_json, [])
            self.assertTrue(features[pk].descricao)
        resource = next(r for r in after.collections[TbRecursoclasse] if r.pk == 2737)
        self.assertEqual(resource.valores_json, {'2': '1', '8': '2', '14': '3'})
        self.assertEqual(TbRecursoclasse.objects.get(pk=2737).valores_json['6'], '2')

    def test_imported_secret_resources_and_feature_replaced_by_identity(self):
        from .models import TbRecursoclasse
        self.setup_catalog()
        composed = compose_choice_revision(self.new, class_id=self.classe.pk,
            feature_ids=self.mapping, secrets_ids={'feature': 1020, 'points': 3775, 'known': 2736})
        before = VersionedClassCatalog(self.new, self.classe.pk)
        after = VersionedClassCatalog(composed, self.classe.pk)
        self.assertEqual({r.pk for r in before.collections[TbRecursoclasse]} -
                         {r.pk for r in after.collections[TbRecursoclasse]}, {3775, 2736})
        secret = next(h for h in after.collections[TbClassehabilidade] if h.pk == 1020)
        self.assertEqual((secret.niveladquirido, secret.tags_json), (2, []))
        self.assertIn('Pontos de Segredo', secret.descricao)
        self.assertTrue(TbClassehabilidade.objects.get(pk=1020).tags_json)
        self.assertTrue(TbRecursoclasse.objects.filter(pk=3775).exists())

    def setup_catalog(self, *, compose=True):
        self.classe = TbClasse.objects.get(slug='cacador')
        # Explicit identities from the reviewed imported baseline.
        self.mapping = {'preparation': 881, 'expertise': 1021}
        if not TbMagia.objects.filter(nome_ingles="Hunter's Mark").exists():
            TbMagia.objects.create(nome='Mark', nome_ingles="Hunter's Mark", slug='mark-test', nivel=1)
        base = CreatorPinnedCatalogTests.seal(self, self.classe)
        self.old = seal_ruleset([e.revision for e in base.entries.select_related('revision')] + [
            create_revision('hunter-rework', catalog())],
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        if compose:
            self.new = compose_choice_revision(self.old, class_id=self.classe.pk, feature_ids=self.mapping)

    def test_creation_without_legacy_style_or_mastery_and_delayed_unlocks(self):
        self.setup_catalog()
        frozen = VersionedClassCatalog(self.new, self.classe.pk)
        ids = lambda level: {row[2].pk for row in frozen.features(level)}
        self.assertNotIn(881, ids(1))
        self.assertIn(881, ids(2))
        self.assertNotIn(1021, ids(2))
        self.assertIn(1021, ids(3))
        groups = picks.resolve_builder(frozen.classe, ruleset=self.new)
        self.assertFalse(any(g['kind'] in ('arma', 'opcao', 'pericia_expertise') for g in groups))
        payload = self._payload('cacador')
        payload.update(hunter_ability='int', estilo_luta='', maestrias=[])
        resolved, _ = views._criador_resolver(payload, ruleset=self.new, class_id=self.classe.pk)
        payload['magias'] = [row['slug'] for row in resolved['conj']['magias_nv1']][:2]
        resolved, errors = views._criador_resolver(payload, ruleset=self.new, class_id=self.classe.pk)
        self.assertEqual(errors, [])
        user = self._novo_usuario('composed-hunter')
        with transaction.atomic():
            person = views._criador_persistir(user, payload, resolved, strict_spell_choices=True)
        self.assertEqual(TbPersonagemCacador.objects.get(
            personagem_classe__id_personagem=person).ruleset_id, self.new.pk)
        self.assertFalse(person.escolhas.filter(id_opcao__isnull=False).exists())
        self.assertTrue(person.magias.filter(sempre_preparada=True,
            id_magia__nome_ingles="Hunter's Mark").exists())

    def test_legacy_source_is_unchanged_and_composition_is_idempotent(self):
        self.setup_catalog()
        self.assertEqual(TbClassehabilidade.objects.get(pk=881).niveladquirido, 1)
        self.assertIn(881, {row[2].pk for row in VersionedClassCatalog(self.old, self.classe.pk).features(1)})
        self.assertEqual(compose_choice_revision(self.new, class_id=self.classe.pk,
            feature_ids=self.mapping).pk, self.new.pk)
        count = TbRuleset.objects.count()
        for mapping in ({'preparation': 881, 'expertise': 881},
                        {'preparation': 999999, 'expertise': 1021}):
            with self.assertRaises(ValueError):
                compose_choice_revision(self.old, class_id=self.classe.pk, feature_ids=mapping)
        self.assertEqual(TbRuleset.objects.count(), count)

    def test_command_dry_run_and_apply_do_not_bind_characters(self):
        self.setup_catalog(compose=False)
        count = TbRuleset.objects.count()
        checksum = None
        for apply in (False, True):
            output = StringIO()
            call_command('compose_hunter_choices', ruleset=self.old.pk, class_id=self.classe.pk,
                preparation_id=881, expertise_id=1021, apply=apply, stdout=output)
            result = json.loads(output.getvalue())
            if checksum is None:
                checksum = result['checksum']
            self.assertEqual(result['checksum'], checksum)
            self.assertEqual(result['persisted'], apply)
            self.assertFalse(result['activated'])
            if apply:
                self.assertEqual(TbRuleset.objects.get(pk=result['ruleset']).checksum, checksum)
            else:
                self.assertIsNone(result['ruleset'])
            self.assertEqual(TbRuleset.objects.count(), count + int(apply))
        self.assertFalse(TbPersonagemCacador.objects.exists())

    def test_imported_baseline_passives_are_replaced_without_touching_other_features(self):
        self.setup_catalog()
        mapping = {'extra_attack': 1036, 'relentless': 1045, 'sharp_instinct': 1047,
                   'unshakable_will': 1066, 'predatory_instinct': 1068}
        composed = compose_choice_revision(self.new, class_id=self.classe.pk,
            feature_ids=self.mapping, passive_ids=mapping)
        from .versioned_classes import _fields
        before = VersionedClassCatalog(self.new, self.classe.pk)
        after = VersionedClassCatalog(composed, self.classe.pk)
        before_rows = {h.pk: _fields(h) for h in before.collections[TbClassehabilidade]}
        after_rows = {h.pk: _fields(h) for h in after.collections[TbClassehabilidade]}
        self.assertEqual(set(before_rows), set(after_rows))
        for pk in before_rows:
            if pk not in mapping.values():
                self.assertEqual(after_rows[pk], before_rows[pk])
        self.assertEqual(after_rows[1036]['nome'], 'Ataque Extra')
        self.assertEqual([after_rows[pk]['niveladquirido'] for pk in mapping.values()], [5, 7, 9, 15, 17])
        for pk in mapping.values():
            self.assertTrue(before_rows[pk]['tags_json'])
            self.assertEqual(after_rows[pk]['tags_json'], [])
            self.assertEqual(TbClassehabilidade.objects.get(pk=pk).tags_json, before_rows[pk]['tags_json'])
