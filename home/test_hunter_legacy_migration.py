"""Legacy multiclass migration into a clean, fully composed class snapshot."""
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from . import test_hunter_bugfix as boundary
from .class_revision_editor import create_class_revision
from .content_versions import create_revision, seal_ruleset
from .hunter_catalog import compose_choice_revision, compose_order_revision
from .hunter_regularization import _reviewed_target
from .hunter_rework import catalog
from .models import (TbClassPublication, TbClassehabilidade, TbPersonagem,
                     TbPersonagemCacador, TbPersonagemClasse, TbSubclasse)
from .test_criador import _CriadorBase
from .versioned_classes import EVALUATOR, VOCABULARY, VersionedClassCatalog, inventory_class


class HunterLegacyMigrationTests(_CriadorBase):
    def setUp(self):
        boundary.HunterBugfixTests.setUp(self)
        composed = compose_choice_revision(self.old, class_id=self.classe.pk,
            feature_ids=self.mapping,
            passive_ids=dict(extra_attack=1036, relentless=1045, sharp_instinct=1047,
                             unshakable_will=1066, predatory_instinct=1068),
            secrets_ids=dict(feature=1020, points=3775, known=2736),
            conditional_ids=dict(favored=884, territory=1037, predator=1055,
                                 hide=1057, domination=1077, favored_resource=2737),
            spellcasting_ids=dict(feature=1019, slots=[2733, 2754, 2779, 2808, 2841]),
            mark_feature_id=880)
        composed = compose_order_revision(composed, class_id=self.classe.pk, order_ids=self.orders)
        frozen = VersionedClassCatalog(composed, self.classe.pk)
        legacy_ids = set(frozen.subclasses) - set(self.orders.values())
        changes = [dict(model='home.tbclassehabilidade', action='remove', pk=row.pk)
                   for row in frozen.collections[TbClassehabilidade]
                   if row.id_subclasse_id in legacy_ids]
        changes += [dict(model='home.tbsubclasse', action='remove', pk=pk)
                    for pk in sorted(legacy_ids)]
        clean = create_class_revision(composed.checksum, self.classe.pk, changes,
                                      presentation_source='catalog')
        self.target = seal_ruleset(
            [entry.revision for entry in clean.entries.select_related('revision')] + [
                create_revision('class-catalog:%s' % self.fighter.pk, inventory_class(self.fighter.pk)),
            ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.assertTrue(_reviewed_target(self.target, self.classe.pk, catalog()))
        self.assertEqual(len(VersionedClassCatalog(self.target, self.classe.pk).subclasses), 8)
        TbClassPublication.objects.create(id_classe=self.classe, ruleset=self.target)
        self.source = inventory_class(self.classe.pk)
        self.person = TbPersonagem.objects.create(dono=self.user, nome='Migration boundary',
            nivel=6, aventuras=130, carteira_pc=2345, braseiros=6, pv_maximo=60, pv_atual=49,
            forca=15, destreza=15, constituicao=14, inteligencia=15, sabedoria=15)
        self.other = TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=self.fighter, nivel=2, principal=True)
        self.legacy = TbSubclasse.objects.filter(id_classe=self.classe,
            nome__icontains='mutante').exclude(slug__endswith='-rework').get()
        self.pc = TbPersonagemClasse.objects.create(id_personagem=self.person,
            id_classe=self.classe, id_subclasse=self.legacy, nivel=4)
        self.choice = self.person.escolhas.create(origem='Segredos de Caçador',
            tipo='segredo', slot=0, valor='segredo-sem-equivalente')
        self.person.inventario.create(nome='Legacy trophy', qtd=2, origem_tipo='legado')
        self.person.magias.create(nome='Acquired outside catalog', nivel=1, preparada=True, origem='Aventura')
        self.person.aventuras_ledger.create(nome_aventura='Legacy adventure', qtd_aventuras=4,
                                           ouro_pago_pc=345, braseiros_pago=6)
        self.assets = self._assets()
        self.url = reverse('hunter_regularization_preview', args=[self.person.pk])
        self.payload = dict(ruleset_checksum=self.target.checksum, expected_level='4',
            expected_order_id=str(self.legacy.pk), ability='int', confirm='1',
            order=str(self.orders['ordem-dos-mutantes']))

    setup_catalog = boundary.HunterBugfixTests.setup_catalog

    def _assets(self):
        self.person.refresh_from_db()
        return ((self.person.carteira_pc, self.person.aventuras, self.person.braseiros),
                list(self.person.inventario.order_by('pk').values()),
                list(self.person.magias.order_by('pk').values()),
                list(self.person.aventuras_ledger.order_by('pk').values()))

    def test_migrate_secondary_legacy_order_then_advance_to_five(self):
        # The publication pointer must win over a stale configured checksum.
        with override_settings(CLASS_CATALOG_RULESETS={'cacador': self.old.checksum}):
            preview = self.client.get(self.url, {'order': self.payload['order']})
            self.assertEqual(preview.status_code, 200)
            self.assertTrue(preview.context['comparison']['target_ready_for_binding'])
            self.assertEqual(preview.context['comparison']['ruleset_checksum'], self.target.checksum)
            self.assertFalse(TbPersonagemCacador.objects.exists())
            rejected = self.client.post(self.url, self.payload)
            self.assertContains(rejected, 'Confirme individualmente')
            self.assertEqual(self._assets(), self.assets)
            accepted = self.client.post(self.url, {**self.payload,
                'replace_choice_id': [str(self.choice.pk)]})
        self.assertEqual(accepted.status_code, 302, accepted.content[:500])
        self.pc.refresh_from_db()
        self.other.refresh_from_db()
        profile = TbPersonagemCacador.objects.get(personagem_classe=self.pc)
        self.assertEqual(self.pc.id_subclasse_id, self.orders['ordem-dos-mutantes'])
        self.assertEqual((self.pc.nivel, self.other.nivel, self.person.nivel), (4, 2, 6))
        self.assertEqual(profile.ruleset_id, self.target.pk)
        self.assertEqual(profile.regularization['replaced_legacy_choices'][0]['id'], self.choice.pk)
        self.assertEqual(self._assets(), self.assets)
        self.assertEqual(self.person.pv_maximo - self.person.pv_atual, 11)
        self.assertEqual(inventory_class(self.classe.pk), self.source)
        self.assertEqual(self.client.get(reverse('ficha_detail', args=[self.person.pk])).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.payload).status_code, 404)
        batch = {'acoes': [{'tipo': 'subir_nivel', 'payload': {'classe': self.classe.pk}}],
                 'request_id': 'migration-level-five'}
        response = self.client.post(reverse('personagem_levelup_aplicar', args=[self.person.pk]),
                                    batch, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content[:500])
        self.pc.refresh_from_db()
        self.assertEqual(self.pc.nivel, 5)
        self.assertEqual(self.client.get(reverse('ficha_detail', args=[self.person.pk])).status_code, 200)

    def test_late_failure_restores_legacy_order_choices_and_assets(self):
        with patch('home.hunter_views.linked_sheet_context', side_effect=ValueError('migration-check-failed')):
            response = self.client.post(self.url, {**self.payload,
                'replace_choice_id': [str(self.choice.pk)]})
        self.assertContains(response, 'migration-check-failed')
        self.pc.refresh_from_db()
        self.assertEqual(self.pc.id_subclasse_id, self.legacy.pk)
        self.assertIsNone(self.pc.ruleset_id)
        self.assertTrue(self.person.escolhas.filter(pk=self.choice.pk).exists())
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=self.pc).exists())
        self.assertEqual(self._assets(), self.assets)

    def test_migration_replaces_previous_class_pin_consistently(self):
        previous = seal_ruleset(
            [entry.revision for entry in self.old.entries.select_related('revision')] + [
                create_revision('class-catalog:%s' % self.fighter.pk, inventory_class(self.fighter.pk)),
            ], evaluator_version=EVALUATOR, vocabulary_version=VOCABULARY)
        self.pc.ruleset = previous
        self.pc.save(update_fields=['ruleset'])
        self.test_migrate_secondary_legacy_order_then_advance_to_five()
        self.pc.refresh_from_db()
        self.assertEqual(self.pc.ruleset_id, self.target.pk)
        profile = self.pc.cacador_rework
        self.assertEqual(profile.regularization['old_ruleset_checksum'], previous.checksum)

    def test_other_class_pin_is_not_silently_reassigned(self):
        self.other.ruleset = self.ruleset
        self.other.save(update_fields=['ruleset'])
        response = self.client.post(self.url, {**self.payload,
            'replace_choice_id': [str(self.choice.pk)]})
        self.assertContains(response, 'Outra classe possui uma revisão diferente')
        self.other.refresh_from_db()
        self.pc.refresh_from_db()
        self.assertEqual(self.other.ruleset_id, self.ruleset.pk)
        self.assertIsNone(self.pc.ruleset_id)
        self.assertEqual(self.pc.id_subclasse_id, self.legacy.pk)
        self.assertFalse(TbPersonagemCacador.objects.filter(personagem_classe=self.pc).exists())
        self.assertEqual(self._assets(), self.assets)
