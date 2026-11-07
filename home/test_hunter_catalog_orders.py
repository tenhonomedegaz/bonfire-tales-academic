import json
from copy import deepcopy
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.utils.text import slugify

from .content_versions import create_revision, resolve_content, seal_ruleset
from .hunter_catalog import compose_order_revision
from .models import TbClassehabilidade, TbSubclasse
from .test_criador import _CriadorBase
from .test_hunter_catalog import HunterCatalogTests
from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog


class HunterOrderCatalogTests(_CriadorBase):
    setup_catalog = HunterCatalogTests.setup_catalog
    def _with_new_order_identities(self):
        self.setup_catalog()
        reference = json.loads((Path(__file__).parent / 'rules/hunter_content.json').read_text(encoding='utf-8'))
        identity = 'class-catalog:%s' % self.classe.pk
        payload = deepcopy(resolve_content(self.new, identity,
            evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY))
        order_ids = {slugify(name): 50001 + index
                     for index, name in enumerate(reference['orders'])}
        for slug, pk in order_ids.items():
            name = next(name for name in reference['orders'] if slugify(name) == slug)
            payload['collections'][TbSubclasse._meta.label_lower].append({
                'id_subclasse': pk, 'id_classe_id': self.classe.pk,
                'nome': name, 'slug': slug + '-rework', 'tagline': None})
        revision = create_revision(identity, payload)
        revisions = [entry.revision for entry in self.new.entries.select_related('revision')
                     if entry.identity != identity]
        base = seal_ruleset(revisions + [revision], evaluator_version=EVALUATOR,
                            vocabulary_version=VOCABULARY)
        return base, reference, order_ids

    def test_all_eight_orders_and_59_features_follow_reference_at_every_unlock(self):
        base, reference, order_ids = self._with_new_order_identities()
        composed = compose_order_revision(base, class_id=self.classe.pk, order_ids=order_ids)
        old = VersionedClassCatalog(base, self.classe.pk)
        new = VersionedClassCatalog(composed, self.classe.pk)
        self.assertEqual(compose_order_revision(composed, class_id=self.classe.pk,
                         order_ids=order_ids).pk, composed.pk)
        old_rows = {row.pk: row for row in old.collections[TbClassehabilidade]}
        new_rows = {row.pk: row for row in new.collections[TbClassehabilidade]}
        for pk, row in old_rows.items():
            self.assertEqual(row.nome, new_rows[pk].nome)
            self.assertEqual(row.descricao, new_rows[pk].descricao)
            self.assertEqual(row.tags_json, new_rows[pk].tags_json)
        self.assertEqual(len(new_rows) - len(old_rows), 59)
        for slug, pk in order_ids.items():
            name = next(name for name in reference['orders'] if slugify(name) == slug)
            expected = [row for row in reference['features'] if row['order'] == name]
            for level in (1, 3, 5, 6, 9, 10, 13, 14, 17, 18, 20):
                actual = [entry[2] for entry in new.features(level, pk)
                          if entry[2].id_subclasse_id == pk]
                self.assertEqual({(row.nome, row.descricao, row.niveladquirido)
                                  for row in actual},
                                 {(row['name'], row['text'], row['level'])
                                  for row in expected if row['level'] <= level})

    def test_legacy_identity_or_incomplete_mapping_is_rejected_without_writes(self):
        base, _reference, order_ids = self._with_new_order_identities()
        from .models import TbRuleset
        before = TbRuleset.objects.count()
        for invalid in ({**order_ids, 'ordem-do-enxame': 116},
                        {key: pk for key, pk in order_ids.items() if key != 'ordem-do-enxame'},
                        {**order_ids, 'ordem-do-enxame': 50001}):
            with self.assertRaises(ValueError):
                compose_order_revision(base, class_id=self.classe.pk, order_ids=invalid)
        self.assertEqual(TbRuleset.objects.count(), before)

    def test_command_simulates_then_persists_without_activation(self):
        base, _reference, order_ids = self._with_new_order_identities()
        from .models import TbPersonagemCacador, TbRuleset
        before = TbRuleset.objects.count()
        checksums = []
        for apply in (False, True):
            output = StringIO()
            call_command('compose_hunter_choices', ruleset=base.pk,
                class_id=self.classe.pk, preparation_id=881, expertise_id=1021,
                order_ids=json.dumps(order_ids), apply=apply, stdout=output)
            result = json.loads(output.getvalue())
            self.assertTrue(result['orders_composed'])
            self.assertFalse(result['activated'])
            self.assertEqual(result['persisted'], apply)
            checksums.append(result['checksum'])
            # The command seals the choice catalog and then the Order catalog.
            self.assertEqual(TbRuleset.objects.count(), before + 2 * int(apply))
        self.assertEqual(checksums[0], checksums[1])
        self.assertFalse(TbPersonagemCacador.objects.exists())

    def test_additive_order_provision_and_composition_preserve_legacy_rows(self):
        self.setup_catalog()
        old_subclasses = {row.pk: (row.nome, row.slug)
                          for row in TbSubclasse.objects.filter(id_classe=self.classe)}
        output = StringIO()
        call_command('prepare_hunter_orders', stdout=output)
        simulated = json.loads(output.getvalue())
        self.assertEqual(simulated['created'], 0)
        self.assertEqual(TbSubclasse.objects.filter(id_classe=self.classe).count(),
                         len(old_subclasses))
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        provisioned = json.loads(output.getvalue())
        self.assertEqual(provisioned['created'], 8)
        self.assertEqual(len(set(provisioned['order_ids'].values())), 8)
        output = StringIO()
        call_command('prepare_hunter_orders', apply=True, stdout=output)
        self.assertEqual(json.loads(output.getvalue())['created'], 0)
        for pk, value in old_subclasses.items():
            row = TbSubclasse.objects.get(pk=pk)
            self.assertEqual((row.nome, row.slug), value)
        composed = compose_order_revision(self.new, class_id=self.classe.pk,
                                          order_ids=provisioned['order_ids'])
        frozen = VersionedClassCatalog(composed, self.classe.pk)
        self.assertEqual(set(provisioned['order_ids'].values()) & set(frozen.subclasses),
                         set(provisioned['order_ids'].values()))
        self.assertEqual(len([row for row in frozen.collections[TbClassehabilidade]
                              if row.id_subclasse_id in provisioned['order_ids'].values()]), 59)
        self.assertEqual(set(VersionedClassCatalog(self.new, self.classe.pk).subclasses),
                         set(old_subclasses))
